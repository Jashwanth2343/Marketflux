"""
Quantitative Signal Library for FundOS (MarketFlux Hedge Fund Edition).

Computes 20+ institutional-grade signals across five categories:
  - Momentum: price momentum (3/6/12m), earnings revision, analyst upgrade momentum
  - Value: EV/EBITDA z-score, FCF yield, price-to-book
  - Quality: ROIC trend, Piotroski F-score, accruals ratio (earnings quality)
  - Sentiment: insider buy/sell ratio, news sentiment 30d MA, short interest
  - Technical: 52w high/low proximity, RSI divergence, golden/death cross, volume surge

Each raw signal is normalised to [-100, +100].
Composite score = weighted average across all categories.
"""

import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weights for composite score
# ---------------------------------------------------------------------------
CATEGORY_WEIGHTS = {
    "momentum": 0.25,
    "value": 0.20,
    "quality": 0.20,
    "sentiment": 0.20,
    "technical": 0.15,
}

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
def _clamp(val: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _pct_to_score(pct: float, scale: float = 1.0) -> float:
    """
    Convert a percentage change into a [-100, 100] score.
    E.g. +25% change with scale=25 → score ≈ 100.
    """
    return _clamp(pct * (100.0 / scale))


# ===========================================================================
# DATA HELPERS  (thin wrappers around yfinance / existing tools)
# ===========================================================================

async def _fetch_history(symbol: str, period: str = "1y"):
    """Return yfinance price history dataframe via thread executor."""
    try:
        import yfinance as yf

        def _get():
            t = yf.Ticker(symbol.upper())
            return t.history(period=period)

        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"_fetch_history({symbol}): {e}")
        return None


async def _fetch_info(symbol: str) -> dict:
    try:
        import yfinance as yf

        def _get():
            return yf.Ticker(symbol.upper()).info or {}

        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"_fetch_info({symbol}): {e}")
        return {}


async def _fetch_financials(symbol: str) -> Tuple[dict, dict]:
    """Return (income_stmt dict, balance_sheet dict) as flattened dicts."""
    try:
        import yfinance as yf

        def _get():
            t = yf.Ticker(symbol.upper())
            income = t.income_stmt
            balance = t.balance_sheet
            income_d = {} if income is None or income.empty else income.iloc[:, 0].to_dict()
            balance_d = {} if balance is None or balance.empty else balance.iloc[:, 0].to_dict()
            # Normalise numeric keys
            income_d = {str(k): v for k, v in income_d.items()}
            balance_d = {str(k): v for k, v in balance_d.items()}
            return income_d, balance_d

        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"_fetch_financials({symbol}): {e}")
        return {}, {}


async def _fetch_insider_txns(symbol: str) -> List[dict]:
    """Fetch recent insider transactions (reusing existing agent tool)."""
    try:
        from agent_tools import get_insider_transactions
        data = await get_insider_transactions(symbol)
        return data.get("transactions", [])
    except Exception:
        return []


async def _fetch_news_sentiment(symbol: str, db=None) -> List[dict]:
    """Fetch recent news sentiment records from MongoDB."""
    if db is None:
        return []
    try:
        articles = await db.news_articles.find(
            {"tickers": {"$in": [symbol.upper()]}, "sentiment": {"$ne": None}},
            {"_id": 0, "sentiment": 1, "sentiment_score": 1, "published_at": 1},
        ).sort("published_at", -1).limit(60).to_list(60)
        return articles
    except Exception as e:
        logger.warning(f"_fetch_news_sentiment({symbol}): {e}")
        return []


# ===========================================================================
# MOMENTUM SIGNALS
# ===========================================================================

async def _momentum_signals(symbol: str, info: dict, hist) -> Dict:
    """
    Price momentum at 3, 6, 12-month horizons.
    Earnings revision (forward EPS estimate change, proxied by forward PE shift).
    Analyst upgrade momentum (recommendation key → score delta).
    """
    signals = {}

    if hist is not None and not hist.empty:
        closes = hist["Close"]
        cur = float(closes.iloc[-1]) if len(closes) else None

        def _mom(n_days: int, label: str):
            if len(closes) > n_days and cur:
                old = float(closes.iloc[-n_days])
                if old > 0:
                    pct = (cur - old) / old * 100
                    signals[label] = _pct_to_score(pct, scale=30)  # 30% move → score ~100
            else:
                signals[label] = 0.0

        _mom(63, "price_mom_3m")   # ~63 trading days
        _mom(126, "price_mom_6m")  # ~126
        _mom(252, "price_mom_12m") # ~252

    # Analyst recommendation → proxy for analyst momentum
    rec = info.get("recommendationKey", "hold").lower()
    rec_map = {
        "strong_buy": 80, "buy": 50, "hold": 0, "underperform": -50, "sell": -80,
        "strongbuy": 80, "strongsell": -80,
    }
    signals["analyst_momentum"] = float(rec_map.get(rec, 0))

    # EPS growth YoY → forward earnings revision proxy
    eps_current = info.get("trailingEps", 0) or 0
    eps_fwd = info.get("forwardEps", 0) or 0
    if eps_current and eps_fwd:
        rev_pct = (eps_fwd - eps_current) / abs(eps_current) * 100 if eps_current != 0 else 0
        signals["earnings_revision"] = _pct_to_score(rev_pct, scale=20)
    else:
        signals["earnings_revision"] = 0.0

    return signals


