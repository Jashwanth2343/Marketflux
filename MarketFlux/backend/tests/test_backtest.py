"""Unit tests for the backtester.

Tests use deterministic synthetic OHLCV via SyntheticPriceConfig so they don't
hit yfinance and run in well under a second.
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from typing import Dict

import numpy as np
import pandas as pd

# Allow `python -m unittest backend/tests/test_backtest.py` from any cwd.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backtest.costs import CostModel, DEFAULT_COSTS
from backtest.data import SyntheticPriceConfig
from backtest.dsl import Strategy, evaluate, validate_strategy, TradeState
from backtest.indicators import attach_indicators
from backtest.metrics import compute_metrics, max_drawdown, sharpe
from backtest.runner import generate_walk_forward_windows, run_backtest, run_walk_forward
from backtest.engine import run_engine


# ---------------------------------------------------------------------------
# DSL validation + evaluation
# ---------------------------------------------------------------------------

class DSLValidationTests(unittest.TestCase):
    def test_valid_minimal_strategy(self):
        strat = {
            "universe": ["AAPL"],
            "entry": {"lt": ["close", 100]},
            "exit": {"gt": ["close", 200]},
        }
        validate_strategy(strat)
        s = Strategy.from_dict(strat)
        self.assertEqual(s.universe, ["AAPL"])

    def test_missing_universe_raises(self):
        with self.assertRaisesRegex(ValueError, "universe"):
            validate_strategy({"entry": {"lt": ["close", 1]}, "exit": {"gt": ["close", 2]}})

    def test_unknown_operator(self):
        with self.assertRaisesRegex(ValueError, "unknown operator"):
            validate_strategy(
                {
                    "universe": ["A"],
                    "entry": {"banana": ["close", 1]},
                    "exit": {"gt": ["close", 2]},
                }
            )

    def test_trade_predicate_rejected_in_entry(self):
        with self.assertRaisesRegex(ValueError, "trade-state"):
            validate_strategy(
                {
                    "universe": ["A"],
                    "entry": {"hold_days_gte": 5},
                    "exit": {"gt": ["close", 2]},
                }
            )


class DSLEvaluationTests(unittest.TestCase):
    def test_basic_comparators(self):
        row = {"close": 50, "rsi": 25}
        self.assertTrue(evaluate({"lt": ["rsi", 30]}, row))
        self.assertFalse(evaluate({"gt": ["rsi", 30]}, row))
        self.assertTrue(evaluate({"lte": ["rsi", 25]}, row))
        self.assertTrue(evaluate({"all": [{"lt": ["rsi", 30]}, {"gt": ["close", 10]}]}, row))
        self.assertTrue(evaluate({"any": [{"lt": ["close", 10]}, {"lt": ["rsi", 30]}]}, row))
        self.assertTrue(evaluate({"not": {"gt": ["rsi", 30]}}, row))

    def test_nan_short_circuits_to_false(self):
        row = {"close": float("nan"), "sma200": 100}
        self.assertFalse(evaluate({"gt": ["close", "sma200"]}, row))
        self.assertFalse(evaluate({"lt": ["close", "sma200"]}, row))

    def test_crosses_above(self):
        prev = {"a": 9, "b": 10}
        cur = {"a": 11, "b": 10}
        self.assertTrue(evaluate({"crosses_above": ["a", "b"]}, cur, prev))
        self.assertFalse(evaluate({"crosses_above": ["a", "b"]}, prev, prev))

    def test_trade_state_predicates(self):
        row = {"close": 100}
        ts = TradeState(hold_days=15, unrealized_return=-0.10)
        self.assertTrue(evaluate({"hold_days_gte": 10}, row, trade=ts))
        self.assertFalse(evaluate({"hold_days_gte": 20}, row, trade=ts))
        self.assertTrue(evaluate({"loss_pct_gte": 0.08}, row, trade=ts))
        self.assertFalse(evaluate({"profit_pct_gte": 0.05}, row, trade=ts))


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

class IndicatorTests(unittest.TestCase):
    def setUp(self):
        cfg = SyntheticPriceConfig(start="2022-01-03", periods=300, drift=0.0005, seed=42)
        self.df = cfg.build("X")

    def test_rsi_bounded_0_100(self):
        enriched = attach_indicators(self.df, {"rsi14": {"type": "rsi", "period": 14}})
        rsi_vals = enriched["rsi14"].dropna()
        self.assertGreaterEqual(rsi_vals.min(), 0.0)
        self.assertLessEqual(rsi_vals.max(), 100.0)

    def test_sma_matches_pandas(self):
        enriched = attach_indicators(self.df, {"sma20": {"type": "sma", "period": 20}})
        expected = self.df["close"].rolling(20).mean()
        pd.testing.assert_series_equal(
            enriched["sma20"].dropna(), expected.dropna(), check_names=False
        )

    def test_unknown_indicator_raises(self):
        with self.assertRaisesRegex(ValueError, "unknown indicator"):
            attach_indicators(self.df, {"x": {"type": "wat"}})


# ---------------------------------------------------------------------------
# Cost model
# ---------------------------------------------------------------------------

class CostModelTests(unittest.TestCase):
    def test_slippage_widens_against_trader(self):
        cm = CostModel(slippage_bps=10)  # 10 bps = 0.10%
        self.assertAlmostEqual(cm.fill_price(100.0, "buy"), 100.10)
        self.assertAlmostEqual(cm.fill_price(100.0, "sell"), 99.90)

    def test_commission_min_floor(self):
        cm = CostModel(commission_per_share=0.005, commission_min=1.0)
        self.assertEqual(cm.commission(10, 50.0), 1.0)  # 10 * 0.005 = 0.05 → floored at 1.0

    def test_commission_pct(self):
        cm = CostModel(commission_pct=0.001)  # 10 bps
        self.assertAlmostEqual(cm.commission(100, 50.0), 100 * 50.0 * 0.001)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class MetricsTests(unittest.TestCase):
    def test_max_drawdown_simple(self):
        idx = pd.date_range("2024-01-01", periods=5, freq="D")
        eq = pd.Series([100, 120, 80, 90, 110], index=idx, dtype=float)
        # max equity = 120, lowest after = 80 → drawdown = (80-120)/120 = -1/3
        self.assertAlmostEqual(max_drawdown(eq), 1 / 3, places=5)

    def test_sharpe_zero_for_constant(self):
        idx = pd.date_range("2024-01-01", periods=50, freq="B")
        eq = pd.Series([100.0] * 50, index=idx)
        rets = eq.pct_change().dropna()
        self.assertEqual(sharpe(rets), 0.0)

    def test_compute_metrics_no_trades(self):
        idx = pd.date_range("2024-01-01", periods=10, freq="B")
        eq = pd.Series(np.linspace(100, 110, 10), index=idx)
        m = compute_metrics(eq, [])
        self.assertAlmostEqual(m.total_return, 0.10, places=6)
        self.assertEqual(m.num_trades, 0)
        self.assertEqual(m.win_rate, 0.0)


# ---------------------------------------------------------------------------
# Engine integration tests
# ---------------------------------------------------------------------------

def _trending_data(symbol: str = "X", periods: int = 250, drift: float = 0.001, seed: int = 7) -> Dict[str, pd.DataFrame]:
    cfg = SyntheticPriceConfig(start="2023-01-02", periods=periods, drift=drift, seed=seed)
    return {symbol: cfg.build(symbol)}


class EngineTests(unittest.TestCase):
    def test_buy_and_hold_recovers_total_return(self):
        # Always-true entry, never-true exit — should buy first bar, hold until end.
        data = _trending_data(periods=120, drift=0.002, seed=1)
        strategy = {
            "name": "always-on",
            "universe": ["X"],
            "indicators": {},
            "entry": {"gt": ["close", 0]},
            "exit": {"lt": ["close", 0]},
            "position_sizing": {"type": "fixed_pct", "pct": 1.0},
            "max_positions": 1,
        }
        # Zero costs so we can compare exactly to price return.
        zero = CostModel(commission_per_share=0, commission_min=0, commission_pct=0, slippage_bps=0)
        result = run_engine(Strategy.from_dict(strategy), data=data, initial_capital=100_000, costs=zero)
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        df = data["X"]
        # Entry signal fires on bar 0; fills at bar 1 open. Force-close at last close.
        expected_entry = df["open"].iloc[1]
        expected_exit = df["close"].iloc[-1]
        self.assertAlmostEqual(trade.entry_price, expected_entry, places=4)
        self.assertAlmostEqual(trade.exit_price, expected_exit, places=4)

    def test_costs_reduce_pnl(self):
        data = _trending_data(periods=120, drift=0.002, seed=1)
        strategy = {
            "name": "always-on",
            "universe": ["X"],
            "entry": {"gt": ["close", 0]},
            "exit": {"lt": ["close", 0]},
            "position_sizing": {"type": "fixed_pct", "pct": 1.0},
            "max_positions": 1,
        }
        zero = CostModel(commission_per_share=0, commission_min=0, commission_pct=0, slippage_bps=0)
        loaded = CostModel(commission_per_share=0, commission_min=0, commission_pct=0.001, slippage_bps=10)
        r_zero = run_engine(Strategy.from_dict(strategy), data=data, initial_capital=100_000, costs=zero)
        r_loaded = run_engine(Strategy.from_dict(strategy), data=data, initial_capital=100_000, costs=loaded)
        self.assertGreater(r_zero.final_equity, r_loaded.final_equity)

    def test_stop_loss_triggers_before_signal_exit(self):
        # Build a price path that drops 15% sharply then recovers.
        idx = pd.bdate_range("2024-01-02", periods=20)
        closes = [100, 100, 95, 90, 85, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150]
        df = pd.DataFrame(
            {
                "open": closes,
                "high": [c * 1.005 for c in closes],
                "low": [c * 0.995 for c in closes],
                "close": closes,
                "volume": [1_000_000] * len(closes),
            },
            index=idx,
            dtype=float,
        )
        data = {"X": df}
        strategy = {
            "name": "stop-loss-test",
            "universe": ["X"],
            "entry": {"gt": ["close", 0]},
            "exit": {"lt": ["close", 0]},  # never true on its own
            "position_sizing": {"type": "fixed_pct", "pct": 1.0},
            "max_positions": 1,
            "stop_loss_pct": 0.10,  # 10% drawdown -> stop
        }
        zero = CostModel(commission_per_share=0, commission_min=0, commission_pct=0, slippage_bps=0)
        result = run_engine(Strategy.from_dict(strategy), data=data, initial_capital=10_000, costs=zero)
        self.assertGreaterEqual(len(result.trades), 1)
        first = result.trades[0]
        self.assertEqual(first.exit_reason, "stop_loss")

    def test_max_positions_enforced(self):
        # 3 symbols all triggering entry, max_positions=2 → only 2 simultaneous trades.
        data = {}
        for sym in ["A", "B", "C"]:
            data[sym] = SyntheticPriceConfig(start="2023-01-02", periods=60, drift=0.001, seed=hash(sym) % 1000).build(sym)
        strategy = {
            "name": "cap-test",
            "universe": ["A", "B", "C"],
            "entry": {"gt": ["close", 0]},
            "exit": {"lt": ["close", 0]},
            "position_sizing": {"type": "fixed_pct", "pct": 0.4},
            "max_positions": 2,
        }
        result = run_engine(Strategy.from_dict(strategy), data=data, initial_capital=100_000)
        # Only 2 force-closes at the end → 2 trades, all from the cap.
        self.assertEqual(len(result.trades), 2)


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------

class WalkForwardTests(unittest.TestCase):
    def test_window_generation_default(self):
        windows = generate_walk_forward_windows("2020-01-01", "2024-01-01", train_months=24, test_months=12)
        self.assertGreaterEqual(len(windows), 2)
        for w in windows:
            self.assertLess(w.train_start, w.train_end)
            self.assertLess(w.test_start, w.test_end)
            self.assertEqual(w.train_end, w.test_start)

    def test_window_truncates_to_end(self):
        windows = generate_walk_forward_windows("2020-01-01", "2023-06-01", train_months=24, test_months=12)
        self.assertTrue(any(w.test_end <= "2023-06-01" for w in windows))

    def test_run_walk_forward_returns_folds(self):
        # Build 4 years of synthetic data so we get at least one fold.
        sym_data = {
            "X": SyntheticPriceConfig(start="2020-01-02", periods=252 * 4, drift=0.0005, seed=11).build("X")
        }
        strategy = {
            "name": "wf-smoke",
            "universe": ["X"],
            "entry": {"gt": ["close", 0]},
            "exit": {"lt": ["close", 0]},
            "position_sizing": {"type": "fixed_pct", "pct": 1.0},
            "max_positions": 1,
        }
        out = run_walk_forward(
            strategy,
            start="2020-01-02",
            end="2024-01-02",
            train_months=24,
            test_months=12,
            initial_capital=10_000,
            data=sym_data,
        )
        self.assertIn("folds", out)
        self.assertGreaterEqual(len(out["folds"]), 1)
        self.assertIn("aggregate_oos", out)
        self.assertIn("equity_curve", out["aggregate_oos"])


# ---------------------------------------------------------------------------
# run_backtest end-to-end (no network)
# ---------------------------------------------------------------------------

class RunBacktestTests(unittest.TestCase):
    def test_run_backtest_with_injected_data(self):
        data = _trending_data(periods=200, drift=0.001, seed=3)
        strategy = {
            "name": "rsi-mean-reversion",
            "universe": ["X"],
            "indicators": {
                "rsi14": {"type": "rsi", "period": 14},
                "sma50": {"type": "sma", "period": 50},
            },
            "entry": {"all": [{"lt": ["rsi14", 35]}, {"gt": ["close", "sma50"]}]},
            "exit": {"any": [{"gt": ["rsi14", 60]}, {"hold_days_gte": 15}]},
            "position_sizing": {"type": "fixed_pct", "pct": 0.5},
            "max_positions": 1,
        }
        result = run_backtest(strategy, "2023-01-02", "2024-01-02", initial_capital=10_000, data=data)
        as_dict = result.as_dict()
        self.assertIn("metrics", as_dict)
        self.assertIn("equity_curve", as_dict)
        self.assertIn("trades", as_dict)
        # Equity must be finite and non-zero.
        self.assertGreater(as_dict["final_equity"], 0)
        self.assertTrue(math.isfinite(as_dict["final_equity"]))


if __name__ == "__main__":
    unittest.main()
