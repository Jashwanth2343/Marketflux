import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vnext.policy_engine import evaluate_paper_trade


class PolicyEngineTests(unittest.TestCase):
    def setUp(self):
        self.base_policies = {
            "max_position_pct": {"enabled": True, "params": {"value": 20}},
            "max_gross_exposure_pct": {"enabled": True, "params": {"value": 100}},
            "max_single_name_concentration": {"enabled": True, "params": {"value": 25}},
            "max_open_trades": {"enabled": True, "params": {"value": 10}},
            "min_confidence_to_trade": {"enabled": True, "params": {"value": 60}},
            "block_during_earnings_window": {"enabled": False, "params": {"days_before": 2, "days_after": 1}},
            "no_live_trading": {"enabled": True, "params": {"value": True}},
        }

    def test_allows_trade_when_rules_pass(self):
        result = evaluate_paper_trade(
            ticker="NVDA",
            proposed_side="buy",
            proposed_size=10,
            current_price=100.0,
            effective_policies=self.base_policies,
            open_trades=[],
            evidence_blocks=[{"confidence": 80}],
            portfolio_holdings=[],
            earnings_event=None,
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["violations"], [])

    def test_blocks_trade_when_position_size_too_large(self):
        result = evaluate_paper_trade(
            ticker="NVDA",
            proposed_side="buy",
            proposed_size=300,
            current_price=100.0,
            effective_policies=self.base_policies,
            open_trades=[],
            evidence_blocks=[{"confidence": 88}],
            portfolio_holdings=[],
            earnings_event=None,
        )

        self.assertFalse(result["allowed"])
        self.assertTrue(any(item["rule_type"] == "max_position_pct" for item in result["violations"]))

    def test_blocks_trade_during_earnings_window(self):
        policies = dict(self.base_policies)
        policies["block_during_earnings_window"] = {
            "enabled": True,
            "params": {"days_before": 2, "days_after": 1},
        }

        result = evaluate_paper_trade(
            ticker="AAPL",
            proposed_side="buy",
            proposed_size=5,
            current_price=100.0,
            effective_policies=policies,
            open_trades=[],
            evidence_blocks=[{"confidence": 90}],
            portfolio_holdings=[],
            earnings_event={"date": (date.today() + timedelta(days=1)).isoformat()},
        )

        self.assertFalse(result["allowed"])
        self.assertTrue(any(item["rule_type"] == "block_during_earnings_window" for item in result["violations"]))


if __name__ == "__main__":
    unittest.main()