# ===========================================================================
# VALUE SIGNALS
# ===========================================================================

async def _value_signals(symbol: str, info: dict) -> Dict:
    """
    FCF yield, EV/EBITDA, P/B, PEG ratio signals.
    """
    signals = {}

    # Free cash flow yield (FCF / Market Cap)
    fcf = info.get("freeCashflow", 0) or 0
    mktcap = info.get("marketCap", 0) or 0
    if mktcap > 0 and fcf:
        fcf_yield_pct = fcf / mktcap * 100
        # 8%+ FCF yield → highly attractive → +100; negative → -100
        signals["fcf_yield"] = _clamp(fcf_yield_pct * 12.5)
    else:
        signals["fcf_yield"] = 0.0

    # EV / EBITDA  (lower = better value; benchmark 10-15x typical)
    ev = info.get("enterpriseValue", 0) or 0
    ebitda = info.get("ebitda", 0) or 0
    if ebitda and ebitda > 0 and ev > 0:
        ev_ebitda = ev / ebitda
        # 10x → neutral; <7x → bullish (+80); >20x → bearish (-80)
        score = _clamp(-(ev_ebitda - 10) * 8)
        signals["ev_ebitda"] = score
    else:
        signals["ev_ebitda"] = 0.0

    # Price-to-Book
    pb = info.get("priceToBook", None)
    if pb is not None and pb > 0:
        # <1 → very cheap (+100); >5 → expensive (-60)
        score = _clamp((2.5 - pb) * 30)
        signals["price_to_book"] = score
    else:
        signals["price_to_book"] = 0.0

    # PEG ratio (P/E divided by growth rate)
    peg = info.get("pegRatio", None)
    if peg and peg > 0:
        # PEG < 1 → attractive (+80); PEG > 3 → expensive (-80)
        score = _clamp((1.5 - peg) * 50)
        signals["peg_ratio"] = score
    else:
        signals["peg_ratio"] = 0.0

    return signals


# ===========================================================================
# QUALITY SIGNALS
# ===========================================================================

async def _quality_signals(symbol: str, info: dict, income: dict, balance: dict) -> Dict:
    """
    ROIC trend, Piotroski F-score (simplified), accruals ratio (earnings quality).
    """
    signals = {}

    # Return on equity trend (using ROE as ROIC proxy)
    roe = info.get("returnOnEquity", None)
    if roe is not None:
        # ROE > 20% → strong (+80); negative → bearish
        signals["roe_quality"] = _clamp(roe * 400)  # 0.25 → 100
    else:
        signals["roe_quality"] = 0.0

    # Return on assets
    roa = info.get("returnOnAssets", None)
    if roa is not None:
        signals["roa_quality"] = _clamp(roa * 1000)  # 0.10 → 100
    else:
        signals["roa_quality"] = 0.0

    # Earnings quality: operating cash flow > net income (accruals ratio)
    # High accruals → earnings manipulation risk
    op_cf = info.get("operatingCashflow", 0) or 0
    net_income = info.get("netIncomeToCommon", 0) or 0
    if net_income and net_income != 0:
        accruals_ratio = (net_income - op_cf) / abs(net_income)
        # Low accruals → high quality; negative accruals ratio → great
        signals["earnings_quality"] = _clamp(-accruals_ratio * 100)
    else:
        signals["earnings_quality"] = 0.0

    # Debt-to-equity quality
    de = info.get("debtToEquity", None)
    if de is not None and de >= 0:
        # Low debt → quality premium; D/E > 200 → -80
        signals["debt_quality"] = _clamp(50 - de * 0.5)
    else:
        signals["debt_quality"] = 0.0

    # Gross margin stability (proxy for moat)
    gm = info.get("grossMargins", None)
    if gm is not None:
        # >50% GM → wide moat indicator (+80); <10% → commodity (-60)
        signals["gross_margin_quality"] = _clamp((gm - 0.10) * 200)
    else:
        signals["gross_margin_quality"] = 0.0

    # Simplified Piotroski F-score (3 criteria we can easily measure)
    f_score = 0
    if (info.get("returnOnAssets") or 0) > 0:
        f_score += 1
    if (info.get("operatingCashflow") or 0) > 0:
        f_score += 1
    if (info.get("currentRatio") or 0) > 1:
        f_score += 1
    if (info.get("revenueGrowth") or 0) > 0:
        f_score += 1
    if (info.get("grossMargins") or 0) > 0.20:
        f_score += 1
    signals["piotroski_f"] = _clamp((f_score - 2.5) * 40)  # score 5 → +100, 0 → -100

    return signals


