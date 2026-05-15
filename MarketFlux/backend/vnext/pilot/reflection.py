"""Reflection layer for the Pilot subsystem.

Three responsibilities, all defensively wired so a missing dep degrades to a
templated answer rather than 500-ing the route:

  - generate_journal_entry(): once per personality per UTC date. Aggregates the
    day's proposals (created, executed, rejected, expired), computes per-category
    P&L attribution from the snapshot at proposal time, and asks the LLM (if
    available) to write a candid first-person journal entry. If no LLM is
    configured, a deterministic template is used and tagged as such.

  - detect_thesis_drift(): for each open ('executed' BUY that hasn't been
    closed yet) position, re-runs signal_engine.compute_signals on the ticker
    and compares the composite + per-category scores to the snapshot at entry.
    Anything that has drifted past `drift_threshold` is materialized as a flag
    on `pilot_drift_flags`. Old flags for the same (personality, ticker) pair
    are superseded (replaced, not appended) so we don't grow unbounded.

  - compute_leaderboard(): cheap ranking of all publicly-visible personalities
    by trailing executed-proposal performance. Pure-Python, no Alpaca dep,
    safe to call from anonymous browsers.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

JOURNAL_COLLECTION = "pilot_journal"
DRIFT_COLLECTION = "pilot_drift_flags"

# Default drift threshold: a composite move of -20 points is "thesis weakening".
# -40 is "thesis materially broken".
DEFAULT_DRIFT_THRESHOLD = -20.0
HIGH_SEVERITY_THRESHOLD = -40.0


# ---------------------------------------------------------------------------
# Lazy imports — keep this module importable in dep-less smoke tests.
# ---------------------------------------------------------------------------
def _get_compute_signals():
    from signal_engine import compute_signals  # type: ignore
    return compute_signals


def _get_strategy_router():
    from vnext.model_router import StrategyLLMRouter  # type: ignore
    return StrategyLLMRouter


def _today_utc_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# ===========================================================================
# Journal
# ===========================================================================
async def generate_journal_entry(
    db: Any,
    personality_id: str,
    *,
    target_date: Optional[str] = None,
    use_llm: bool = True,
) -> Optional[Dict[str, Any]]:
    """Create (or refresh) the journal entry for `personality_id` on
    `target_date` (UTC, default today). Idempotent: same (personality_id, date)
    upserts the existing document.

    Returns the stored entry, or None if the personality doesn't exist.
    """
    from .personality import get_personality
    from .trade_proposals import list_proposals, ProposalStatus

    personality = await get_personality(db, personality_id)
    if personality is None:
        return None

    target = target_date or _today_utc_iso()

    # Pull a generous slice of recent proposals and filter by date prefix.
    all_proposals = await list_proposals(
        db, personality_id=personality_id, limit=500
    )
    todays = [p for p in all_proposals if (p.created_at or "").startswith(target)]

    by_status: Dict[str, List[Any]] = defaultdict(list)
    for p in todays:
        by_status[p.status].append(p)

    executed = by_status.get(ProposalStatus.EXECUTED.value, [])
    rejected = by_status.get(ProposalStatus.REJECTED.value, [])
    expired = by_status.get(ProposalStatus.EXPIRED.value, [])
    failed = by_status.get(ProposalStatus.FAILED.value, [])

    # Per-category attribution: sum signal-category scores across executed BUYs
    # only. Sells / shorts contribute negatively.
    attribution: Dict[str, float] = defaultdict(float)
    avg_conviction = 0.0
    for prop in executed:
        sign = 1.0 if prop.side == "buy" else -1.0
        cats = (prop.signal_snapshot or {}).get("categories") or {}
        for cat_name, payload in cats.items():
            attribution[cat_name] += sign * float((payload or {}).get("score") or 0.0)
        avg_conviction += float(prop.conviction or 0)
    if executed:
        avg_conviction /= len(executed)

    stats = {
        "date": target,
        "proposals_today": len(todays),
        "executed": len(executed),
        "rejected": len(rejected),
        "expired": len(expired),
        "failed": len(failed),
        "tickers_traded": sorted({p.ticker for p in executed}),
        "tickers_rejected": sorted({p.ticker for p in rejected}),
        "avg_conviction_executed": round(avg_conviction, 2),
        "attribution": {k: round(v, 2) for k, v in attribution.items()},
    }

    # Build the LLM payload (or skip to template if disabled / unavailable).
    summary_text = ""
    lessons = ""
    tomorrows_watch: List[str] = []
    source = "template"

    if use_llm:
        try:
            summary_text, lessons, tomorrows_watch = await _llm_journal(
                personality.name,
                personality.mandate,
                target,
                executed,
                rejected,
                expired,
                attribution,
            )
            source = "llm"
        except Exception as exc:
            logger.info(
                "reflection: LLM journal failed for %s; falling back to template: %s",
                personality.name, exc,
            )

    if not summary_text:
        summary_text = _template_summary(personality.name, stats, attribution)
        lessons = _template_lessons(stats, attribution)
        tomorrows_watch = stats["tickers_rejected"][:3]
        source = "template"

    entry = {
        "id": f"{personality_id}:{target}",
        "personality_id": personality_id,
        "personality_name": personality.name,
        "date": target,
        "summary": summary_text,
        "lessons": lessons,
        "tomorrows_watchlist": tomorrows_watch,
        "stats": stats,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paper_only": True,
        "disclaimer": "Paper trading only. Not investment advice.",
    }

    # Upsert by deterministic id so re-runs replace cleanly.
    coll = db[JOURNAL_COLLECTION]
    await coll.replace_one({"id": entry["id"]}, entry, upsert=True)
    return entry


async def list_journal_entries(
    db: Any,
    *,
    personality_id: Optional[str] = None,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    coll = db[JOURNAL_COLLECTION]
    query: Dict[str, Any] = {}
    if personality_id:
        query["personality_id"] = personality_id
    cursor = coll.find(query).sort("date", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    async for doc in cursor:
        doc.pop("_id", None)
        out.append(doc)
    return out


def _template_summary(name: str, stats: Dict[str, Any], attribution: Dict[str, float]) -> str:
    parts = [
        f"{name} ran {stats['proposals_today']} candidates today",
        f"executed {stats['executed']} (paper)",
        f"rejected {stats['rejected']}",
        f"expired {stats['expired']}",
    ]
    if attribution:
        leader = max(attribution.items(), key=lambda kv: kv[1])
        parts.append(f"strongest tailwind: {leader[0]} ({leader[1]:+.1f})")
    if stats["tickers_traded"]:
        parts.append("traded: " + ", ".join(stats["tickers_traded"]))
    return ". ".join(parts) + "."


def _template_lessons(stats: Dict[str, Any], attribution: Dict[str, float]) -> str:
    if not attribution:
        return "No fills today; nothing to reflect on yet."
    weakest = min(attribution.items(), key=lambda kv: kv[1])
    if weakest[1] < -10:
        return (
            f"Weakest contribution came from {weakest[0]} ({weakest[1]:+.1f}). "
            "Watching this category closely tomorrow; if it stays soft I may "
            "reduce its weighting next week."
        )
    return "Day fell within the expected envelope; no weight changes planned."


async def _llm_journal(
    personality_name: str,
    mandate: str,
    date: str,
    executed: List[Any],
    rejected: List[Any],
    expired: List[Any],
    attribution: Dict[str, float],
) -> tuple[str, str, List[str]]:
    """Call the StrategyLLMRouter to draft a first-person journal entry.

    Returns (summary, lessons, tomorrows_watchlist). Raises on any failure so
    the caller can fall back to the template.
    """
    Router = _get_strategy_router()
    router = Router()

    def _line(p: Any) -> str:
        return (
            f"{p.side.upper()} {p.qty:g} {p.ticker} @ ~${p.quote_price:.2f} "
            f"(conviction {p.conviction}/10): {p.thesis[:200]}"
        )

    executed_lines = [_line(p) for p in executed[:8]] or ["(no fills)"]
    rejected_lines = [_line(p) for p in rejected[:5]] or ["(nothing rejected)"]
    expired_lines = [_line(p) for p in expired[:5]] or ["(none expired)"]

    attr_lines = [f"  {k}: {v:+.2f}" for k, v in sorted(attribution.items())]

    system_prompt = (
        "You are an AI portfolio manager writing your end-of-day journal. "
        "Voice: first person, candid, plain English, no hype, no jargon. "
        "Two paragraphs max. Acknowledge mistakes if any. Paper trading only. "
        "Never give investment advice; describe your own decisions only."
    )
    user_prompt = (
        f"Personality: {personality_name}\n"
        f"Mandate: {mandate}\n"
        f"Date (UTC): {date}\n\n"
        f"Today's executed paper trades:\n- " + "\n- ".join(executed_lines) + "\n\n"
        f"Today's rejected candidates:\n- " + "\n- ".join(rejected_lines) + "\n\n"
        f"Today's expired (timed out without approval):\n- " + "\n- ".join(expired_lines) + "\n\n"
        f"Per-category attribution (sum of category scores on executed BUYs minus SELLs):\n"
        + ("\n".join(attr_lines) if attr_lines else "  (no fills today)") + "\n\n"
        "Output format (use these exact labels, one per line):\n"
        "SUMMARY: <two short paragraphs of self-reflection>\n"
        "LESSONS: <one or two candid sentences>\n"
        "WATCHLIST: <comma-separated tickers I'm watching tomorrow, max 5>\n"
    )

    raw = await router.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        reasoning=False,
        max_tokens=900,
        temperature=0.5,
        request_purpose="pilot_journal",
    )

    return _parse_journal_output(raw)


def _parse_journal_output(raw: str) -> tuple[str, str, List[str]]:
    summary, lessons = "", ""
    watch: List[str] = []
    if not raw:
        raise ValueError("LLM returned empty journal")
    current = None
    buf: Dict[str, List[str]] = {"SUMMARY": [], "LESSONS": [], "WATCHLIST": []}
    for line in raw.splitlines():
        s = line.strip()
        if s.upper().startswith("SUMMARY:"):
            current = "SUMMARY"
            buf[current].append(s.split(":", 1)[1].strip())
        elif s.upper().startswith("LESSONS:"):
            current = "LESSONS"
            buf[current].append(s.split(":", 1)[1].strip())
        elif s.upper().startswith("WATCHLIST:"):
            current = "WATCHLIST"
            buf[current].append(s.split(":", 1)[1].strip())
        elif current:
            buf[current].append(s)
    summary = " ".join(b for b in buf["SUMMARY"] if b).strip()
    lessons = " ".join(b for b in buf["LESSONS"] if b).strip()
    raw_watch = " ".join(b for b in buf["WATCHLIST"] if b)
    for token in raw_watch.replace(",", " ").split():
        cleaned = "".join(c for c in token if c.isalnum() or c in "._-").upper()
        if 1 <= len(cleaned) <= 8 and cleaned.isascii() and not cleaned.isdigit():
            watch.append(cleaned)
        if len(watch) >= 5:
            break
    if not summary:
        # Use the whole body as the summary rather than failing — caller can
        # still decide it's better than the template.
        summary = raw.strip()
    return summary, lessons, watch


# ===========================================================================
# Thesis drift
# ===========================================================================
async def detect_thesis_drift(
    db: Any,
    personality_id: str,
    *,
    drift_threshold: float = DEFAULT_DRIFT_THRESHOLD,
    concurrency: int = 4,
) -> List[Dict[str, Any]]:
    """For every still-open BUY for this personality, recompute signals and
    flag positions whose composite score has dropped by more than
    `drift_threshold` (negative number; default -20).

    Old flags for the same (personality_id, ticker) are replaced.

    Returns the list of flags that were materialized this run (may be empty).
    """
    from .personality import get_personality
    from .trade_proposals import list_proposals, ProposalStatus

    personality = await get_personality(db, personality_id)
    if personality is None:
        return []

    executed = await list_proposals(
        db,
        personality_id=personality_id,
        status=ProposalStatus.EXECUTED.value,
        limit=200,
    )

    # We only care about positions that look "open" — i.e., a BUY that we
    # haven't yet seen a matching SELL for. Build a tiny tally per ticker.
    open_tickers: Dict[str, Any] = {}
    sells: Dict[str, int] = defaultdict(int)
    for p in executed:
        if p.side == "sell":
            sells[p.ticker] += 1
    for p in executed:
        if p.side != "buy":
            continue
        # If a sell came in after this buy, treat the position as closed.
        if sells[p.ticker] > 0:
            sells[p.ticker] -= 1
            continue
        # Most recent BUY per ticker wins.
        existing = open_tickers.get(p.ticker)
        if existing is None or (p.executed_at or p.created_at) > (existing.executed_at or existing.created_at):
            open_tickers[p.ticker] = p

    if not open_tickers:
        return []

    compute_signals = _get_compute_signals()
    semaphore = asyncio.Semaphore(concurrency)

    async def _check_one(prop: Any) -> Optional[Dict[str, Any]]:
        async with semaphore:
            try:
                current = await compute_signals(prop.ticker, db=db)
            except Exception as exc:
                logger.debug("drift: compute_signals(%s) failed: %s", prop.ticker, exc)
                return None
            entry_score = float((prop.signal_snapshot or {}).get("composite_score") or 0.0)
            current_score = float(current.get("composite_score") or 0.0)
            delta = current_score - entry_score
            if delta > drift_threshold:
                return None  # Still within tolerance.

            entry_cats = (prop.signal_snapshot or {}).get("categories") or {}
            current_cats = current.get("categories") or {}
            cat_deltas: Dict[str, float] = {}
            for name in set(entry_cats) | set(current_cats):
                e = float((entry_cats.get(name) or {}).get("score") or 0.0)
                c = float((current_cats.get(name) or {}).get("score") or 0.0)
                cat_deltas[name] = round(c - e, 2)

            severity = "high" if delta <= HIGH_SEVERITY_THRESHOLD else "medium"
            return {
                "id": f"{personality_id}:{prop.ticker}",  # supersedes
                "personality_id": personality_id,
                "personality_name": prop.personality_name,
                "ticker": prop.ticker,
                "entry_score": round(entry_score, 2),
                "current_score": round(current_score, 2),
                "delta": round(delta, 2),
                "severity": severity,
                "category_deltas": cat_deltas,
                "entry_proposal_id": prop.id,
                "entry_at": prop.executed_at or prop.created_at,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "invalidation": prop.invalidation or "",
            }

    raw_flags = await asyncio.gather(*[_check_one(p) for p in open_tickers.values()])
    flags = [f for f in raw_flags if f]

    coll = db[DRIFT_COLLECTION]
    # Clear stale flags for any open tickers that are now back inside tolerance.
    open_set = set(open_tickers.keys())
    flagged_set = {f["ticker"] for f in flags}
    cleared = open_set - flagged_set
    if cleared:
        await coll.delete_many({
            "personality_id": personality_id,
            "ticker": {"$in": list(cleared)},
        })

    for flag in flags:
        await coll.replace_one({"id": flag["id"]}, flag, upsert=True)
    return flags


async def list_drift_flags(
    db: Any,
    *,
    personality_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    coll = db[DRIFT_COLLECTION]
    query: Dict[str, Any] = {}
    if personality_id:
        query["personality_id"] = personality_id
    if severity:
        query["severity"] = severity
    cursor = coll.find(query).sort("checked_at", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    async for doc in cursor:
        doc.pop("_id", None)
        out.append(doc)
    return out


# ===========================================================================
# Leaderboard
# ===========================================================================
async def compute_leaderboard(
    db: Any,
    *,
    days: int = 30,
    limit: int = 20,
    include_private: bool = False,
) -> List[Dict[str, Any]]:
    """Rank personalities by paper performance over the last `days`.

    Performance is approximated from executed proposals: per BUY-then-SELL
    pair on the same ticker, P&L = sell_fill * sell_qty - buy_fill * buy_qty,
    plus mark-to-market on still-open BUYs using their most recent quote
    snapshot. Crude on purpose — Alpaca is the source of truth for paying
    users; the leaderboard just needs a defensible ordering.
    """
    from .personality import PERSONALITY_COLLECTION
    from .trade_proposals import PROPOSAL_COLLECTION, ProposalStatus

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pers_coll = db[PERSONALITY_COLLECTION]
    prop_coll = db[PROPOSAL_COLLECTION]

    pquery: Dict[str, Any] = {}
    if not include_private:
        pquery["public_visibility"] = True
    personalities = []
    async for doc in pers_coll.find(pquery):
        doc.pop("_id", None)
        personalities.append(doc)

    rows: List[Dict[str, Any]] = []
    for p in personalities:
        pid = p.get("id")
        if not pid:
            continue
        cursor = prop_coll.find({
            "personality_id": pid,
            "status": ProposalStatus.EXECUTED.value,
            "executed_at": {"$gte": cutoff},
        }).sort("executed_at", 1)

        buys: List[Dict[str, Any]] = []
        realized: float = 0.0
        trade_returns: List[float] = []
        latest_quotes: Dict[str, float] = {}
        open_quantities: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        async for prop in cursor:
            ticker = prop.get("ticker")
            side = prop.get("side")
            fill_price = float(prop.get("fill_price") or prop.get("quote_price") or 0.0)
            fill_qty = float(prop.get("fill_qty") or prop.get("qty") or 0.0)
            latest_quotes[ticker] = fill_price
            if side == "buy":
                open_quantities[ticker].append({"qty": fill_qty, "price": fill_price})
            elif side == "sell":
                qty_left = fill_qty
                while qty_left > 0 and open_quantities[ticker]:
                    lot = open_quantities[ticker][0]
                    use = min(qty_left, lot["qty"])
                    pl = (fill_price - lot["price"]) * use
                    realized += pl
                    cost = lot["price"] * use
                    if cost > 0:
                        trade_returns.append(pl / cost)
                    lot["qty"] -= use
                    qty_left -= use
                    if lot["qty"] <= 1e-9:
                        open_quantities[ticker].pop(0)

        # Mark-to-market open lots at the last known fill price.
        unrealized: float = 0.0
        open_notional: float = 0.0
        open_positions: int = 0
        for ticker, lots in open_quantities.items():
            mark = latest_quotes.get(ticker)
            for lot in lots:
                if lot["qty"] <= 0:
                    continue
                open_positions += 1
                open_notional += lot["price"] * lot["qty"]
                if mark is not None:
                    unrealized += (mark - lot["price"]) * lot["qty"]

        total_pl = realized + unrealized
        capital = float(p.get("initial_capital_usd") or 25_000.0)
        ret_pct = (total_pl / capital) * 100 if capital else 0.0

        # Trade win rate / Sharpe-lite.
        wins = sum(1 for r in trade_returns if r > 0)
        win_rate = (wins / len(trade_returns)) * 100 if trade_returns else 0.0
        try:
            sharpe_lite = (
                (statistics.mean(trade_returns) / statistics.pstdev(trade_returns)) * (252 ** 0.5)
                if len(trade_returns) >= 2 and statistics.pstdev(trade_returns) > 0
                else 0.0
            )
        except statistics.StatisticsError:
            sharpe_lite = 0.0

        rows.append({
            "personality_id": pid,
            "personality_name": p.get("name") or pid,
            "user_id": p.get("user_id"),
            "is_seed": bool(p.get("is_seed", False)),
            "public_visibility": bool(p.get("public_visibility", False)),
            "avatar_glyph": p.get("avatar_glyph") or "circle",
            "accent_color": p.get("accent_color") or "#22c55e",
            "trades": len(trade_returns),
            "open_positions": open_positions,
            "open_notional": round(open_notional, 2),
            "realized_pl": round(realized, 2),
            "unrealized_pl": round(unrealized, 2),
            "total_pl": round(total_pl, 2),
            "return_pct": round(ret_pct, 2),
            "win_rate_pct": round(win_rate, 2),
            "sharpe_lite": round(sharpe_lite, 2),
            "window_days": days,
        })

    rows.sort(key=lambda r: (r["return_pct"], r["sharpe_lite"]), reverse=True)
    return rows[:limit]


# ===========================================================================
# Convenience: run the nightly batch over every personality.
# ===========================================================================
async def run_nightly_reflection(db: Any) -> Dict[str, Any]:
    """Generate journal + drift flags for every personality. Best-effort:
    a failure on one personality must not stop the others."""
    from .personality import list_personalities

    personalities = await list_personalities(db)
    journals_written = 0
    drift_flags_written = 0
    errors: List[str] = []

    for p in personalities:
        if p.paused:
            continue
        try:
            entry = await generate_journal_entry(db, p.id)
            if entry:
                journals_written += 1
        except Exception as exc:
            errors.append(f"journal[{p.id}]: {exc}")
        try:
            flags = await detect_thesis_drift(db, p.id)
            drift_flags_written += len(flags)
        except Exception as exc:
            errors.append(f"drift[{p.id}]: {exc}")

    return {
        "personalities_total": len(personalities),
        "journals_written": journals_written,
        "drift_flags_written": drift_flags_written,
        "errors": errors,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }
