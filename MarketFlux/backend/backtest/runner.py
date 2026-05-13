"""High-level entry points: ``run_backtest`` and ``run_walk_forward``.

These wrap the engine with data loading, walk-forward window generation, and
result serialization so callers (HTTP layer, scripts, agents) can stay light.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Mapping, Optional

import pandas as pd

from .costs import CostModel, cost_model_from_dict, DEFAULT_COSTS
from .data import load_universe
from .dsl import Strategy
from .engine import BacktestResult, run_engine
from .metrics import compute_metrics


def _parse_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value)


def run_backtest(
    strategy: Mapping,
    start: str,
    end: str,
    initial_capital: float = 100_000.0,
    costs: Optional[Mapping] = None,
    data: Optional[Dict[str, pd.DataFrame]] = None,
) -> BacktestResult:
    """Load data and run a single in-sample backtest.

    Pass `data` to bypass yfinance entirely (useful for tests / replays).
    """
    strat = Strategy.from_dict(strategy)
    cost_model = cost_model_from_dict(costs) if costs is not None else DEFAULT_COSTS
    if data is None:
        data = load_universe(strat.universe, _parse_date(start), _parse_date(end))
    return run_engine(strat, data=data, initial_capital=initial_capital, costs=cost_model)


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------

@dataclass
class WalkForwardWindow:
    train_start: str
    train_end: str
    test_start: str
    test_end: str

    def as_dict(self) -> dict:
        return asdict(self)


def generate_walk_forward_windows(
    start: str,
    end: str,
    train_months: int = 36,
    test_months: int = 12,
    step_months: Optional[int] = None,
) -> List[WalkForwardWindow]:
    """Anchored, non-overlapping (in test) walk-forward windows.

    Default = 3y train, 1y test, advance by 1y. The last window may have a
    shorter test segment if the requested ``end`` falls in the middle.
    """
    step_months = step_months or test_months
    start_dt = pd.Timestamp(start)
    end_dt = pd.Timestamp(end)
    if end_dt <= start_dt:
        return []

    windows: List[WalkForwardWindow] = []
    cursor = start_dt
    while True:
        train_end = cursor + pd.DateOffset(months=train_months)
        test_end = train_end + pd.DateOffset(months=test_months)
        if train_end >= end_dt:
            break
        if test_end > end_dt:
            test_end = end_dt
        windows.append(
            WalkForwardWindow(
                train_start=cursor.strftime("%Y-%m-%d"),
                train_end=train_end.strftime("%Y-%m-%d"),
                test_start=train_end.strftime("%Y-%m-%d"),
                test_end=test_end.strftime("%Y-%m-%d"),
            )
        )
        if test_end >= end_dt:
            break
        cursor = cursor + pd.DateOffset(months=step_months)
    return windows


def run_walk_forward(
    strategy: Mapping,
    start: str,
    end: str,
    train_months: int = 36,
    test_months: int = 12,
    step_months: Optional[int] = None,
    initial_capital: float = 100_000.0,
    costs: Optional[Mapping] = None,
    data: Optional[Dict[str, pd.DataFrame]] = None,
) -> dict:
    """Run a walk-forward analysis.

    For each window we run an in-sample backtest (train) and an out-of-sample
    backtest (test) with the same parameters. The DSL is static today, so
    "training" is just running the rules over the in-sample window — useful
    for sanity-checking performance decay between regimes. When the strategy
    becomes parameterized, the train segment is where the optimizer would run.
    """
    strat = Strategy.from_dict(strategy)
    cost_model = cost_model_from_dict(costs) if costs is not None else DEFAULT_COSTS
    if data is None:
        data = load_universe(strat.universe, _parse_date(start), _parse_date(end))

    windows = generate_walk_forward_windows(start, end, train_months, test_months, step_months)
    fold_results = []
    oos_equity_segments: List[pd.Series] = []
    oos_trades: List[dict] = []

    for w in windows:
        train_data = _slice_window(data, w.train_start, w.train_end)
        test_data = _slice_window(data, w.test_start, w.test_end)

        train_result = run_engine(strat, data=train_data, initial_capital=initial_capital, costs=cost_model)
        test_result = run_engine(strat, data=test_data, initial_capital=initial_capital, costs=cost_model)

        train_metrics = compute_metrics(train_result.equity_curve, [t.as_dict() for t in train_result.trades])
        test_metrics = compute_metrics(test_result.equity_curve, [t.as_dict() for t in test_result.trades])

        fold_results.append(
            {
                "window": w.as_dict(),
                "train": {
                    "metrics": train_metrics.as_dict(),
                    "num_trades": len(train_result.trades),
                },
                "test": {
                    "metrics": test_metrics.as_dict(),
                    "num_trades": len(test_result.trades),
                    "trades": [t.as_dict() for t in test_result.trades],
                },
            }
        )

        if not test_result.equity_curve.empty:
            oos_equity_segments.append(test_result.equity_curve)
        for t in test_result.trades:
            oos_trades.append(t.as_dict())

    aggregate_metrics = _stitch_oos_metrics(oos_equity_segments, oos_trades, initial_capital)

    return {
        "strategy_name": strat.name,
        "windows": [w.as_dict() for w in windows],
        "folds": fold_results,
        "aggregate_oos": aggregate_metrics,
    }


def _slice_window(
    data: Dict[str, pd.DataFrame],
    start: str,
    end: str,
) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    for sym, df in data.items():
        sliced = df.loc[(df.index >= start_ts) & (df.index < end_ts)]
        if not sliced.empty:
            out[sym] = sliced
    return out


def _stitch_oos_metrics(
    segments: List[pd.Series], trades: List[dict], initial_capital: float
) -> dict:
    """Chain per-fold equity curves into one continuous OOS curve."""
    if not segments:
        empty = pd.Series(dtype=float)
        metrics = compute_metrics(empty, trades)
        return {
            "metrics": metrics.as_dict(),
            "equity_curve": [],
            "num_trades": len(trades),
        }
    stitched_values: List[float] = []
    stitched_index: List[pd.Timestamp] = []
    running = initial_capital
    for seg in segments:
        if seg.empty:
            continue
        seg_returns = seg.pct_change().fillna(seg.iloc[0] / initial_capital - 1.0)
        for ts, ret in seg_returns.items():
            running = running * (1.0 + float(ret))
            stitched_values.append(running)
            stitched_index.append(ts)
    stitched = pd.Series(stitched_values, index=stitched_index, dtype=float).sort_index()
    metrics = compute_metrics(stitched, trades)
    return {
        "metrics": metrics.as_dict(),
        "equity_curve": [
            {"date": idx.isoformat(), "equity": float(val)}
            for idx, val in stitched.items()
        ],
        "num_trades": len(trades),
    }