# ===========================================================================
# SENTIMENT SIGNALS
# ===========================================================================

async def _sentiment_signals(symbol: str, info: dict, db=None) -> Dict:
    """
    News sentiment 30d MA, insider net buy ratio.
    """
    signals = {}

    # News sentiment from MongoDB
    articles = await _fetch_news_sentiment(symbol, db)
    if articles:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        recent = []
        for a in articles:
            pub = a.get("published_at")
            if isinstance(pub, str):
                try:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    if pub_dt >= cutoff:
                        recent.append(a)
                except Exception:
                    recent.append(a)
            elif isinstance(pub, datetime):
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if pub >= cutoff:
                    recent.append(a)

        if recent:
            sent_map = {"Positive": 1, "Negative": -1, "Neutral": 0}
            scores = [sent_map.get(a.get("sentiment", "Neutral"), 0) for a in recent]
            avg = sum(scores) / len(scores) if scores else 0
            signals["news_sentiment_30d"] = _clamp(avg * 80)
        else:
            signals["news_sentiment_30d"] = 0.0
    else:
        signals["news_sentiment_30d"] = 0.0

    # Insider net buying ratio
    try:
        insider_txns = await _fetch_insider_txns(symbol)
        if insider_txns:
            buys = sum(t.get("shares", 0) for t in insider_txns if t.get("transaction_type", "").lower() in ("buy", "purchase", "p - purchase"))
            sells = sum(t.get("shares", 0) for t in insider_txns if t.get("transaction_type", "").lower() in ("sale", "sell", "s - sale"))
            total = buys + sells
            if total > 0:
                net_ratio = (buys - sells) / total  # -1 to +1
                signals["insider_net_buy"] = _clamp(net_ratio * 80)
            else:
                signals["insider_net_buy"] = 0.0
        else:
            signals["insider_net_buy"] = 0.0
    except Exception:
        signals["insider_net_buy"] = 0.0

    # Short interest proxy (via info.get shortRatio)
    short_ratio = info.get("shortRatio", None)
    if short_ratio is not None:
        # High short ratio = more negative sentiment; low = less overhang
        # Ratio > 10 → very short → bearish signal (-80)
        signals["short_interest"] = _clamp(-(short_ratio - 3) * 10)
    else:
        signals["short_interest"] = 0.0

    return signals


# ===========================================================================
# TECHNICAL SIGNALS
# ===========================================================================

