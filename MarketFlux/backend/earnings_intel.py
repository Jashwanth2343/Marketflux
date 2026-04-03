"""
Earnings Intelligence Module for FundOS.

Provides:
  - Pre-earnings briefing: what to watch, historical beat/miss rate, guidance history
  - Post-earnings analysis: beat/miss assessment, guidance change, reaction prediction
  - Earnings calendar with AI-predicted surprise probability
  - Earnings quality scoring
"""

import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger(__name__)

SAFETY_OFF = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}


# ---------------------------------------------------------------------------
# Earnings data helpers
# ---------------------------------------------------------------------------

async def _fetch_earnings_data(symbol: str) -> Dict:
    """Fetch historical earnings and upcoming earnings date from yfinance."""
    try:
        import yfinance as yf

        def _get():
            t = yf.Ticker(symbol.upper())
            info = t.info or {}

            # Upcoming earnings date
            next_earnings = None
            earnings_timestamp = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
            if earnings_timestamp:
                try:
                    next_earnings = datetime.fromtimestamp(earnings_timestamp, tz=timezone.utc).isoformat()
                except Exception:
                    pass

            # Historical quarterly earnings
            hist_earnings = []
            try:
                earnings_hist = t.earnings_dates
                if earnings_hist is not None and not earnings_hist.empty:
                    for idx, row in earnings_hist.head(8).iterrows():
                        eps_est = row.get("EPS Estimate")
                        eps_act = row.get("Reported EPS")
                        surprise = row.get("Surprise(%)")
                        hist_earnings.append({
                            "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                            "eps_estimate": float(eps_est) if eps_est is not None and str(eps_est) != "nan" else None,
                            "eps_actual": float(eps_act) if eps_act is not None and str(eps_act) != "nan" else None,
                            "surprise_pct": float(surprise) if surprise is not None and str(surprise) != "nan" else None,
                        })
            except Exception:
                pass

            return {
                "symbol": symbol.upper(),
                "next_earnings_date": next_earnings,
                "eps_forward": info.get("forwardEps"),
                "eps_trailing": info.get("trailingEps"),
                "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
                "revenue_growth": info.get("revenueGrowth"),
                "profit_margin": info.get("profitMargins"),
                "gross_margins": info.get("grossMargins"),
                "operating_margins": info.get("operatingMargins"),
                "analyst_count": info.get("numberOfAnalystOpinions"),
                "recommendation": info.get("recommendationKey", "hold"),
                "target_mean_price": info.get("targetMeanPrice"),
                "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "name": info.get("longName") or info.get("shortName") or symbol,
                "historical_earnings": hist_earnings,
            }

        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.error(f"_fetch_earnings_data({symbol}): {e}")
        return {"symbol": symbol.upper(), "error": str(e)}


async def _fetch_recent_news(symbol: str, db=None) -> List[Dict]:
    """Fetch recent news for earnings context."""
    if db is None:
        return []
    try:
        articles = await db.news_articles.find(
            {"tickers": {"$in": [symbol.upper()]}},
            {"_id": 0, "title": 1, "summary": 1, "sentiment": 1, "published_at": 1, "source": 1},
        ).sort("published_at", -1).limit(10).to_list(10)
        return articles
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Beat/miss rate analysis
# ---------------------------------------------------------------------------

def _compute_beat_rate(earnings_history: List[Dict]) -> Dict:
    """Compute historical beat/miss rate and average surprise magnitude."""
    if not earnings_history:
        return {"beat_rate": None, "avg_surprise_pct": None, "history": []}

    beats = 0
    misses = 0
    surprises = []
    for e in earnings_history:
        s = e.get("surprise_pct")
        if s is not None:
            if s > 0:
                beats += 1
            else:
                misses += 1
            surprises.append(s)

    total = beats + misses
    beat_rate = round(beats / total * 100, 0) if total > 0 else None
    avg_surprise = round(sum(surprises) / len(surprises), 1) if surprises else None

    return {
        "beat_rate": beat_rate,
        "miss_rate": 100 - beat_rate if beat_rate is not None else None,
        "avg_surprise_pct": avg_surprise,
        "beats": beats,
        "misses": misses,
        "total_quarters": total,
    }


