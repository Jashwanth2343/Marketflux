"""Intelligence, risk, backtest & compliance tools for the MarketFlux Copilot.

This module is the bridge that finally connects the agent's reasoning loop to the
three deep engines the product already has but the copilot previously could not
reach:

  * ``signal_engine``    — 20+ institutional quant signals → a composite conviction
                           score (momentum / value / quality / sentiment / technical).
  * ``risk_engine``      — portfolio beta, parametric VaR, stress tests, sector
                           concentration, factor exposure, position sizing.
  * ``backtest.runner``  — the full DSL backtester, so the agent can *validate* a
                           strategy idea on history before recommending or trading it.

Plus ``compliance_engine`` so the agent can pre-flight an order against the same
controls the execution chokepoint enforces.

Every function here is a plain callable with a rich docstring — that docstring is
the tool description the LLM sees, so it must read like a manual for the model.
The async ones are awaited by the agent loop; the sync ones are run in a thread.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Keep backtests bounded so a single tool call can't exceed the agent's tool
# timeout or hammer the data provider.
_MAX_BACKTEST_SYMBOLS = 8


def _err(message: str, **extra) -> dict:
    return {"ok": False, "error": message, **extra}


def _f(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ===========================================================================
# QUANT INTELLIGENCE
# ===========================================================================

async def get_quant_signals(symbol: str) -> dict:
    """Compute MarketFlux's institutional quant scorecard for one ticker.

    Runs 20+ signals across five factor families — momentum, value, quality,
    sentiment, technical — and blends them into a single composite conviction
    score from -100 (strong sell) to +100 (strong buy), with a human label.
    Use this to ground a buy/sell thesis in systematic factors instead of vibes:
    call it before forming conviction on a name, and cite the composite score and
    the strongest category in your reasoning.

    Args:
        symbol: Stock ticker, e.g. "NVDA".

    Returns the composite score, label, and per-category sub-scores.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return _err("symbol is required.")
    try:
        import signal_engine
        res = await signal_engine.compute_signals(symbol)
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_quant_signals(%s) failed: %s", symbol, exc)
        return _err(f"signal computation failed: {exc}")
    cats = res.get("categories", {})
    return {
        "ok": True,
        "symbol": res.get("symbol", symbol),
        "name": res.get("name"),
        "sector": res.get("sector"),
        "composite_score": res.get("composite_score"),
        "signal_label": res.get("signal_label"),
        "category_scores": {k: v.get("score") for k, v in cats.items()},
        "metadata": res.get("metadata", {}),
    }


async def scan_signals(tickers: str) -> dict:
    """Rank a basket of tickers by their composite quant score, best first.

    Use this to find the strongest names in a watchlist or a candidate set —
    e.g. "which of these 6 chip stocks screens best right now". Returns each
    ticker's composite score and label, sorted descending, so you can pick the
    top-conviction idea to research deeper or size into.

    Args:
        tickers: Comma-separated tickers, e.g. "NVDA,AMD,AVGO,MU,INTC,TSM".
            Capped at 12 names per call to stay responsive.

    Returns the ranked list.
    """
    syms = [t.strip().upper() for t in (tickers or "").replace(" ", ",").split(",") if t.strip()]
    syms = list(dict.fromkeys(syms))[:12]  # dedupe, cap
    if not syms:
        return _err("Provide at least one ticker (comma-separated).")
    try:
        import signal_engine
        results = await signal_engine.scan_universe(syms)
    except Exception as exc:  # noqa: BLE001
        logger.warning("scan_signals failed: %s", exc)
        return _err(f"scan failed: {exc}")
    ranked = [{
        "symbol": r.get("symbol"),
        "composite_score": r.get("composite_score"),
        "signal_label": r.get("signal_label"),
        "sector": r.get("sector"),
    } for r in results]
    return {"ok": True, "count": len(ranked), "ranked": ranked}


# ===========================================================================
# RISK MANAGEMENT
# ===========================================================================

