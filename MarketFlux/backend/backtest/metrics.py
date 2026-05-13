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
        }


def compute_metrics(equity: pd.Series, trades: List[Mapping]) -> MetricSummary:
    rets = daily_returns(equity)
    if equity is None or equity.empty:
        total = 0.0
    else:
        total = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
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
    )