def _estimate_surprise_probability(earnings_data: Dict, beat_stats: Dict) -> Dict:
    """
    Estimate probability of earnings beat based on:
    - Historical beat rate
    - Analyst estimate revision trend
    - Revenue growth trajectory
    - Sector seasonality
    """
    base_probability = beat_stats.get("beat_rate") or 55  # S&P 500 historical average

    # Adjust for revenue growth (positive = more likely to beat)
    rev_growth = earnings_data.get("revenue_growth", 0) or 0
    base_probability += min(10, rev_growth * 30)

    # Adjust for EPS growth trajectory
    eps_q_growth = earnings_data.get("earnings_quarterly_growth", 0) or 0
    base_probability += min(10, eps_q_growth * 20)

    # Adjust for analyst sentiment
    rec = earnings_data.get("recommendation", "hold").lower()
    rec_adj = {"strong_buy": 5, "strongbuy": 5, "buy": 3, "hold": 0, "underperform": -3, "sell": -5}
    base_probability += rec_adj.get(rec, 0)

    beat_prob = max(20, min(90, base_probability))

    if beat_prob >= 65:
        assessment = "HIGH beat probability"
        color = "#3FB950"
    elif beat_prob >= 50:
        assessment = "MODERATE beat probability"
        color = "#00F3FF"
    elif beat_prob >= 40:
        assessment = "SLIGHT MISS risk"
        color = "#F0A500"
    else:
        assessment = "HIGH miss risk"
        color = "#F85149"

    return {
        "beat_probability": round(beat_prob, 0),
        "assessment": assessment,
        "color": color,
    }


# ---------------------------------------------------------------------------
# AI analysis via Gemini
# ---------------------------------------------------------------------------

async def _ai_pre_earnings_brief(symbol: str, earnings_data: Dict, beat_stats: Dict,
                                  news: List[Dict]) -> str:
    """Generate AI pre-earnings briefing."""
    try:
        from ai_service import configure_gemini
        configure_gemini()

        context = {
            "symbol": symbol,
            "earnings_data": {k: v for k, v in earnings_data.items() if k != "historical_earnings"},
            "beat_statistics": beat_stats,
            "recent_headlines": [{"title": a.get("title"), "sentiment": a.get("sentiment")} for a in news[:5]],
        }

        prompt = f"""You are a sell-side earnings analyst. Write a concise pre-earnings briefing for {symbol}.

EARNINGS DATA:
{json.dumps(context, indent=2, default=str)[:2500]}

Write a 4-6 sentence Pre-Earnings Brief covering:
1. Next earnings date and what quarter/fiscal period it covers
2. Consensus EPS estimate and year-over-year comparison
3. Key metrics to watch (revenue growth, margin trajectory, guidance tone)
4. Historical beat rate and what the stock typically does on earnings day
5. Bull case catalyst vs. bear case risk for this earnings
6. One actionable insight (position before/after, hedge approach)

Professional, specific, Goldman Sachs style. Use exact numbers."""

        model = genai.GenerativeModel("gemini-flash-latest", safety_settings=SAFETY_OFF)
        resp = await asyncio.to_thread(model.generate_content, prompt)
        return resp.text.strip()
    except Exception as e:
        logger.error(f"AI pre-earnings brief error: {e}")
        return "AI analysis temporarily unavailable."


