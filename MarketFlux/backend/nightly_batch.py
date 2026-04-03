"""
Nightly Pre-Computation Pipeline for FundOS.

Runs as a background batch job (can be triggered via API or cron).
Pre-generates:
  - Research memos for all watchlisted stocks
  - Morning briefing for all active users
  - Sector rotation analysis
  - Anomaly detection across S&P 1500 universe

Results are cached in MongoDB for instant retrieval during the day.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Representative S&P 500 universe (large-caps for scanning)
# ---------------------------------------------------------------------------
SP500_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "UNH", "LLY",
    "JPM", "V", "XOM", "MA", "AVGO", "PG", "HD", "CVX", "MRK", "ABBV",
    "COST", "ORCL", "AMD", "NFLX", "ADBE", "CRM", "ACN", "BAC", "PEP", "TMO",
    "INTC", "QCOM", "WMT", "DIS", "VZ", "T", "CSCO", "MCD", "NKE", "IBM",
    "GS", "MS", "GE", "CAT", "HON", "UPS", "RTX", "DE", "BA", "MMM",
    "AMT", "CCI", "PLD", "SPG", "EQIX", "WFC", "USB", "C", "AXP", "BLK",
]

# Thematic baskets for sector analysis
THEMATIC_BASKETS = {
    "AI Infrastructure": ["NVDA", "AMD", "INTC", "AVGO", "QCOM", "TSM", "SMCI", "ANET", "PANW"],
    "Clean Energy": ["NEE", "ENPH", "SEDG", "FSLR", "GEV", "PLUG", "BE", "HASI"],
    "Healthcare Innovation": ["LLY", "ABBV", "MRNA", "REGN", "GILD", "BMY", "AMGN", "BIIB"],
    "Big Tech": ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "NFLX"],
    "Financials": ["JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "V", "MA"],
    "Commodities & Materials": ["XOM", "CVX", "COP", "SLB", "FCX", "NEM", "GOLD"],
}


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

async def detect_anomalies(tickers: List[str], db=None) -> List[Dict]:
    """
    Scan tickers for anomalies:
    - Unusual volume (>2x 20-day average)
    - Price breakouts (new 52w high or 20-day high)
    - RSI extremes (>75 or <25)
    - Insider cluster activity
    """
    try:
        import yfinance as yf

        semaphore = asyncio.Semaphore(5)

        async def _scan_one(sym: str) -> Optional[Dict]:
            async with semaphore:
                try:
                    def _fetch():
                        t = yf.Ticker(sym.upper())
                        hist = t.history(period="1y")
                        info = t.info or {}
                        return hist, info

                    hist, info = await asyncio.to_thread(_fetch)
                    if hist.empty or len(hist) < 22:
                        return None

                    closes = hist["Close"]
                    volumes = hist["Volume"]
                    cur_price = float(closes.iloc[-1])
                    cur_vol = float(volumes.iloc[-1])
                    avg_vol_20 = float(volumes.tail(21).iloc[:-1].mean())
                    vol_ratio = cur_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

                    # 52w metrics
                    high_52w = float(closes.tail(252).max()) if len(closes) >= 252 else float(closes.max())
                    low_52w = float(closes.tail(252).min()) if len(closes) >= 252 else float(closes.min())

                    # RSI 14
                    delta = closes.diff()
                    gain = delta.where(delta > 0, 0).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    rsi_series = 100 - (100 / (1 + rs))
                    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

                    # 1-day change
                    change_1d = float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100) if len(closes) >= 2 else 0

                    anomalies = []

                    if vol_ratio >= 2.0:
                        direction = "surge up" if change_1d > 0 else "heavy selling"
                        anomalies.append(f"Volume {vol_ratio:.1f}x avg ({direction})")

                    if cur_price >= high_52w * 0.99:
                        anomalies.append("At/near 52-week high — breakout")

                    if cur_price <= low_52w * 1.01:
                        anomalies.append("At/near 52-week low — breakdown risk")

                    if rsi >= 75:
                        anomalies.append(f"RSI {rsi:.0f} — overbought")

                    if rsi <= 25:
                        anomalies.append(f"RSI {rsi:.0f} — oversold, potential reversal")

                    # Large 1-day move
                    if abs(change_1d) >= 5:
                        anomalies.append(f"Large 1-day move: {change_1d:+.1f}%")

                    if not anomalies:
                        return None

                    return {
                        "ticker": sym.upper(),
                        "name": info.get("shortName", sym),
                        "sector": info.get("sector", "Unknown"),
                        "price": round(cur_price, 2),
                        "change_1d_pct": round(change_1d, 2),
                        "volume_ratio": round(vol_ratio, 1),
                        "rsi": round(rsi, 0),
                        "anomalies": anomalies,
                        "anomaly_count": len(anomalies),
                        "detected_at": datetime.now(timezone.utc).isoformat(),
                    }
                except Exception:
                    return None

        tasks = [_scan_one(t) for t in tickers]
        results = await asyncio.gather(*tasks)
        anomalies_found = [r for r in results if r is not None]
        anomalies_found.sort(key=lambda x: -x["anomaly_count"])
        return anomalies_found

    except Exception as e:
        logger.error(f"detect_anomalies error: {e}")
        return []


# ---------------------------------------------------------------------------
# Sector Rotation Analysis
# ---------------------------------------------------------------------------

async def analyze_sector_rotation() -> Dict:
    """
    Analyse sector rotation using SPDR ETFs.
    Returns relative performance, momentum, and rotation signals.
    """
    sector_etfs = {
        "XLK": "Technology",
        "XLF": "Financials",
        "XLV": "Health Care",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLY": "Consumer Discretionary",
        "XLP": "Consumer Staples",
        "XLRE": "Real Estate",
        "XLU": "Utilities",
        "XLB": "Materials",
        "XLC": "Communication",
    }

    try:
        import yfinance as yf

        def _fetch_sectors():
            results = []
            for etf, name in sector_etfs.items():
                try:
                    t = yf.Ticker(etf)
                    hist = t.history(period="3mo")
                    if hist.empty or len(hist) < 22:
                        continue

                    closes = hist["Close"]
                    cur = float(closes.iloc[-1])
                    ret_1m = float((closes.iloc[-1] - closes.iloc[-22]) / closes.iloc[-22] * 100) if len(closes) >= 22 else 0
                    ret_3m = float((closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0] * 100)

                    # Momentum: recent 10d vs 1m
                    ret_10d = float((closes.iloc[-1] - closes.iloc[-11]) / closes.iloc[-11] * 100) if len(closes) >= 11 else 0
                    accel = ret_10d - ret_1m / 2  # positive = accelerating

                    results.append({
                        "etf": etf,
                        "sector": name,
                        "return_1m": round(ret_1m, 2),
                        "return_3m": round(ret_3m, 2),
                        "return_10d": round(ret_10d, 2),
                        "momentum_acceleration": round(accel, 2),
                    })
                except Exception:
                    pass
            return results

        sectors = await asyncio.to_thread(_fetch_sectors)

        # Sort by 1m return
        sectors.sort(key=lambda x: x["return_1m"], reverse=True)

        # Classify rotation phase
        top_sectors = [s["sector"] for s in sectors[:3]]
        bottom_sectors = [s["sector"] for s in sectors[-3:]]

        # Simple rotation signal based on which sectors lead
        if "Technology" in top_sectors and "Consumer Discretionary" in top_sectors:
            rotation_phase = "RISK-ON"
            rotation_note = "Growth sectors leading — risk appetite elevated, momentum/growth positioning favored"
        elif "Utilities" in top_sectors or "Consumer Staples" in top_sectors:
            rotation_phase = "RISK-OFF"
            rotation_note = "Defensive sectors leading — recession/uncertainty hedging in progress"
        elif "Energy" in top_sectors or "Materials" in top_sectors:
            rotation_phase = "REFLATION"
            rotation_note = "Commodities/cyclicals leading — inflation or recovery trade in play"
        elif "Financials" in top_sectors:
            rotation_phase = "RATE-SENSITIVE"
            rotation_note = "Financials outperforming — rate expectations shifting, curve steepening"
        else:
            rotation_phase = "MIXED"
            rotation_note = "No clear sector leadership — market in consolidation"

        return {
            "sectors": sectors,
            "top_sectors": top_sectors,
            "bottom_sectors": bottom_sectors,
            "rotation_phase": rotation_phase,
            "rotation_note": rotation_note,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"analyze_sector_rotation error: {e}")
        return {"error": str(e), "sectors": []}


# ---------------------------------------------------------------------------
# Morning Briefing
# ---------------------------------------------------------------------------

async def generate_morning_briefing(db=None) -> Dict:
    """
    Generate the daily morning briefing with:
    - Pre-market key moves
    - Top anomalies from overnight scan
    - Sector rotation signal
    - Macro context
    - Top 5 opportunities from signal scan
    """
    try:
        from macro_data import get_macro_dashboard
        from signal_engine import scan_universe

        # Run everything in parallel
        macro_task = get_macro_dashboard(db)
        anomaly_task = detect_anomalies(SP500_WATCHLIST[:50], db)  # Top 50 for speed
        sector_task = analyze_sector_rotation()
        signal_task = scan_universe(SP500_WATCHLIST[:30], db, concurrency=3)

        macro, anomalies, sectors, signals = await asyncio.gather(
            macro_task, anomaly_task, sector_task, signal_task,
            return_exceptions=True,
        )

        # Safe fallbacks for exceptions
        macro = macro if not isinstance(macro, Exception) else {}
        anomalies = anomalies if not isinstance(anomalies, Exception) else []
        sectors = sectors if not isinstance(sectors, Exception) else {}
        signals = signals if not isinstance(signals, Exception) else []

        # Top signals (strong buy/sell)
        top_buys = [s for s in signals if s.get("signal_label") in ("STRONG BUY", "BUY")][:5]
        top_sells = [s for s in signals if s.get("signal_label") in ("STRONG SELL", "SELL")][:5]

        vix_regime = macro.get("vix_regime", {})
        fear_greed = macro.get("fear_greed", {})
        yield_curve = macro.get("yield_curve", {})

        briefing = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "market_conditions": {
                "vix_regime": vix_regime.get("label", "Unknown"),
                "vix_value": vix_regime.get("vix"),
                "fear_greed": fear_greed.get("value"),
                "fear_greed_label": fear_greed.get("label"),
                "yield_curve": yield_curve.get("curve_label"),
                "spread_2s10s": yield_curve.get("spread_2s10s"),
                "macro_summary": macro.get("macro_summary", ""),
            },
            "sector_rotation": {
                "phase": sectors.get("rotation_phase", "MIXED"),
                "note": sectors.get("rotation_note", ""),
                "top_sectors": sectors.get("top_sectors", []),
                "bottom_sectors": sectors.get("bottom_sectors", []),
            },
            "anomalies": anomalies[:10],
            "top_buys": [
                {
                    "ticker": s["symbol"],
                    "name": s.get("name", ""),
                    "score": s["composite_score"],
                    "label": s["signal_label"],
                    "sector": s.get("sector", ""),
                }
                for s in top_buys
            ],
            "top_sells": [
                {
                    "ticker": s["symbol"],
                    "name": s.get("name", ""),
                    "score": s["composite_score"],
                    "label": s["signal_label"],
                    "sector": s.get("sector", ""),
                }
                for s in top_sells
            ],
            "today_playbook": vix_regime.get("playbook", [])[:3] if vix_regime else [],
        }

        # Store in MongoDB
        if db is not None:
            try:
                await db.morning_briefings.replace_one(
                    {"date": briefing["date"]},
                    briefing,
                    upsert=True,
                )
                logger.info(f"Morning briefing stored for {briefing['date']}")
            except Exception as e:
                logger.error(f"Failed to store morning briefing: {e}")

        return briefing

    except Exception as e:
        logger.error(f"generate_morning_briefing error: {e}")
        return {"error": str(e), "generated_at": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Thematic Research Engine
# ---------------------------------------------------------------------------

async def run_thematic_research(theme: str, db=None) -> Dict:
    """
    Given a theme (e.g. 'AI infrastructure'), identify related tickers,
    score them, and produce a long/short idea list.
    """
    from ai_service import configure_gemini
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold

    SAFETY_OFF = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    try:
        configure_gemini()

        # Step 1: Check predefined baskets
        tickers = None
        theme_lower = theme.lower()
        for basket_name, basket_tickers in THEMATIC_BASKETS.items():
            if any(word in theme_lower for word in basket_name.lower().split()):
                tickers = basket_tickers
                break

        # Step 2: If not in baskets, use AI to identify tickers
        if not tickers:
            model = genai.GenerativeModel("gemini-flash-latest", safety_settings=SAFETY_OFF)
            ticker_prompt = f"""You are a sector expert. List 10-15 US-listed stock tickers most directly exposed to the theme: "{theme}"

