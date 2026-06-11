"""Market Regime Radar — classify the current tape so the copilot can adapt.

A god-tier PM never sizes the same way in a calm uptrend as in a high-vol
downtrend. This module reads SPY trend, the VIX volatility band, and sector
breadth, and distils them into a single regime label + a concrete playbook
(suggested gross exposure, posture). The agent calls it via the
``get_market_regime`` tool and conditions its recommendations on the result.

The classification (`classify_regime`) is a **pure** function — deterministic and
unit-tested. Only `compute_regime` touches the network (one batched yfinance
download for SPY, ^VIX, and the sector ETFs).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# S&P sector SPDR ETFs — breadth = share trading above their own 50-day average.
SECTOR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLI", "XLP", "XLU", "XLB", "XLRE", "XLC"]


def _sma(values: List[float], n: int) -> Optional[float]:
    if len(values) < n or n <= 0:
        return None
    return sum(values[-n:]) / n


def classify_regime(spy_closes: List[float], vix: Optional[float],
                    breadth_pct: Optional[float]) -> Dict:
    """Classify the market regime from SPY closes, the VIX level, and breadth.

    Pure & deterministic. Returns the regime label, the component reads, a
    risk_state (risk-on / neutral / risk-off), a suggested gross-exposure band,
    and a one-line playbook.
    """
    cur = spy_closes[-1] if spy_closes else None
    sma50 = _sma(spy_closes, 50)
    sma200 = _sma(spy_closes, 200)

    # --- trend ---
    if cur and sma50 and sma200:
        if cur > sma50 > sma200:
            trend = "uptrend"
        elif cur < sma50 < sma200:
            trend = "downtrend"
        else:
            trend = "sideways"
        trend_strength = round((cur - sma200) / sma200 * 100, 1)
    else:
        trend, trend_strength = "unknown", None

    # --- volatility band ---
    if vix is None:
        vix_band = "unknown"
    elif vix < 15:
        vix_band = "calm"
    elif vix < 20:
        vix_band = "normal"
    elif vix < 28:
        vix_band = "elevated"
    else:
        vix_band = "stressed"

    # --- risk state (combine vol + trend + breadth) ---
    score = 0  # positive = risk-on
    score += {"calm": 2, "normal": 1, "elevated": -1, "stressed": -3, "unknown": 0}[vix_band]
    score += {"uptrend": 2, "sideways": 0, "downtrend": -2, "unknown": 0}[trend]
    if breadth_pct is not None:
        score += 1 if breadth_pct >= 60 else (-1 if breadth_pct <= 40 else 0)

    if score >= 3:
        risk_state, exposure, posture = "risk-on", "90-100%", "Press winners; momentum and high-beta work here."
    elif score >= 1:
        risk_state, exposure, posture = "constructive", "70-90%", "Lean long but keep some dry powder; favour quality."
    elif score >= -1:
        risk_state, exposure, posture = "neutral", "50-70%", "Balanced; demand a higher conviction score before sizing up."
    elif score >= -3:
        risk_state, exposure, posture = "cautious", "30-50%", "De-risk; trim high-beta, add hedges, tighten stops."
    else:
        risk_state, exposure, posture = "risk-off", "10-30%", "Defensive; cash, low-beta, and hedges. Avoid new longs."

    label_trend = {"uptrend": "Uptrend", "downtrend": "Downtrend", "sideways": "Range", "unknown": "Unclear"}[trend]
    vix_str = "" if vix_band == "unknown" else f" · {vix_band} vol"
    regime_label = f"{risk_state.title()} {label_trend}{vix_str}"

    return {
        "regime_label": regime_label,
        "risk_state": risk_state,
        "spy_trend": trend,
        "trend_strength_pct": trend_strength,
        "vix": round(vix, 1) if vix is not None else None,
        "vix_band": vix_band,
        "breadth_pct": round(breadth_pct, 0) if breadth_pct is not None else None,
        "suggested_gross_exposure": exposure,
        "playbook": posture,
        "score": score,
    }


async def compute_regime() -> Dict:
    """Fetch market data and classify the current regime. Network-bound."""
    try:
        import yfinance as yf

        def _fetch():
            tickers = ["SPY", "^VIX"] + SECTOR_ETFS
            df = yf.download(tickers, period="1y", interval="1d",
                             progress=False, auto_adjust=True)
            return df["Close"] if "Close" in df else df

        closes = await asyncio.to_thread(_fetch)
    except Exception as exc:  # noqa: BLE001
        logger.warning("compute_regime fetch failed: %s", exc)
        return {"ok": False, "error": f"could not fetch market data: {exc}"}

    try:
        spy = [float(x) for x in closes["SPY"].dropna().tolist()]
        vix_series = closes["^VIX"].dropna()
        vix = float(vix_series.iloc[-1]) if len(vix_series) else None

        # Breadth: share of sector ETFs trading above their own 50-day SMA.
        above = 0
        counted = 0
        for etf in SECTOR_ETFS:
            try:
                s = [float(x) for x in closes[etf].dropna().tolist()]
                sma50 = _sma(s, 50)
                if sma50 and s:
                    counted += 1
                    if s[-1] > sma50:
                        above += 1
            except Exception:
                continue
        breadth_pct = (above / counted * 100) if counted else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("compute_regime parse failed: %s", exc)
        return {"ok": False, "error": f"could not parse market data: {exc}"}

    result = classify_regime(spy, vix, breadth_pct)
    result["ok"] = True
    result["computed_at"] = datetime.now(timezone.utc).isoformat()
    return result
