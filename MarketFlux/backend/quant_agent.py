"""
Autonomous Quant Agent — backtesting engine and full research pipeline.

Provides:
- Simple vectorised strategy implementations (SMA crossover, RSI mean-reversion, Momentum)
- run_backtest() to execute any strategy on yfinance data
- run_autonomous_research() to run the full quant pipeline as an async generator of SSE events
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import numpy as np
import yfinance as yf

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sse(event_type: str, payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


def _step(step: str, message: str) -> str:
    return _sse("step", {"step": step, "message": message})


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        v = float(value)
        return fallback if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return fallback


# ---------------------------------------------------------------------------
# Core backtest runner
# ---------------------------------------------------------------------------

def _compute_metrics(equity_series: np.ndarray, trade_log: List[Dict]) -> Dict[str, Any]:
    """Compute performance metrics from an equity curve (daily portfolio values)."""
    if len(equity_series) < 2:
        return {}

    returns = np.diff(equity_series) / equity_series[:-1]
    total_return = (equity_series[-1] / equity_series[0] - 1) * 100
    n_days = len(equity_series)
    years = n_days / 252
    ann_return = ((1 + total_return / 100) ** (1 / max(years, 0.01)) - 1) * 100 if years > 0 else 0.0

    daily_std = float(np.std(returns)) if len(returns) > 1 else 0.0
    ann_vol = daily_std * math.sqrt(252) * 100
    sharpe = (ann_return / ann_vol) if ann_vol > 0 else 0.0

    # Max drawdown
    peak = equity_series[0]
    max_dd = 0.0
    for v in equity_series:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd:
            max_dd = dd

    wins = [t for t in trade_log if t.get("pnl_pct", 0) > 0]
    win_rate = len(wins) / len(trade_log) * 100 if trade_log else 0.0
    avg_pnl = float(np.mean([t.get("pnl_pct", 0) for t in trade_log])) if trade_log else 0.0
    avg_win = float(np.mean([t["pnl_pct"] for t in wins])) if wins else 0.0
    losses = [t for t in trade_log if t.get("pnl_pct", 0) <= 0]
    avg_loss = float(np.mean([t["pnl_pct"] for t in losses])) if losses else 0.0
    gross_loss = sum(t["pnl_pct"] for t in losses)
    gross_win = sum(t["pnl_pct"] for t in wins)
    if losses and gross_loss != 0:
        profit_factor = abs(gross_win / gross_loss)
    elif wins and not losses:
        profit_factor = 9999.0  # infinite profit factor: all wins, no losses
    else:
        profit_factor = 0.0

    return {
        "total_return_pct": round(_safe_float(total_return), 2),
        "annualized_return_pct": round(_safe_float(ann_return), 2),
        "annualized_volatility_pct": round(_safe_float(ann_vol), 2),
        "sharpe_ratio": round(_safe_float(sharpe), 3),
        "max_drawdown_pct": round(_safe_float(max_dd), 2),
        "win_rate_pct": round(_safe_float(win_rate), 2),
        "num_trades": len(trade_log),
        "avg_trade_pnl_pct": round(_safe_float(avg_pnl), 3),
        "avg_win_pct": round(_safe_float(avg_win), 3),
        "avg_loss_pct": round(_safe_float(avg_loss), 3),
        "profit_factor": round(_safe_float(profit_factor), 3),
    }


def _build_drawdown_series(equity: np.ndarray, dates: List[str]) -> List[Dict]:
    result = []
    peak = equity[0]
    for i, v in enumerate(equity):
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        result.append({"date": dates[i], "drawdown": round(-_safe_float(dd), 2)})
    return result


def _monthly_returns(equity: np.ndarray, dates: List[str]) -> List[Dict]:
    """Aggregate equity curve into monthly return bars."""
    monthly: Dict[str, float] = {}
    for i in range(1, len(dates)):
        month_key = dates[i][:7]  # YYYY-MM
        if month_key not in monthly:
            monthly[month_key] = equity[i - 1]
        monthly[month_key + "_end"] = equity[i]

    result = []
    months = sorted({k[:7] for k in monthly.keys()})
    for m in months:
        start = monthly.get(m)
        end = monthly.get(m + "_end")
        if start and end:
            ret = (end / start - 1) * 100
            result.append({"month": m, "return_pct": round(_safe_float(ret), 2)})
    return result


# ---------------------------------------------------------------------------
# Strategy implementations (pure-Python, vectorised with numpy)
# ---------------------------------------------------------------------------

def _run_sma_crossover(
    dates: List[str],
    closes: np.ndarray,
    capital: float,
    fast: int = 20,
    slow: int = 50,
) -> Dict[str, Any]:
    """Simple moving-average crossover long-only strategy."""
    n = len(closes)
    if n < slow + 5:
        return {}

    sma_fast = np.convolve(closes, np.ones(fast) / fast, mode="full")[:n]
    sma_slow = np.convolve(closes, np.ones(slow) / slow, mode="full")[:n]

    position = 0
    cash = capital
    shares = 0.0
    equity = np.zeros(n)
    trade_log: List[Dict] = []
    entry_price = 0.0
    entry_date = ""

    for i in range(slow, n):
        price = _safe_float(closes[i])
        if price <= 0:
            equity[i] = cash + shares * _safe_float(closes[i - 1], price)
            continue

        prev_fast = _safe_float(sma_fast[i - 1])
        curr_fast = _safe_float(sma_fast[i])
        prev_slow = _safe_float(sma_slow[i - 1])
        curr_slow = _safe_float(sma_slow[i])

        # Buy signal
        if prev_fast <= prev_slow and curr_fast > curr_slow and position == 0:
            shares = cash / price
            cash = 0.0
            position = 1
            entry_price = price
            entry_date = dates[i]

        # Sell signal
        elif prev_fast >= prev_slow and curr_fast < curr_slow and position == 1:
            cash = shares * price
            pnl_pct = (price / entry_price - 1) * 100
            trade_log.append({
                "entry_date": entry_date,
                "exit_date": dates[i],
                "entry_price": round(entry_price, 4),
                "exit_price": round(price, 4),
                "pnl_pct": round(pnl_pct, 3),
                "direction": "LONG",
            })
            shares = 0.0
            position = 0

        equity[i] = cash + shares * price

    # Close open position at end of series and log the final trade
    if position == 1 and shares > 0:
        exit_price = _safe_float(closes[-1])
        cash = shares * exit_price
        pnl_pct = (exit_price / entry_price - 1) * 100 if entry_price > 0 else 0.0
        trade_log.append({
            "entry_date": entry_date,
            "exit_date": dates[-1],
            "entry_price": round(entry_price, 4),
            "exit_price": round(exit_price, 4),
            "pnl_pct": round(pnl_pct, 3),
            "direction": "LONG",
        })
        shares = 0.0
        equity[-1] = cash
    if equity[slow - 1] == 0:
        equity[:slow] = capital
    for i in range(1, slow):
        if equity[i] == 0:
            equity[i] = equity[i - 1] if equity[i - 1] > 0 else capital

    return {"strategy": "SMA Crossover", "equity": equity, "trade_log": trade_log}


def _run_rsi_strategy(
    dates: List[str],
    closes: np.ndarray,
    capital: float,
    period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
) -> Dict[str, Any]:
    """RSI mean-reversion long-only strategy."""
    n = len(closes)
    if n < period + 5:
        return {}

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.zeros(n)
    avg_loss = np.zeros(n)
    avg_gain[period] = np.mean(gains[:period])
    avg_loss[period] = np.mean(losses[:period])

    for i in range(period + 1, n):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = np.where(avg_loss == 0, 100.0, 100 - 100 / (1 + avg_gain / avg_loss))

    position = 0
    cash = capital
    shares = 0.0
    equity = np.zeros(n)
    trade_log: List[Dict] = []
    entry_price = 0.0
    entry_date = ""

    for i in range(period + 1, n):
        price = _safe_float(closes[i])
        if price <= 0:
            equity[i] = cash + shares * _safe_float(closes[i - 1], price)
            continue

        if rsi[i] < oversold and position == 0:
            shares = cash / price
            cash = 0.0
            position = 1
            entry_price = price
            entry_date = dates[i]

        elif rsi[i] > overbought and position == 1:
            cash = shares * price
            pnl_pct = (price / entry_price - 1) * 100
            trade_log.append({
                "entry_date": entry_date,
                "exit_date": dates[i],
                "entry_price": round(entry_price, 4),
                "exit_price": round(price, 4),
                "pnl_pct": round(pnl_pct, 3),
                "direction": "LONG",
            })
            shares = 0.0
            position = 0

        equity[i] = cash + shares * price

    for i in range(1, period + 1):
        equity[i] = capital
    # Close open position at end of series and log the final trade
    if position == 1 and shares > 0:
        exit_price = _safe_float(closes[-1])
        if exit_price <= 0:
            exit_price = entry_price  # last resort: close flat if price is unavailable
        cash = shares * exit_price
        pnl_pct = (exit_price / entry_price - 1) * 100 if entry_price > 0 else 0.0
        trade_log.append({
            "entry_date": entry_date,
            "exit_date": dates[-1],
            "entry_price": round(entry_price, 4),
            "exit_price": round(exit_price, 4),
            "pnl_pct": round(pnl_pct, 3),
            "direction": "LONG",
        })
        shares = 0.0
        equity[-1] = cash

    return {"strategy": "RSI Mean Reversion", "equity": equity, "trade_log": trade_log}


def _run_momentum(
    dates: List[str],
    closes: np.ndarray,
    capital: float,
    lookback: int = 60,
    hold: int = 20,
) -> Dict[str, Any]:
    """Simple price-momentum strategy: buy if 60-day return > 0, hold for 20 days."""
    n = len(closes)
    if n < lookback + hold + 5:
        return {}

    position = 0
    cash = capital
    shares = 0.0
    equity = np.zeros(n)
    trade_log: List[Dict] = []
    entry_price = 0.0
    entry_date = ""
    hold_counter = 0

    for i in range(lookback, n):
        price = _safe_float(closes[i])
        if price <= 0:
            equity[i] = cash + shares * _safe_float(closes[i - 1], price)
            continue

        past_price = _safe_float(closes[i - lookback])
        momentum = (price / past_price - 1) if past_price > 0 else 0

        if momentum > 0 and position == 0:
            shares = cash / price
            cash = 0.0
            position = 1
            entry_price = price
            entry_date = dates[i]
            hold_counter = 0

        elif position == 1:
            hold_counter += 1
            if hold_counter >= hold or momentum < -0.05:
                cash = shares * price
                pnl_pct = (price / entry_price - 1) * 100
                trade_log.append({
                    "entry_date": entry_date,
                    "exit_date": dates[i],
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(price, 4),
                    "pnl_pct": round(pnl_pct, 3),
                    "direction": "LONG",
                })
                shares = 0.0
                position = 0

        equity[i] = cash + shares * price

    for i in range(lookback):
        equity[i] = capital
    # Close open position at end of series and log the final trade
    if position == 1 and shares > 0:
        final_price = _safe_float(closes[-1])
        cash = shares * final_price
        pnl_pct = (final_price / entry_price - 1) * 100 if entry_price > 0 else 0.0
        trade_log.append({
            "entry_date": entry_date,
            "exit_date": dates[-1],
            "entry_price": round(entry_price, 4),
            "exit_price": round(final_price, 4),
            "pnl_pct": round(pnl_pct, 3),
            "direction": "LONG",
        })
        shares = 0.0
        equity[-1] = cash

    return {"strategy": "Momentum", "equity": equity, "trade_log": trade_log}


# ---------------------------------------------------------------------------
# Public backtest API
# ---------------------------------------------------------------------------

def _run_strategy_on_data(
    strategy: str,
    dates: List[str],
    closes: np.ndarray,
    capital: float,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Run one named strategy on pre-fetched dates/closes arrays."""
    if strategy == "sma_crossover":
        return _run_sma_crossover(dates, closes, capital,
                                  fast=params.get("fast", 20),
                                  slow=params.get("slow", 50))
    elif strategy == "rsi_mean_reversion":
        return _run_rsi_strategy(dates, closes, capital,
                                 period=params.get("rsi_period", 14),
                                 oversold=params.get("oversold", 30),
                                 overbought=params.get("overbought", 70))
    elif strategy == "momentum":
        return _run_momentum(dates, closes, capital,
                             lookback=params.get("lookback", 60),
                             hold=params.get("hold", 20))
    return {}


