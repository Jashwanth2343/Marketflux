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
import inspect
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

import agent_tools
import compliance_engine
import copilot_intelligence_tools as intel
import sec_filings
import copilot_trading_tools as trading
import copilot_memory
import copilot_models
from copilot_code_tool import run_python
from ai_service import GEMINI_FLASH, configure_gemini

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 18

# Tools that fan out to multiple LLM calls or do heavy compute need a longer
# timeout than the default per-tool budget.
_HEAVY_TIMEOUT = 110.0
_HEAVY_TOOLS = {"deep_research", "run_strategy_backtest", "review_and_learn",
                "debate_thesis", "get_market_regime", "get_earnings_intel",
                "search_filings", "diff_risk_factors"}


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
Intelligence (the fund's quant brain — use it to ground conviction in systematic factors):
- get_quant_signals — a 20+ signal institutional scorecard for one ticker across
  momentum/value/quality/sentiment/technical → one composite conviction score
  (-100..+100) with a label. Run this before forming a buy/sell view on a name.
- scan_signals — rank a basket of tickers by composite score; use to pick the
  strongest idea from a candidate set.
Risk (manage the book like a real PM):
- analyze_portfolio_risk — beta, 95% VaR, stress tests, sector concentration,
  factor tilt for your CURRENT live positions. Use for "what's my risk / how would
  I do in a crash" and before large adds.
- analyze_stock_risk — beta, volatility, VaR, and a sizing recommendation
  (suggested %, max %, stop %) for one name. Use BEFORE sizing a new position.
- get_market_regime — classify the tape (risk-on…risk-off, vol band, trend,
  breadth) with a suggested gross-exposure band. Read it FIRST on "how should I
  position" questions and scale conviction/size to it.
- simulate_trade — what-if: project the book AFTER a hypothetical order (new
  weight, cash, buying power, concentration) AND whether it clears compliance, with
  nothing placed. Use to right-size before committing.
- get_earnings_intel — next earnings date, beat rate, surprise probability, and a
  pre/post-earnings brief. Check it before sizing — avoid getting caught into a print.
Backtest (prove ideas instead of guessing):
- run_strategy_backtest — backtest a rules-based strategy (DSL JSON) over history
  and get Sharpe, return, drawdown, win rate. Use when asked "does this work / would
  this have made money", or to validate a systematic entry before sizing into it.
Delegation (span a team when one pass isn't enough):
- deep_research — convene 5 specialist analyst sub-agents (Fundamentals, Technical,
  Macro, Sentiment, Risk) IN PARALLEL plus a Director synthesis → a committee-grade
  research memo with rating + price target. Reserve for high-stakes / ambiguous calls.
- debate_thesis — stage an adversarial BULL vs BEAR debate on the same evidence,
  then a Research-Manager verdict (Bullish/Neutral/Bearish + conviction + action +
  what would change the call). Use to stress-test the bear case before high
  conviction; it's your antidote to overconfidence.
Self-improvement (get better over time):
- review_and_learn — review your OWN track record (account, positions, performance,
  your executed trades), grade what worked vs hurt, and write durable lessons into
  your long-term memory so future decisions improve. Use when asked "how am I doing /
  what have you learned", and run it periodically — this is how you compound.
Compliance:
- compliance_precheck — pre-flight an order against buying power, the per-order cap,
  single-name concentration ceiling, short-sale/PDT/penny/wash-sale controls,
  WITHOUT placing it. Run it before a non-trivial order so you size it to clear.
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

== OPERATING DOCTRINE (how an elite PM works the book) ==
1. GROUND IN REALITY FIRST. Before trading, call get_account_summary and
   get_open_positions so you size against real buying power and avoid
   over-concentration. The current snapshot is also injected below. For "how should
   I position / is now a good time" questions, also read get_market_regime and let
   it scale your conviction and size (smaller in risk-off / high-vol regimes).
2. SCORE THE CONVICTION. For a buy/sell decision, run get_quant_signals (and
   scan_signals across alternatives when picking among names). Combine the
   composite score with a snapshot plus at least one of technicals / fundamentals /
   news / analyst targets. Cite the composite score and the numbers that drove you.
3. SIZE TO RISK, NOT HOPE. Before sizing a new position, call analyze_stock_risk and
   respect its suggested %, max %, and stop. For portfolio-level questions or large
   adds, run analyze_portfolio_risk and keep beta, VaR, and concentration sane.
4. VALIDATE SYSTEMATIC IDEAS. If the user proposes a rules-based strategy, or you
   do, run_strategy_backtest it before trading. A negative Sharpe or ugly drawdown
   is a reason to decline, and you should say so.
5. CLEAR COMPLIANCE, THEN EXECUTE. For any non-trivial order, run compliance_precheck
   and size so it returns PASS (or an acceptable WARN you explain). Then, when the
   user's intent is clear (buy / sell / trade / take profit / cut / trim / add /
   rebalance / deploy / hedge), you MUST call the trading tools to actually do it —
   do not merely suggest. After executing, confirm fills. NOTE: every order also
   passes a hard compliance gate automatically; a BLOCK there means it will NOT run,
   so pre-check and resize rather than retrying the same order.
6. PROPOSE WHEN ASKED FOR IDEAS. If they ask "what should I do / any ideas / your
   take", research, score, risk-size, and give a concrete, sized recommendation,
   then offer to execute.
7. MANAGE RISK & FOLLOW THE RULES. Default to keeping any single name under ~20% of
   equity unless told otherwise. Never knowingly exceed buying power. Mention a stop
   level or invalidation when you open a position. Honor the user's stated mandate
   (e.g. "never short"). If the market is closed, say so — market orders queue for
   the next open.
8. PRESSURE-TEST & PROJECT. For a high-stakes or ambiguous call, run debate_thesis
   to stress-test the bear case, and/or deep_research to convene the analyst team,
   before committing real size. Right-size with simulate_trade — confirm the
   projected weight, buying power, and that it clears compliance — before you place.
9. LEARN FROM YOURSELF. Treat recalled "Trading lesson (from self-review)" memories
   as hard-won guidance and apply them. When asked how you're doing — or periodically
   on your own — call review_and_learn so your mistakes don't repeat and your edge
   compounds over time.

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
    sec_filings.get_recent_filings,
    sec_filings.search_filings,
    sec_filings.diff_risk_factors,
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

_INTELLIGENCE_TOOLS = [
    intel.get_quant_signals,
    intel.scan_signals,
    intel.analyze_portfolio_risk,
    intel.analyze_stock_risk,
    intel.get_market_regime,
    intel.simulate_trade,
    intel.get_earnings_intel,
    intel.run_strategy_backtest,
    intel.deep_research,
    intel.debate_thesis,
    intel.review_and_learn,
    intel.compliance_precheck,
]

_CODE_TOOLS = [run_python]

_ALL_TOOLS = _RESEARCH_TOOLS + _TRADING_TOOLS + _INTELLIGENCE_TOOLS + _CODE_TOOLS

# Research-only mode keeps every read (including account/positions — portfolio-
# aware research is the differentiator) but removes the three execution tools.
_RESEARCH_MODE_TOOLS = [t for t in _ALL_TOOLS if t.__name__ not in trading.EXECUTION_TOOLS]


def _tools_for_mode(mode: str):
    return _RESEARCH_MODE_TOOLS if mode == "research" else _ALL_TOOLS

# name -> callable
_TOOL_MAP: Dict[str, Any] = {fn.__name__: fn for fn in _ALL_TOOLS}
# alias used by Gemini for the overview tool
_TOOL_MAP["get_market_overview"] = agent_tools.get_market_overview_tool
_TOOL_MAP["get_company_profile"] = agent_tools.get_company_profile_tool


def _build_model(system_instruction: str, model_name: str = GEMINI_FLASH, tools=None):
    configure_gemini()
    safety = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    return genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction,
        safety_settings=safety,
        tools=tools if tools is not None else _ALL_TOOLS,
    )


