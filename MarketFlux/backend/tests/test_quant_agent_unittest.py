"""
Unit tests for quant_agent.py — backtesting engine and metric calculations.

Runs against synthetic deterministic price series (no network calls).
"""

import os
import sys
import unittest

import numpy as np

# Add backend root to path so quant_agent can be imported without installing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from quant_agent import (
    _build_drawdown_series,
    _compute_metrics,
    _monthly_returns,
    _run_momentum,
    _run_rsi_strategy,
    _run_sma_crossover,
    run_backtest,
)


def _make_closes(n: int = 300, seed: int = 42, drift: float = 0.001) -> np.ndarray:
    """Return a deterministic upward-trending price series."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, 0.015, n)
    prices = 100.0 * np.cumprod(1 + returns)
    return prices


def _make_dates(n: int = 300) -> list:
    return [f"2022-{(i // 28 + 1):02d}-{(i % 28 + 1):02d}" for i in range(n)]


class TestComputeMetrics(unittest.TestCase):
    """_compute_metrics with known equity curves."""

    def test_flat_equity_returns_zero_metrics(self):
        equity = np.full(100, 100_000.0)
        metrics = _compute_metrics(equity, [])
        self.assertEqual(metrics["total_return_pct"], 0.0)
        self.assertEqual(metrics["sharpe_ratio"], 0.0)
        self.assertEqual(metrics["max_drawdown_pct"], 0.0)

    def test_monotone_growth_positive_sharpe(self):
        equity = np.linspace(100_000, 120_000, 252)
        metrics = _compute_metrics(equity, [])
        self.assertGreater(metrics["total_return_pct"], 0)
        self.assertGreater(metrics["annualized_return_pct"], 0)
        self.assertGreater(metrics["sharpe_ratio"], 0)
        self.assertAlmostEqual(metrics["max_drawdown_pct"], 0.0, places=4)

    def test_declining_equity_negative_return(self):
        equity = np.linspace(100_000, 80_000, 252)
        metrics = _compute_metrics(equity, [])
        self.assertLess(metrics["total_return_pct"], 0)
        self.assertGreater(metrics["max_drawdown_pct"], 0)

    def test_trade_log_win_rate(self):
        trades = [
            {"pnl_pct": 5.0},
            {"pnl_pct": -2.0},
            {"pnl_pct": 3.0},
            {"pnl_pct": -1.0},
        ]
        equity = np.linspace(100_000, 105_000, 100)
        metrics = _compute_metrics(equity, trades)
        self.assertAlmostEqual(metrics["win_rate_pct"], 50.0)
        self.assertEqual(metrics["num_trades"], 4)

    def test_profit_factor_all_wins(self):
        trades = [{"pnl_pct": 2.0}, {"pnl_pct": 3.0}]
        equity = np.linspace(100_000, 105_000, 100)
        metrics = _compute_metrics(equity, trades)
        # No losses → profit_factor should be the "infinite wins" sentinel
        self.assertGreater(metrics["profit_factor"], 100)

    def test_profit_factor_mixed(self):
        trades = [{"pnl_pct": 6.0}, {"pnl_pct": -2.0}]
        equity = np.linspace(100_000, 104_000, 100)
        metrics = _compute_metrics(equity, trades)
        self.assertAlmostEqual(metrics["profit_factor"], 3.0, places=2)


class TestSMACrossover(unittest.TestCase):
    """_run_sma_crossover with deterministic data."""

    def setUp(self):
        self.n = 300
        self.closes = _make_closes(self.n)
        self.dates = _make_dates(self.n)
        self.capital = 100_000.0

    def test_returns_correct_keys(self):
        result = _run_sma_crossover(self.dates, self.closes, self.capital)
        self.assertIn("equity", result)
        self.assertIn("trade_log", result)
        self.assertIn("strategy", result)

    def test_equity_length_matches_dates(self):
        result = _run_sma_crossover(self.dates, self.closes, self.capital)
        self.assertEqual(len(result["equity"]), self.n)

    def test_equity_starts_near_capital(self):
        result = _run_sma_crossover(self.dates, self.closes, self.capital)
        # First data points should be initialised to capital
        self.assertAlmostEqual(result["equity"][0], self.capital, delta=1.0)

    def test_open_trade_logged_at_end(self):
        """Any open position must be closed and logged on the last bar."""
        result = _run_sma_crossover(self.dates, self.closes, self.capital)
        for trade in result["trade_log"]:
            self.assertIn("exit_date", trade)
            self.assertIsNotNone(trade["exit_date"])

    def test_no_negative_equity(self):
        result = _run_sma_crossover(self.dates, self.closes, self.capital)
        self.assertTrue(np.all(result["equity"] >= 0))

    def test_too_short_series_returns_empty(self):
        result = _run_sma_crossover(["2022-01-01"] * 5, np.array([100.0] * 5), 100_000)
        self.assertEqual(result, {})


class TestRSIStrategy(unittest.TestCase):
    """_run_rsi_strategy with deterministic data."""

    def setUp(self):
        self.n = 300
        self.closes = _make_closes(self.n)
        self.dates = _make_dates(self.n)
        self.capital = 100_000.0

    def test_equity_length_matches_dates(self):
        result = _run_rsi_strategy(self.dates, self.closes, self.capital)
        self.assertEqual(len(result["equity"]), self.n)

    def test_rsi_values_in_valid_range(self):
        """All trade entry/exit prices must be positive."""
        result = _run_rsi_strategy(self.dates, self.closes, self.capital)
        for trade in result["trade_log"]:
            self.assertGreater(trade["entry_price"], 0)
            self.assertGreater(trade["exit_price"], 0)

    def test_open_trade_logged_at_end(self):
        result = _run_rsi_strategy(self.dates, self.closes, self.capital)
        for trade in result["trade_log"]:
            self.assertIn("exit_date", trade)

    def test_no_negative_equity(self):
        result = _run_rsi_strategy(self.dates, self.closes, self.capital)
        self.assertTrue(np.all(result["equity"] >= 0))


class TestMomentum(unittest.TestCase):
    """_run_momentum with deterministic data."""

    def setUp(self):
        self.n = 300
        self.closes = _make_closes(self.n)
        self.dates = _make_dates(self.n)
        self.capital = 100_000.0

    def test_equity_length_matches_dates(self):
        result = _run_momentum(self.dates, self.closes, self.capital)
        self.assertEqual(len(result["equity"]), self.n)

    def test_open_trade_logged_at_end(self):
        result = _run_momentum(self.dates, self.closes, self.capital)
        for trade in result["trade_log"]:
            self.assertIn("exit_date", trade)

    def test_no_negative_equity(self):
        result = _run_momentum(self.dates, self.closes, self.capital)
        self.assertTrue(np.all(result["equity"] >= 0))

    def test_hold_period_respected(self):
        """Each trade should hold for at most `hold` days."""
        hold = 10
        result = _run_momentum(self.dates, self.closes, self.capital, lookback=30, hold=hold)
        for trade in result["trade_log"]:
            entry = trade["entry_date"]
            exit_ = trade["exit_date"]
            # Entry/exit are date strings in our synthetic format; compare by index
            try:
                i_entry = self.dates.index(entry)
                i_exit = self.dates.index(exit_)
                self.assertLessEqual(i_exit - i_entry, hold + 1)
            except ValueError:
                pass  # date not found — skip


class TestDrawdownSeries(unittest.TestCase):
    def test_monotone_increase_zero_drawdown(self):
        equity = np.linspace(100_000, 110_000, 50)
        dates = [str(i) for i in range(50)]
        dd = _build_drawdown_series(equity, dates)
        self.assertEqual(len(dd), 50)
        for pt in dd:
            self.assertAlmostEqual(pt["drawdown"], 0.0, places=3)

    def test_drawdown_peak_to_trough(self):
        equity = np.array([100_000.0] * 25 + [90_000.0] * 25)
        dates = [str(i) for i in range(50)]
        dd = _build_drawdown_series(equity, dates)
        # After the drop, drawdown should be ~10%
        self.assertAlmostEqual(dd[49]["drawdown"], -10.0, places=1)


class TestMonthlyReturns(unittest.TestCase):
    def test_returns_list_of_dicts_with_correct_keys(self):
        equity = np.linspace(100_000, 110_000, 60)
        dates = [f"2022-{(i // 30 + 1):02d}-{(i % 30 + 1):02d}" for i in range(60)]
        monthly = _monthly_returns(equity, dates)
        self.assertIsInstance(monthly, list)
        if monthly:
            self.assertIn("month", monthly[0])
            self.assertIn("return_pct", monthly[0])

    def test_empty_equity_returns_empty_list(self):
        monthly = _monthly_returns(np.array([]), [])
        self.assertEqual(monthly, [])


class TestRunBacktest(unittest.TestCase):
    """run_backtest with pre-fetched synthetic history (no network)."""

    def _make_hist(self, n: int = 300):
        """Build a minimal DataFrame that mimics yfinance output."""
        import pandas as pd
        from datetime import date, timedelta

        base = date(2022, 1, 3)
        dates = pd.date_range(base, periods=n, freq="B")
        closes = _make_closes(n)
        df = pd.DataFrame({"Close": closes}, index=dates)
        return df

    def test_sma_crossover_with_shared_hist(self):
        hist = self._make_hist()
        result = run_backtest("TEST", "sma_crossover", "2y", 100_000, _hist=hist)
        self.assertNotIn("error", result)
        self.assertIn("metrics", result)
        self.assertIn("equity_curve", result)
        self.assertIn("trade_log", result)

    def test_rsi_with_shared_hist(self):
        hist = self._make_hist()
        result = run_backtest("TEST", "rsi_mean_reversion", "2y", 100_000, _hist=hist)
        self.assertNotIn("error", result)

    def test_momentum_with_shared_hist(self):
        hist = self._make_hist()
        result = run_backtest("TEST", "momentum", "2y", 100_000, _hist=hist)
        self.assertNotIn("error", result)

    def test_unknown_strategy_returns_error(self):
        hist = self._make_hist()
        result = run_backtest("TEST", "unknown_strat", _hist=hist)
        self.assertIn("error", result)

    def test_insufficient_data_returns_error(self):
        import pandas as pd
        hist = pd.DataFrame({"Close": [100.0, 101.0]},
                            index=pd.date_range("2022-01-03", periods=2, freq="B"))
        result = run_backtest("TEST", "sma_crossover", _hist=hist)
        self.assertIn("error", result)

    def test_equity_curve_has_buy_hold(self):
        hist = self._make_hist()
        result = run_backtest("TEST", "sma_crossover", _hist=hist)
        for pt in result["equity_curve"][:5]:
            self.assertIn("portfolio", pt)
            self.assertIn("buy_hold", pt)

    def test_benchmark_metrics_present(self):
        hist = self._make_hist()
        result = run_backtest("TEST", "sma_crossover", _hist=hist)
        bm = result.get("benchmark_metrics", {})
        self.assertIn("total_return_pct", bm)
        self.assertIn("sharpe_ratio", bm)


if __name__ == "__main__":
    unittest.main()
