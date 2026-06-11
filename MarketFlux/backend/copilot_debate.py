"""Adversarial Bull vs Bear investment debate for the MarketFlux Copilot.

Inspired by the research-desk pattern in TradingAgents (Tauric Research) and the
investor-persona agents in popular open-source AI hedge funds: before a
high-conviction call, a Bull researcher and a Bear researcher argue the SAME
name from opposite sides using the SAME evidence, then a Research Manager weighs
the debate into a structured verdict. Adversarial reasoning is the cheapest known
antidote to LLM overconfidence — it surfaces the bear case the model would
otherwise gloss over.

Design notes:
- Reuses ``multi_agent._assemble_data`` so the debate runs on the exact same
  grounded evidence the research team uses (DRY, no duplicate fetching).
- The Bull/Bear runs are issued in parallel; the Judge runs after.
- The verdict is typed JSON (verdict / conviction / action / swing factor) — the
  same "structured output, logged for audit" discipline real desks use.
- Every debate is persisted to ``copilot_debates`` for an audit trail.
- Grounding guard: prompts forbid any number not present in the supplied data
  (mitigates the LLM information-leakage failure mode documented in the
  "Profit Mirage" paper).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEBATE_COLLECTION = "copilot_debates"

_BULL_PROMPT = """You are the BULL-side analyst — a growth-minded researcher in the \
spirit of a Cathie Wood / Peter Lynch optimist. Using ONLY the evidence below, build \
the strongest EVIDENCE-BASED long case for {symbol}. Cite specific numbers from the \
data (valuation, growth, momentum, signal scores, catalysts). Be persuasive but honest \
— no numbers that aren't in the data. 4-6 crisp sentences.

EVIDENCE:
{evidence}"""

_BEAR_PROMPT = """You are the BEAR-side analyst — a skeptical short-seller in the spirit \
of a Michael Burry / Jim Chanos deep-value contrarian. Using ONLY the evidence below, \
build the strongest EVIDENCE-BASED case to AVOID or SHORT {symbol}. Attack the bull \
thesis: valuation, deteriorating fundamentals, technical weakness, negative signals, \
crowding, downside catalysts. Cite specific numbers from the data — no inventions. \
4-6 crisp sentences.

EVIDENCE:
{evidence}"""

_JUDGE_PROMPT = """You are the Research Manager chairing an investment committee. A Bull \
and a Bear analyst have debated {symbol} using the same evidence. Weigh both sides on \
the merits of the EVIDENCE — do not split the difference; decide.

=== EVIDENCE (composite signal score, valuation, technicals, sentiment) ===
{evidence}

=== BULL CASE ===
{bull}

=== BEAR CASE ===
{bear}

Respond with ONLY a JSON object, no prose:
{{
  "verdict": "Bullish" | "Neutral" | "Bearish",
  "conviction": "Low" | "Medium" | "High",
  "recommended_action": "one concrete action, e.g. 'Buy a starter 3% position, add on a pullback to $X' or 'Avoid / no position' ",
  "key_swing_factor": "the single most important variable that decides this call",
  "would_change_my_mind": "what new fact would flip the verdict",
  "summary": "2-3 sentence verdict rationale"
}}"""


def _parse_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    if "```" in text:
        for part in text.split("```"):
            p = part.strip()
            if p.startswith("{"):
                text = p
                break
        else:
            text = text.replace("```json", "").replace("```", "")
    a, b = text.find("{"), text.rfind("}")
    if a != -1 and b != -1 and b > a:
        text = text[a:b + 1]
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


def _evidence_block(data: Dict[str, Any]) -> str:
    """Compress the assembled research data into a compact evidence string."""
    signals = data.get("signals") or {}
    snapshot = data.get("snapshot") or {}
    fundamentals = data.get("fundamentals") or {}
    technicals = data.get("technicals") or {}
    analyst = data.get("analyst") or {}
    compact = {
        "price": snapshot.get("price"),
        "composite_signal": {
            "score": signals.get("composite_score"),
            "label": signals.get("signal_label"),
            "categories": {k: v.get("score") for k, v in (signals.get("categories") or {}).items()},
        },
        "fundamentals": fundamentals,
        "technicals": technicals,
        "analyst_targets": analyst,
        "sector": signals.get("sector"),
    }
    try:
        return json.dumps(compact, indent=2, default=str)[:3500]
    except Exception:
        return str(compact)[:3500]


async def _gen(model, prompt: str) -> str:
    try:
        resp = await asyncio.to_thread(model.generate_content, prompt)
        return (getattr(resp, "text", "") or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("debate generation failed: %s", exc)
        return ""


async def run_debate_impl(db, user_id: str, symbol: str) -> Dict[str, Any]:
    """Run a Bull vs Bear debate + Research-Manager verdict for one ticker."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {"ok": False, "error": "symbol is required."}

    try:
        import google.generativeai as genai
        from ai_service import configure_gemini, GEMINI_FLASH
        import multi_agent
        configure_gemini()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"debate unavailable: {exc}"}

    # Reuse the research team's data assembler — same grounded evidence.
    try:
        data = await multi_agent._assemble_data(symbol, db=db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("debate assemble failed: %s", exc)
        data = {}
    evidence = _evidence_block(data)

    model = genai.GenerativeModel(GEMINI_FLASH, safety_settings=multi_agent.SAFETY_OFF)

    # Bull and Bear argue in parallel on identical evidence.
    bull, bear = await asyncio.gather(
        _gen(model, _BULL_PROMPT.format(symbol=symbol, evidence=evidence)),
        _gen(model, _BEAR_PROMPT.format(symbol=symbol, evidence=evidence)),
    )
    if not bull and not bear:
        return {"ok": False, "error": "the debate models returned nothing (check GEMINI_API_KEY)."}

    judge_raw = await _gen(model, _JUDGE_PROMPT.format(
        symbol=symbol, evidence=evidence, bull=bull or "(no bull case)", bear=bear or "(no bear case)"))
    verdict = _parse_json(judge_raw)

    signals = data.get("signals") or {}
    result = {
        "ok": True,
        "symbol": symbol,
        "composite_score": signals.get("composite_score"),
        "signal_label": signals.get("signal_label"),
        "bull_case": bull,
        "bear_case": bear,
        "verdict": verdict.get("verdict"),
        "conviction": verdict.get("conviction"),
        "recommended_action": verdict.get("recommended_action"),
        "key_swing_factor": verdict.get("key_swing_factor"),
        "would_change_my_mind": verdict.get("would_change_my_mind"),
        "summary": verdict.get("summary"),
        "debated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Audit trail — persist every committee decision.
    if db is not None:
        try:
            await db[DEBATE_COLLECTION].insert_one({"user_id": user_id, **result})
        except Exception as exc:  # noqa: BLE001
            logger.warning("debate persist failed: %s", exc)

    return result