def _build_result(
    ticker: str,
    strategy: str,
    period: str,
    capital: float,
    dates: List[str],
    closes: np.ndarray,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the standard backtest result dict from a completed strategy run."""
    equity = result["equity"]
    # Forward-fill zeros
    for i in range(1, len(equity)):
        if equity[i] == 0:
            equity[i] = equity[i - 1]
    if equity[0] == 0:
        equity[0] = capital

    bh_equity = closes / closes[0] * capital
    trade_log = result["trade_log"]
    metrics = _compute_metrics(equity, trade_log)
    bh_metrics = _compute_metrics(bh_equity, [])

    equity_curve = [
        {
            "date": dates[i],
            "portfolio": round(_safe_float(equity[i]), 2),
            "buy_hold": round(_safe_float(bh_equity[i]), 2),
        }
        for i in range(len(dates))
    ]

    return {
        "ticker": ticker.upper(),
        "strategy_name": result["strategy"],
        "period": period,
        "capital": capital,
        "start_date": dates[0] if dates else "",
        "end_date": dates[-1] if dates else "",
        "metrics": metrics,
        "benchmark_metrics": {
            "total_return_pct": bh_metrics.get("total_return_pct", 0),
            "annualized_return_pct": bh_metrics.get("annualized_return_pct", 0),
            "max_drawdown_pct": bh_metrics.get("max_drawdown_pct", 0),
            "sharpe_ratio": bh_metrics.get("sharpe_ratio", 0),
        },
        "equity_curve": equity_curve,
        "drawdown_series": _build_drawdown_series(equity, dates),
        "monthly_returns": _monthly_returns(equity, dates),
        "trade_log": trade_log,
    }


def run_backtest(
    ticker: str,
    strategy: str = "sma_crossover",
    period: str = "2y",
    capital: float = 100_000,
    params: Optional[Dict[str, Any]] = None,
    _hist=None,
) -> Dict[str, Any]:
    """
    Fetch historical data for *ticker* and run the requested *strategy*.

    Pass *_hist* (a pandas DataFrame from yf.Ticker.history) to reuse already-
    fetched data and skip a redundant network call.

    Supported strategies: "sma_crossover", "rsi_mean_reversion", "momentum".

    Returns a dict with: strategy_name, ticker, period, metrics, equity_curve,
    drawdown_series, monthly_returns, trade_log, and benchmark_metrics.
    """
    params = params or {}
    if _hist is None:
        hist = yf.Ticker(ticker).history(period=period)
    else:
        hist = _hist
    if hist is None or hist.empty or len(hist) < 30:
        return {"error": f"Insufficient historical data for {ticker}"}

    hist = hist.dropna(subset=["Close"])
    dates = [str(d.date()) for d in hist.index]
    closes = hist["Close"].values.astype(float)

    if strategy not in ("sma_crossover", "rsi_mean_reversion", "momentum"):
        return {"error": f"Unknown strategy: {strategy}"}

    result = _run_strategy_on_data(strategy, dates, closes, capital, params)
    if not result or "equity" not in result:
        return {"error": "Backtest produced no data"}

    return _build_result(ticker, strategy, period, capital, dates, closes, result)


# ---------------------------------------------------------------------------
# Autonomous research pipeline (streaming SSE generator)
# ---------------------------------------------------------------------------

async def run_autonomous_research(
    ticker: str,
    capital: float = 100_000,
    risk_profile: str = "balanced",
    user_id: Optional[str] = None,
    db=None,
) -> AsyncGenerator[str, None]:
    """
    Full autonomous quant research pipeline.  Emits SSE events at each step:
      step     — progress message
      data     — intermediate JSON results
      backtest — backtest result for one strategy
      done     — final compiled report
    """
    ticker = ticker.upper().strip()

    yield _step("init", f"Initializing autonomous quant research for {ticker}...")
    await asyncio.sleep(0.1)

    # 1. Fetch macro regime
    yield _step("macro", "Fetching macro regime and market conditions...")
    try:
        from vnext.engines import build_macro_regime_view
        macro = await build_macro_regime_view()
    except Exception:
        _log.warning("build_macro_regime_view failed", exc_info=True)
        macro = {"regime": "unknown", "confidence": 50, "summary": "Macro data unavailable"}

    yield _sse("data", {"section": "macro", "macro": {
        "regime": macro.get("regime"),
        "confidence": macro.get("confidence"),
        "summary": macro.get("summary"),
    }})
    await asyncio.sleep(0.05)

    # 2. Fetch live ticker data
    yield _step("market_data", f"Fetching live price data and fundamentals for {ticker}...")
    try:
        from vnext.engines import build_ticker_workspace
        workspace = await build_ticker_workspace(ticker)
        snapshot = workspace.get("snapshot") or {}
        technicals = workspace.get("technicals") or {}
        price = snapshot.get("price")
        change_pct = snapshot.get("change_percent")
        sector = snapshot.get("sector")
        pe = snapshot.get("pe_ratio")
        trend = technicals.get("trend")
    except Exception:
        _log.warning("build_ticker_workspace(%s) failed", ticker, exc_info=True)
        snapshot = {}
        price = None
        change_pct = None
        sector = None
        pe = None
        trend = "unknown"

    yield _sse("data", {"section": "snapshot", "snapshot": {
        "ticker": ticker,
        "price": price,
        "change_pct": change_pct,
        "sector": sector,
        "pe_ratio": pe,
        "trend": trend,
    }})
    await asyncio.sleep(0.05)

    # 3. Strategy swarm analysis
    yield _step("swarm", "Running multi-agent strategy swarm analysis...")
    swarm_result: Dict[str, Any] = {}
    try:
        from vnext.strategy_swarm import run_swarm
        regime_context = {"regime": macro.get("regime", "unknown"), "confidence": macro.get("confidence", 50)}
        swarm_result = await run_swarm(
            prompt=f"Analyze {ticker} for a {'defensive' if risk_profile == 'conservative' else 'aggressive' if risk_profile == 'aggressive' else 'balanced'} trade based on current market conditions.",
            regime_context=regime_context,
            tickers=[ticker],
            user_id=user_id or "anonymous",
        )
        yield _sse("data", {"section": "swarm", "swarm_summary": swarm_result.get("final_strategy", "")[:2000]})
    except Exception as e:
        _log.warning("Strategy swarm failed for %s", ticker, exc_info=True)
        yield _sse("data", {"section": "swarm", "swarm_summary": f"Strategy swarm unavailable: {e}"})
    await asyncio.sleep(0.05)

    # 4. Run backtests — fetch history once and share across all strategy variants
    yield _step("backtest", "Running historical backtests across three strategy families...")
    strategies = ["sma_crossover", "rsi_mean_reversion", "momentum"]
    strategy_labels = {
        "sma_crossover": "SMA Crossover (20/50)",
        "rsi_mean_reversion": "RSI Mean Reversion (14)",
        "momentum": "Price Momentum (60-day)",
    }
    backtest_period = "2y"
    backtest_results: Dict[str, Dict] = {}

    # Single yfinance fetch shared by all three strategies
    shared_hist = None
    try:
        shared_hist = await asyncio.to_thread(
            lambda: yf.Ticker(ticker).history(period=backtest_period)
        )
    except Exception:
        _log.warning("Shared history fetch failed for %s; each strategy will fetch independently", ticker, exc_info=True)

    for strat in strategies:
        yield _step("backtest", f"Backtesting {strategy_labels[strat]}...")
        try:
            bt = await asyncio.to_thread(
                run_backtest, ticker, strat, backtest_period, capital, None, shared_hist
            )
            if "error" not in bt:
                backtest_results[strat] = bt
                yield _sse("backtest", {
                    "strategy_id": strat,
                    "strategy_name": strategy_labels[strat],
                    "metrics": bt["metrics"],
                    "benchmark_metrics": bt.get("benchmark_metrics", {}),
                    "equity_curve": bt["equity_curve"][-60:],  # last 60 points for preview
                    "monthly_returns": bt["monthly_returns"][-12:],
                    "trade_log": bt["trade_log"][-10:],
                })
        except Exception as ex:
            _log.warning("Backtest %s failed for %s", strat, ticker, exc_info=True)
            yield _sse("data", {"section": "backtest_error", "strategy": strat, "error": str(ex)})
        await asyncio.sleep(0.1)

    # 5. Select best strategy by Sharpe ratio
    yield _step("evaluate", "Evaluating backtest results and selecting optimal strategy...")
    best_strat_id = None
    best_sharpe = -999.0
    for strat_id, bt in backtest_results.items():
        sharpe = bt.get("metrics", {}).get("sharpe_ratio", -999)
        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_strat_id = strat_id

    yield _sse("data", {"section": "best_strategy", "best_strategy_id": best_strat_id,
                        "best_strategy_name": strategy_labels.get(best_strat_id, "N/A"),
                        "best_sharpe": round(best_sharpe, 3)})
    await asyncio.sleep(0.05)

    # 6. Build final report
    yield _step("report", "Compiling full quant research report...")
    await asyncio.sleep(0.1)

    all_bt_light = {}
    for strat_id, bt in backtest_results.items():
        all_bt_light[strat_id] = {
            "strategy_name": bt["strategy_name"],
            "metrics": bt["metrics"],
            "benchmark_metrics": bt.get("benchmark_metrics", {}),
            # Full data for the dashboard
            "equity_curve": bt["equity_curve"],
            "drawdown_series": bt["drawdown_series"],
            "monthly_returns": bt["monthly_returns"],
            "trade_log": bt["trade_log"],
            "start_date": bt.get("start_date"),
            "end_date": bt.get("end_date"),
        }

    report = {
        "ticker": ticker,
        "generated_at": _utcnow(),
        "capital": capital,
        "risk_profile": risk_profile,
        "macro": {
            "regime": macro.get("regime"),
            "confidence": macro.get("confidence"),
            "summary": macro.get("summary"),
        },
        "snapshot": {
            "price": price,
            "change_pct": change_pct,
            "sector": sector,
            "pe_ratio": pe,
            "trend": trend,
        },
        "swarm_strategy": swarm_result.get("final_strategy", ""),
        "backtests": all_bt_light,
        "best_strategy_id": best_strat_id,
        "best_strategy_name": strategy_labels.get(best_strat_id, "N/A"),
        "is_paper": True,
        "execution_status": "pending_approval",
    }

    yield _sse("done", {"status": "ok", "report": report})
