"""Hardening tests: kill switch, compliance chokepoint (fail-closed), rate limiter.

Run: ./venv/bin/python -m pytest tests/test_hardening.py -v
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi import HTTPException

import trading_halt
import copilot_trading_tools as trading
from vnext import alpaca_client


@pytest.fixture(autouse=True)
def _reset_halt():
    """Kill switch starts released for every test; env override scrubbed."""
    trading_halt.set_trading_halted(False)
    old = os.environ.pop("TRADING_HALTED", None)
    yield
    trading_halt.set_trading_halted(False)
    if old is not None:
        os.environ["TRADING_HALTED"] = old


class TestKillSwitch:
    def test_halt_blocks_place_order(self):
        trading_halt.set_trading_halted(True)
        assert trading_halt.is_trading_halted() is True
        result = trading.place_order("AAPL", 1, "buy")
        assert result["ok"] is False
        assert "halted" in result["error"].lower()

    def test_released_allows_validation_to_proceed(self, monkeypatch):
        # With the halt released and no broker configured, place_order must
        # get PAST the halt check and fail on the (mocked) broker check.
        monkeypatch.setattr(alpaca_client, "is_alpaca_configured", lambda: False)
        result = trading.place_order("AAPL", 1, "buy")
        assert result["ok"] is False
        assert "halted" not in result["error"].lower()
        assert "not configured" in result["error"].lower()

    def test_env_var_halts(self, monkeypatch):
        monkeypatch.setenv("TRADING_HALTED", "1")
        assert trading_halt.is_trading_halted() is True

    def test_env_var_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("TRADING_HALTED", "TrUe")
        assert trading_halt.is_trading_halted() is True

    def test_status_shape(self):
        status = trading_halt.halt_status()
        assert set(status) == {"halted", "runtime_halted", "env_halted", "env_var"}
        assert status["halted"] is False


class TestComplianceChokepoint:
    """The mandatory gate inside place_order must BLOCK and must fail closed."""

    def _mock_broker(self, monkeypatch, buying_power="100"):
        monkeypatch.setattr(alpaca_client, "is_alpaca_configured", lambda: True)
        monkeypatch.setattr(
            alpaca_client,
            "get_account",
            lambda: {"equity": "100000", "cash": "50000", "buying_power": buying_power},
        )
        monkeypatch.setattr(alpaca_client, "get_positions", lambda: [])
        monkeypatch.setattr(trading, "_estimate_price", lambda symbol: 150.0)

    def test_block_stops_order(self, monkeypatch):
        # $15,000 notional vs $100 buying power -> buying_power BLOCK.
        self._mock_broker(monkeypatch, buying_power="100")

        def _must_not_submit(**kwargs):
            raise AssertionError("submit_market_order must not be called on BLOCK")

        monkeypatch.setattr(alpaca_client, "submit_market_order", _must_not_submit)
        result = trading.place_order("AAPL", 100, "buy")
        assert result["ok"] is False
        assert result.get("blocked_by_compliance") is True
        assert result.get("decision") == "BLOCK"

    def test_fail_closed_on_compliance_error(self, monkeypatch):
        # If the compliance check itself throws, the order must NOT proceed.
        self._mock_broker(monkeypatch, buying_power="100000")
        monkeypatch.setattr(
            alpaca_client, "get_account", lambda: (_ for _ in ()).throw(RuntimeError("broker down"))
        )

        def _must_not_submit(**kwargs):
            raise AssertionError("submit_market_order must not be called when the gate errors")

        monkeypatch.setattr(alpaca_client, "submit_market_order", _must_not_submit)
        result = trading.place_order("AAPL", 1, "buy")
        assert result["ok"] is False
        assert result.get("blocked_by_compliance") is True

    def test_passing_order_reaches_broker(self, monkeypatch):
        # Healthy account: gate passes, order goes to the broker.
        self._mock_broker(monkeypatch, buying_power="100000")
        monkeypatch.setattr(
            alpaca_client,
            "submit_market_order",
            lambda **kwargs: {"order_id": "ord-123", "symbol": "AAPL", "side": "buy",
                              "qty": 1, "type": "market", "status": "accepted",
                              "filled_avg_price": 150.0, "submitted_at": "now"},
        )
        result = trading.place_order("AAPL", 1, "buy")
        assert result["ok"] is True
        assert result["order_id"] == "ord-123"


class TestRateLimiter:
    def _fresh(self, monkeypatch, per_minute="2"):
        import copilot_router
        monkeypatch.setenv("COPILOT_CHAT_PER_MINUTE", per_minute)
        monkeypatch.delenv("REDIS_URL", raising=False)
        copilot_router._chat_buckets.clear()
        # Force in-memory path even if a previous test cached a Redis client.
        monkeypatch.setattr(copilot_router, "_rl_redis_failed", True)
        return copilot_router

    def test_allows_up_to_limit(self, monkeypatch):
        router = self._fresh(monkeypatch, "2")
        router.check_copilot_chat_rate_limit("u1")
        router.check_copilot_chat_rate_limit("u1")  # no raise

    def test_blocks_over_limit_with_retry_after(self, monkeypatch):
        import copilot_router
        router = self._fresh(monkeypatch, "2")
        router.check_copilot_chat_rate_limit("u1")
        router.check_copilot_chat_rate_limit("u1")
        with pytest.raises(HTTPException) as excinfo:
            router.check_copilot_chat_rate_limit("u1")
        assert excinfo.value.status_code == 429
        assert "Retry-After" in (excinfo.value.headers or {})

    def test_per_user_buckets(self, monkeypatch):
        router = self._fresh(monkeypatch, "1")
        router.check_copilot_chat_rate_limit("alice")
        router.check_copilot_chat_rate_limit("bob")  # different user: no raise

    def test_zero_disables(self, monkeypatch):
        router = self._fresh(monkeypatch, "0")
        for _ in range(10):
            router.check_copilot_chat_rate_limit("u1")  # no raise


class TestAdminHaltAuth:
    """The kill-switch admin endpoints must fail closed without ADMIN_TOKEN."""

    def _server(self, monkeypatch):
        # server.py hard-requires MONGO_URL/DB_NAME at import.
        monkeypatch.setenv("MONGO_URL", "mongodb://127.0.0.1:27017")
        monkeypatch.setenv("DB_NAME", "test")
        import server

        return server

    def test_toggle_503_without_admin_token(self, monkeypatch):
        server = self._server(monkeypatch)
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)
        import asyncio

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                server.admin_trading_halt(
                    server.TradingHaltRequest(halted=True), x_admin_token=None
                )
            )
        assert excinfo.value.status_code == 503

    def test_status_503_without_admin_token(self, monkeypatch):
        server = self._server(monkeypatch)
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
        monkeypatch.delenv("NODE_ENV", raising=False)
        import asyncio

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(server.admin_trading_halt_status(x_admin_token=None))
        assert excinfo.value.status_code == 503

    def test_toggle_401_with_wrong_token(self, monkeypatch):
        server = self._server(monkeypatch)
        monkeypatch.setenv("ADMIN_TOKEN", "correct-secret")
        import asyncio

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                server.admin_trading_halt(
                    server.TradingHaltRequest(halted=True), x_admin_token="wrong"
                )
            )
        assert excinfo.value.status_code == 401


class TestComplianceGateScopedData:
    """The gate must accept caller-supplied (broker-mode) account/positions
    and use them instead of fetching the default account."""

    def _no_fetch(self, monkeypatch):
        def _must_not_fetch(*a, **k):
            raise AssertionError("must not fetch default account when scoped data is given")

        monkeypatch.setattr(alpaca_client, "get_account", _must_not_fetch)
        monkeypatch.setattr(alpaca_client, "get_positions", _must_not_fetch)

    def test_gate_passes_on_scoped_account(self, monkeypatch):
        self._no_fetch(monkeypatch)
        err = trading._mandatory_compliance_gate(
            symbol="AAPL",
            side="buy",
            quantity=1,
            order_type="market",
            limit_price=0.0,
            est_price=150.0,
            account={"equity": "100000", "cash": "50000", "buying_power": "100000"},
            positions=[],
        )
        assert err is None

    def test_gate_blocks_on_scoped_account(self, monkeypatch):
        # $15,000 notional vs $100 buying power -> buying_power BLOCK,
        # evaluated against the SUPPLIED account, not the default one.
        self._no_fetch(monkeypatch)
        err = trading._mandatory_compliance_gate(
            symbol="AAPL",
            side="buy",
            quantity=100,
            order_type="market",
            limit_price=0.0,
            est_price=150.0,
            account={"equity": "100000", "cash": "50000", "buying_power": "100"},
            positions=[],
        )
        assert err is not None
        assert err.get("blocked_by_compliance") is True
