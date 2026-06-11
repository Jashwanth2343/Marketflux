"""Self-improvement loop for the MarketFlux Copilot.

The agent's long-term memory ([copilot_memory.py]) learns durable facts from what
the *user says*. This module closes the harder loop: learning from what the agent
*does* — the outcomes of its own trades.

`review_and_learn` pulls the live book (account, positions, portfolio history) and
the agent's executed-trade log, has an LLM grade the decisions, and distils a few
concrete, generalizable **lessons** which it writes back into long-term memory.
Those lessons are then recalled on future turns, so the copilot's behaviour
compounds — it stops repeating mistakes and doubles down on what worked. This is
the "trade journal + AI post-mortem" on the roadmap, wired so a standing agent can
run it unattended (e.g. "review my book and learn every morning").

Everything degrades gracefully: if the LLM or memory layer is unavailable, the
review still returns its quantitative summary and is persisted for the UI.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

REVIEW_COLLECTION = "copilot_reviews"

_REVIEW_PROMPT = """You are the Chief Investment Officer reviewing an AI portfolio \
manager's track record on a PAPER account. Be rigorous and specific — your job is \
to make the PM measurably better, not to flatter it.

=== ACCOUNT ===
{account}

=== PORTFOLIO PERFORMANCE (period) ===
{performance}

=== CURRENT POSITIONS (mark-to-market) ===
{positions}

=== RECENT DECISIONS (the agent's executed trades) ===
{trades}

Analyze what worked and what didn't. Then extract a SMALL set of durable, \
GENERALIZABLE lessons the PM should remember for ALL future decisions — not \
one-off observations. Good lessons are behavioural and reusable, e.g. "Winners \
were trimmed too early; let momentum names run with a trailing stop instead of a \
fixed take-profit" or "High-beta entries during choppy tape underperformed; \
require a stronger composite score (>40) before sizing them".

Respond with ONLY a JSON object, no prose, in this exact shape:
{{
  "grade": "A|B|C|D|F",
  "assessment": "2-4 sentence honest assessment of the track record",
  "what_worked": ["..."],
  "what_hurt": ["..."],
  "lessons": ["durable lesson 1", "durable lesson 2", "..."]
}}
Keep lessons to at most 5, each one sentence, concrete and actionable."""


def _fmt(obj: Any, limit: int = 2500) -> str:
    try:
        return json.dumps(obj, indent=2, default=str)[:limit]
    except Exception:
        return str(obj)[:limit]


async def _gather_book(lookback_days: int) -> Dict[str, Any]:
    """Collect account, positions, performance, and the recent trade-decision set."""
    import asyncio
    import copilot_trading_tools as trading

    account, positions, history = await asyncio.gather(
        asyncio.to_thread(trading.get_account_summary),
        asyncio.to_thread(trading.get_open_positions),
        asyncio.to_thread(lambda: trading.get_portfolio_history(period=_period_for(lookback_days))),
    )
    return {"account": account, "positions": positions, "history": history}


def _period_for(days: int) -> str:
    if days <= 7:
        return "1W"
    if days <= 31:
        return "1M"
    if days <= 93:
        return "3M"
    if days <= 186:
        return "6M"
    return "1A"


async def _recent_trades(db, user_id: str, limit: int = 40) -> List[Dict[str, Any]]:
    if db is None:
        return []
    try:
        rows = await db[ "copilot_trade_log" ].find(
            {"user_id": user_id}, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        return rows
    except Exception as exc:  # noqa: BLE001
        logger.warning("review: trade log read failed: %s", exc)
        return []


async def _grade_with_llm(book: Dict[str, Any], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ask Gemini to grade the track record and extract durable lessons."""
    import asyncio
    try:
        import google.generativeai as genai
        from ai_service import configure_gemini, GEMINI_FLASH
        configure_gemini()
        model = genai.GenerativeModel(GEMINI_FLASH)
        prompt = _REVIEW_PROMPT.format(
            account=_fmt(book.get("account")),
            performance=_fmt(book.get("history")),
            positions=_fmt(book.get("positions")),
            trades=_fmt(trades or "No executed trades recorded yet."),
        )
        resp = await asyncio.to_thread(model.generate_content, prompt)
        text = (getattr(resp, "text", "") or "").strip()
        return _parse_json(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("review: LLM grading failed: %s", exc)
        return {}


def _parse_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    # Strip code fences if present.
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("{"):
                text = p
                break
        else:
            text = text.replace("```json", "").replace("```", "")
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


async def review_and_learn_impl(db, user_id: str, lookback_days: int = 30) -> Dict[str, Any]:
    """Review the agent's own track record and write durable lessons to memory.

    Returns a structured performance review. Side effects: persists the review to
    ``copilot_reviews`` and adds each distilled lesson to long-term memory so it is
    recalled on future turns (the self-improvement loop).
    """
    try:
        lookback_days = max(1, min(int(lookback_days or 30), 365))
    except (TypeError, ValueError):
        lookback_days = 30

    book = await _gather_book(lookback_days)
    trades = await _recent_trades(db, user_id)

    graded = await _grade_with_llm(book, trades)
    lessons = [str(x).strip() for x in (graded.get("lessons") or []) if str(x).strip()][:5]

    # Write lessons into long-term memory → recalled on future turns.
    learned = 0
    if lessons:
        try:
            import copilot_memory
            for lesson in lessons:
                if await copilot_memory.add_fact(user_id, f"Trading lesson (from self-review): {lesson}"):
                    learned += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("review: writing lessons to memory failed: %s", exc)

    acct = book.get("account") or {}
    hist = book.get("history") or {}
    positions = (book.get("positions") or {}).get("positions") or []
    review = {
        "ok": True,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "grade": graded.get("grade"),
        "assessment": graded.get("assessment"),
        "what_worked": graded.get("what_worked") or [],
        "what_hurt": graded.get("what_hurt") or [],
        "lessons": lessons,
        "lessons_learned_count": learned,
        "stats": {
            "equity": acct.get("equity"),
            "day_pl": acct.get("day_pl"),
            "period_return_pct": hist.get("change_pct"),
            "open_positions": len(positions),
            "decisions_reviewed": len(trades),
        },
    }
    if not graded:
        review["assessment"] = review["assessment"] or (
            "Quantitative review only — the grading model was unavailable, so no "
            "qualitative lessons were distilled this run."
        )

    # Persist the review for history / the UI.
    if db is not None:
        try:
            await db[REVIEW_COLLECTION].insert_one({"user_id": user_id, **review})
        except Exception as exc:  # noqa: BLE001
            logger.warning("review: persist failed: %s", exc)

    return review
