"""Performance metrics for backtest results.

All ratios assume daily bars and 252 trading days per year. Inputs are pandas
Series indexed by trading date.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping

import math

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def _safe_std(arr: np.ndarray) -> float:
    if arr.size < 2:
        return 0.0
    return float(np.std(arr, ddof=1))


def daily_returns(equity: pd.Series) -> pd.Series:
    if equity is None or equity.empty:
        return pd.Series(dtype=float)
    return equity.pct_change().dropna()


def cagr(equity: pd.Series) -> float:
    if equity is None or len(equity) < 2:
        return 0.0
    start, end = float(equity.iloc[0]), float(equity.iloc[-1])
    if start <= 0 or end <= 0:
        return 0.0
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    years = days / 365.25
    if years <= 0:
        return 0.0
    return (end / start) ** (1.0 / years) - 1.0


def sharpe(returns: pd.Series, risk_free: float = 0.0) -> float:
    arr = returns.dropna().to_numpy()
    if arr.size < 2:
        return 0.0
    excess = arr - (risk_free / TRADING_DAYS)
    sigma = _safe_std(excess)
    if sigma == 0:
        return 0.0
    return float(np.mean(excess) / sigma * math.sqrt(TRADING_DAYS))


def sortino(returns: pd.Series, risk_free: float = 0.0) -> float:
    arr = returns.dropna().to_numpy()
    if arr.size < 2:
        return 0.0
    excess = arr - (risk_free / TRADING_DAYS)
    downside = excess[excess < 0]
    if downside.size == 0:
        return 0.0
    downside_dev = math.sqrt(float(np.mean(downside ** 2)))
    if downside_dev == 0:
        return 0.0
    return float(np.mean(excess) / downside_dev * math.sqrt(TRADING_DAYS))


def max_drawdown(equity: pd.Series) -> float:
    """Worst peak-to-trough drawdown as a positive decimal (e.g. 0.23 = -23%)."""
    if equity is None or equity.empty:
        return 0.0
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    return float(-dd.min()) if not dd.empty else 0.0


def volatility(returns: pd.Series) -> float:
    arr = returns.dropna().to_numpy()
    if arr.size < 2:
        return 0.0
    return float(_safe_std(arr) * math.sqrt(TRADING_DAYS))


def win_rate(trades: List[Mapping]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if float(t.get("pnl", 0.0)) > 0)
    return wins / len(trades)


def profit_factor(trades: List[Mapping]) -> float:
    gross_win = sum(float(t.get("pnl", 0.0)) for t in trades if float(t.get("pnl", 0.0)) > 0)
    gross_loss = sum(-float(t.get("pnl", 0.0)) for t in trades if float(t.get("pnl", 0.0)) < 0)
    if gross_loss == 0:
        return float("inf") if gross_win > 0 else 0.0
    return gross_win / gross_loss


def avg_trade(trades: List[Mapping]) -> float:
    if not trades:
        return 0.0
    return float(np.mean([float(t.get("pnl", 0.0)) for t in trades]))


def expectancy(trades: List[Mapping]) -> float:
    """Average return per trade as decimal of capital invested at entry."""
    if not trades:
        return 0.0
    rets = []
    for t in trades:
        notional = float(t.get("entry_price", 0.0)) * float(t.get("shares", 0.0))
        if notional > 0:
            rets.append(float(t.get("pnl", 0.0)) / notional)
    return float(np.mean(rets)) if rets else 0.0


# ---------------------------------------------------------------------------
# New metric helpers
# ---------------------------------------------------------------------------

def calmar_ratio(equity: pd.Series) -> float:
    """CAGR / max_drawdown. Returns 0.0 if drawdown is zero."""
    c = cagr(equity)
    dd = max_drawdown(equity)
    if abs(dd) < 1e-12:
        return 0.0
    return c / dd


def best_trade_pct(trades: List[Mapping]) -> float:
    if not trades:
        return 0.0
    pcts = [float(t.get("return_pct", 0.0)) for t in trades]
    return float(max(pcts)) if pcts else 0.0


def worst_trade_pct(trades: List[Mapping]) -> float:
    if not trades:
        return 0.0
    pcts = [float(t.get("return_pct", 0.0)) for t in trades]
    return float(min(pcts)) if pcts else 0.0


def avg_bars_held(trades: List[Mapping]) -> float:
    if not trades:
        return 0.0
    bars = [float(t.get("bars_held", 0)) for t in trades]
    return float(np.mean(bars)) if bars else 0.0


def _consecutive_streaks(trades: List[Mapping]) -> tuple:
    """Return (max_wins, max_losses, avg_wins, avg_losses) from consecutive streaks."""
    if not trades:
        return 0, 0, 0.0, 0.0

    win_streaks: List[int] = []
    loss_streaks: List[int] = []
    current_streak = 0
    current_is_win = None

    for t in trades:
        is_win = float(t.get("pnl", 0.0)) > 0
        if current_is_win is None:
            current_is_win = is_win
            current_streak = 1
        elif is_win == current_is_win:
            current_streak += 1
        else:
            (win_streaks if current_is_win else loss_streaks).append(current_streak)
            current_is_win = is_win
            current_streak = 1

    if current_streak > 0 and current_is_win is not None:
        (win_streaks if current_is_win else loss_streaks).append(current_streak)

    max_w = max(win_streaks) if win_streaks else 0
    max_l = max(loss_streaks) if loss_streaks else 0
    avg_w = float(np.mean(win_streaks)) if win_streaks else 0.0
    avg_l = float(np.mean(loss_streaks)) if loss_streaks else 0.0
    return max_w, max_l, avg_w, avg_l


def max_consecutive_wins(trades: List[Mapping]) -> int:
    return _consecutive_streaks(trades)[0]


def max_consecutive_losses(trades: List[Mapping]) -> int:
    return _consecutive_streaks(trades)[1]


def avg_consecutive_wins(trades: List[Mapping]) -> float:
    return _consecutive_streaks(trades)[2]


def avg_consecutive_losses(trades: List[Mapping]) -> float:
    return _consecutive_streaks(trades)[3]


# ---------------------------------------------------------------------------
# Monthly returns (for heatmap)
# ---------------------------------------------------------------------------

def monthly_returns(equity: pd.Series) -> List[dict]:
    """Resample equity curve to month-end and return pct change per month.

    Returns a list of ``{"year": int, "month": int, "return_pct": float}``.
    """
    if equity is None or len(equity) < 2:
        return []
    try:
        monthly = equity.resample("ME").last().dropna()
        if monthly.empty:
            return []
        pct = monthly.pct_change().dropna()
        result = []
        for ts, ret in pct.items():
            val = float(ret)
            if math.isnan(val) or math.isinf(val):
                val = 0.0
            result.append({
                "year": int(ts.year),
                "month": int(ts.month),
                "return_pct": round(val, 6),
            })
        return result
    except Exception:
        return []


@dataclass
class MetricSummary:
    total_return: float
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown: float
    volatility: float
    win_rate: float
    profit_factor: float
    avg_trade_pnl: float
    expectancy: float
    num_trades: int
    calmar_ratio: float
    best_trade_pct: float
    worst_trade_pct: float
    avg_bars_held: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_consecutive_wins: float
    avg_consecutive_losses: float

    def as_dict(self) -> dict:
        return {
            "total_return": self.total_return,
            "cagr": self.cagr,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "max_drawdown": self.max_drawdown,
            "volatility": self.volatility,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_trade_pnl": self.avg_trade_pnl,
            "expectancy": self.expectancy,
            "num_trades": self.num_trades,
            "calmar_ratio": self.calmar_ratio,
            "best_trade_pct": self.best_trade_pct,
            "worst_trade_pct": self.worst_trade_pct,
            "avg_bars_held": self.avg_bars_held,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "avg_consecutive_wins": self.avg_consecutive_wins,
            "avg_consecutive_losses": self.avg_consecutive_losses,
        }


def compute_metrics(equity: pd.Series, trades: List[Mapping]) -> MetricSummary:
    rets = daily_returns(equity)
    if equity is None or equity.empty:
        total = 0.0
    else:
        total = float(equity.iloc[-1] / equity.iloc[0] - 1.0)

    streaks = _consecutive_streaks(trades)

    return MetricSummary(
        total_return=total,
        cagr=cagr(equity),
        sharpe=sharpe(rets),
        sortino=sortino(rets),
        max_drawdown=max_drawdown(equity),
        volatility=volatility(rets),
        win_rate=win_rate(trades),
        profit_factor=profit_factor(trades),
        avg_trade_pnl=avg_trade(trades),
        expectancy=expectancy(trades),
        num_trades=len(trades),
        calmar_ratio=calmar_ratio(equity),
        best_trade_pct=best_trade_pct(trades),
        worst_trade_pct=worst_trade_pct(trades),
        avg_bars_held=avg_bars_held(trades),
        max_consecutive_wins=streaks[0],
        max_consecutive_losses=streaks[1],
        avg_consecutive_wins=streaks[2],
        avg_consecutive_losses=streaks[3],
    )