# OpenAI-compatible tool schemas, generated once per mode by introspection.
_OPENAI_TOOLS_CACHE: Dict[str, List[dict]] = {}


def _openai_tool_schemas(mode: str = "trade") -> List[dict]:
    cached = _OPENAI_TOOLS_CACHE.get(mode)
    if cached is not None:
        return cached
    type_map = {float: "number", int: "integer", bool: "boolean", str: "string"}
    schemas = []
    for fn in _tools_for_mode(mode):
        props: Dict[str, Any] = {}
        required: List[str] = []
        for pname, p in inspect.signature(fn).parameters.items():
            props[pname] = {"type": type_map.get(p.annotation, "string")}
            if p.default is inspect.Parameter.empty:
                required.append(pname)
        schemas.append({"type": "function", "function": {
            "name": fn.__name__,
            "description": (fn.__doc__ or "").strip()[:1024],
            "parameters": {"type": "object", "properties": props, "required": required},
        }})
    _OPENAI_TOOLS_CACHE[mode] = schemas
    return schemas


async def _exec_tool(name: str, args: Dict[str, Any], db=None, user_id: str = "",
                     confirm_mode: bool = False) -> Dict[str, Any]:
    """Execute a tool by name (shared by the Gemini and OpenAI-compatible loops).

    In confirm_mode, execution tools are STAGED for user approval rather than run.
    """
    if confirm_mode and name in trading.EXECUTION_TOOLS and db is not None:
        import copilot_trades
        return await copilot_trades.stage(db, user_id, name, args)

    # Context-aware tools run with (db, user_id) injected by the runtime rather
    # than filled by the LLM. Their registered callable is only a schema stub.
    if name in intel.CONTEXT_TOOLS:
        try:
            if name == "review_and_learn":
                import copilot_learning
                result = await asyncio.wait_for(
                    copilot_learning.review_and_learn_impl(db, user_id, **args), timeout=_HEAVY_TIMEOUT)
                return _sanitize(result)
            if name == "debate_thesis":
                import copilot_debate
                result = await asyncio.wait_for(
                    copilot_debate.run_debate_impl(db, user_id, **args), timeout=_HEAVY_TIMEOUT)
                return _sanitize(result)
        except asyncio.TimeoutError:
            return {"ok": False, "error": f"{name} timed out"}
        except Exception as exc:  # noqa: BLE001
            logger.error(f"copilot context tool {name} failed: {exc}")
            return {"ok": False, "error": f"{name} failed: {exc}"}

    func = _TOOL_MAP.get(name) or getattr(agent_tools, name, None)
    if func is None:
        return {"ok": False, "error": f"unknown tool {name}"}
    # Multi-LLM-call tools (research team, backtests) need a longer leash.
    timeout = _HEAVY_TIMEOUT if name in _HEAVY_TOOLS else 40.0
    try:
        if asyncio.iscoroutinefunction(func):
            result = await asyncio.wait_for(func(**args), timeout=timeout)
        else:
            result = await asyncio.wait_for(asyncio.to_thread(func, **args), timeout=timeout)
    except asyncio.TimeoutError:
        result = {"ok": False, "error": f"{name} timed out"}
    except Exception as exc:
        logger.error(f"copilot tool {name} failed: {exc}")
        result = {"ok": False, "error": f"{name} failed: {exc}"}
    result = _sanitize(result)
    return result if isinstance(result, dict) else {"result": result}


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------
def _sse(event_type: str, seq: int = 0, **data) -> str:
    """Build a Server-Sent Event string.

    Includes an ``id:`` field so clients can use the ``Last-Event-ID`` header
    to resume a dropped stream.  The ``seq`` counter is injected by the
    ``run_copilot_agent`` generator; callers that don't pass it get ``id: 0``
    (safe default, no reconnect support for one-off helper calls).
    """
    return f"id: {seq}\ndata: {json.dumps({'type': event_type, **data})}\n\n"


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
    if name == "get_quant_signals":
        return f"Scoring {sym}: 20+ quant signals" if sym else "Scoring quant signals"
    if name == "scan_signals":
        return "Ranking candidates by quant score"
    if name == "analyze_portfolio_risk":
        return "Running a portfolio risk X-ray"
    if name == "analyze_stock_risk":
        return f"Risk profile: {sym}" if sym else "Risk profile"
    if name == "run_strategy_backtest":
        return "Backtesting the strategy on history"
    if name == "get_market_regime":
        return "Reading the market regime"
    if name == "simulate_trade":
        return f"Simulating the trade impact: {sym}" if sym else "Simulating the trade impact"
    if name == "get_earnings_intel":
        return f"Checking earnings catalyst: {sym}" if sym else "Checking earnings catalyst"
    if name == "debate_thesis":
        return f"Bull vs Bear debate on {sym}" if sym else "Bull vs Bear debate"
    if name == "deep_research":
        return f"Convening the research team on {sym}" if sym else "Convening the research team"
    if name == "review_and_learn":
        return "Reviewing my track record to learn"
    if name == "compliance_precheck":
        return f"Pre-trade compliance check: {sym}" if sym else "Pre-trade compliance check"
    if name == "run_python":
        return "Running a Python calculation"
    if name == "get_recent_filings":
        return f"Listing SEC filings: {sym}" if sym else "Listing SEC filings"
    if name == "search_filings":
        return f"Reading the {args.get('form', '10-K')}: {sym}" if sym else "Reading the filing"
    if name == "diff_risk_factors":
        return f"Diffing risk factors YoY: {sym}" if sym else "Diffing risk factors"
    pretty = name.replace("get_", "").replace("_", " ")
    if sym:
        return f"Researching {sym}: {pretty}"
    if args.get("query"):
        return f"Searching: {args.get('query')}"
    return f"Running {pretty}"


