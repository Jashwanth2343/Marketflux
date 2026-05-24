"""MarketFlux Trading Copilot — a conversational, autonomous paper-trading agent.

This is the brain behind the "Trading Copilot" tab. Unlike react_agent (research
only) this agent can ALSO act: it places, sizes, and closes trades on the user's
Alpaca PAPER account through copilot_trading_tools.

It runs a manual ReAct loop over Gemini function calling and streams a rich set
of Server-Sent Events so the UI can render exactly what the agent is thinking and
doing in real time:

    thinking      — short status / planning lines
    tool_call     — {name, label, args}  a tool is about to run
    tool_result   — {name, ok, summary}  compact outcome
    trade         — {action, symbol, qty, side, status, price}  an order executed
    token         — streamed chunk of the final natural-language answer
    done          — terminal event

Everything is PAPER trading. Educational simulation, not investment advice.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

import agent_tools
import copilot_trading_tools as trading
import copilot_memory
from copilot_code_tool import run_python
from ai_service import GEMINI_FLASH, configure_gemini

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 14


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
_SYSTEM_TEMPLATE = """\
You are MarketFlux Copilot — an elite, autonomous AI portfolio manager operating a
LIVE Alpaca PAPER trading account (simulated money, real market prices and fills).

TODAY: {{TODAY}}. Treat this as the present. Never cite prices or events from your
training data — only numbers returned by your tools are real.

== WHO YOU ARE ==
You research markets AND execute trades. You are not a chatbot that gives generic
advice — you are a hands-on operator. When the user wants to act, you ACT through
your trading tools, then report exactly what happened.

== MEMORY ==
You have long-term memory of this user across sessions. Anything relevant you've
learned before appears under "RELEVANT LONG-TERM MEMORY" in the context below.
Treat it as standing instructions — honor their stated preferences, risk limits,
and constraints (e.g. "never short", "max 10% per position") in every
recommendation and trade. New durable facts the user shares are saved
automatically; you don't need to do anything to remember them.

== YOUR TOOLS ==
Research: stock snapshots, fundamentals, analyst targets, technical indicators,
news, SEC financials, insider activity, macro/FRED data, sector performance, and
web search.
Trading (these really execute on the paper account):
- get_account_summary — equity, cash, buying power, day P&L
- get_open_positions  — what you currently hold
- get_orders          — recent / open orders
- get_market_clock    — is the market open right now
- place_order         — BUY or SELL shares (market or limit)
- close_position      — fully exit a holding
- cancel_all_open_orders
Compute:
- run_python — a sandboxed Python scratchpad (numpy/pandas/scipy pre-loaded) for
  any math the other tools can't do directly: position sizing (Kelly,
  fixed-fractional), Sharpe/Sortino, correlations, expected value, portfolio
  weights/optimization, quick simulations. Embed numbers as literals and print
  results. Prefer it over doing nontrivial arithmetic in your head.

== HOW TO OPERATE ==
1. GROUND IN REALITY FIRST. Before trading, call get_account_summary and
   get_open_positions so you size against real buying power and avoid
   over-concentration. The current snapshot is also injected below.
2. RESEARCH BEFORE CONVICTION. For a buy/sell decision, pull a snapshot plus at
   least one of: technicals, fundamentals, news, or analyst targets. Briefly cite
   the numbers that drove your decision.
3. EXECUTE WHEN INTENT IS CLEAR. If the user says buy / sell / trade / take profit
   / cut / trim / add / rebalance / deploy / hedge, you MUST call the trading tools
   to actually do it — do not merely suggest. After executing, confirm fills.
4. PROPOSE WHEN ASKED FOR IDEAS. If they ask "what should I do / any ideas / your
   take", research and give a concrete, sized recommendation, then offer to execute.
5. SIZE SENSIBLY. Default to position sizes that keep any single name under ~20% of
   equity unless told otherwise. Never knowingly exceed buying power. If the market
   is closed, say so — market orders will queue for the next open.
6. MANAGE RISK. Think about downside and mention a stop level or invalidation when
   you open a position. Diversify. Don't chase.

== OUTPUT FORMAT — write like a research note, never a wall of text ==
- Open with a one-line **bold takeaway** — the answer or action, up front.
- Use `##` section headers when the response has multiple parts.
- ALWAYS put structured numbers in a Markdown table: positions, orders, prices,
  technicals (RSI/MACD/SMA), analyst targets, P&L, position-sizing scenarios, and
  any multi-name or multi-metric comparison. Never list more than ~3 numbers as
  prose — tabulate them. Example:

  | Ticker | Price | RSI | Analyst target | Unrealized P&L |
  |--------|------:|----:|---------------:|---------------:|
  | **NVDA** | $215.33 | 53.7 | $240 | +$1,204 (8.1%) |

