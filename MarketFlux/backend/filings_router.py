"""FastAPI router exposing the SEC EDGAR full-text layer to the terminal UI.

Read-only, free public data, no auth required — same posture as the market
data endpoints. The copilot reaches these capabilities as agent tools
(sec_filings.*); these routes give the Filings panel direct access.

Hardening (PR #28 review feedback):
  * symbols are validated/normalized before any outbound EDGAR call, so
    garbage paths can't amplify outbound traffic or grow the cache (422)
  * error details returned to clients are the module's own user-facing
    messages; raw exception text never flows out (CodeQL: information
    exposure through an exception)
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Query

import sec_filings

logger = logging.getLogger(__name__)

_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]{0,9}$")

# Module-generated messages that are safe to show users. Anything else
# (e.g. messages embedding low-level exception text) is replaced.
_SAFE_ERROR_MARKERS = (
    "No EDGAR filings found", "No recent", "Need two 10-Ks",
    "Could not locate Item 1A", "Could not download", "symbol is required",
    "form must be", "symbol and query are required",
)


def _clean_symbol(symbol: str) -> str:
    symbol = (symbol or "").strip().upper()
    if not _SYMBOL_RE.match(symbol):
        raise HTTPException(422, "Invalid ticker symbol.")
    return symbol


def _fail(res: dict, fallback: str) -> HTTPException:
    msg = res.get("error") or ""
    if not any(msg.startswith(m) for m in _SAFE_ERROR_MARKERS):
        logger.warning("filings route error (sanitized): %s", msg)
        msg = fallback
    return HTTPException(404, msg)


def build_filings_router() -> APIRouter:
    router = APIRouter(prefix="/api/filings", tags=["filings"])

    @router.get("/{symbol}")
    async def filings_list(symbol: str):
        symbol = _clean_symbol(symbol)
        res = await sec_filings.get_recent_filings(symbol)
        if not res.get("ok"):
            raise _fail(res, f"No EDGAR filings available for {symbol}.")
        return res

    @router.get("/{symbol}/risk-diff")
    async def filings_risk_diff(symbol: str):
        symbol = _clean_symbol(symbol)
        res = await sec_filings.diff_risk_factors(symbol)
        if not res.get("ok"):
            raise _fail(res, f"Risk-factor diff is unavailable for {symbol}.")
        return res

    @router.get("/{symbol}/search")
    async def filings_search(symbol: str, q: str = Query(min_length=2, max_length=200),
                             form: str = "10-K"):
        symbol = _clean_symbol(symbol)
        res = await sec_filings.search_filings(symbol, q, form=form)
        if not res.get("ok"):
            raise _fail(res, f"Filing search is unavailable for {symbol}.")
        return res

    return router
