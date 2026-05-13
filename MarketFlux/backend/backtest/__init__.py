"""MarketFlux backtesting engine.

Strategy DSL + bar-by-bar simulator with transaction costs, walk-forward harness,
and institutional-grade metrics. Designed to be the foundation of the
backtest -> execute -> learn loop.
"""

from .runner import run_backtest, run_walk_forward
from .dsl import Strategy, validate_strategy
from .metrics import compute_metrics

__all__ = [
    "run_backtest",
    "run_walk_forward",
    "Strategy",
    "validate_strategy",
    "compute_metrics",
]