- Use bullet lists for action items, risks, and next steps.
- **Bold** tickers and key figures. Keep sentences short and decisive.
- End any response that placed or recommended a trade with one line:
  "Paper trading — educational, not investment advice."
"""


def _system_prompt() -> str:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    return _SYSTEM_TEMPLATE.replace("{{TODAY}}", today)


# ---------------------------------------------------------------------------
# Tool registry — research tools + trading tools
# ---------------------------------------------------------------------------
_RESEARCH_TOOLS = [
    agent_tools.get_stock_snapshot,
    agent_tools.get_fundamentals,
    agent_tools.get_analyst_targets,
    agent_tools.get_news,
    agent_tools.get_technical_indicators,
    agent_tools.get_insider_transactions,
    agent_tools.get_macro_context,
    agent_tools.get_market_overview_tool,
    agent_tools.get_sector_performance,
    agent_tools.web_search,
    agent_tools.get_company_profile_tool,
    agent_tools.get_sec_financials,
    agent_tools.get_fred_macro,
    agent_tools.get_earnings_transcript,
]

_TRADING_TOOLS = [
    trading.get_account_summary,
    trading.get_open_positions,
    trading.get_orders,
    trading.get_market_clock,
    trading.get_portfolio_history,
    trading.place_order,
    trading.close_position,
    trading.cancel_all_open_orders,
]

_CODE_TOOLS = [run_python]

_ALL_TOOLS = _RESEARCH_TOOLS + _TRADING_TOOLS + _CODE_TOOLS

# name -> callable
_TOOL_MAP: Dict[str, Any] = {fn.__name__: fn for fn in _ALL_TOOLS}
# alias used by Gemini for the overview tool
_TOOL_MAP["get_market_overview"] = agent_tools.get_market_overview_tool
_TOOL_MAP["get_company_profile"] = agent_tools.get_company_profile_tool


def _build_model(system_instruction: str):
    configure_gemini()
    safety = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    return genai.GenerativeModel(
        model_name=GEMINI_FLASH,
        system_instruction=system_instruction,
        safety_settings=safety,
        tools=_ALL_TOOLS,
    )


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------
def _sse(event_type: str, **data) -> str:
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


def _sanitize(data):
    from decimal import Decimal
    if isinstance(data, dict):
        return {str(k): _sanitize(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_sanitize(i) for i in data]
    if isinstance(data, Decimal):
        return float(data)
    if isinstance(data, (int, float, str, bool)) or data is None:
        return data
    try:
        return str(data)
    except Exception:
        return "[unserializable]"


# ---------------------------------------------------------------------------
# Live portfolio context — grounds the agent in the real account state
# ---------------------------------------------------------------------------
async def _live_context() -> str:
    try:
        account, positions, clock = await asyncio.gather(
            asyncio.to_thread(trading.get_account_summary),
            asyncio.to_thread(trading.get_open_positions),
            asyncio.to_thread(trading.get_market_clock),
        )
    except Exception as exc:
        logger.warning(f"copilot live context failed: {exc}")
        return ""

    lines: List[str] = ["=== LIVE PAPER ACCOUNT (current state) ==="]
    if account.get("ok"):
        lines.append(
            f"Equity ${account.get('equity')} | Cash ${account.get('cash')} | "
            f"Buying power ${account.get('buying_power')} | "
            f"Day P&L ${account.get('day_pl')} ({account.get('day_pl_pct')}%)"
        )
    else:
        lines.append("Account: unavailable.")

    if clock.get("ok"):
        state = "OPEN" if clock.get("is_open") else "CLOSED"
        lines.append(f"Market is {state}. Next open: {clock.get('next_open')}.")

    poss = positions.get("positions") or []
    if poss:
        lines.append("Current positions:")
        for p in poss:
            lines.append(
                f"  - {p['symbol']}: {p['qty']} sh @ avg ${p['avg_entry_price']}, "
                f"now ${p['current_price']}, P&L ${p['unrealized_pl']} "
                f"({p['unrealized_pl_pct']}%)"
            )
    else:
        lines.append("No open positions — the portfolio is all cash.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool-call presentation helpers
# ---------------------------------------------------------------------------
def _tool_label(name: str, args: Dict[str, Any]) -> str:
    sym = args.get("symbol") or args.get("ticker")
    if name == "place_order":
        return f"Placing {args.get('side','?')} order: {args.get('quantity','?')} {sym}"
    if name == "close_position":
        return f"Closing position in {sym}"
    if name == "cancel_all_open_orders":
        return "Cancelling all open orders"
    if name == "get_account_summary":
        return "Reading account balance"
    if name == "get_open_positions":
        return "Reading current positions"
    if name == "get_orders":
        return "Reviewing recent orders"
    if name == "get_market_clock":
        return "Checking if market is open"
    if name == "get_portfolio_history":
        return "Pulling performance history"
    if name == "run_python":
        return "Running a Python calculation"
    pretty = name.replace("get_", "").replace("_", " ")
    if sym:
        return f"Researching {sym}: {pretty}"
    if args.get("query"):
        return f"Searching: {args.get('query')}"
    return f"Running {pretty}"


def _result_summary(name: str, result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return "done"
    if result.get("ok") is False or result.get("error"):
        return f"⚠ {result.get('error', 'failed')}"
    if name == "get_account_summary":
        return f"Equity ${result.get('equity')}, buying power ${result.get('buying_power')}"
    if name == "get_open_positions":
        return f"{result.get('count', 0)} position(s)"
    if name == "place_order":
        return f"{result.get('side')} {result.get('qty')} {result.get('symbol')} → {result.get('status')}"
    if name == "close_position":
        return f"closed {result.get('closed_symbol')} → {result.get('status')}"
    if name == "get_orders":
        return f"{result.get('count', 0)} order(s)"
    if name == "run_python":
        out = (result.get("stdout") or "").strip().splitlines()
        return out[-1][:80] if out else (result.get("note") or "ran")
    return "ok"


def _trade_event_payload(name: str, args: Dict[str, Any], result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not (isinstance(result, dict) and result.get("ok") and result.get("executed")):
        return None
    if name == "place_order":
        return {
            "action": "order",
            "symbol": result.get("symbol"),
            "side": result.get("side"),
            "qty": result.get("qty"),
            "order_type": result.get("order_type"),
            "status": result.get("status"),
            "price": result.get("filled_avg_price"),
        }
    if name == "close_position":
        return {
            "action": "close",
            "symbol": result.get("closed_symbol"),
            "side": result.get("side"),
            "qty": result.get("qty"),
            "status": result.get("status"),
        }
    if name == "cancel_all_open_orders":
        return {"action": "cancel_all", "status": "done"}
    return None


# ---------------------------------------------------------------------------
# Response-parsing helpers
# ---------------------------------------------------------------------------
def _function_calls(resp) -> List[Any]:
    calls = []
    try:
        for part in resp.parts:
            fc = getattr(part, "function_call", None)
            if fc and fc.name:
                calls.append(fc)
    except (ValueError, AttributeError):
        pass
    return calls


def _text_of(resp) -> str:
    texts = []
    try:
        for part in resp.parts:
            if getattr(part, "text", None):
                texts.append(part.text)
    except (ValueError, AttributeError):
        pass
    return "".join(texts)


# ---------------------------------------------------------------------------
# Main entry — the streaming agent loop
# ---------------------------------------------------------------------------
async def run_copilot_agent(
    message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    db=None,
    user_id: str = "",
    session_id: str = "",
) -> AsyncGenerator[str, None]:
    """Run one turn of the trading copilot, streaming SSE events."""
    yield _sse("thinking", step="plan", message="Reading your portfolio and planning…")

    system_prompt = _system_prompt()
    model = _build_model(system_prompt)

    # Seed prior conversation turns.
    gemini_history: List[Dict[str, Any]] = []
    for h in (history or [])[-8:]:
        msg, resp = h.get("message", ""), h.get("response", "")
        if isinstance(msg, str) and isinstance(resp, str) and msg.strip() and resp.strip():
            gemini_history.append({"role": "user", "parts": [msg]})
            gemini_history.append({"role": "model", "parts": [resp]})

    chat = model.start_chat(history=gemini_history)

    # Pull live account state and relevant long-term memory in parallel.
    ctx_tasks = [_live_context()]
    if db is not None:
        ctx_tasks.append(copilot_memory.memory_context_block(user_id, message))
    ctx_results = await asyncio.gather(*ctx_tasks)
    live_ctx = ctx_results[0]
    mem_ctx = ctx_results[1] if len(ctx_results) > 1 else ""
    context = "\n\n".join(p for p in (mem_ctx, live_ctx) if p)
    user_prompt = f"{context}\n\nUser: {message}" if context else message

    tool_calls = 0
    called_signatures: set = set()
    final_text = ""

    try:
        response = await asyncio.to_thread(chat.send_message, user_prompt)

        iteration = 0
        while tool_calls < MAX_TOOL_CALLS and iteration < MAX_TOOL_CALLS + 4:
            iteration += 1
            calls = _function_calls(response)
            if not calls:
                break

            function_responses = []
            for fc in calls:
                if tool_calls >= MAX_TOOL_CALLS:
                    break
                name = fc.name
                args = dict(fc.args) if fc.args else {}

                signature = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
                # Allow execution tools to repeat; dedupe only read tools.
                if signature in called_signatures and name not in trading.EXECUTION_TOOLS:
                    function_responses.append({"function_response": {
                        "name": name, "response": {"note": "already fetched"}}})
                    continue
                called_signatures.add(signature)
                tool_calls += 1

                yield _sse("tool_call", name=name, label=_tool_label(name, args),
                           args=_sanitize(args), is_trade=(name in trading.EXECUTION_TOOLS))

                func = _TOOL_MAP.get(name) or getattr(agent_tools, name, None)
                if func is None:
                    result = {"ok": False, "error": f"unknown tool {name}"}
                else:
                    try:
                        if asyncio.iscoroutinefunction(func):
                            result = await asyncio.wait_for(func(**args), timeout=40.0)
                        else:
                            result = await asyncio.wait_for(
                                asyncio.to_thread(func, **args), timeout=40.0)
                    except asyncio.TimeoutError:
                        result = {"ok": False, "error": f"{name} timed out"}
                    except Exception as exc:
                        logger.error(f"copilot tool {name} failed: {exc}")
                        result = {"ok": False, "error": f"{name} failed: {exc}"}

                result = _sanitize(result)
                if not isinstance(result, dict):
                    result = {"result": result}

                yield _sse("tool_result", name=name, ok=bool(result.get("ok", True)),
                           summary=_result_summary(name, result))

                trade_payload = _trade_event_payload(name, args, result)
                if trade_payload:
                    yield _sse("trade", **trade_payload)
                    if db is not None:
                        await _log_trade(db, user_id, trade_payload)

                function_responses.append({"function_response": {
                    "name": name, "response": result}})

            if not function_responses:
                break

            response = await asyncio.to_thread(
                chat.send_message, {"role": "function", "parts": function_responses})

        # If we hit the ceiling with calls still pending, force a wrap-up.
        if tool_calls >= MAX_TOOL_CALLS and _function_calls(response):
            yield _sse("thinking", step="finalize", message="Wrapping up with what I have…")
            response = await asyncio.to_thread(
                chat.send_message,
                "Tool limit reached. Stop calling tools and give your final answer now, "
                "summarizing any trades you executed.")

        final_text = _text_of(response)
        if not final_text:
            try:
                response = await asyncio.to_thread(
                    chat.send_message,
                    "Provide your final answer now in markdown. Summarize any actions taken.")
                final_text = _text_of(response)
            except Exception:
                pass
        if not final_text:
            final_text = ("I gathered the data and acted where possible, but couldn't compose a "
                          "summary. Check the activity log above for what ran.")

        yield _sse("thinking", step="write", message="Writing it up…")
        for i in range(0, len(final_text), 60):
            yield _sse("token", content=final_text[i:i + 60])
            await asyncio.sleep(0.004)

        yield _sse("done")

        if db is not None:
            try:
                await db.copilot_messages.insert_one({
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": message,
                    "response": final_text,
                    "created_at": datetime.now(timezone.utc),
                })
            except Exception as exc:
                logger.error(f"copilot db save failed: {exc}")
            # Extract + persist long-term memory in the background (never blocks).
            copilot_memory.schedule_add_turn(user_id, message, final_text)

    except Exception as exc:
        logger.critical(f"copilot agent crashed: {exc}", exc_info=True)
        yield _sse("token", content=f"\n\n⚠ The copilot hit an error: {exc}")
        yield _sse("done", error=str(exc))


async def _log_trade(db, user_id: str, payload: Dict[str, Any]) -> None:
    try:
        await db.copilot_trade_log.insert_one({
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        })
    except Exception as exc:
        logger.warning(f"copilot trade log failed: {exc}")
