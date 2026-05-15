"""Alpaca Webhook handler for real-time trade update events.

Handles order fills, partial fills, cancellations, and rejections pushed
from Alpaca via webhooks. Updates internal records and triggers notifications.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from .alpaca_config import get_alpaca_config

logger = logging.getLogger(__name__)

# Supported Alpaca event types
EVENT_NEW = "new"
EVENT_FILL = "fill"
EVENT_PARTIAL_FILL = "partial_fill"
EVENT_CANCELED = "canceled"
EVENT_EXPIRED = "expired"
EVENT_REJECTED = "rejected"
EVENT_REPLACED = "replaced"
EVENT_PENDING_NEW = "pending_new"
EVENT_STOPPED = "stopped"
EVENT_SUSPENDED = "suspended"
EVENT_CALCULATED = "calculated"
EVENT_DONE_FOR_DAY = "done_for_day"

ALL_EVENTS = {
    EVENT_NEW, EVENT_FILL, EVENT_PARTIAL_FILL, EVENT_CANCELED,
    EVENT_EXPIRED, EVENT_REJECTED, EVENT_REPLACED, EVENT_PENDING_NEW,
    EVENT_STOPPED, EVENT_SUSPENDED, EVENT_CALCULATED, EVENT_DONE_FOR_DAY,
}


def build_webhook_router(db) -> APIRouter:
    """Build the webhook router for Alpaca trade events."""
    router = APIRouter(prefix="/api/webhooks/alpaca", tags=["alpaca-webhooks"])

    @router.post("/trade-updates")
    async def handle_trade_update(request: Request):
        """Receive and process Alpaca trade update webhooks.
        
        Alpaca sends POST requests with JSON body containing order events.
        We verify the signature (if configured), process the event, and
        update internal state.
        """
        config = get_alpaca_config()
        if not config or not config.enable_webhooks:
            raise HTTPException(503, "Webhooks are not enabled.")

        body = await request.body()

        # Webhook secret is mandatory — reject all requests if not configured.
        # Without it, anyone can POST fake trade events and corrupt order state.
        if not config.webhook_secret:
            logger.error("Webhook received but ALPACA_WEBHOOK_SECRET is not set. Rejecting.")
            raise HTTPException(503, "Webhook signature verification is not configured. Set ALPACA_WEBHOOK_SECRET.")

        signature = request.headers.get("X-Alpaca-Signature") or request.headers.get("x-alpaca-signature")
        if not _verify_signature(body, signature, config.webhook_secret):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(401, "Invalid webhook signature.")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON payload.")

        event_type = payload.get("event") or payload.get("event_type")
        order_data = payload.get("order") or payload.get("data", {}).get("order") or payload

        if not event_type:
            logger.warning(f"Webhook received without event type: {payload.keys()}")
            return {"status": "ignored", "reason": "no event type"}

        logger.info(f"Alpaca webhook: {event_type} for order {order_data.get('id', 'unknown')}")

        # Process the event
        result = await _process_trade_event(db, event_type, order_data, payload)
        return {"status": "processed", "event": event_type, **result}

    @router.post("/account-updates")
    async def handle_account_update(request: Request):
        """Receive Alpaca account status webhooks (KYC, approval, etc.)."""
        config = get_alpaca_config()
        if not config or not config.enable_webhooks:
            raise HTTPException(503, "Webhooks are not enabled.")

        body = await request.body()

        if not config.webhook_secret:
            logger.error("Account webhook received but ALPACA_WEBHOOK_SECRET is not set. Rejecting.")
            raise HTTPException(503, "Webhook signature verification is not configured. Set ALPACA_WEBHOOK_SECRET.")

        signature = request.headers.get("X-Alpaca-Signature") or request.headers.get("x-alpaca-signature")
        if not _verify_signature(body, signature, config.webhook_secret):
            raise HTTPException(401, "Invalid webhook signature.")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON payload.")

        event_type = payload.get("event") or payload.get("event_type")
        account_id = payload.get("account_id") or (payload.get("data", {}) or {}).get("account_id")

        logger.info(f"Alpaca account webhook: {event_type} for account {account_id}")

        # Store event for audit trail
        await db.alpaca_events.insert_one({
            "event_type": f"account.{event_type}",
            "account_id": account_id,
            "payload": payload,
            "received_at": datetime.now(timezone.utc).isoformat(),
        })

        return {"status": "processed", "event": event_type}

    return router


async def _process_trade_event(
    db,
    event_type: str,
    order_data: Dict[str, Any],
    full_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Process a trade update event and update internal state."""

    order_id = order_data.get("id")
    symbol = order_data.get("symbol")
    account_id = order_data.get("account_id")

    # Store all events for audit trail
    await db.alpaca_events.insert_one({
        "event_type": f"trade.{event_type}",
        "order_id": order_id,
        "account_id": account_id,
        "symbol": symbol,
        "payload": full_payload,
        "received_at": datetime.now(timezone.utc).isoformat(),
    })

    # Update paper_trades if this order is linked
    if order_id:
        from .fundos_pg_client import get_pg_connection
        try:
            conn = await get_pg_connection()

            if event_type == EVENT_FILL:
                filled_avg_price = order_data.get("filled_avg_price")
                filled_qty = order_data.get("filled_qty")

                await conn.execute(
                    """
                    UPDATE paper_trades
                    SET
                        alpaca_status = 'filled',
                        exit_price = CASE WHEN status = 'open' THEN $2::numeric ELSE exit_price END,
                        updated_at = NOW()
                    WHERE alpaca_order_id = $1
                    """,
                    order_id,
                    float(filled_avg_price) if filled_avg_price else None,
                )

                # Also update paper_orders table
                await conn.execute(
                    """
                    UPDATE paper_orders
                    SET
                        broker_status = 'filled',
                        alpaca_status = 'filled',
                        execution_status = 'filled',
                        updated_at = NOW()
                    WHERE alpaca_order_id = $1
                    """,
                    order_id,
                )

            elif event_type == EVENT_PARTIAL_FILL:
                await conn.execute(
                    """
                    UPDATE paper_orders
                    SET
                        broker_status = 'partial_fill',
                        alpaca_status = 'partial_fill',
                        updated_at = NOW()
                    WHERE alpaca_order_id = $1
                    """,
                    order_id,
                )

            elif event_type in (EVENT_CANCELED, EVENT_EXPIRED, EVENT_REJECTED):
                status_map = {
                    EVENT_CANCELED: "cancelled",
                    EVENT_EXPIRED: "cancelled",
                    EVENT_REJECTED: "blocked",
                }
                new_status = status_map[event_type]

                await conn.execute(
                    """
                    UPDATE paper_trades
                    SET alpaca_status = $2, updated_at = NOW()
                    WHERE alpaca_order_id = $1
                    """,
                    order_id,
                    new_status,
                )

                await conn.execute(
                    """
                    UPDATE paper_orders
                    SET
                        broker_status = $2,
                        alpaca_status = $2,
                        execution_status = $2,
                        updated_at = NOW()
                    WHERE alpaca_order_id = $1
                    """,
                    order_id,
                    new_status,
                )

            elif event_type == EVENT_NEW:
                await conn.execute(
                    """
                    UPDATE paper_orders
                    SET
                        broker_status = 'submitted',
                        alpaca_status = 'new',
                        execution_status = 'submitted',
                        updated_at = NOW()
                    WHERE alpaca_order_id = $1
                    """,
                    order_id,
                )

            await conn.close()
        except Exception as exc:
            logger.error(f"Failed to process trade event {event_type} for order {order_id}: {exc}")
            return {"updated": False, "error": str(exc)}

    return {"updated": True, "order_id": order_id}


def _verify_signature(body: bytes, signature: Optional[str], secret: str) -> bool:
    """Verify Alpaca webhook signature using HMAC-SHA256."""
    if not signature:
        return False
    expected = hmac.HMAC(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