def _result_summary(name: str, result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return "done"
    if result.get("staged"):
        return "staged — awaiting your approval"
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
    if name == "get_quant_signals":
        return f"{result.get('signal_label')} · composite {result.get('composite_score')}"
    if name == "scan_signals":
        return f"ranked {result.get('count', 0)} name(s)"
    if name == "analyze_portfolio_risk":
        if result.get("empty"):
            return "all cash — no market risk"
        return f"beta {result.get('portfolio_beta')}, 95% VaR {result.get('var_95')}%"
    if name == "analyze_stock_risk":
        return f"beta {result.get('beta')}, vol {result.get('annualised_volatility_pct')}%"
    if name == "run_strategy_backtest":
        m = result.get("metrics", {})
        return f"return {m.get('total_return_pct')}%, Sharpe {m.get('sharpe')}, {m.get('num_trades')} trades"
    if name == "get_market_regime":
        return f"{result.get('regime_label')} · exposure {result.get('suggested_gross_exposure')}"
    if name == "simulate_trade":
        a = result.get("after", {})
        return f"{result.get('symbol')} → {a.get('weight_pct')}% of book · {result.get('compliance_decision')}"
    if name == "get_earnings_intel":
        return f"next earnings {result.get('next_earnings_date') or result.get('earnings_date') or '—'}"
    if name == "debate_thesis":
        return f"verdict {result.get('verdict') or '—'} ({result.get('conviction') or '—'} conviction)"
    if name == "deep_research":
        return f"5-analyst memo: {result.get('signal_label')} · {result.get('signal_score')}"
    if name == "review_and_learn":
        return f"grade {result.get('grade') or '—'} · learned {result.get('lessons_learned_count', 0)} lesson(s)"
    if name == "compliance_precheck":
        return f"{result.get('decision')} — {(result.get('summary') or '')[:64]}"
    if name == "run_python":
        out = (result.get("stdout") or "").strip().splitlines()
        return out[-1][:80] if out else (result.get("note") or "ran")
    return "ok"


def _trade_event_payload(name: str, args: Dict[str, Any], result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Staged (confirm mode) — render an Approve/Reject card.
    if isinstance(result, dict) and result.get("staged"):
        return {
            "action": result.get("action"),
            "symbol": result.get("symbol"),
            "side": result.get("side"),
            "qty": result.get("qty"),
            "order_type": result.get("order_type"),
            "limit_price": result.get("limit_price"),
            "status": "awaiting approval",
            "pending": True,
            "proposal_id": result.get("proposal_id"),
        }
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
# Intelligence "insight" cards — structured payloads the UI renders richly.
# ---------------------------------------------------------------------------
def _insight_payload(name: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(result, dict) or not result.get("ok"):
        return None
    if name == "get_quant_signals":
        return {
            "kind": "signals",
            "symbol": result.get("symbol"),
            "name": result.get("name"),
            "composite_score": result.get("composite_score"),
            "signal_label": result.get("signal_label"),
            "category_scores": result.get("category_scores"),
        }
    if name == "scan_signals":
        return {"kind": "scan", "ranked": result.get("ranked")}
    if name == "analyze_portfolio_risk":
        if result.get("empty"):
            return None
        return {
            "kind": "portfolio_risk",
            "portfolio_beta": result.get("portfolio_beta"),
            "var_95": result.get("var_95"),
            "max_drawdown": result.get("max_drawdown"),
            "concentration_warning": result.get("concentration_warning"),
            "sector_concentration": result.get("sector_concentration"),
            "factor_exposure": result.get("factor_exposure"),
            "stress_tests": result.get("stress_tests"),
            "risk_summary": result.get("risk_summary"),
        }
    if name == "analyze_stock_risk":
        return {
            "kind": "stock_risk",
            "ticker": result.get("ticker"),
            "beta": result.get("beta"),
            "annualised_volatility_pct": result.get("annualised_volatility_pct"),
            "var_95_daily_pct": result.get("var_95_daily_pct"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "sizing_recommendation": result.get("sizing_recommendation"),
        }
    if name == "run_strategy_backtest":
        return {
            "kind": "backtest",
            "strategy_name": result.get("strategy_name"),
            "universe": result.get("universe"),
            "period": result.get("period"),
            "metrics": result.get("metrics"),
        }
    if name == "deep_research":
        return {
            "kind": "research",
            "symbol": result.get("symbol"),
            "name": result.get("name"),
            "signal_score": result.get("signal_score"),
            "signal_label": result.get("signal_label"),
            "specialists": list((result.get("specialist_reports") or {}).keys()),
        }
    if name == "review_and_learn":
        return {
            "kind": "review",
            "grade": result.get("grade"),
            "assessment": result.get("assessment"),
            "lessons": result.get("lessons"),
            "lessons_learned_count": result.get("lessons_learned_count"),
            "stats": result.get("stats"),
        }
    if name == "get_market_regime":
        return {
            "kind": "regime",
            "regime_label": result.get("regime_label"),
            "risk_state": result.get("risk_state"),
            "spy_trend": result.get("spy_trend"),
            "trend_strength_pct": result.get("trend_strength_pct"),
            "vix": result.get("vix"),
            "vix_band": result.get("vix_band"),
            "breadth_pct": result.get("breadth_pct"),
            "suggested_gross_exposure": result.get("suggested_gross_exposure"),
            "playbook": result.get("playbook"),
        }
    if name == "simulate_trade":
        return {
            "kind": "simulation",
            "symbol": result.get("symbol"),
            "side": result.get("side"),
            "qty": result.get("qty"),
            "notional": result.get("notional"),
            "before": result.get("before"),
            "after": result.get("after"),
            "largest_position_after": result.get("largest_position_after"),
            "compliance_decision": result.get("compliance_decision"),
            "compliance_summary": result.get("compliance_summary"),
        }
    if name == "debate_thesis":
        return {
            "kind": "debate",
            "symbol": result.get("symbol"),
            "verdict": result.get("verdict"),
            "conviction": result.get("conviction"),
            "bull_case": result.get("bull_case"),
            "bear_case": result.get("bear_case"),
            "recommended_action": result.get("recommended_action"),
            "key_swing_factor": result.get("key_swing_factor"),
            "would_change_my_mind": result.get("would_change_my_mind"),
            "summary": result.get("summary"),
        }
    if name == "get_earnings_intel":
        if result.get("error"):
            return None
        return {
            "kind": "earnings",
            "symbol": result.get("symbol"),
            "next_earnings_date": result.get("next_earnings_date"),
            "days_until_earnings": result.get("days_until_earnings"),
            "beat_statistics": result.get("beat_statistics"),
            "surprise_probability": result.get("surprise_probability"),
        }
    return None


# ---------------------------------------------------------------------------
# Pre-trade compliance chokepoint — runs before any order is staged/executed.
# ---------------------------------------------------------------------------
async def _compliance_for_order(args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Run the pre-trade gate for a place_order call. Returns the report, or
    None if the controls themselves errored (fail-open: place_order + the broker
    still enforce notional and buying-power independently)."""
    try:
        symbol = (args.get("symbol") or "").upper()
        side = (args.get("side") or "").lower()
        account, positions, est_price = await intel._order_context(symbol)
        return compliance_engine.pre_trade_check(
            symbol=symbol,
            side=side,
            quantity=args.get("quantity"),
            est_price=est_price,
            order_type=(args.get("order_type") or "market"),
            limit_price=args.get("limit_price") or 0.0,
            account=account,
            positions=positions,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("compliance chokepoint failed (fail-open): %s", exc)
        return None


def _compliance_event(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "decision": report.get("decision"),
        "symbol": report.get("symbol"),
        "side": report.get("side"),
        "qty": report.get("qty"),
        "notional": report.get("notional"),
        "projected_weight_pct": report.get("projected_weight_pct"),
        "summary": report.get("summary"),
        "checks": report.get("checks"),
    }


async def _run_one_tool(name, args, db, user_id, confirm, emit, out: List[Any]):
    """Execute one tool call with full SSE transparency, shared by both LLM loops.

    Yields SSE event strings (compliance, tool_call, tool_result, insight, trade)
    and appends the result dict (the payload to feed back to the model) to ``out``.
    The compliance gate is a HARD chokepoint: a BLOCK on an order means it is
    never staged or executed — the model gets a blocked result instead.
    """
    # Hard pre-trade compliance gate for real orders.
    if name == "place_order":
        report = await _compliance_for_order(args)
        if report is not None:
            yield emit("compliance", **_compliance_event(report))
            if report.get("decision") == compliance_engine.BLOCK:
                blocked = {
                    "ok": False,
                    "executed": False,
                    "blocked_by_compliance": True,
                    "decision": "BLOCK",
                    "summary": report.get("summary"),
                    "checks": report.get("checks"),
                }
                yield emit("tool_result", name=name, ok=False,
                           summary=f"⛔ Blocked by compliance: {report.get('summary')}")
                out.append(blocked)
                return

    yield emit("tool_call", name=name, label=_tool_label(name, args),
               args=_sanitize(args), is_trade=(name in trading.EXECUTION_TOOLS))
    result = await _exec_tool(name, args, db, user_id, confirm)
    yield emit("tool_result", name=name, ok=bool(result.get("ok", True)),
               summary=_result_summary(name, result))

    insight = _insight_payload(name, result)
    if insight:
        yield emit("insight", **insight)

    tp = _trade_event_payload(name, args, result)
    if tp:
        yield emit("trade", **tp)
        if db is not None and not tp.get("pending"):
            await _log_trade(db, user_id, tp)
    out.append(result)


# Tools that must never fan out concurrently: order execution goes through the
# compliance gate one at a time, and run_python shares a scratchpad session.
_SEQUENTIAL_TOOLS = trading.EXECUTION_TOOLS | {"place_order", "run_python"}


async def _run_read_tools_parallel(batch, db, user_id, confirm, emit,
                                   results: Dict[int, Any]):
    """Fan out a round of read-only tool calls concurrently.

    ``batch`` is a list of ``(slot, name, args)``. All tool_call events are
    emitted up front so the UI shows every tool as running; executions happen
    concurrently; results are emitted in reverse call order because the client
    pairs a tool_result with its newest pending tool_call of the same name —
    reverse emission keeps that pairing correct even for duplicate names.
    """
    for _, name, args in batch:
        yield emit("tool_call", name=name, label=_tool_label(name, args),
                   args=_sanitize(args), is_trade=False)
    settled = await asyncio.gather(
        *(_exec_tool(name, args, db, user_id, confirm) for _, name, args in batch),
        return_exceptions=True)
    for (slot, name, args), result in reversed(list(zip(batch, settled))):
        if isinstance(result, BaseException):
            logger.error(f"parallel tool {name} failed: {result}")
            result = {"ok": False, "error": str(result)}
        yield emit("tool_result", name=name, ok=bool(result.get("ok", True)),
                   summary=_result_summary(name, result))
        insight = _insight_payload(name, result)
        if insight:
            yield emit("insight", **insight)
        results[slot] = result


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
    model: Optional[str] = None,
    confirm: bool = True,
    mode: str = "trade",
) -> AsyncGenerator[str, None]:
    """Run one turn of the trading copilot, streaming SSE events.

    Dispatches to Gemini (native function-calling) or an OpenAI-compatible
    provider (OpenRouter / NIM) based on the selected model. Tools, system
    prompt, transparency events, memory, and trade logging are identical across
    both backends — only the LLM-call mechanics differ.

    Every SSE event includes an ``id:`` field (monotonically increasing per
    turn) so clients can use ``Last-Event-ID`` to detect dropped events.
    """
    seq: List[int] = [0]  # mutable counter shared with sub-generators
    # Insight/trade events from this turn, inspected at finalize by the
    # conviction ledger's auto-log rule (structured events, no text parsing).
    turn_events: List[Dict[str, Any]] = []

    def sse(event_type: str, **data) -> str:
        seq[0] += 1
        if event_type in ("insight", "trade"):
            turn_events.append({"type": event_type, **data})
        return _sse(event_type, seq=seq[0], **data)

    resolved = copilot_models.resolve(model)
    yield sse("model", key=resolved.key, label=resolved.label, provider=resolved.provider)
    yield sse("thinking", step="plan", message=f"Reading your portfolio and planning… (via {resolved.label})")

    mode = mode if mode in ("trade", "research") else "trade"
    system_prompt = _system_prompt()
    if mode == "research":
        system_prompt += (
            "\n\n== RESEARCH-ONLY MODE ==\n"
            "Trading execution is DISABLED for this session: you have no order tools. "
            "You can still read the account and positions and use every research, "
            "intelligence, risk, backtest, and filings tool. When the user asks you to "
            "trade, give the fully-sized recommendation instead and note that trading "
            "is switched off in this mode."
        )
    if confirm:
        system_prompt += (
            "\n\n== TRADE CONFIRMATION IS ON ==\n"
            "Trades need the user's one-click approval. CRITICAL: you MUST still CALL the "
            "place_order / close_position / cancel_all_open_orders tools exactly as normal — "
            "the tool call itself is what stages the trade for approval (it does NOT hit the "
            "broker until the user approves in the UI). NEVER claim a trade is 'staged', "
            "'placed', or 'queued' unless you actually called the tool in this turn. After "
            "calling it, tell the user what you staged and why; say it's pending their approval."
        )

    # Live account state + relevant long-term memory, fetched in parallel (shared).
    ctx_tasks = [_live_context()]
    if db is not None:
        ctx_tasks.append(copilot_memory.memory_context_block(user_id, message))
    ctx_results = await asyncio.gather(*ctx_tasks)
    live_ctx = ctx_results[0]
    mem_ctx = ctx_results[1] if len(ctx_results) > 1 else ""
    context = "\n\n".join(p for p in (mem_ctx, live_ctx) if p)

    holder: Dict[str, Any] = {"final_text": ""}
    try:
        if resolved.provider == "gemini":
            sub = _run_gemini(resolved, system_prompt, history, context, message, db, user_id, holder, confirm, sse_fn=sse, mode=mode)
        else:
            sub = _run_openai(resolved, system_prompt, history, context, message, db, user_id, holder, confirm, sse_fn=sse, mode=mode)
        async for ev in sub:
            yield ev

        final_text = holder.get("final_text") or (
            "I gathered the data and acted where possible, but couldn't compose a "
            "summary. Check the activity log above for what ran.")

        yield sse("thinking", step="write", message="Writing it up…")
        for i in range(0, len(final_text), 60):
            yield sse("token", content=final_text[i:i + 60])
            await asyncio.sleep(0.004)
        yield sse("done")
        await _finalize(db, user_id, session_id, message, final_text, turn_events)

    except Exception as exc:
        logger.critical(f"copilot agent crashed: {exc}", exc_info=True)
        yield sse("token", content=f"\n\n⚠ The copilot hit an error: {exc}")
        yield sse("done", error=str(exc))


async def _finalize(db, user_id: str, session_id: str, message: str, final_text: str,
                    turn_events: Optional[List[Dict[str, Any]]] = None) -> None:
    """Persist the turn + schedule the background memory write (shared)."""
    if db is None:
        return
    try:
        import copilot_store
        await copilot_store.insert_message(db, user_id, session_id, message, final_text)
    except Exception as exc:
        logger.error(f"copilot db save failed: {exc}")
    copilot_memory.schedule_add_turn(user_id, message, final_text)
    # Conviction ledger auto-log: a turn that both scored a name (|composite|
    # >= threshold) and sized/traded it becomes a recorded, gradeable thesis.
    try:
        import conviction_ledger
        await conviction_ledger.auto_log_from_turn(db, user_id, turn_events or [], final_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"conviction ledger auto-log failed: {exc}")


async def _run_gemini(resolved, system_prompt, history, context, message, db, user_id, holder, confirm=False, sse_fn=None, mode="trade"):
    """Native Gemini function-calling loop."""
    model = _build_model(system_prompt, model_name=resolved.model_id, tools=_tools_for_mode(mode))
    gemini_history: List[Dict[str, Any]] = []
    for h in (history or [])[-8:]:
        msg, resp = h.get("message", ""), h.get("response", "")
        if isinstance(msg, str) and isinstance(resp, str) and msg.strip() and resp.strip():
            gemini_history.append({"role": "user", "parts": [msg]})
            gemini_history.append({"role": "model", "parts": [resp]})
    chat = model.start_chat(history=gemini_history)
    user_prompt = f"{context}\n\nUser: {message}" if context else message

    tool_calls = 0
    called_signatures: set = set()
    response = await asyncio.to_thread(chat.send_message, user_prompt)

    iteration = 0
    while tool_calls < MAX_TOOL_CALLS and iteration < MAX_TOOL_CALLS + 4:
        iteration += 1
        calls = _function_calls(response)
        if not calls:
            break
        _emit = sse_fn or _sse
        function_responses: List[Optional[Dict[str, Any]]] = []
        slot_names: Dict[int, str] = {}
        pending: List[tuple] = []  # (slot, name, args)
        for fc in calls:
            if tool_calls >= MAX_TOOL_CALLS:
                break
            name = fc.name
            args = dict(fc.args) if fc.args else {}
            signature = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
            if signature in called_signatures and name not in trading.EXECUTION_TOOLS:
                function_responses.append({"function_response": {"name": name, "response": {"note": "already fetched"}}})
                continue
            called_signatures.add(signature)
            tool_calls += 1
            function_responses.append(None)
            slot = len(function_responses) - 1
            slot_names[slot] = name
            pending.append((slot, name, args))

        # Read-only tools fan out concurrently; execution/code tools run
        # sequentially through the compliance-gated path.
        read_batch = [p for p in pending if p[1] not in _SEQUENTIAL_TOOLS]
        seq_batch = [p for p in pending if p[1] in _SEQUENTIAL_TOOLS]
        results: Dict[int, Any] = {}
        if len(read_batch) > 1:
            async for ev in _run_read_tools_parallel(read_batch, db, user_id, confirm, _emit, results):
                yield ev
        else:
            seq_batch = read_batch + seq_batch
        for slot, name, args in seq_batch:
            out: List[Any] = []
            async for ev in _run_one_tool(name, args, db, user_id, confirm, _emit, out):
                yield ev
            results[slot] = out[0] if out else {"ok": False, "error": "no result"}
        for slot, result in results.items():
            function_responses[slot] = {"function_response": {"name": slot_names[slot], "response": result}}
        if not function_responses:
            break
        response = await asyncio.to_thread(chat.send_message, {"role": "function", "parts": function_responses})

    if tool_calls >= MAX_TOOL_CALLS and _function_calls(response):
        yield _sse("thinking", step="finalize", message="Wrapping up with what I have…")
        response = await asyncio.to_thread(
            chat.send_message,
            "Tool limit reached. Stop calling tools and give your final answer now, summarizing any trades.")

    final_text = _text_of(response)
    if not final_text:
        try:
            response = await asyncio.to_thread(
                chat.send_message, "Provide your final answer now in markdown. Summarize any actions taken.")
            final_text = _text_of(response)
        except Exception:
            pass
    holder["final_text"] = final_text


async def _run_openai(resolved, system_prompt, history, context, message, db, user_id, holder, confirm=False, sse_fn=None, mode="trade"):
    """OpenAI-compatible tool-calling loop (OpenRouter / NVIDIA NIM)."""
    from openai import AsyncOpenAI

    headers = {"HTTP-Referer": "https://marketflux.local", "X-Title": "MarketFlux Copilot"} \
        if resolved.provider == "openrouter" else None
    client = AsyncOpenAI(api_key=resolved.api_key, base_url=resolved.base_url,
                         default_headers=headers, timeout=120.0)
    tools = _openai_tool_schemas(mode)

    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for h in (history or [])[-8:]:
        u, a = h.get("message", ""), h.get("response", "")
        if isinstance(u, str) and u.strip():
            messages.append({"role": "user", "content": u})
        if isinstance(a, str) and a.strip():
            messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": f"{context}\n\nUser: {message}" if context else message})

    async def _complete(msgs, with_tools=True):
        kwargs: Dict[str, Any] = dict(model=resolved.model_id, messages=msgs, temperature=0.2, max_tokens=1600)
        if with_tools:
            kwargs.update(tools=tools, tool_choice="auto")
        return await client.chat.completions.create(**kwargs)

    called: set = set()
    tool_calls = 0
    for _ in range(MAX_TOOL_CALLS + 4):
        try:
            resp = await _complete(messages)
        except Exception as exc:
            logger.error(f"openai-compat ({resolved.label}) failed: {exc}")
            holder["final_text"] = (
                f"⚠ **{resolved.label}** returned an error: {str(exc)[:300]}\n\n"
                "It may not support tool-calling on this account. Pick another model from the selector.")
            return
        msg = resp.choices[0].message
        tcs = getattr(msg, "tool_calls", None) or []
        if not tcs:
            holder["final_text"] = msg.content or ""
            return
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in tcs]})
        _emit = sse_fn or _sse
        pending: List[tuple] = []  # (tool_call_id, name, args)
        for tc in tcs:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            if tool_calls >= MAX_TOOL_CALLS:
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps({"note": "tool limit reached"})})
                continue
            signature = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
            if signature in called and name not in trading.EXECUTION_TOOLS:
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps({"note": "already fetched"})})
                continue
            called.add(signature)
            tool_calls += 1
            pending.append((tc.id, name, args))

        read_batch = [p for p in pending if p[1] not in _SEQUENTIAL_TOOLS]
        seq_batch = [p for p in pending if p[1] in _SEQUENTIAL_TOOLS]
        results: Dict[Any, Any] = {}
        if len(read_batch) > 1:
            async for ev in _run_read_tools_parallel(read_batch, db, user_id, confirm, _emit, results):
                yield ev
        else:
            seq_batch = read_batch + seq_batch
        for tc_id, name, args in seq_batch:
            out: List[Any] = []
            async for ev in _run_one_tool(name, args, db, user_id, confirm, _emit, out):
                yield ev
            results[tc_id] = out[0] if out else {"ok": False, "error": "no result"}
        for tc_id, result in results.items():
            messages.append({"role": "tool", "tool_call_id": tc_id,
                             "content": json.dumps(result, default=str)[:8000]})

    if not holder.get("final_text"):
        try:
            messages.append({"role": "user", "content": "Stop using tools and give your final answer now in markdown."})
            resp = await _complete(messages, with_tools=False)
            holder["final_text"] = resp.choices[0].message.content or ""
        except Exception:
            holder["final_text"] = "I gathered data but couldn't compose a final summary."


async def _log_trade(db, user_id: str, payload: Dict[str, Any]) -> None:
    try:
        import copilot_store
        await copilot_store.log_trade(db, user_id, payload)
    except Exception as exc:
        logger.warning(f"copilot trade log failed: {exc}")