async def _technical_signals(symbol: str, info: dict, hist) -> Dict:
    """
    52-week high/low proximity, RSI divergence, golden/death cross, volume surge.
    """
    signals = {}

    if hist is None or hist.empty:
        return {"52w_proximity": 0.0, "rsi_signal": 0.0, "ma_cross": 0.0, "volume_surge": 0.0}

    closes = hist["Close"]
    volumes = hist["Volume"]
    cur_price = float(closes.iloc[-1])

    # 52-week proximity (distance from 52w high as bearish; from 52w low as bullish)
    year_high = float(closes.tail(252).max()) if len(closes) >= 252 else float(closes.max())
    year_low = float(closes.tail(252).min()) if len(closes) >= 252 else float(closes.min())
    if year_high > year_low:
        pct_from_high = (cur_price - year_high) / year_high * 100  # negative = below high
        pct_from_low = (cur_price - year_low) / year_low * 100     # positive = above low
        # Near 52w high = technically strong (+); near 52w low = technically weak (-)
        proximity_score = _clamp(pct_from_high * 3 + pct_from_low * 0.5)
        signals["52w_proximity"] = proximity_score
    else:
        signals["52w_proximity"] = 0.0

    # RSI 14-day signal
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = float(rsi.iloc[-1]) if not rsi.empty and not math.isnan(rsi.iloc[-1]) else 50.0
    # RSI > 70 = overbought (bearish momentum signal); RSI < 30 = oversold (bullish reversal)
    # Neutral zone: 40-60 = 0
    if rsi_val >= 70:
        rsi_score = _clamp(-(rsi_val - 70) * 5)   # overbought → negative
    elif rsi_val <= 30:
        rsi_score = _clamp((30 - rsi_val) * 5)    # oversold → positive
    else:
        rsi_score = _clamp((rsi_val - 50) * 1.5)  # slight trend signal
    signals["rsi_signal"] = rsi_score

    # Golden/Death cross (SMA50 vs SMA200)
    sma50 = float(closes.tail(50).mean()) if len(closes) >= 50 else None
    sma200 = float(closes.tail(200).mean()) if len(closes) >= 200 else None
    if sma50 and sma200:
        cross_pct = (sma50 - sma200) / sma200 * 100
        # SMA50 > SMA200 → golden cross → bullish
        signals["ma_cross"] = _clamp(cross_pct * 5)
    else:
        signals["ma_cross"] = 0.0

    # Volume surge (current vs 20d avg)
    if len(volumes) >= 20:
        vol_20d_avg = float(volumes.tail(20).mean())
        cur_vol = float(volumes.iloc[-1])
        if vol_20d_avg > 0:
            vol_ratio = cur_vol / vol_20d_avg
            # 2x average volume → strong signal confirming trend
            # Surge with positive price → bullish; surge with negative price → bearish
            price_1d_chg = float((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100) if len(closes) >= 2 else 0
            direction = 1 if price_1d_chg >= 0 else -1
            signals["volume_surge"] = _clamp(direction * (vol_ratio - 1) * 30)
        else:
            signals["volume_surge"] = 0.0
    else:
        signals["volume_surge"] = 0.0

    # Trend strength: price vs SMA200 (above SMA200 = uptrend)
    if sma200 and cur_price:
        trend_pct = (cur_price - sma200) / sma200 * 100
        signals["trend_strength"] = _clamp(trend_pct * 2)
    else:
        signals["trend_strength"] = 0.0

    return signals


# ===========================================================================
# COMPOSITE SCORE CALCULATOR
# ===========================================================================

def _category_score(signals_dict: dict) -> float:
    """Average all signals in a category dict → one [-100, 100] score."""
    vals = [v for v in signals_dict.values() if isinstance(v, (int, float)) and not math.isnan(v)]
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def _overall_score(categories: dict) -> float:
    """Weighted composite of category scores."""
    total = 0.0
    for cat, score in categories.items():
        w = CATEGORY_WEIGHTS.get(cat, 0.2)
        total += score * w
    return round(_clamp(total), 1)


def _signal_label(score: float) -> str:
    if score >= 60:
        return "STRONG BUY"
    elif score >= 25:
        return "BUY"
    elif score >= -25:
        return "NEUTRAL"
    elif score >= -60:
        return "SELL"
    else:
        return "STRONG SELL"


# ===========================================================================
# PUBLIC API
# ===========================================================================

async def compute_signals(symbol: str, db=None) -> dict:
    """
    Compute all signals for a given ticker.

    Returns:
        {
          "symbol": "AAPL",
          "composite_score": 42.5,
          "signal_label": "BUY",
          "categories": {
              "momentum": {"score": 55.0, "signals": {...}},
              "value": {"score": -10.0, "signals": {...}},
              ...
          },
          "computed_at": "ISO8601"
        }
    """
    symbol = symbol.upper().strip()

    # Fetch all data in parallel
    hist, info, (income, balance) = await asyncio.gather(
        _fetch_history(symbol, "1y"),
        _fetch_info(symbol),
        _fetch_financials(symbol),
    )

    # Compute each category in parallel
    mom, val, qual, sent, tech = await asyncio.gather(
        _momentum_signals(symbol, info, hist),
        _value_signals(symbol, info),
        _quality_signals(symbol, info, income, balance),
        _sentiment_signals(symbol, info, db),
        _technical_signals(symbol, info, hist),
    )

    categories = {
        "momentum": {"score": _category_score(mom), "signals": mom},
        "value":    {"score": _category_score(val), "signals": val},
        "quality":  {"score": _category_score(qual), "signals": qual},
        "sentiment":{"score": _category_score(sent), "signals": sent},
        "technical":{"score": _category_score(tech), "signals": tech},
    }

    cat_scores = {k: v["score"] for k, v in categories.items()}
    composite = _overall_score(cat_scores)

    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "sector": info.get("sector", "Unknown"),
        "composite_score": composite,
        "signal_label": _signal_label(composite),
        "categories": categories,
        "metadata": {
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


async def scan_universe(tickers: List[str], db=None, concurrency: int = 5) -> List[dict]:
    """
    Run signal computation across a list of tickers with bounded concurrency.
    Returns sorted list by composite_score descending.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _safe_compute(sym: str) -> Optional[dict]:
        async with semaphore:
            try:
                return await compute_signals(sym, db=db)
            except Exception as e:
                logger.warning(f"scan_universe: failed {sym}: {e}")
                return None

    results = await asyncio.gather(*[_safe_compute(t) for t in tickers])
    valid = [r for r in results if r is not None]
    valid.sort(key=lambda x: x["composite_score"], reverse=True)
    return valid
