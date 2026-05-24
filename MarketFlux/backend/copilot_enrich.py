"""Position enrichment for the Copilot sidebar.

Joins the Alpaca paper positions with light fundamentals (sector, analyst
consensus) and a short price history for a sparkline, plus each position's share
of total equity. yfinance lookups are parallelized per symbol and cached (15 min)
so the 30s sidebar refresh stays cheap.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

from vnext import alpaca_client

logger = logging.getLogger(__name__)

_CACHE: Dict[str, tuple] = {}   # symbol -> (ts, enrichment dict)
_TTL = 900  # 15 minutes


def _yf_enrich(symbol: str) -> Dict[str, Any]:
    """Blocking yfinance lookup (run in a thread). Best-effort + cached."""
    cached = _CACHE.get(symbol)
    if cached and (time.time() - cached[0]) < _TTL:
        return cached[1]
    out: Dict[str, Any] = {"sector": None, "industry": None, "analyst": None, "spark": []}
    try:
        import yfinance as yf
        tk = yf.Ticker(symbol)
        try:
            hist = tk.history(period="1mo")
            if hist is not None and not hist.empty:
                out["spark"] = [round(float(c), 2) for c in hist["Close"].tail(20).tolist()]
        except Exception:
            pass
        try:
            info = tk.info or {}
            out["sector"] = info.get("sector")
            out["industry"] = info.get("industry")
            rec = info.get("recommendationKey")  # e.g. strong_buy / buy / hold / sell
            out["analyst"] = rec.replace("_", " ") if isinstance(rec, str) else None
        except Exception:
            pass
    except Exception as exc:
        logger.warning(f"position enrich {symbol} failed: {exc}")
    _CACHE[symbol] = (time.time(), out)
    return out


def _f(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


async def enrich_positions() -> Dict[str, Any]:
    positions, account = await asyncio.gather(
        asyncio.to_thread(alpaca_client.get_positions),
        asyncio.to_thread(alpaca_client.get_account),
    )
    positions = positions or []
    equity = _f((account or {}).get("equity")) or 1.0

    async def _one(p: Dict[str, Any]) -> Dict[str, Any]:
        symbol = p.get("symbol")
        extra = await asyncio.to_thread(_yf_enrich, symbol)
        mv = _f(p.get("market_value"))
        return {
            "symbol": symbol,
            "qty": p.get("qty"),
            "avg_entry_price": p.get("avg_entry_price"),
            "current_price": p.get("current_price"),
            "market_value": p.get("market_value"),
            "unrealized_pl": p.get("unrealized_pl"),
            "unrealized_pl_pct": round(_f(p.get("unrealized_plpc")) * 100, 2),
            "pct_of_equity": round(mv / equity * 100, 1) if equity else 0,
            "sector": extra.get("sector"),
            "industry": extra.get("industry"),
            "analyst": extra.get("analyst"),
            "spark": extra.get("spark") or [],
        }

    items = await asyncio.gather(*[_one(p) for p in positions]) if positions else []
    return {"items": list(items), "equity": equity}
