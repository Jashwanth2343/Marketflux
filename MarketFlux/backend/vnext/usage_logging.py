from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_usage_metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    usage = payload.get("usage") or {}
    prompt_tokens = _to_int(
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or usage.get("promptTokenCount")
        or usage.get("inputTokenCount")
    )
    completion_tokens = _to_int(
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or usage.get("completionTokenCount")
        or usage.get("outputTokenCount")
    )
    total_tokens = _to_int(
        usage.get("total_tokens")
        or usage.get("totalTokenCount")
        or ((prompt_tokens or 0) + (completion_tokens or 0) if prompt_tokens is not None or completion_tokens is not None else None)
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "raw_usage": usage,
    }


def estimate_cost_usd(model_info: Optional[Dict[str, Any]], usage: Dict[str, Any]) -> Optional[float]:
    if not model_info:
        return None

    pricing = model_info.get("pricing") or {}
    prompt_rate = _to_float(pricing.get("prompt"))
    completion_rate = _to_float(pricing.get("completion"))
    if prompt_rate is None and completion_rate is None:
        return None

    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    if prompt_tokens is None and completion_tokens is None:
        return None

    prompt_cost = ((prompt_tokens or 0) / 1_000_000) * (prompt_rate or 0)
    completion_cost = ((completion_tokens or 0) / 1_000_000) * (completion_rate or 0)
    cost = prompt_cost + completion_cost
    return round(cost, 6)


def build_usage_event(
    *,
    provider: str,
    model_id: str,
    request_purpose: str,
    payload: Dict[str, Any],
    model_info: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    usage = extract_usage_metrics(payload)
    return {
        "session_id": session_id,
        "owner_user_id": owner_user_id,
        "provider": provider,
        "model_id": model_id,
        "request_purpose": request_purpose,
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
        "estimated_cost_usd": estimate_cost_usd(model_info, usage),
        "raw_usage": usage["raw_usage"],
        "created_at": _utcnow_iso(),
    }
