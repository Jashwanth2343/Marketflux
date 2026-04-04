from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from .fundos_pg_client import get_pg_connection


def _maybe_json(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _serialize_value(value: Any) -> Any:
    value = _maybe_json(value)
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _serialize_record(record: Any) -> Dict[str, Any]:
    return {key: _serialize_value(value) for key, value in dict(record).items()}


def _group_evidence(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(item["source"], []).append(item)
    return grouped


def _snapshot_from_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "claim": fields["claim"],
        "why_now": fields["why_now"],
        "time_horizon": fields["time_horizon"],
        "status": fields["status"],
        "invalidation_conditions": fields["invalidation_conditions"],
    }


DEFAULT_POLICY_ITEMS: List[Dict[str, Any]] = [
    {"rule_type": "no_live_trading", "enabled": True, "params": {"value": True}},
    {"rule_type": "max_position_pct", "enabled": True, "params": {"value": 20}},
    {"rule_type": "max_gross_exposure_pct", "enabled": True, "params": {"value": 100}},
    {"rule_type": "max_single_name_concentration", "enabled": True, "params": {"value": 25}},
    {"rule_type": "block_during_earnings_window", "enabled": False, "params": {"days_before": 2, "days_after": 1}},
    {"rule_type": "max_open_trades", "enabled": True, "params": {"value": 10}},
    {"rule_type": "min_confidence_to_trade", "enabled": True, "params": {"value": 60}},
]


def _build_policy_effective(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    effective = {
        item["rule_type"]: {
            "enabled": item["enabled"],
            "params": item.get("params", {}),
        }
        for item in DEFAULT_POLICY_ITEMS
    }
    for item in items:
        effective[item["rule_type"]] = {
            "enabled": item["enabled"],
            "params": item.get("params", {}),
        }
    return effective


async def list_theses(user_id: str) -> List[Dict[str, Any]]:
    conn = await get_pg_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT
                t.*,
                COALESCE(latest.version, 0) AS latest_revision_version,
                COALESCE(ev.evidence_count, 0) AS evidence_count,
                COALESCE(pt.open_trade_count, 0) AS open_trade_count
            FROM theses t
            LEFT JOIN LATERAL (
                SELECT version
                FROM thesis_revisions
                WHERE thesis_id = t.id
                ORDER BY version DESC
                LIMIT 1
            ) latest ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS evidence_count
                FROM evidence_blocks
                WHERE thesis_id = t.id
            ) ev ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS open_trade_count
                FROM paper_trades
                WHERE thesis_id = t.id AND status = 'open'
            ) pt ON TRUE
            WHERE t.owner_user_id = $1
            ORDER BY t.updated_at DESC
            """,
            user_id,
        )
        return [_serialize_record(row) for row in rows]
    finally:
        await conn.close()


async def fetch_thesis_row(user_id: str, thesis_id: str) -> Optional[Dict[str, Any]]:
    conn = await get_pg_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM theses
            WHERE id = $1::uuid AND owner_user_id = $2
            """,
            thesis_id,
            user_id,
        )
        return _serialize_record(row) if row else None
    finally:
        await conn.close()


async def get_workspace(user_id: str, thesis_id: str) -> Optional[Dict[str, Any]]:
    thesis = await fetch_thesis_row(user_id, thesis_id)
    if not thesis:
        return None

    conn = await get_pg_connection()
    try:
        revisions_rows = await conn.fetch(
            """
            SELECT *
            FROM thesis_revisions
            WHERE thesis_id = $1::uuid
            ORDER BY version DESC, created_at DESC
            """,
            thesis_id,
        )
        evidence_rows = await conn.fetch(
            """
            SELECT *
            FROM evidence_blocks
            WHERE thesis_id = $1::uuid
            ORDER BY observed_at DESC, created_at DESC
            """,
            thesis_id,
        )
        memo_rows = await conn.fetch(
            """
            SELECT *
            FROM memos
            WHERE thesis_id = $1::uuid
            ORDER BY created_at DESC
            """,
            thesis_id,
        )
        trade_rows = await conn.fetch(
            """
            SELECT *
            FROM paper_trades
            WHERE thesis_id = $1::uuid
            ORDER BY opened_at DESC, created_at DESC
            """,
            thesis_id,
        )
    finally:
        await conn.close()

    revisions = [_serialize_record(row) for row in revisions_rows]
    evidence_blocks = [_serialize_record(row) for row in evidence_rows]
    memos = [_serialize_record(row) for row in memo_rows]
    paper_trades = [_serialize_record(row) for row in trade_rows]

    return {
        "thesis": thesis,
        "latest_revision": revisions[0] if revisions else None,
        "revisions": revisions,
        "evidence_blocks": evidence_blocks,
        "evidence_groups": _group_evidence(evidence_blocks),
        "memos": memos,
        "paper_trades": paper_trades,
    }