async def analyze_portfolio_risk() -> dict:
    """Run a hedge-fund-grade risk X-ray on the CURRENT live paper portfolio.

    Pulls your real open positions from the broker and computes: portfolio beta
    vs SPY, 95% 1-day parametric VaR, sector concentration + Herfindahl warning,
    pairwise correlations, factor tilt (growth/value/quality), and six stress
    scenarios (market crash, rate spike, recession, etc.). Call this whenever the
    user asks "what's my risk / how exposed am I / how would I do in a crash", or
    before a large add, to manage the book like a real PM.

    Returns the full risk report (beta, VaR, max drawdown, stress tests,
    concentration, factor exposure, and a narrative summary).
    """
    try:
        from vnext import alpaca_client
        positions = await _to_thread(alpaca_client.get_positions)
    except Exception as exc:  # noqa: BLE001
        return _err(f"could not read positions: {exc}")
    holdings = []
    for p in positions or []:
        try:
            holdings.append({
                "ticker": (p.get("symbol") or "").upper(),
                "shares": float(p.get("qty") or 0),
                "avg_price": float(p.get("avg_entry_price") or 0),
            })
        except (TypeError, ValueError):
            continue
    if not holdings:
        return {"ok": True, "empty": True,
                "message": "Portfolio is all cash — no market risk to analyze. Nothing held."}
    try:
        import risk_engine
        report = await risk_engine.analyze_portfolio_risk(holdings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("analyze_portfolio_risk failed: %s", exc)
        return _err(f"risk analysis failed: {exc}")
    report["ok"] = True
    return report


async def analyze_stock_risk(symbol: str) -> dict:
    """Risk profile for a single name: beta, annualised volatility, 95% daily VaR,
    max drawdown, factor exposure, and a Kelly-inspired position-sizing
    recommendation (suggested %, max %, stop-loss %). Call this before sizing a
    new position so you size to its risk, not just its upside.

    Args:
        symbol: Stock ticker, e.g. "TSLA".
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return _err("symbol is required.")
    try:
        import risk_engine
        report = await risk_engine.analyze_single_stock_risk(symbol)
    except Exception as exc:  # noqa: BLE001
        logger.warning("analyze_stock_risk(%s) failed: %s", symbol, exc)
        return _err(f"risk analysis failed: {exc}")
    report["ok"] = True
    return report


# ===========================================================================
# BACKTESTING  (validate an idea on history before trading it)
# ===========================================================================

def run_strategy_backtest(strategy_json: str, start: str, end: str,
                          initial_capital: float = 100000.0) -> dict:
    """Backtest a rules-based strategy on historical data BEFORE trading it live.

    This is how you prove an idea instead of guessing. Pass a strategy as a JSON
    string in MarketFlux's strategy DSL and a date range; you get headline
    performance (total return, CAGR, Sharpe, Sortino, max drawdown, win rate,
    profit factor, number of trades). Use it when the user asks "does this
    strategy work / would this have made money / backtest X", or to sanity-check
    a systematic entry rule before you size into it.

    The DSL (strategy_json) shape:
        {
          "name": "RSI dip in uptrend",
          "universe": ["AAPL","MSFT"],          // <= 8 tickers
          "indicators": {"rsi14":{"type":"rsi","period":14},
                          "sma200":{"type":"sma","period":200}},
          "entry": {"all":[{"lt":["rsi14",30]},{"gt":["close","sma200"]}]},
          "exit":  {"any":[{"gt":["rsi14",65]},{"hold_days_gte":20}]},
          "position_sizing": {"type":"fixed_pct","pct":0.1},
          "max_positions": 5, "stop_loss_pct": 0.08, "take_profit_pct": 0.2
        }
    Operators: lt/lte/gt/gte/eq/neq, crosses_above/crosses_below, and combinators
    all/any/not. Exit-only predicates: hold_days_gte, profit_pct_gte, loss_pct_gte.
    Indicator types include sma, ema, rsi, macd, atr, bbands. Operands are numbers
    or column/indicator names (open/high/low/close/volume + your indicators).

    Args:
        strategy_json: the strategy as a JSON string (see shape above).
        start: ISO start date, e.g. "2021-01-01".
        end: ISO end date, e.g. "2024-01-01".
        initial_capital: starting capital, default 100000.

    Returns headline metrics, or a clear validation error to fix and retry.
    """
    try:
        strategy = json.loads(strategy_json) if isinstance(strategy_json, str) else dict(strategy_json)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return _err(f"strategy_json is not valid JSON: {exc}")
    if not isinstance(strategy, dict):
        return _err("strategy_json must decode to a JSON object.")

    universe = strategy.get("universe")
    if not isinstance(universe, list) or not universe:
        return _err("strategy.universe must be a non-empty list of tickers.")
    if len(universe) > _MAX_BACKTEST_SYMBOLS:
        return _err(f"Universe too large ({len(universe)}). Cap at {_MAX_BACKTEST_SYMBOLS} tickers per backtest.")

    try:
        from backtest.runner import run_backtest
        from backtest.metrics import compute_metrics
        result = run_backtest(strategy, start=start, end=end, initial_capital=float(initial_capital))
    except ValueError as exc:  # DSL validation / bad inputs — actionable
        return _err(f"strategy invalid: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("run_strategy_backtest failed: %s", exc)
        return _err(f"backtest failed: {exc}")

    trades = [t.as_dict() for t in result.trades]
    m = compute_metrics(result.equity_curve, trades).as_dict()
    return {
        "ok": True,
        "strategy_name": result.strategy_name,
        "universe": [s.upper() for s in universe],
        "period": {"start": start, "end": end},
        "metrics": {
            "total_return_pct": round(m["total_return"] * 100, 2),
            "cagr_pct": round(m["cagr"] * 100, 2),
            "sharpe": round(m["sharpe"], 2),
            "sortino": round(m["sortino"], 2),
            "max_drawdown_pct": round(m["max_drawdown"] * 100, 2),
            "volatility_pct": round(m["volatility"] * 100, 2),
            "win_rate_pct": round(m["win_rate"] * 100, 1),
            "profit_factor": round(m["profit_factor"], 2) if m["profit_factor"] != float("inf") else None,
            "num_trades": m["num_trades"],
        },
    }


# ===========================================================================
# MARKET REGIME  (adapt posture to the tape)
# ===========================================================================

async def get_market_regime() -> dict:
    """Classify the CURRENT market regime so you size and posture correctly.

    Reads SPY trend (vs 50/200-day), the VIX volatility band, and sector breadth,
    and returns a regime label (risk-on … risk-off), a suggested gross-exposure
    band, and a one-line playbook. Call this at the start of any "what should I do /
    how should I position / is now a good time" question, and let it scale your
    conviction: demand higher scores and smaller size in risk-off/high-vol regimes.
    """
    try:
        import market_regime
        res = await market_regime.compute_regime()
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_market_regime failed: %s", exc)
        return _err(f"regime computation failed: {exc}")
    return res


# ===========================================================================
# WHAT-IF  (project the portfolio impact of a trade before placing it)
# ===========================================================================

def project_trade(account: Dict[str, Any], positions: List[Dict[str, Any]],
                  symbol: str, side: str, qty: float, price: float) -> dict:
    """Pure projection of a portfolio AFTER a hypothetical trade. Deterministic."""
    symbol = (symbol or "").strip().upper()
    side = (side or "").strip().lower()
    equity = _f(account.get("equity"))
    cash = _f(account.get("cash"))
    bp = _f(account.get("buying_power"))
    qty = _f(qty)
    price = _f(price)
    notional = qty * price

    held = next((p for p in positions if (p.get("symbol") or "").upper() == symbol), None)
    held_mv = abs(_f(held.get("market_value"))) if held else 0.0

    if side == "sell":
        sell_val = min(notional, held_mv) if held_mv else notional
        new_mv = max(0.0, held_mv - notional)
        cash_after = cash + sell_val
        bp_after = bp + sell_val
    else:  # buy
        new_mv = held_mv + notional
        cash_after = cash - notional
        bp_after = bp - notional

    before_w = (held_mv / equity * 100) if equity else 0.0
    after_w = (new_mv / equity * 100) if equity else 0.0

    # Largest single-name weight after the trade.
    largest_sym, largest_w = symbol, after_w
    for p in positions:
        s = (p.get("symbol") or "").upper()
        mv = new_mv if s == symbol else abs(_f(p.get("market_value")))
        w = (mv / equity * 100) if equity else 0.0
        if w > largest_w:
            largest_sym, largest_w = s, w

    return {
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": round(price, 2),
        "notional": round(notional, 2),
        "equity": round(equity, 2),
        "before": {"position_value": round(held_mv, 2), "weight_pct": round(before_w, 1),
                   "cash": round(cash, 2), "buying_power": round(bp, 2)},
        "after": {"position_value": round(new_mv, 2), "weight_pct": round(after_w, 1),
                  "cash": round(cash_after, 2), "buying_power": round(bp_after, 2)},
        "largest_position_after": {"symbol": largest_sym, "weight_pct": round(largest_w, 1)},
    }


async def simulate_trade(symbol: str, side: str, quantity: float,
                         order_type: str = "market", limit_price: float = 0.0) -> dict:
    """Simulate a trade's portfolio impact BEFORE placing it (what-if sandbox).

    Shows the projected book after the hypothetical order — the position's new
    weight, cash and buying power left, and the largest resulting concentration —
    and runs the same pre-trade compliance gate so you can see whether it would
    clear. Use this to right-size before you commit: "what happens if I buy 50
    NVDA?". Nothing is placed.

    Args:
        symbol: ticker.
        side: "buy" or "sell".
        quantity: shares.
        order_type: "market" or "limit".
        limit_price: limit price for limit orders (else 0).
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return _err("symbol is required.")
    account, positions, est_price = await _order_context(symbol)
    px = limit_price if (order_type == "limit" and limit_price and limit_price > 0) else est_price
    if not px or px <= 0:
        return _err(f"could not estimate a price for {symbol}; cannot simulate.")
    projection = project_trade(account, positions, symbol, side, quantity, px)

    import compliance_engine
    compliance = compliance_engine.pre_trade_check(
        symbol=symbol, side=side, quantity=quantity, est_price=est_price,
        order_type=order_type, limit_price=limit_price,
        account=account, positions=positions,
    )
    return {
        "ok": True,
        **projection,
        "compliance_decision": compliance.get("decision"),
        "compliance_summary": compliance.get("summary"),
    }


# ===========================================================================
# CATALYST AWARENESS  (earnings intelligence — reuses earnings_intel.py)
# ===========================================================================

async def get_earnings_intel(symbol: str) -> dict:
    """Earnings catalyst intelligence: next earnings date, historical beat rate, an
    estimated surprise probability, and an AI pre/post-earnings brief. Call this
    before sizing into a name so you don't get caught into an earnings print — a
    near-dated, high-uncertainty catalyst is a reason to wait or size smaller.

    Args:
        symbol: Stock ticker, e.g. "NVDA".
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return _err("symbol is required.")
    try:
        import earnings_intel
        res = await earnings_intel.get_earnings_intelligence(symbol)
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_earnings_intel(%s) failed: %s", symbol, exc)
        return _err(f"earnings intel failed: {exc}")
    if isinstance(res, dict):
        res.setdefault("ok", True)
    return res


# ===========================================================================
# MULTI-AGENT DELEGATION  (span a research team when one pass isn't enough)
# ===========================================================================

async def deep_research(symbol: str) -> dict:
    """Summon a 5-specialist research TEAM for a deep, institutional dive on a name.

    Spawns five analyst sub-agents IN PARALLEL — Fundamentals, Technical, Macro,
    Sentiment, and Risk — each producing a focused section, then a Director agent
    synthesises them into a full investment research note with a rating and price
    target. Use this for HIGH-STAKES or ambiguous decisions where a single research
    pass isn't enough and you want a committee-grade memo before sizing real
    conviction. Heavier and slower than the individual tools, so reserve it for the
    calls that matter.

    Args:
        symbol: Stock ticker, e.g. "NVDA".

    Returns the synthesised memo, the composite signal score/label, and a compact
    set of per-specialist takes.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return _err("symbol is required.")
    try:
        import multi_agent
        res = await multi_agent.run_multi_agent_research(symbol)
    except Exception as exc:  # noqa: BLE001
        logger.warning("deep_research(%s) failed: %s", symbol, exc)
        return _err(f"research team failed: {exc}")
    memo = res.get("memo_markdown") or ""
    return {
        "ok": True,
        "symbol": res.get("symbol", symbol),
        "name": res.get("name"),
        "sector": res.get("sector"),
        "signal_score": res.get("signal_score"),
        "signal_label": res.get("signal_label"),
        "specialist_reports": res.get("specialist_reports", {}),
        # Cap the memo so it fits the model's tool-result budget; the agent
        # summarises it for the user and can cite specifics.
        "memo_markdown": memo[:6000],
    }


# ===========================================================================
# SELF-IMPROVEMENT  (review own outcomes, distil lessons into long-term memory)
# ===========================================================================

async def review_and_learn(lookback_days: int = 30) -> dict:
    """Review your OWN trading track record and LEARN durable lessons from it.

    Pulls the live account, positions, performance, and your executed-trade history,
    grades what worked vs what hurt, and writes a few generalizable lessons into your
    long-term memory so future decisions improve (you'll recall them automatically on
    later turns). Call this when the user asks "how am I doing / review my trades /
    what have you learned", periodically to self-improve, or as a scheduled standing
    agent ("review my book and learn every morning").

    Args:
        lookback_days: window to review, default 30 (1-365).

    Returns a graded performance review with the lessons captured. NOTE: this tool is
    executed with your account context injected by the runtime.
    """
    # Real implementation lives in copilot_learning.review_and_learn_impl and is
    # invoked by the agent loop with (db, user_id) injected — see copilot_agent.
    # This stub exists for tool-schema introspection and should not be called
    # directly; if it is (no context), return a clear notice.
    return _err("review_and_learn must run with account context (handled by the agent runtime).")


async def debate_thesis(symbol: str) -> dict:
    """Run an adversarial BULL vs BEAR debate, then a Research-Manager verdict.

    Convenes two opposing analysts on the SAME evidence — a growth-minded bull and
    a skeptical short-seller bear — then a judge weighs the debate into a typed
    verdict (Bullish/Neutral/Bearish), conviction, a concrete recommended action,
    the key swing factor, and what would change the call. Use this for high-stakes
    or genuinely ambiguous decisions where you want the bear case stress-tested
    before committing real conviction. Every debate is logged for audit.

    Args:
        symbol: Stock ticker, e.g. "NVDA".
    """
    # Real implementation lives in copilot_debate.run_debate_impl and is invoked by
    # the agent loop with (db, user_id) injected. This stub is for schema only.
    return _err("debate_thesis must run with account context (handled by the agent runtime).")


# ===========================================================================
# COMPLIANCE  (pre-flight an order against the same controls the loop enforces)
# ===========================================================================

async def compliance_precheck(symbol: str, side: str, quantity: float,
                              order_type: str = "market", limit_price: float = 0.0) -> dict:
    """Pre-flight an order through the pre-trade compliance & risk controls.

    Runs the exact same gate the execution chokepoint enforces — buying power,
    per-order notional cap, single-name concentration ceiling, short-sale flag,
    pattern-day-trader equity floor, penny-stock liquidity, and wash-sale
    awareness — against the live account, WITHOUT placing anything. Call this
    before proposing or placing a non-trivial order so you can size it to clear
    compliance and tell the user it's within the limits. A BLOCK here means the
    order would be refused; adjust size and re-check.

    Args:
        symbol: ticker.
        side: "buy" or "sell".
        quantity: shares.
        order_type: "market" or "limit".
        limit_price: limit price for limit orders (else 0).

    Returns decision (PASS/WARN/BLOCK), the per-rule checks, and order economics.
    """
    import compliance_engine
    account, positions, est_price = await _order_context(symbol)
    return compliance_engine.pre_trade_check(
        symbol=symbol, side=side, quantity=quantity, est_price=est_price,
        order_type=order_type, limit_price=limit_price,
        account=account, positions=positions,
    )


# ===========================================================================
# Shared helpers (also used by the agent loop's enforcement chokepoint)
# ===========================================================================

async def _order_context(symbol: str):
    """Fetch (account, positions, est_price) for a symbol — best effort."""
    account: Dict[str, Any] = {}
    positions: List[Dict[str, Any]] = []
    est_price = 0.0
    try:
        import copilot_trading_tools as trading
        from vnext import alpaca_client
        acct = await _to_thread(alpaca_client.get_account)
        if acct:
            account = {
                "equity": acct.get("equity"),
                "cash": acct.get("cash"),
                "buying_power": acct.get("buying_power"),
            }
        raw_positions = await _to_thread(alpaca_client.get_positions) or []
        positions = [{
            "symbol": p.get("symbol"),
            "qty": p.get("qty"),
            "market_value": p.get("market_value"),
            "unrealized_pl": p.get("unrealized_pl"),
            "avg_entry_price": p.get("avg_entry_price"),
        } for p in raw_positions]
        est_price = await _to_thread(trading._estimate_price, (symbol or "").upper())
    except Exception as exc:  # noqa: BLE001
        logger.warning("_order_context(%s) failed: %s", symbol, exc)
    return account, positions, est_price


async def _to_thread(func, *args):
    import asyncio
    return await asyncio.to_thread(func, *args)


# Tools the agent may call (name -> callable). Imported by copilot_agent.
INTELLIGENCE_TOOLS = {
    "get_quant_signals": get_quant_signals,
    "scan_signals": scan_signals,
    "analyze_portfolio_risk": analyze_portfolio_risk,
    "analyze_stock_risk": analyze_stock_risk,
    "get_market_regime": get_market_regime,
    "simulate_trade": simulate_trade,
    "get_earnings_intel": get_earnings_intel,
    "run_strategy_backtest": run_strategy_backtest,
    "deep_research": deep_research,
    "debate_thesis": debate_thesis,
    "review_and_learn": review_and_learn,
    "compliance_precheck": compliance_precheck,
}

# Tools whose real execution needs (db, user_id) injected by the agent runtime
# rather than filled by the LLM. The registered callables above are stubs used
# only for schema/labels; copilot_agent routes these to their *_impl.
CONTEXT_TOOLS = {"review_and_learn", "debate_thesis"}
