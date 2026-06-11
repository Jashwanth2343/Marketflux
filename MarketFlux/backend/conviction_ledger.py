"""Conviction Ledger — record every thesis, then grade it against reality.

The ledger is the product spine of MarketFlux lean v1 (see
docs/prd-copilot-godtier.md roadmap #1 and the approved design doc): every
thesis — whether the copilot's or a human's — is persisted with its entry
signal score and a STRUCTURED invalidation rule, then auto-graded nightly
against SPY. The output is the number free chat tools can't produce: a hit
rate and alpha-per-call you can audit.

Design rules (from the approved design doc):
  * agent_id is ALWAYS set ("human" is an agent_id) — this one field keeps the
    future agent-leaderboard option open with zero schema migration.
  * Invalidation is structured (price / date / score-floor); prose is for the
    reader, the grading job only evaluates structured fields.
  * Expiry defaults to entry + 90 days. Targets/invalidations are evaluated on
    DAILY ADJUSTED CLOSES only (no intraday touches; splits handled upstream
    by auto_adjust=True).
  * Grade = alpha vs SPY over the thesis window, sign-flipped for shorts:
    A >= +5pp, B +1..+5, C -1..+1, D -5..-1, F <= -5.
  * Invalidation truncates the window — the thesis is graded over
    entry -> invalidation date, it doesn't auto-fail.

Storage: MongoDB (the app's primary store) via the same motor handle the rest
of the backend uses. A Supabase Postgres migration is shipped in
docs/migrations/ledger.sql for when the ledger graduates to Postgres; this
module's public API is storage-agnostic so the swap doesn't touch callers.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

COLLECTION = "ledger_theses"
AUDIT_COLLECTION = "ledger_audit"
CLOSES_COLLECTION = "ledger_daily_closes"

DEFAULT_EXPIRY_DAYS = 90
AUTO_LOG_SCORE_THRESHOLD = float(os.environ.get("LEDGER_AUTOLOG_SCORE", "30"))

VALID_DIRECTIONS = {"long", "short"}
OPEN = "open"
CLOSED = "closed"
INVALIDATED = "invalidated"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today_iso() -> str:
    return _now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Pure grading math (unit-tested in tests/test_conviction_ledger.py)
# ---------------------------------------------------------------------------
def thesis_return_pct(entry_price: float, exit_price: float, direction: str) -> float:
    """Direction-adjusted return in percent. Short profits when price falls."""
    if not entry_price:
        return 0.0
    raw = (exit_price / entry_price - 1.0) * 100.0
    return raw if direction == "long" else -raw


def alpha_pp(thesis_ret_pct: float, bench_ret_pct: float, direction: str) -> float:
    """Alpha in percentage points vs SPY over the same window.

    For shorts the benchmark is sign-flipped: a short is judged against
    shorting the market, so falling tape doesn't gift a bad short an A.
    """
    bench = bench_ret_pct if direction == "long" else -bench_ret_pct
    return thesis_ret_pct - bench


def grade_from_alpha(alpha: float) -> str:
    if alpha >= 5.0:
        return "A"
    if alpha >= 1.0:
        return "B"
    if alpha > -1.0:
        return "C"
    if alpha > -5.0:
        return "D"
    return "F"


def evaluate_open_thesis(
    thesis: Dict[str, Any],
    closes: List[Tuple[str, float]],
    as_of: str,
) -> Dict[str, Any]:
    """Decide what happens to one open thesis given its daily closes.

    Pure function: no IO. ``closes`` is a date-ascending list of
    (YYYY-MM-DD, adjusted_close) for the thesis ticker, starting at or after
    entry_date. Returns one of:
      {"action": "close", "reason": "target"|"invalidation_price"|"expiry",
       "close_date": iso, "close_price": float}
      {"action": "update", "current_price": float}
      {"action": "skip", "why": str}
    Target and invalidation_price are checked in date order so whichever a
    close crosses FIRST wins; expiry closes at the last close on/before the
    invalidation_date.
    """
    direction = thesis.get("direction", "long")
    target = thesis.get("price_target") or 0.0
    inv_price = thesis.get("invalidation_price") or 0.0
    inv_date = thesis.get("invalidation_date") or ""

    usable = [(d, c) for d, c in closes if d <= as_of and c and c > 0]
    if not usable:
        return {"action": "skip", "why": "no price data"}

    for d, c in usable:
        if target > 0:
            hit = c >= target if direction == "long" else c <= target
            if hit:
                return {"action": "close", "reason": "target", "close_date": d, "close_price": c}
        if inv_price > 0:
            stopped = c <= inv_price if direction == "long" else c >= inv_price
            if stopped:
                return {"action": "close", "reason": "invalidation_price", "close_date": d, "close_price": c}

    if inv_date and as_of >= inv_date:
        on_or_before = [(d, c) for d, c in usable if d <= inv_date] or usable
        d, c = on_or_before[-1]
        return {"action": "close", "reason": "expiry", "close_date": d, "close_price": c}

    return {"action": "update", "current_price": usable[-1][1]}


def window_return_pct(closes: List[Tuple[str, float]], start: str, end: str,
                      entry_price: Optional[float] = None) -> float:
    """Benchmark/raw return in % between the first close >= start and the last
    close <= end. If entry_price is given it anchors the start instead."""
    inside = [(d, c) for d, c in closes if start <= d <= end and c and c > 0]
    if not inside:
        return 0.0
    first = entry_price if entry_price else inside[0][1]
    last = inside[-1][1]
    if not first:
        return 0.0
    return (last / first - 1.0) * 100.0


# ---------------------------------------------------------------------------
# Price data — daily adjusted closes, cached on disk (24h) by backtest.data
# and mirrored into Mongo for an auditable record of what grading saw.
# ---------------------------------------------------------------------------
async def _fetch_closes(symbol: str, start: str, end: str) -> List[Tuple[str, float]]:
    from backtest.data import load_ohlcv

    def _load() -> List[Tuple[str, float]]:
        df = load_ohlcv(symbol, start=start, end=end, interval="1d")
        if df is None or df.empty or "close" not in df.columns:
            return []
        return [(idx.strftime("%Y-%m-%d"), float(v)) for idx, v in df["close"].items()]

    try:
        return await asyncio.to_thread(_load)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ledger: close fetch failed for %s: %s", symbol, exc)
        return []


async def _mirror_closes(db, symbol: str, closes: List[Tuple[str, float]]) -> None:
    if db is None or not closes:
        return
    try:
        from pymongo import UpdateOne
        ops = [UpdateOne({"symbol": symbol, "date": d},
                         {"$set": {"close": c}}, upsert=True) for d, c in closes[-120:]]
        await db[CLOSES_COLLECTION].bulk_write(ops, ordered=False)
    except Exception as exc:  # noqa: BLE001
        logger.debug("ledger: close mirror skipped: %s", exc)


# ---------------------------------------------------------------------------
# Audit trail — append-only; every mutation lands here
# ---------------------------------------------------------------------------
async def _audit(db, thesis_id: str, event: str, detail: Dict[str, Any]) -> None:
    try:
        await db[AUDIT_COLLECTION].insert_one({
            "thesis_id": thesis_id,
            "event": event,
            "detail": detail,
            "at": _now().isoformat(),
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning("ledger: audit write failed: %s", exc)


def _public(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def create_thesis(
    db,
    *,
    user_id: str,
    agent_id: str,
    ticker: str,
    direction: str,
    rationale: str,
    source: str = "manual",
    entry_price: Optional[float] = None,
    composite_score: Optional[float] = None,
    signal_label: Optional[str] = None,
    price_target: Optional[float] = None,
    invalidation_price: Optional[float] = None,
    invalidation_date: Optional[str] = None,
    invalidation_score_floor: Optional[float] = None,
    invalidation_notes: str = "",
) -> Dict[str, Any]:
    ticker = (ticker or "").strip().upper()
    direction = (direction or "long").strip().lower()
    if not ticker:
        return {"ok": False, "error": "ticker is required"}
    if direction not in VALID_DIRECTIONS:
        return {"ok": False, "error": "direction must be 'long' or 'short'"}
    if not (rationale or "").strip():
        return {"ok": False, "error": "rationale is required"}

    entry_date = _today_iso()
    if not entry_price or entry_price <= 0:
        lookback = (_now() - timedelta(days=7)).strftime("%Y-%m-%d")
        closes = await _fetch_closes(ticker, lookback, entry_date)
        if not closes:
            return {"ok": False, "error": f"could not fetch an entry price for {ticker}"}
        entry_price = closes[-1][1]

    if not invalidation_date:
        invalidation_date = (_now() + timedelta(days=DEFAULT_EXPIRY_DAYS)).strftime("%Y-%m-%d")

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "agent_id": (agent_id or "human").strip()[:64],
        "ticker": ticker,
        "direction": direction,
        "source": source,
        "status": OPEN,
        "entry_date": entry_date,
        "entry_price": round(float(entry_price), 4),
        "composite_score": composite_score,
        "signal_label": signal_label,
        "rationale": (rationale or "").strip()[:8000],
        "price_target": float(price_target) if price_target else None,
        "invalidation_price": float(invalidation_price) if invalidation_price else None,
        "invalidation_date": invalidation_date,
        "invalidation_score_floor": float(invalidation_score_floor) if invalidation_score_floor else None,
        "invalidation_notes": (invalidation_notes or "").strip()[:1000],
        "current_price": round(float(entry_price), 4),
        "unrealized_return_pct": 0.0,
        "close_date": None,
        "close_price": None,
        "close_reason": None,
        "return_pct": None,
        "benchmark_return_pct": None,
        "alpha_pp": None,
        "grade": None,
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    await db[COLLECTION].insert_one(dict(doc))
    await _audit(db, doc["id"], "created", {"source": source, "agent_id": doc["agent_id"],
                                            "ticker": ticker, "entry_price": doc["entry_price"]})
    return {"ok": True, "item": _public(doc)}


async def list_theses(db, user_id: str, status: Optional[str] = None,
                      agent_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"user_id": user_id}
    if status:
        q["status"] = status
    if agent_id:
        q["agent_id"] = agent_id
    cur = db[COLLECTION].find(q, {"_id": 0}).sort("created_at", -1).limit(min(limit, 500))
    return [doc async for doc in cur]


async def get_stats(db, user_id: str) -> Dict[str, Any]:
    """Hit rate, average alpha per call, and per-agent breakdown.

    A 'win' is a graded thesis with positive alpha (grade A or B); C is a push
    and excluded from the hit-rate denominator.
    """
    rows = await db[COLLECTION].find({"user_id": user_id}, {"_id": 0}).to_list(2000)
    open_rows = [r for r in rows if r.get("status") == OPEN]
    graded = [r for r in rows if r.get("grade")]
    decisive = [r for r in graded if r["grade"] != "C"]
    wins = [r for r in decisive if r["grade"] in ("A", "B")]
    alphas = [r["alpha_pp"] for r in graded if isinstance(r.get("alpha_pp"), (int, float))]

    per_agent: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        a = per_agent.setdefault(r.get("agent_id") or "human",
                                 {"total": 0, "open": 0, "graded": 0, "wins": 0, "alpha_sum": 0.0})
        a["total"] += 1
        if r.get("status") == OPEN:
            a["open"] += 1
        if r.get("grade"):
            a["graded"] += 1
            if r["grade"] in ("A", "B"):
                a["wins"] += 1
            if isinstance(r.get("alpha_pp"), (int, float)):
                a["alpha_sum"] += r["alpha_pp"]

    return {
        "total": len(rows),
        "open": len(open_rows),
        "graded": len(graded),
        "hit_rate_pct": round(len(wins) / len(decisive) * 100, 1) if decisive else None,
        "avg_alpha_pp": round(sum(alphas) / len(alphas), 2) if alphas else None,
        "grade_counts": {g: sum(1 for r in graded if r["grade"] == g) for g in "ABCDF"},
        "per_agent": per_agent,
    }


async def close_thesis(db, user_id: str, thesis_id: str, reason: str = "manual") -> Dict[str, Any]:
    """Manually close an open thesis at the latest close and grade it."""
    t = await db[COLLECTION].find_one({"id": thesis_id, "user_id": user_id}, {"_id": 0})
    if not t:
        return {"ok": False, "error": "thesis not found"}
    if t.get("status") != OPEN:
        return {"ok": False, "error": "thesis is not open"}

    today = _today_iso()
    closes = await _fetch_closes(t["ticker"], t["entry_date"], today)
    if not closes:
        return {"ok": False, "error": f"no price data for {t['ticker']}"}
    close_date, close_price = closes[-1]
    return await _settle(db, t, close_date, close_price, reason)


async def _settle(db, thesis: Dict[str, Any], close_date: str, close_price: float,
                  reason: str) -> Dict[str, Any]:
    """Compute final return/alpha/grade and persist the closed thesis."""
    bench = await _fetch_closes("SPY", thesis["entry_date"], close_date)
    t_ret = thesis_return_pct(thesis["entry_price"], close_price, thesis["direction"])
    b_ret = window_return_pct(bench, thesis["entry_date"], close_date)
    a_pp = alpha_pp(t_ret, b_ret, thesis["direction"])
    grade = grade_from_alpha(a_pp)
    status = INVALIDATED if reason in ("invalidation_price", "score_floor") else CLOSED

    fields = {
        "status": status,
        "close_date": close_date,
        "close_price": round(float(close_price), 4),
        "close_reason": reason,
        "return_pct": round(t_ret, 2),
        "benchmark_return_pct": round(b_ret, 2),
        "alpha_pp": round(a_pp, 2),
        "grade": grade,
        "updated_at": _now().isoformat(),
    }
    await db[COLLECTION].update_one({"id": thesis["id"]}, {"$set": fields})
    await _audit(db, thesis["id"], "graded", {"reason": reason, **fields})
    return {"ok": True, "item": {**thesis, **fields}}


# ---------------------------------------------------------------------------
# Nightly grading job — closes what's due, marks the rest to market
# ---------------------------------------------------------------------------
async def grade_all(db, as_of: Optional[str] = None) -> Dict[str, Any]:
    """Evaluate every open thesis across all users. Called by the nightly cron
    (POST /api/ledger/grade) and safe to run any time — idempotent."""
    as_of = as_of or _today_iso()
    open_rows = await db[COLLECTION].find({"status": OPEN}, {"_id": 0}).to_list(2000)
    if not open_rows:
        return {"ok": True, "open": 0, "closed": 0, "updated": 0, "skipped": 0}

    closed = updated = skipped = 0
    by_ticker: Dict[str, List[Dict[str, Any]]] = {}
    for r in open_rows:
        by_ticker.setdefault(r["ticker"], []).append(r)

    for ticker, theses in by_ticker.items():
        earliest = min(t["entry_date"] for t in theses)
        closes = await _fetch_closes(ticker, earliest, as_of)
        await _mirror_closes(db, ticker, closes)
        if not closes:
            skipped += len(theses)
            continue
        for t in theses:
            t_closes = [(d, c) for d, c in closes if d >= t["entry_date"]]
            decision = evaluate_open_thesis(t, t_closes, as_of)
            if decision["action"] == "close":
                await _settle(db, t, decision["close_date"], decision["close_price"],
                              decision["reason"])
                closed += 1
            elif decision["action"] == "update":
                cur = decision["current_price"]
                await db[COLLECTION].update_one({"id": t["id"]}, {"$set": {
                    "current_price": round(cur, 4),
                    "unrealized_return_pct": round(
                        thesis_return_pct(t["entry_price"], cur, t["direction"]), 2),
                    "updated_at": _now().isoformat(),
                }})
                updated += 1
            else:
                skipped += 1

    summary = {"ok": True, "as_of": as_of, "open": len(open_rows),
               "closed": closed, "updated": updated, "skipped": skipped}
    logger.info("ledger grade_all: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Auto-log — called by the copilot at end of turn (see copilot_agent._finalize)
# ---------------------------------------------------------------------------
async def auto_log_from_turn(db, user_id: str, turn_events: List[Dict[str, Any]],
                             final_text: str, agent_id: str = "copilot") -> int:
    """Apply the design-doc capture rule to one conversation turn.

    Rule: log a thesis for symbol S when the turn contains BOTH
      (a) a `signals` insight for S with |composite_score| >= threshold, and
      (b) a sizing-or-trade event for S — a `stock_risk` insight carrying a
          sizing_recommendation, or a staged/executed order (trade event).
    Direction follows the score sign. Skips symbols that already have an open
    thesis for this user+agent. Returns the number of theses logged.
    """
    if db is None or not turn_events:
        return 0

    scores: Dict[str, Dict[str, Any]] = {}
    sized: Dict[str, Dict[str, Any]] = {}
    for ev in turn_events:
        kind = ev.get("kind") or ev.get("type")
        sym = (ev.get("symbol") or ev.get("ticker") or "").upper()
        if not sym:
            continue
        if kind == "signals" and isinstance(ev.get("composite_score"), (int, float)):
            scores[sym] = ev
        elif kind == "stock_risk" and ev.get("sizing_recommendation"):
            sized.setdefault(sym, ev)
        elif kind == "trade" and ev.get("side"):
            sized[sym] = ev  # an actual order outranks a sizing card

    logged = 0
    for sym, sig in scores.items():
        score = float(sig["composite_score"])
        if abs(score) < AUTO_LOG_SCORE_THRESHOLD or sym not in sized:
            continue
        existing = await db[COLLECTION].find_one(
            {"user_id": user_id, "agent_id": agent_id, "ticker": sym, "status": OPEN})
        if existing:
            continue
        direction = "long" if score > 0 else "short"
        trade_ev = sized[sym]
        entry_price = None
        if trade_ev.get("price"):
            try:
                entry_price = float(trade_ev["price"])
            except (TypeError, ValueError):
                entry_price = None
        res = await create_thesis(
            db, user_id=user_id, agent_id=agent_id, ticker=sym, direction=direction,
            rationale=(final_text or "").strip()[:8000] or f"Auto-logged from copilot turn ({sig.get('signal_label')})",
            source="copilot-auto", entry_price=entry_price,
            composite_score=score, signal_label=sig.get("signal_label"),
        )
        if res.get("ok"):
            logged += 1
            logger.info("ledger auto-logged %s %s (score %.1f) for %s", direction, sym, score, user_id)
    return logged