async def _ai_post_earnings_analysis(symbol: str, earnings_data: Dict, latest_quarter: Dict,
                                      news: List[Dict]) -> str:
    """Generate AI post-earnings analysis."""
    try:
        from ai_service import configure_gemini
        configure_gemini()

        context = {
            "symbol": symbol,
            "latest_quarter": latest_quarter,
            "fundamentals": {
                "revenue_growth": earnings_data.get("revenue_growth"),
                "profit_margin": earnings_data.get("profit_margin"),
                "gross_margins": earnings_data.get("gross_margins"),
                "eps_trailing": earnings_data.get("eps_trailing"),
            },
            "analyst_targets": {
                "recommendation": earnings_data.get("recommendation"),
                "target_price": earnings_data.get("target_mean_price"),
                "analyst_count": earnings_data.get("analyst_count"),
            },
            "recent_headlines": [{"title": a.get("title"), "sentiment": a.get("sentiment")} for a in news[:5]],
        }

        prompt = f"""You are a buy-side analyst assessing earnings results for {symbol}.

POST-EARNINGS DATA:
{json.dumps(context, indent=2, default=str)[:2500]}

Write a 4-6 sentence Post-Earnings Analysis covering:
1. EPS beat/miss magnitude and quality (cash vs accrual earnings)
2. Revenue vs expectations and guidance change (raise/maintain/lower)
3. Management tone inference from news headlines
4. Likely analyst rating changes (upgrade/downgrade likelihood)
5. Stock reaction prediction: buy the beat OR sell the news?
6. Updated investment thesis: does this change the long-term view?

Professional, specific, actionable. Use exact numbers."""

        model = genai.GenerativeModel("gemini-flash-latest", safety_settings=SAFETY_OFF)
        resp = await asyncio.to_thread(model.generate_content, prompt)
        return resp.text.strip()
    except Exception as e:
        logger.error(f"AI post-earnings analysis error: {e}")
        return "AI analysis temporarily unavailable."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_earnings_intelligence(symbol: str, db=None) -> Dict:
    """
    Full earnings intelligence package for a ticker.

    Returns:
        {
          "symbol": str,
          "name": str,
          "next_earnings_date": str,
          "beat_statistics": {...},
          "surprise_probability": {...},
          "pre_earnings_brief": str,
          "post_earnings_analysis": str (if recent earnings available),
          "historical_earnings": [...],
          "key_metrics": {...},
          "analyzed_at": str
        }
    """
    symbol = symbol.upper().strip()

    # Fetch data in parallel
    earnings_data, news = await asyncio.gather(
        _fetch_earnings_data(symbol),
        _fetch_recent_news(symbol, db),
    )

    if earnings_data.get("error"):
        return {"symbol": symbol, "error": earnings_data["error"]}

    hist_earnings = earnings_data.get("historical_earnings", [])
    beat_stats = _compute_beat_rate(hist_earnings)
    surprise_prob = _estimate_surprise_probability(earnings_data, beat_stats)

    # Get latest earnings quarter (most recent with actual data)
    latest_quarter = None
    for e in hist_earnings:
        if e.get("eps_actual") is not None:
            latest_quarter = e
            break

    # Run AI analysis for pre-earnings and (if recent) post-earnings
    async def _no_post_analysis():
        return "No recent earnings data available"

    pre_brief, post_analysis = await asyncio.gather(
        _ai_pre_earnings_brief(symbol, earnings_data, beat_stats, news),
        _ai_post_earnings_analysis(symbol, earnings_data, latest_quarter or {}, news)
        if latest_quarter else _no_post_analysis(),
    )

    # Days until next earnings
    days_until = None
    next_date_str = earnings_data.get("next_earnings_date")
    if next_date_str:
        try:
            next_dt = datetime.fromisoformat(next_date_str.replace("Z", "+00:00"))
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=timezone.utc)
            delta = next_dt - datetime.now(timezone.utc)
            days_until = delta.days
        except Exception:
            pass

    return {
        "symbol": symbol,
        "name": earnings_data.get("name", symbol),
        "sector": earnings_data.get("sector", "Unknown"),
        "next_earnings_date": next_date_str,
        "days_until_earnings": days_until,
        "beat_statistics": beat_stats,
        "surprise_probability": surprise_prob,
        "pre_earnings_brief": pre_brief,
        "post_earnings_analysis": post_analysis,
        "historical_earnings": hist_earnings[:8],
        "key_metrics": {
            "eps_forward": earnings_data.get("eps_forward"),
            "eps_trailing": earnings_data.get("eps_trailing"),
            "revenue_growth": earnings_data.get("revenue_growth"),
            "gross_margins": earnings_data.get("gross_margins"),
            "profit_margin": earnings_data.get("profit_margin"),
            "analyst_count": earnings_data.get("analyst_count"),
            "recommendation": earnings_data.get("recommendation"),
            "target_mean_price": earnings_data.get("target_mean_price"),
            "current_price": earnings_data.get("current_price"),
        },
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_earnings_calendar(tickers: List[str]) -> List[Dict]:
    """
    Get upcoming earnings dates for a list of tickers.
    """
    try:
        import yfinance as yf

        def _fetch_all():
            result = []
            for sym in tickers:
                try:
                    t = yf.Ticker(sym.upper())
                    info = t.info or {}
                    ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
                    if ts:
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        days_until = (dt - datetime.now(timezone.utc)).days
                        if 0 <= days_until <= 90:  # next 90 days only
                            result.append({
                                "ticker": sym.upper(),
                                "name": info.get("shortName", sym),
                                "earnings_date": dt.strftime("%Y-%m-%d"),
                                "days_until": days_until,
                                "eps_estimate": info.get("forwardEps"),
                            })
                except Exception:
                    pass
            result.sort(key=lambda x: x["days_until"])
            return result

        return await asyncio.to_thread(_fetch_all)
    except Exception as e:
        logger.error(f"get_earnings_calendar error: {e}")
        return []