async def create_thesis(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = await get_pg_connection()
    try:
        async with conn.transaction():
            thesis_row = await conn.fetchrow(
                """
                INSERT INTO theses (
                    owner_user_id,
                    ticker,
                    time_horizon,
                    status,
                    claim,
                    why_now,
                    invalidation_conditions
                ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                RETURNING *
                """,
                user_id,
                payload["ticker"].upper(),
                payload["time_horizon"],
                "active",
                payload["claim"],
                payload.get("why_now", ""),
                json.dumps(payload.get("invalidation_conditions", [])),
            )
            snapshot = _snapshot_from_fields(
                {
                    "claim": payload["claim"],
                    "why_now": payload.get("why_now", ""),
                    "time_horizon": payload["time_horizon"],
                    "status": "active",
                    "invalidation_conditions": payload.get("invalidation_conditions", []),
                }
            )
            await conn.execute(
                """
                INSERT INTO thesis_revisions (
                    thesis_id,
                    version,
                    change_summary,
                    claim,
                    why_now,
                    time_horizon,
                    status,
                    invalidation_conditions,
                    snapshot
                ) VALUES ($1, 1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
                """,
                thesis_row["id"],
                "Initial thesis created.",
                payload["claim"],
                payload.get("why_now", ""),
                payload["time_horizon"],
                "active",
                json.dumps(payload.get("invalidation_conditions", [])),
                json.dumps(snapshot),
            )
        thesis_id = str(thesis_row["id"])
    finally:
        await conn.close()

    workspace = await get_workspace(user_id, thesis_id)
    return workspace or {"thesis": _serialize_record(thesis_row)}


async def create_revision(user_id: str, thesis_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    current = await fetch_thesis_row(user_id, thesis_id)
    if not current:
        raise ValueError("Thesis not found")

    next_fields = {
        "claim": payload.get("claim") or current["claim"],
        "why_now": payload.get("why_now") if payload.get("why_now") is not None else current.get("why_now", ""),
        "time_horizon": payload.get("time_horizon") or current["time_horizon"],
        "status": payload.get("status") or current["status"],
        "invalidation_conditions": (
            payload.get("invalidation_conditions")
            if payload.get("invalidation_conditions") is not None
            else current.get("invalidation_conditions", [])
        ),
    }
    snapshot = _snapshot_from_fields(next_fields)

    conn = await get_pg_connection()
    try:
        async with conn.transaction():
            version = await conn.fetchval(
                """
                SELECT COALESCE(MAX(version), 0) + 1
                FROM thesis_revisions
                WHERE thesis_id = $1::uuid
                """,
                thesis_id,
            )
            revision_row = await conn.fetchrow(
                """
                INSERT INTO thesis_revisions (
                    thesis_id,
                    version,
                    change_summary,
                    claim,
                    why_now,
                    time_horizon,
                    status,
                    invalidation_conditions,
                    snapshot
                ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb)
                RETURNING *
                """,
                thesis_id,
                version,
                payload.get("change_summary"),
                next_fields["claim"],
                next_fields["why_now"],
                next_fields["time_horizon"],
                next_fields["status"],
                json.dumps(next_fields["invalidation_conditions"]),
                json.dumps(snapshot),
            )
            await conn.execute(
                """
                UPDATE theses
                SET
                    claim = $2,
                    why_now = $3,
                    time_horizon = $4,
                    status = $5,
                    invalidation_conditions = $6::jsonb,
                    updated_at = NOW()
                WHERE id = $1::uuid
                """,
                thesis_id,
                next_fields["claim"],
                next_fields["why_now"],
                next_fields["time_horizon"],
                next_fields["status"],
                json.dumps(next_fields["invalidation_conditions"]),
            )
    finally:
        await conn.close()

    workspace = await get_workspace(user_id, thesis_id)
    if not workspace:
        raise ValueError("Thesis not found after revision")
    workspace["revision"] = _serialize_record(revision_row)
    return workspace


async def insert_evidence_blocks(thesis_id: str, revision_id: Optional[str], items: List[Dict[str, Any]]) -> None:
    if not items:
        return

    conn = await get_pg_connection()
    try:
        async with conn.transaction():
            for item in items:
                await conn.execute(
                    """
                    INSERT INTO evidence_blocks (
                        thesis_id,
                        revision_id,
                        source,
                        summary,
                        payload,
                        confidence,
                        freshness,
                        links,
                        observed_at
                    ) VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7, $8::jsonb, $9)
                    """,
                    thesis_id,
                    revision_id,
                    item["source"],
                    item["summary"],
                    json.dumps(item.get("payload", {})),
                    item.get("confidence", 0),
                    item["freshness"],
                    json.dumps(item.get("links", [])),
                    item["observed_at"],
                )
            await conn.execute(
                "UPDATE theses SET updated_at = NOW() WHERE id = $1::uuid",
                thesis_id,
            )
    finally:
        await conn.close()


async def create_memo(
    user_id: str,
    thesis_id: str,
    revision_id: Optional[str],
    summary: str,
    body: str,
    generated_by: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not await fetch_thesis_row(user_id, thesis_id):
        raise ValueError("Thesis not found")

    conn = await get_pg_connection()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO memos (
                thesis_id,
                revision_id,
                summary,
                body,
                generated_by,
                metadata
            ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb)
            RETURNING *
            """,
            thesis_id,
            revision_id,
            summary,
            body,
            generated_by,
            json.dumps(metadata or {}),
        )
        await conn.execute("UPDATE theses SET updated_at = NOW() WHERE id = $1::uuid", thesis_id)
        return _serialize_record(row)
    finally:
        await conn.close()


async def get_policies(user_id: str) -> Dict[str, Any]:
    conn = await get_pg_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT *
            FROM policy_rules
            WHERE owner_user_id = $1
            ORDER BY rule_type ASC
            """,
            user_id,
        )
    finally:
        await conn.close()

    items = [_serialize_record(row) for row in rows]
    return {
        "items": items,
        "effective": _build_policy_effective(items),
    }


async def upsert_policies(user_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    conn = await get_pg_connection()
    try:
        async with conn.transaction():
            for item in items:
                await conn.execute(
                    """
                    INSERT INTO policy_rules (
                        owner_user_id,
                        rule_type,
                        enabled,
                        params
                    ) VALUES ($1, $2, $3, $4::jsonb)
                    ON CONFLICT (owner_user_id, rule_type)
                    DO UPDATE SET
                        enabled = EXCLUDED.enabled,
                        params = EXCLUDED.params,
                        updated_at = NOW()
                    """,
                    user_id,
                    item["rule_type"],
                    item.get("enabled", True),
                    json.dumps(item.get("params", {})),
                )
    finally:
        await conn.close()

    return await get_policies(user_id)


async def list_open_paper_trades(user_id: str) -> List[Dict[str, Any]]:
    conn = await get_pg_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT *
            FROM paper_trades
            WHERE owner_user_id = $1 AND status = 'open'
            ORDER BY opened_at DESC
            """,
            user_id,
        )
        return [_serialize_record(row) for row in rows]
    finally:
        await conn.close()


async def get_paper_trade(user_id: str, trade_id: str) -> Optional[Dict[str, Any]]:
    conn = await get_pg_connection()
    try:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM paper_trades
            WHERE id = $1::uuid AND owner_user_id = $2
            """,
            trade_id,
            user_id,
        )
        return _serialize_record(row) if row else None
    finally:
        await conn.close()


async def create_paper_trade(
    user_id: str,
    thesis_id: str,
    thesis_revision_id: Optional[str],
    ticker: str,
    side: str,
    size: float,
    entry_price: float,
    notes: Optional[str],
    policy_check_snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    conn = await get_pg_connection()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO paper_trades (
                owner_user_id,
                thesis_id,
                thesis_revision_id,
                ticker,
                side,
                size,
                entry_price,
                status,
                notes,
                policy_check_snapshot
            ) VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6, $7, 'open', $8, $9::jsonb)
            RETURNING *
            """,
            user_id,
            thesis_id,
            thesis_revision_id,
            ticker.upper(),
            side,
            size,
            entry_price,
            notes,
            json.dumps(policy_check_snapshot),
        )
        await conn.execute("UPDATE theses SET updated_at = NOW() WHERE id = $1::uuid", thesis_id)
        return _serialize_record(row)
    finally:
        await conn.close()


async def update_paper_trade(
    user_id: str,
    trade_id: str,
    status: str,
    exit_price: Optional[float],
    notes: Optional[str],
) -> Optional[Dict[str, Any]]:
    existing = await get_paper_trade(user_id, trade_id)
    if not existing:
        return None

    conn = await get_pg_connection()
    try:
        if status == "closed":
            entry_price = float(existing["entry_price"])
            size = float(existing["size"])
            pnl = (exit_price - entry_price) * size if existing["side"] == "buy" else (entry_price - exit_price) * size
            row = await conn.fetchrow(
                """
                UPDATE paper_trades
                SET
                    status = 'closed',
                    exit_price = $2,
                    pnl = $3,
                    notes = COALESCE($4, notes),
                    closed_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1::uuid
                RETURNING *
                """,
                trade_id,
                exit_price,
                pnl,
                notes,
            )
        else:
            row = await conn.fetchrow(
                """
                UPDATE paper_trades
                SET
                    notes = COALESCE($2, notes),
                    updated_at = NOW()
                WHERE id = $1::uuid
                RETURNING *
                """,
                trade_id,
                notes,
            )
        await conn.execute("UPDATE theses SET updated_at = NOW() WHERE id = $1::uuid", existing["thesis_id"])
        return _serialize_record(row) if row else None
    finally:
        await conn.close()


async def backfill_legacy_saved_theses(mongo_db) -> int:
    inserted = 0
    cursor = mongo_db.saved_theses.find({}, {"_id": 1, "owner_user_id": 1, "ticker": 1, "thesis_text": 1})
    docs = await cursor.to_list(length=None)
    conn = await get_pg_connection()
    try:
        async with conn.transaction():
            for doc in docs:
                legacy_id = str(doc.get("_id"))
                owner_user_id = doc.get("owner_user_id")
                ticker = (doc.get("ticker") or "").upper()
                claim = doc.get("thesis_text") or ""
                if not owner_user_id or not ticker or not claim:
                    continue

                thesis_row = await conn.fetchrow(
                    """
                    INSERT INTO theses (
                        owner_user_id,
                        legacy_saved_thesis_id,
                        ticker,
                        time_horizon,
                        status,
                        claim,
                        why_now,
                        invalidation_conditions
                    ) VALUES ($1, $2, $3, 'medium_term', 'active', $4, '', '[]'::jsonb)
                    ON CONFLICT (legacy_saved_thesis_id) DO NOTHING
                    RETURNING id
                    """,
                    owner_user_id,
                    legacy_id,
                    ticker,
                    claim,
                )
                if not thesis_row:
                    continue

                snapshot = _snapshot_from_fields(
                    {
                        "claim": claim,
                        "why_now": "",
                        "time_horizon": "medium_term",
                        "status": "active",
                        "invalidation_conditions": [],
                    }
                )
                await conn.execute(
                    """
                    INSERT INTO thesis_revisions (
                        thesis_id,
                        version,
                        change_summary,
                        claim,
                        why_now,
                        time_horizon,
                        status,
                        invalidation_conditions,
                        snapshot
                    ) VALUES ($1::uuid, 1, 'Backfilled from Mongo saved_theses.', $2, '', 'medium_term', 'active', '[]'::jsonb, $3::jsonb)
                    """,
                    thesis_row["id"],
                    claim,
                    json.dumps(snapshot),
                )
                inserted += 1
    finally:
        await conn.close()
    return inserted