Include companies across the value chain (pure plays AND beneficiaries).
Return ONLY a JSON array of ticker symbols, nothing else.
Example: ["NVDA", "AMD", "INTC", "TSM"]"""

            resp = await asyncio.to_thread(model.generate_content, ticker_prompt)
            text = resp.text.strip()
            # Parse JSON
            import re
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                tickers = json.loads(match.group())
            else:
                tickers = SP500_WATCHLIST[:10]

        # Step 3: Score all tickers
        from signal_engine import scan_universe
        scored = await scan_universe(tickers[:15], db=db, concurrency=3)

        # Step 4: AI narrative for the theme
        context = {
            "theme": theme,
            "top_scored": [
                {"ticker": s["symbol"], "score": s["composite_score"], "label": s["signal_label"],
                 "sector": s.get("sector", "")}
                for s in scored[:8]
            ],
        }

        model2 = genai.GenerativeModel("gemini-flash-latest", safety_settings=SAFETY_OFF)
        narrative_prompt = f"""Write a concise thematic investment brief for: "{theme}"

SCORED UNIVERSE:
{json.dumps(context, indent=2, default=str)}

Write 4-6 sentences covering:
1. Theme definition and investment case
2. Key growth drivers (next 12-18 months)
3. Top 3 long ideas with brief rationale
4. Top 1-2 short/avoid ideas with brief rationale
5. Key risks to the theme
6. Positioning recommendation (early cycle / peak / late)

Professional, Goldman Sachs style. Be specific."""

        resp2 = await asyncio.to_thread(model2.generate_content, narrative_prompt)
        narrative = resp2.text.strip()

        return {
            "theme": theme,
            "tickers_analyzed": [s["symbol"] for s in scored],
            "top_longs": [s for s in scored if s["composite_score"] >= 20][:5],
            "top_shorts": [s for s in scored if s["composite_score"] <= -20][:3],
            "neutral": [s for s in scored if -20 < s["composite_score"] < 20][:3],
            "narrative": narrative,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"run_thematic_research error: {e}")
        return {"theme": theme, "error": str(e)}
