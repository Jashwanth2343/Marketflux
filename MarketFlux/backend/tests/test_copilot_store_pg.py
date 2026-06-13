"""Integration tests for copilot_store against real Postgres.

Runs against the local docker-compose.vnext.yml Postgres by default
(postgresql://marketflux:marketflux@localhost:5432/marketflux) or whatever
COPILOT_STORE_TEST_DSN points at. Skips cleanly when no Postgres is reachable,
so the suite stays green on machines without Docker.
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

TEST_DSN = os.environ.get(
    "COPILOT_STORE_TEST_DSN",
    "postgresql://marketflux:marketflux@localhost:5432/marketflux",
)


def _pg_reachable() -> bool:
    import asyncpg

    async def probe():
        conn = await asyncpg.connect(TEST_DSN, timeout=3)
        await conn.close()

    try:
        asyncio.run(probe())
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_reachable(), reason="No test Postgres reachable (start docker-compose.vnext.yml)")


@pytest.fixture()
def store(monkeypatch):
    """copilot_store wired to the test DSN with a fresh pool."""
    monkeypatch.setenv("SUPABASE_DB_URL", TEST_DSN)
    import vnext.fundos_pg_client as pgc
    import copilot_store as cs
    pgc._POOL = None          # force a new pool against the test DSN
    cs._SCHEMA_APPLIED = False
    yield cs


def _run(coro):
    """Run a test coroutine and close the pg pool inside the same event loop —
    asyncpg pools are loop-bound, so closing later (in teardown) would raise
    'Event loop is closed'."""
    async def wrapped():
        import vnext.fundos_pg_client as pgc
        try:
            return await coro
        finally:
            await pgc.close_pg_pool()
            pgc._POOL = None
    return asyncio.run(wrapped())


def _doc(user_id, **over):
    base = {
        "id": str(uuid.uuid4()), "user_id": user_id, "tool": "place_order",
        "args": {"symbol": "AAPL", "side": "buy", "quantity": 1},
        "preview": {"action": "order", "symbol": "AAPL", "side": "buy", "qty": 1},
        "status": "pending", "created_at": datetime.now(timezone.utc),
    }
    base.update(over)
    return base


def test_pending_lifecycle(store):
    user = f"t-{uuid.uuid4()}"

    async def go():
        doc = _doc(user)
        await store.insert_pending(None, doc)

        rows = await store.list_pending(None, user)
        assert [r["id"] for r in rows] == [doc["id"]]
        assert rows[0]["args"]["symbol"] == "AAPL"

        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        claimed = await store.claim_pending(None, user, doc["id"], cutoff)
        assert claimed and claimed["tool"] == "place_order"
        # Mutex: a second claim must fail.
        assert await store.claim_pending(None, user, doc["id"], cutoff) is None

        await store.set_pending_result(None, doc["id"], "executed", {"ok": True})
        meta = await store.get_pending_meta(None, user, doc["id"])
        assert meta["status"] == "executed"
        assert await store.list_pending(None, user) == []

    _run(go())


def test_reject_and_staleness(store):
    user = f"t-{uuid.uuid4()}"

    async def go():
        fresh, stale = _doc(user), _doc(
            user, created_at=datetime.now(timezone.utc) - timedelta(hours=2))
        await store.insert_pending(None, fresh)
        await store.insert_pending(None, stale)

        # Stale proposals don't rehydrate and can't be claimed.
        assert [r["id"] for r in await store.list_pending(None, user)] == [fresh["id"]]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        assert await store.claim_pending(None, user, stale["id"], cutoff) is None

        assert await store.mark_rejected(None, user, fresh["id"]) is True
        assert await store.mark_rejected(None, user, fresh["id"]) is False  # already rejected

    _run(go())


def test_messages_and_budget(store):
    user = f"t-{uuid.uuid4()}"

    async def go():
        assert await store.count_turns_today(None, user) == 0
        await store.insert_message(None, user, "s1", "first q", "first a")
        await store.insert_message(None, user, "s1", "second q", "second a")
        await store.insert_message(None, user, "s2", "other session", "x")

        assert await store.count_turns_today(None, user) == 3
        hist = await store.recent_history(None, user, "s1")
        assert [h["message"] for h in hist] == ["first q", "second q"]  # oldest first

    _run(go())


def test_trade_log_roundtrip(store):
    user = f"t-{uuid.uuid4()}"

    async def go():
        await store.log_trade(None, user, {"action": "order", "symbol": "MSFT", "qty": 2})
        rows = await store.recent_trades(None, user)
        assert rows[0]["symbol"] == "MSFT" and rows[0]["qty"] == 2
        assert "timestamp" in rows[0]

    _run(go())
