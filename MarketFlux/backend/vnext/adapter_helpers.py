from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from agent_tools import get_fred_macro
from market_data import get_market_overview, get_stock_info

logger = logging.getLogger(__name__)


def _utcnow_zulu() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_timestamp(values: Iterable[Optional[str]]) -> str:
    parsed = [item for item in (_parse_iso(value) for value in values) if item is not None]
    if not parsed:
        return _utcnow_zulu()
    return max(parsed).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_adapter_envelope(*, payload: Dict[str, Any], data_as_of: Optional[str] = None, source: str = "marketflux-live") -> Dict[str, Any]:
    return {
        "data_as_of": data_as_of or _utcnow_zulu(),
        "source": source,
        "payload": payload,
    }


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "N/A", "."):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_index_field(overview: Dict[str, Any], symbol: str, field: str) -> Optional[float]:
    return _safe_float((overview.get(symbol) or {}).get(field))


async def collect_regime_inputs() -> Dict[str, Any]:
    overview, tlt_snapshot, fred_payload = await asyncio.gather(
        get_market_overview(),
        get_stock_info("TLT"),
        get_fred_macro(),
    )

    warnings: List[str] = []
    vix = _extract_index_field(overview, "^VIX", "price")
    sp500_change_percent = _extract_index_field(overview, "^GSPC", "change_percent")
    nasdaq_change_percent = _extract_index_field(overview, "^IXIC", "change_percent")

    tlt_price = _safe_float((tlt_snapshot or {}).get("price"))
    tlt_change_percent = _safe_float((tlt_snapshot or {}).get("change_percent"))
    if not tlt_price or tlt_price <= 0:
        warnings.append("TLT unavailable in current data layer; defaulted bonds_stable to true.")
        logger.warning("Regime inputs: TLT unavailable, defaulting bonds_stable=true")
        tlt_change_percent = None

    unemployment_rate = _safe_float(
        ((fred_payload.get("indicators") or {}).get("Unemployment Rate") or {}).get("latest_value")
    )
    fed_funds_rate = _safe_float(
        ((fred_payload.get("indicators") or {}).get("Fed Funds Rate") or {}).get("latest_value")
    )
    ten_two_spread = _safe_float(
        ((fred_payload.get("indicators") or {}).get("10Y-2Y Yield Spread") or {}).get("latest_value")
    )

    bonds_stable = True if tlt_change_percent is None else abs(tlt_change_percent) <= 0.6
    growth_data_positive = unemployment_rate is not None and unemployment_rate < 4.5 and ten_two_spread is not None and ten_two_spread > -0.5

    source_timestamps = {
        "market_overview": _latest_timestamp(
            (row.get("as_of") for row in (overview or {}).values() if isinstance(row, dict))
        ),
        "tlt": (tlt_snapshot or {}).get("as_of"),
        "fred": fred_payload.get("as_of"),
    }

    data_as_of = _latest_timestamp(source_timestamps.values())

    return {
        "data_as_of": data_as_of,
        "source_timestamps": source_timestamps,
        "vix": vix,
        "sp500_change_percent": sp500_change_percent,
        "nasdaq_change_percent": nasdaq_change_percent,
        "tlt_change_percent": tlt_change_percent,
        "unemployment_rate": unemployment_rate,
        "fed_funds_rate": fed_funds_rate,
        "ten_two_spread": ten_two_spread,
        "bonds_stable": bonds_stable,
        "growth_data_positive": growth_data_positive,
        "warnings": warnings,
    }


def classify_regime(inputs: Dict[str, Any]) -> Dict[str, Any]:
    vix = _safe_float(inputs.get("vix"))
    sp500_change_percent = _safe_float(inputs.get("sp500_change_percent"))
    nasdaq_change_percent = _safe_float(inputs.get("nasdaq_change_percent"))
    bonds_stable = bool(inputs.get("bonds_stable", True))
    growth_data_positive = bool(inputs.get("growth_data_positive", False))
    warnings = list(inputs.get("warnings") or [])

    regime = "mixed_uncertain"
    confidence = 54
    summary = "Inputs are mixed, so the tape remains uncertain until volatility, equity breadth, and macro data align."

    if vix is not None and vix > 25 and ((sp500_change_percent is not None and sp500_change_percent < -1.0) or (nasdaq_change_percent is not None and nasdaq_change_percent < -1.0)):
        regime = "risk_off"
        confidence = 84
        summary = "Volatility is elevated and equity indices are under pressure, which supports a risk-off regime."
    elif vix is not None and vix < 18 and (sp500_change_percent is not None and sp500_change_percent > 0) and bonds_stable:
        regime = "goldilocks"
        confidence = 72
        summary = "Volatility is contained, equities are positive, and bond pricing is stable enough to support a goldilocks regime."
    elif vix is not None and 18 <= vix <= 25 and growth_data_positive:
        regime = "late_cycle"
        confidence = 66
        summary = "Volatility is elevated but not extreme, while macro growth inputs remain constructive, which points to a late-cycle setup."

    if warnings:
        confidence = max(40, confidence - min(8, len(warnings) * 2))

    return {
        "regime": regime,
        "confidence": confidence,
        "summary": summary,
        "signals": {
            "vix": vix,
            "sp500_change_percent": sp500_change_percent,
            "nasdaq_change_percent": nasdaq_change_percent,
            "tlt_change_percent": inputs.get("tlt_change_percent"),
            "bonds_stable": bonds_stable,
            "growth_data_positive": growth_data_positive,
        },
        "warnings": warnings,
    }
