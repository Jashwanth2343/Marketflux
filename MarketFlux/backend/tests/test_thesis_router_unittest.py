import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vnext.thesis_router import build_thesis_router


async def fake_current_user(_request):
    return {"user_id": "user-123", "email": "tester@example.com"}


class ThesisRouterTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(build_thesis_router(object(), fake_current_user), prefix="/api/vnext")
        self.client = TestClient(app)

    @patch("vnext.thesis_router.list_theses", new_callable=AsyncMock)
    def test_lists_theses_for_authenticated_user(self, mock_list_theses):
        mock_list_theses.return_value = [
            {
                "id": "thesis-1",
                "ticker": "NVDA",
                "claim": "AI demand stays elevated.",
                "status": "active",
            }
        ]

        response = self.client.get("/api/vnext/theses")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["ticker"], "NVDA")
        mock_list_theses.assert_awaited_once_with("user-123")

    @patch("vnext.thesis_router.create_paper_trade", new_callable=AsyncMock)
    @patch("vnext.thesis_router.evaluate_paper_trade")
    @patch("vnext.thesis_router.get_next_earnings_event", new_callable=AsyncMock)
    @patch("vnext.thesis_router.get_portfolio_holdings", new_callable=AsyncMock)
    @patch("vnext.thesis_router.list_open_paper_trades", new_callable=AsyncMock)
    @patch("vnext.thesis_router.get_policies", new_callable=AsyncMock)
    @patch("vnext.thesis_router.get_stock_info", new_callable=AsyncMock)
    @patch("vnext.thesis_router.get_workspace", new_callable=AsyncMock)
    def test_blocks_paper_trade_when_policy_engine_rejects(
        self,
        mock_workspace,
        mock_stock_info,
        mock_get_policies,
        mock_list_open_trades,
        mock_holdings,
        mock_earnings,
        mock_evaluate_trade,
        mock_create_trade,
    ):
        mock_workspace.return_value = {
            "thesis": {"id": "thesis-1", "ticker": "NVDA", "claim": "Demand remains strong."},
            "latest_revision": {"id": "revision-1", "version": 2},
            "evidence_blocks": [{"confidence": 42}],
            "paper_trades": [],
        }
        mock_stock_info.return_value = {"price": 100}
        mock_get_policies.return_value = {"items": [], "effective": {}}
        mock_list_open_trades.return_value = []
        mock_holdings.return_value = []
        mock_earnings.return_value = None
        mock_evaluate_trade.return_value = {
            "allowed": False,
            "violations": [{"rule_type": "min_confidence_to_trade", "message": "Evidence confidence is below threshold."}],
            "warnings": [],
        }

        response = self.client.post(
            "/api/vnext/theses/thesis-1/paper-trades",
            json={"side": "buy", "size": 5},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("policy_result", response.json()["detail"])
        mock_create_trade.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
