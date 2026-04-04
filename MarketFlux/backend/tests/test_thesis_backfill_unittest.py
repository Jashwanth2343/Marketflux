import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vnext.thesis_repository import backfill_legacy_saved_theses


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, length=None):
        return self.docs


class FakeSavedThesesCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, *_args, **_kwargs):
        return FakeCursor(self.docs)


class FakeMongoDb:
    def __init__(self, docs):
        self.saved_theses = FakeSavedThesesCollection(docs)


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.fetchrow_calls = []
        self.execute_calls = []
        self.closed = False

    def transaction(self):
        return FakeTransaction()

    async def fetchrow(self, query, owner_user_id, legacy_id, ticker, claim):
        self.fetchrow_calls.append(
            {
                "owner_user_id": owner_user_id,
                "legacy_id": legacy_id,
                "ticker": ticker,
                "claim": claim,
            }
        )
        return {"id": "11111111-1111-1111-1111-111111111111"}

    async def execute(self, query, thesis_id, claim, snapshot):
        self.execute_calls.append(
            {
                "thesis_id": thesis_id,
                "claim": claim,
                "snapshot": snapshot,
            }
        )

    async def close(self):
        self.closed = True


class ThesisBackfillTests(unittest.IsolatedAsyncioTestCase):
    async def test_backfill_moves_saved_theses_into_pg_tables(self):
        mongo_db = FakeMongoDb(
            [
                {
                    "_id": "legacy-1",
                    "owner_user_id": "user-123",
                    "ticker": "nvda",
                    "thesis_text": "AI infrastructure demand remains supply constrained.",
                },
                {
                    "_id": "legacy-2",
                    "owner_user_id": "user-123",
                    "ticker": "",
                    "thesis_text": "This row should be skipped.",
                },
            ]
        )
        fake_connection = FakeConnection()

        with patch("vnext.thesis_repository.get_pg_connection", return_value=fake_connection):
            inserted = await backfill_legacy_saved_theses(mongo_db)

        self.assertEqual(inserted, 1)
        self.assertEqual(fake_connection.fetchrow_calls[0]["legacy_id"], "legacy-1")
        self.assertEqual(fake_connection.fetchrow_calls[0]["ticker"], "NVDA")
        self.assertEqual(fake_connection.execute_calls[0]["claim"], "AI infrastructure demand remains supply constrained.")
        self.assertTrue(fake_connection.closed)


if __name__ == "__main__":
    unittest.main()
