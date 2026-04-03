"""
Macro Dashboard Data Module for FundOS.

Provides:
  - Yield curve data (2s10s spread, full curve)
  - Fed Funds Rate / SOFR expectations
  - DXY, Gold, Oil with sector correlation context
  - Economic calendar with AI impact assessment
  - VIX regime classification with playbook
  - FRED macro indicators (CPI, unemployment, GDP growth)
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VIX Regime Classification
# ---------------------------------------------------------------------------

def classify_vix_regime(vix: float) -> Dict:
    """Classify VIX into regime with associated playbook."""
    if vix < 13:
        regime = "CALM"
        label = "Low Volatility"
        color = "#3FB950"
        playbook = [
            "Risk-on environment — favour growth and momentum stocks",
            "Reduce defensive allocation; increase cyclicals and tech",
            "Options are cheap — consider buying protective puts on concentrated positions",
            "Complacency risk: use this window to hedge tail risk cost-effectively",
        ]
    elif vix < 20:
        regime = "NORMAL"
        label = "Normal Volatility"
        color = "#00F3FF"
        playbook = [
            "Balanced risk posture — maintain standard allocations",
            "Single-stock volatility elevated; ensure diversification",
            "Standard options pricing — hedging at normal cost",
            "Watch Fed communications and earnings for potential regime shift",
        ]
    elif vix < 30:
        regime = "ELEVATED"
        label = "Elevated Volatility"
        color = "#F0A500"
        playbook = [
            "Reduce leverage and concentrated positions",
            "Favour quality and defensive sectors (Healthcare, Utilities, Consumer Staples)",
            "Increase cash buffer — prepare to deploy at better prices",
            "Monitor credit spreads; correlation between equities rising",
            "Avoid initiating new speculative positions",
        ]
    elif vix < 40:
        regime = "STRESS"
        label = "Market Stress"
        color = "#F85149"
        playbook = [
            "Capital preservation is priority #1 — reduce gross exposure significantly",
            "Long gold, long Treasuries as portfolio hedge",
            "Avoid illiquid small-caps; bid-ask spreads are wide",
            "Systematic buying opportunity emerging — begin scaling into quality names",
            "Watch for climax selling (VIX spike + volume surge) as potential entry signal",
        ]
    else:
        regime = "PANIC"
        label = "Panic / Extreme Fear"
        color = "#FF0000"
        playbook = [
            "Maximum defensive positioning — cash, gold, short-duration Treasuries",
            "Extreme fear = historically strong forward returns (12-18 months)",
            "Staged buying of highest-quality names; do NOT try to catch falling knives",
            "Correlation across assets spikes to 1 — diversification fails temporarily",
            "Monitor for policy response (Fed pivot, fiscal stimulus) as reversal catalyst",
        ]

    return {
        "vix": vix,
        "regime": regime,
        "label": label,
        "color": color,
        "playbook": playbook,
    }


# ---------------------------------------------------------------------------
# Yield Curve Data
# ---------------------------------------------------------------------------

async def get_yield_curve() -> Dict:
    """
    Fetch US Treasury yield curve from yfinance.
    Returns current yields across maturities + 2s10s spread.
    """
    maturities = {
        "3M": "^IRX",
        "2Y": "^TWOYEAR",
        "5Y": "^FVX",
        "10Y": "^TNX",
        "30Y": "^TYX",
    }

    # Use yfinance tickers for Treasury rates
    treasury_tickers = {
        "3M": "^IRX",
        "2Y": "^TWOYEAR",
        "5Y": "^FVX",
        "10Y": "^TNX",
        "30Y": "^TYX",
    }

    try:
        import yfinance as yf

        def _fetch():
            result = {}
            for label, ticker in treasury_tickers.items():
                try:
                    t = yf.Ticker(ticker)
                    info = t.info
                    price = info.get("regularMarketPrice") or info.get("previousClose")
                    if price:
                        result[label] = round(float(price), 3)
                except Exception:
                    pass
            return result

        yields = await asyncio.to_thread(_fetch)

        if not yields:
            # Fallback: use approximate current values
            yields = {"3M": 5.25, "2Y": 4.90, "5Y": 4.60, "10Y": 4.40, "30Y": 4.55}

        spread_2s10s = None
        if "2Y" in yields and "10Y" in yields:
            spread_2s10s = round(yields["10Y"] - yields["2Y"], 3)

        # Interpret the curve
        if spread_2s10s is not None:
            if spread_2s10s < -0.5:
                curve_label = "DEEPLY INVERTED"
                curve_interpretation = "Strongly inverted curve historically precedes recession within 12-18 months"
                curve_color = "#F85149"
            elif spread_2s10s < 0:
                curve_label = "INVERTED"
                curve_interpretation = "Inverted yield curve — recession risk elevated; watch credit spreads"
                curve_color = "#F0A500"
            elif spread_2s10s < 0.5:
                curve_label = "FLAT"
                curve_interpretation = "Flat curve — economy at potential inflection; uncertainty high"
                curve_color = "#00F3FF"
            else:
                curve_label = "NORMAL"
                curve_interpretation = "Positive slope — economic expansion, healthy credit conditions"
                curve_color = "#3FB950"
        else:
            curve_label = "UNKNOWN"
            curve_interpretation = "Insufficient data"
            curve_color = "#666"

        return {
            "yields": yields,
            "spread_2s10s": spread_2s10s,
            "curve_label": curve_label,
            "curve_interpretation": curve_interpretation,
            "curve_color": curve_color,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"get_yield_curve error: {e}")
        return {"yields": {}, "spread_2s10s": None, "curve_label": "UNKNOWN", "curve_color": "#666"}


# ---------------------------------------------------------------------------
# Key Macro Assets (DXY, Gold, Oil, Bitcoin)
# ---------------------------------------------------------------------------

async def get_macro_assets() -> Dict:
    """Fetch DXY, Gold, Oil, Bitcoin with 1-day change and sector correlations."""
    assets = {
        "DXY": "DX-Y.NYB",
        "GOLD": "GC=F",
        "OIL_WTI": "CL=F",
        "BITCOIN": "BTC-USD",
        "VIX": "^VIX",
        "SP500": "^GSPC",
    }

    correlations = {
        "DXY": "Strong USD → headwind for Emerging Markets, Commodities, Multinationals. Tailwind for US domestic.",
        "GOLD": "Gold rising → risk-off signal, inflation/uncertainty hedge being bid up.",
        "OIL_WTI": "Oil rising → tailwind for Energy, headwind for Airlines, Consumer Discretionary.",
        "BITCOIN": "BTC rising → risk-on sentiment, institutional risk appetite elevated.",
    }

    try:
        import yfinance as yf

        def _fetch():
            result = {}
            for label, ticker in assets.items():
                try:
                    t = yf.Ticker(ticker)
                    info = t.info
                    price = info.get("regularMarketPrice") or info.get("previousClose")
                    prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
                    chg_pct = 0.0
                    if price and prev and prev > 0:
                        chg_pct = round((price - prev) / prev * 100, 2)
                    result[label] = {
                        "price": round(float(price), 2) if price else None,
                        "change_pct": chg_pct,
                        "correlation_note": correlations.get(label, ""),
                    }
                except Exception:
                    pass
            return result

        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"get_macro_assets error: {e}")
        return {}


# ---------------------------------------------------------------------------
# Sector Performance (rolling 1-month)
# ---------------------------------------------------------------------------

async def get_sector_performance() -> List[Dict]:
    """Get 1-month sector performance using SPDR sector ETFs."""
    sector_etfs = {
        "XLK": "Technology",
        "XLF": "Financials",
        "XLV": "Health Care",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLY": "Consumer Disc.",
        "XLP": "Consumer Staples",
        "XLRE": "Real Estate",
        "XLU": "Utilities",
        "XLB": "Materials",
        "XLC": "Communication",
    }

    try:
        import yfinance as yf

        def _fetch():
            results = []
            for etf, name in sector_etfs.items():
                try:
                    t = yf.Ticker(etf)
                    hist = t.history(period="1mo")
                    if not hist.empty and len(hist) >= 2:
                        start_price = float(hist["Close"].iloc[0])
                        end_price = float(hist["Close"].iloc[-1])
                        if start_price > 0:
                            pct = round((end_price - start_price) / start_price * 100, 2)
                            results.append({"etf": etf, "sector": name, "return_1m": pct})
                except Exception:
                    pass
            results.sort(key=lambda x: x["return_1m"], reverse=True)
            return results

        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error(f"get_sector_performance error: {e}")
        return []


# ---------------------------------------------------------------------------
# Economic Calendar (upcoming releases)
# ---------------------------------------------------------------------------

def get_economic_calendar() -> List[Dict]:
    """
    Return a static near-term economic calendar with AI impact assessment.
    In production this would pull from a real calendar API (Finnhub, Quandl).
    """
    now = datetime.now(timezone.utc)

    # Simulate upcoming events based on typical US economic calendar
    events = [
        {
            "event": "FOMC Meeting Minutes",
            "date": (now + timedelta(days=2)).strftime("%Y-%m-%d"),
            "country": "US",
            "importance": "HIGH",
            "impact_assessment": "Markets will scan for any language shift on rate path. Hawkish surprise → equities sell-off, USD rally. Dovish surprise → growth stocks rally.",
        },
        {
            "event": "CPI (Consumer Price Index)",
            "date": (now + timedelta(days=5)).strftime("%Y-%m-%d"),
            "country": "US",
            "importance": "CRITICAL",
            "impact_assessment": "Core CPI above 3.5% → Fed pivot delayed → rate-sensitive sectors (REIT, Utilities) sell off. Below 3% → risk-on, growth stocks benefit.",
        },
        {
            "event": "Nonfarm Payrolls",
            "date": (now + timedelta(days=7)).strftime("%Y-%m-%d"),
            "country": "US",
            "importance": "HIGH",
            "impact_assessment": "Strong jobs (+250K+) → Fed stays hawkish → bonds sell, USD rallies. Weak jobs (<150K) → recession fears, flight to safety.",
        },
        {
            "event": "GDP Growth (Preliminary)",
            "date": (now + timedelta(days=12)).strftime("%Y-%m-%d"),
            "country": "US",
            "importance": "HIGH",
            "impact_assessment": "GDP above 2.5% → soft landing narrative intact → risk assets bid. Below 1% → stagflation/recession fears resurface.",
        },
        {
            "event": "PCE Deflator (Fed's Preferred Inflation Gauge)",
            "date": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
            "country": "US",
            "importance": "CRITICAL",
            "impact_assessment": "PCE is the Fed's primary inflation measure. Core PCE above 2.6% sustains higher-for-longer narrative, pressuring P/E multiples.",
        },
        {
            "event": "ISM Manufacturing PMI",
            "date": (now + timedelta(days=18)).strftime("%Y-%m-%d"),
            "country": "US",
            "importance": "MEDIUM",
            "impact_assessment": "PMI above 50 = expansion. Industrial and Materials sectors outperform. PMI below 45 signals contraction — defensive rotation likely.",
        },
    ]

    return events


# ---------------------------------------------------------------------------
# Full Macro Dashboard
# ---------------------------------------------------------------------------

async def get_macro_dashboard(db=None) -> Dict:
    """
    Assemble the full macro dashboard in parallel.
    Returns yield curve, assets, sectors, VIX regime, and economic calendar.
    """
    # Fetch data in parallel
    yield_curve, assets, sectors = await asyncio.gather(
        get_yield_curve(),
        get_macro_assets(),
        get_sector_performance(),
    )

    # Get VIX value and classify regime
    vix_val = None
    vix_data = assets.get("VIX", {})
    if vix_data.get("price"):
        vix_val = float(vix_data["price"])

    vix_regime = classify_vix_regime(vix_val or 20.0)

    # Fear & Greed index from existing endpoint
    fng_value = 50
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.alternative.me/fng/")
            fng_data = resp.json()
            if fng_data.get("data"):
                fng_value = int(fng_data["data"][0]["value"])
    except Exception:
        pass

    # Economic calendar
    calendar = get_economic_calendar()

    # Macro summary AI insight
    macro_summary = _generate_macro_summary(yield_curve, vix_regime, assets, sectors, fng_value)

    return {
        "yield_curve": yield_curve,
        "assets": assets,
        "sectors": sectors,
        "vix_regime": vix_regime,
        "fear_greed": {"value": fng_value, "label": _fng_label(fng_value)},
        "economic_calendar": calendar,
        "macro_summary": macro_summary,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _fng_label(val: int) -> str:
    if val <= 25:
        return "Extreme Fear"
    elif val <= 45:
        return "Fear"
    elif val <= 55:
        return "Neutral"
    elif val <= 75:
        return "Greed"
    else:
        return "Extreme Greed"


def _generate_macro_summary(yield_curve: dict, vix_regime: dict, assets: dict, sectors: list, fng: int) -> str:
    """Generate a one-paragraph macro summary from the data."""
    curve_label = yield_curve.get("curve_label", "UNKNOWN")
    vix_label = vix_regime.get("label", "Normal Volatility")
    vix_val = vix_regime.get("vix", 20)
    fng_label = _fng_label(fng)

    top_sector = sectors[0]["sector"] if sectors else "Technology"
    bottom_sector = sectors[-1]["sector"] if sectors else "Utilities"

    oil_chg = assets.get("OIL_WTI", {}).get("change_pct", 0) or 0
    gold_chg = assets.get("GOLD", {}).get("change_pct", 0) or 0
    dxy_chg = assets.get("DXY", {}).get("change_pct", 0) or 0

    spread = yield_curve.get("spread_2s10s")
    spread_str = f"{spread:+.2f}%" if spread is not None else "N/A"

    return (
        f"Macro Environment: {curve_label} yield curve (2s10s: {spread_str}) with VIX at {vix_val:.1f} ({vix_label}). "
        f"Sentiment indicators show {fng_label} ({fng}/100). "
        f"Commodity signals: Oil {oil_chg:+.1f}%, Gold {gold_chg:+.1f}%, DXY {dxy_chg:+.1f}%. "
        f"Sector rotation: {top_sector} leading, {bottom_sector} lagging over past month. "
        f"{vix_regime['playbook'][0] if vix_regime.get('playbook') else ''}"
    )
