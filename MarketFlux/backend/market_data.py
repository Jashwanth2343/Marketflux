import yfinance as yf
import asyncio
import logging
import time
from fastapi import HTTPException
import diskcache
from typing import Dict, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Persistent disk cache
cache = diskcache.Cache('/tmp/market_cache')
CACHE_TTL = 180  # 3 minutes — keeps top gainers/losers fresh

async def cache_get_async(key):
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, cache.get, key)
    if res:
        if len(res) == 3:
            data, ts, ttl = res
        else:
            data, ts = res
            ttl = 180
        if time.time() - ts < ttl:
            return data
    return None

async def cache_set_async(key, data, expire=180):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: cache.set(key, (data, time.time(), expire), expire=expire+60))

async def _async_yf_call(func, *args):
    loop = asyncio.get_running_loop()
    ticker = args[0] if args else "unknown"
    for attempt in range(4):
        try:
            res = await loop.run_in_executor(None, func, *args)
            if res is None or (isinstance(res, dict) and not res.get("price") and "price" in res) or (isinstance(res, list) and len(res) == 0 and func.__name__ not in ["_search_all_tickers", "_search_tickers"]):
                pass # let it pass or raise?
            return res
        except HTTPException:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "connection" in error_msg or "max retries exceeded" in error_msg:
                if attempt < 3:
                    delays = [1, 2, 4]
                    await asyncio.sleep(delays[attempt])
                    continue
                logger.error(f"yfinance_error | ticker={ticker} | error_type={type(e).__name__} | message={str(e)}")
                raise HTTPException(503, "Market data temporarily unavailable, please try again in 60 seconds")
            elif "jsondecodeerror" in error_msg:
                logger.error(f"yfinance_error | ticker={ticker} | error_type={type(e).__name__} | message={str(e)}")
                raise HTTPException(503, "Market data temporarily unavailable, please try again in 60 seconds")
            else:
                logger.error(f"yfinance_error | ticker={ticker} | error_type={type(e).__name__} | message={str(e)}")
                raise HTTPException(500, "Internal server error")

def sanitize_for_json(data):
    """
    Recursively walk through data (dicts, lists) and replace 
    NaN, Inf, -Inf with None (null in JSON).
    """
    import math
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(x) for x in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
    return data



MAJOR_INDICES = {
    "^GSPC": {"name": "S&P 500", "type": "index"},
    "^DJI": {"name": "Dow Jones", "type": "index"},
    "^IXIC": {"name": "NASDAQ", "type": "index"},
    "^RUT": {"name": "Russell 2000", "type": "index"},
    "^VIX": {"name": "VIX", "type": "volatility"},
    "BTC-USD": {"name": "Bitcoin", "type": "crypto"},
    "ETH-USD": {"name": "Ethereum", "type": "crypto"},
    "GC=F": {"name": "Gold", "type": "commodity"},
    "CL=F": {"name": "Crude Oil", "type": "commodity"},
}

POPULAR_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM",
    "V", "WMT", "JNJ", "XOM", "PG", "MA", "HD", "BAC", "AVGO", "KO",
    "PFE", "COST", "DIS", "MRK", "NFLX", "AMD", "INTC", "CRM"
]

FULL_UNIVERSE = [
    # Technology
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "CRM", "ADBE", "ORCL",
    "INTC", "AMD", "QCOM", "AVGO", "IBM", "NOW", "UBER", "SHOP", "SQ", "SNOW",
    # Finance
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "V", "MA",
    "BRK-B", "USB", "PNC", "TFC",
    # Healthcare
    "JNJ", "PFE", "MRK", "UNH", "ABT", "TMO", "ABBV", "LLY", "BMY", "AMGN",
    "GILD", "MDT", "ISRG", "VRTX",
    # Consumer
    "WMT", "KO", "PG", "PEP", "COST", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX",
    # Industrial
    "CAT", "HON", "GE", "BA", "UPS", "RTX", "DE", "LMT", "MMM",
    # Communication
    "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS",
    # Real Estate
    "AMT", "PLD", "CCI", "SPG",
    # Utilities
    "NEE", "DUK", "SO",
]

SECTOR_MAP = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology", "AMZN": "Technology", "NVDA": "Technology", "META": "Technology", "TSLA": "Technology", "CRM": "Technology", "ADBE": "Technology", "ORCL": "Technology",
    "INTC": "Technology", "AMD": "Technology", "QCOM": "Technology", "AVGO": "Technology", "IBM": "Technology", "NOW": "Technology", "UBER": "Technology", "SHOP": "Technology", "SQ": "Technology", "SNOW": "Technology",
    # Finance
    "JPM": "Financials", "BAC": "Financials", "WFC": "Financials", "GS": "Financials", "MS": "Financials", "C": "Financials", "BLK": "Financials", "SCHW": "Financials", "AXP": "Financials", "V": "Financials", "MA": "Financials",
    "BRK-B": "Financials", "USB": "Financials", "PNC": "Financials", "TFC": "Financials",
    # Healthcare
    "JNJ": "Healthcare", "PFE": "Healthcare", "MRK": "Healthcare", "UNH": "Healthcare", "ABT": "Healthcare", "TMO": "Healthcare", "ABBV": "Healthcare", "LLY": "Healthcare", "BMY": "Healthcare", "AMGN": "Healthcare",
    "GILD": "Healthcare", "MDT": "Healthcare", "ISRG": "Healthcare", "VRTX": "Healthcare",
    # Consumer
    "WMT": "Consumer", "KO": "Consumer", "PG": "Consumer", "PEP": "Consumer", "COST": "Consumer", "HD": "Consumer", "MCD": "Consumer", "NKE": "Consumer", "SBUX": "Consumer", "TGT": "Consumer", "LOW": "Consumer",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy", "EOG": "Energy", "MPC": "Energy", "PSX": "Energy",
    # Industrial
    "CAT": "Industrials", "HON": "Industrials", "GE": "Industrials", "BA": "Industrials", "UPS": "Industrials", "RTX": "Industrials", "DE": "Industrials", "LMT": "Industrials", "MMM": "Industrials",
    # Communication
    "NFLX": "Communication", "DIS": "Communication", "CMCSA": "Communication", "T": "Communication", "VZ": "Communication", "TMUS": "Communication",
    # Real Estate
    "AMT": "Real Estate", "PLD": "Real Estate", "CCI": "Real Estate", "SPG": "Real Estate",
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",
    # Materials
    "LIN": "Materials", "APD": "Materials", "SHW": "Materials", "ECL": "Materials",
}

MARKET_CAP_THRESHOLDS = {"large": 10e9, "mid": 2e9}


def _get_ticker_data(symbol: str) -> Dict:

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        hist = ticker.history(period="2d")

        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose", 0)

        if not current_price and len(hist) > 0:
            current_price = float(hist["Close"].iloc[-1])
        if not previous_close and len(hist) > 1:
            previous_close = float(hist["Close"].iloc[-2])

        change = current_price - previous_close if current_price and previous_close else 0
        change_pct = (change / previous_close * 100) if previous_close else 0

        raw_yield = info.get("dividendYield")

        result = {
            "symbol": symbol,
            "name": info.get("shortName") or info.get("longName", symbol),
            "price": round(float(current_price), 2) if current_price else 0,
            "change": round(float(change), 2),
            "change_percent": round(float(change_pct), 2),
            "volume": info.get("volume", 0),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE"),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "day_high": info.get("dayHigh", 0),
            "day_low": info.get("dayLow", 0),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0),
            "avg_volume": info.get("averageVolume", 0),
            "dividend_yield": round(float(raw_yield) * 100, 2) if raw_yield is not None and float(raw_yield) < 1 else raw_yield,
            "beta": info.get("beta"),
            "description": info.get("longBusinessSummary", "")[:500],
        }
        return result
    except Exception as e:
        logger.error(f"Error fetching ticker {symbol}: {e}")
        return {"symbol": symbol, "name": symbol, "price": 0, "change": 0, "change_percent": 0}


def _get_chart_data(symbol: str, period: str = "1mo", interval: str = "1d") -> List[Dict]:
    cache_key = f"chart_{symbol}_{period}_{interval}"

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            return []

        # Reset index to access Date/Datetime
        hist = hist.reset_index()
        
        # Find the date column (it varies based on interval) and convert to string
        date_col = 'Datetime' if 'Datetime' in hist.columns else 'Date'
        hist[date_col] = hist[date_col].astype(str)
        hist = hist.rename(columns={date_col: 'date'})
        
        # Lowercase all remaining columns for standard frontend parsing
        hist.columns = [c.lower() for c in hist.columns]
        
        # Handle NaN values to prevent JSON serialization errors
        hist = hist.fillna(0)
        
        return hist.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching chart for {symbol}: {e}")
        return []


def _search_tickers(query: str) -> List[Dict]:
    query_upper = query.upper()
    results = []

    for symbol in POPULAR_TICKERS:
        if query_upper in symbol:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info or {}
                results.append({
                    "symbol": symbol,
                    "name": info.get("shortName", symbol),
                    "sector": info.get("sector", ""),
                    "exchange": info.get("exchange", ""),
                })
            except Exception:
                results.append({"symbol": symbol, "name": symbol, "sector": "", "exchange": ""})

    if not results:
        try:
            ticker = yf.Ticker(query_upper)
            info = ticker.info or {}
            if info.get("shortName"):
                results.append({
                    "symbol": query_upper,
                    "name": info.get("shortName", query_upper),
                    "sector": info.get("sector", ""),
                    "exchange": info.get("exchange", ""),
                })
        except Exception:
            pass

    return results[:10]





async def get_market_overview() -> Dict:
    cache_key = "market_overview"
    cached = await cache_get_async(cache_key)
    if cached: return cached

    indices = {}
    symbols = list(MAJOR_INDICES.keys())
    tasks = [get_stock_info(sym) for sym in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for symbol, res in zip(symbols, results):
        if isinstance(res, dict) and res.get("price", 0) > 0:
            # We copy to avoid modifying the cached get_stock_info result
            res_copy = dict(res)
            res_copy.update(MAJOR_INDICES[symbol])
            indices[symbol] = res_copy
        elif isinstance(res, Exception):
            logger.error(f"Error fetching index {symbol}: {res}")

    if indices:
        await cache_set_async(cache_key, indices)

    return indices


def _fetch_movers_sync() -> Dict:
    """Batch-download the full universe and rank by real-time % change."""
    try:
        import yfinance as yf
        import pandas as pd

        # 1. Try to use yfinance built-in screeners first
        gainers, losers = [], []
        try:
            g_scr = yf.screen("day_gainers")
            if g_scr and "quotes" in g_scr:
                for q in g_scr["quotes"][:10]:
                    gainers.append({
                        "symbol": q.get("symbol", ""),
                        "name": q.get("longName") or q.get("shortName") or q.get("symbol", ""),
                        "price": round(float(q.get("regularMarketPrice", 0)), 2),
                        "change": round(float(q.get("regularMarketChange", 0)), 2),
                        "change_percent": round(float(q.get("regularMarketChangePercent", 0)), 2),
                    })
                    
            l_scr = yf.screen("day_losers")
            if l_scr and "quotes" in l_scr:
                for q in l_scr["quotes"][:10]:
                    losers.append({
                        "symbol": q.get("symbol", ""),
                        "name": q.get("longName") or q.get("shortName") or q.get("symbol", ""),
                        "price": round(float(q.get("regularMarketPrice", 0)), 2),
                        "change": round(float(q.get("regularMarketChange", 0)), 2),
                        "change_percent": round(float(q.get("regularMarketChangePercent", 0)), 2),
                    })
        except Exception as e:
            logger.warning(f"Screener failed: {e}")
            
        if len(gainers) >= 5 and len(losers) >= 5:
            return {"gainers": gainers, "losers": losers}

        # 2. Fallback to computing from FULL_UNIVERSE
        # Download with group_by='column' → MultiIndex is (field, ticker)
        # so raw['Close'][sym] correctly gives the close series for each symbol
        raw = yf.download(
            FULL_UNIVERSE,
            period="2d",
            interval="1d",
            group_by="column",
            auto_adjust=True,
            threads=True,
            progress=False,
        )

        movers = []
        for sym in FULL_UNIVERSE:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    # (field, ticker) order — standard with group_by='column'
                    close = raw["Close"][sym].dropna()
                else:
                    # Single-ticker fallback
                    close = raw["Close"].dropna()

                if len(close) < 2:
                    continue

                prev_close = float(close.iloc[-2])
                cur_price  = float(close.iloc[-1])

                if prev_close <= 0:
                    continue

                change     = cur_price - prev_close
                change_pct = (change / prev_close) * 100

                movers.append({
                    "symbol":         sym,
                    "name":           sym,          # enriched below for top-10
                    "price":          round(cur_price, 2),
                    "change":         round(change, 2),
                    "change_percent": round(change_pct, 2),
                })
            except Exception:
                continue

        if not movers:
            return {"gainers": [], "losers": []}

        movers.sort(key=lambda x: x["change_percent"], reverse=True)
        gainers_raw = movers[:10]
        losers_raw  = movers[-10:][::-1]      # worst first

        # Enrich the top-10 with real names / extra fields via .info
        def _enrich(sym_list):
            enriched = []
            for item in sym_list:
                try:
                    info = yf.Ticker(item["symbol"]).fast_info
                    name = getattr(info, "display_name", None) or item["symbol"]
                    item["name"] = name
                except Exception:
                    pass
                enriched.append(item)
            return enriched

        return {
            "gainers": _enrich(gainers_raw),
            "losers":  _enrich(losers_raw),
        }
    except Exception as e:
        logger.error(f"_fetch_movers_sync error: {e}")
        return {"gainers": [], "losers": []}


async def get_top_movers() -> Dict:
    cached = await cache_get_async("top_movers_v2")
    if cached:
        return cached

    result = await asyncio.to_thread(_fetch_movers_sync)

    # Only cache if we actually got data
    if result["gainers"] or result["losers"]:
        await cache_set_async("top_movers_v2", result)

    return result


def _fetch_heatmap_sync() -> Dict:
    """Fetch 1-day change for FULL_UNIVERSE and group by SECTOR_MAP."""
    try:
        import pandas as pd
        raw = yf.download(
            FULL_UNIVERSE,
            period="2d",
            interval="1d",
            group_by="column",
            auto_adjust=True,
            threads=True,
            progress=False,
        )

        sectors = {}
        for sector in set(SECTOR_MAP.values()):
            sectors[sector] = []

        for sym in FULL_UNIVERSE:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    close = raw["Close"][sym].dropna()
                else:
                    close = raw["Close"].dropna()

                if len(close) < 2:
                    continue

                prev_close = float(close.iloc[-2])
                cur_price  = float(close.iloc[-1])

                if prev_close <= 0:
                    continue

                change     = cur_price - prev_close
                change_pct = (change / prev_close) * 100

                sector = SECTOR_MAP.get(sym, "Other")
                if sector not in sectors:
                    sectors[sector] = []

                sectors[sector].append({
                    "symbol":         sym,
                    "price":          round(cur_price, 2),
                    "change":         round(change, 2),
                    "change_percent": round(change_pct, 2),
                })
            except Exception:
                continue

        for s in sectors:
            sectors[s] = sorted(sectors[s], key=lambda x: abs(x.get("change_percent", 0)), reverse=True)

        return sectors
    except Exception as e:
        logger.error(f"_fetch_heatmap_sync error: {e}")
        return {}


async def get_heatmap_data() -> Dict:
    cached = await cache_get_async("heatmap_data")
    if cached:
        return cached

    sectors = await asyncio.to_thread(_fetch_heatmap_sync)
    if sectors:
        result = {
            "sectors": sectors,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        await cache_set_async("heatmap_data", result, expire=180)
        return result
    return {}


async def get_stock_info(symbol: str) -> Dict:
    cache_key = f"ticker_{symbol}"
    cached = await cache_get_async(cache_key)
    if cached: return cached
    res = await _async_yf_call(_get_ticker_data, symbol)
    if not res or not res.get("price"):
        raise HTTPException(404, "Stock symbol not found")
    await cache_set_async(cache_key, res)
    return res


async def get_stock_chart(symbol: str, period: str = "1mo", interval: str = "1d") -> List[Dict]:
    cache_key = f"chart_{symbol}_{period}_{interval}"
    cached = await cache_get_async(cache_key)
    if cached: return cached
    res = await _async_yf_call(_get_chart_data, symbol, period, interval)
    if not res:
        raise HTTPException(404, "Stock symbol not found")
    await cache_set_async(cache_key, res)
    return res
async def search_tickers(query: str) -> List[Dict]:
    return await _async_yf_call(_search_tickers, query)


async def get_ticker_news(symbol: str) -> List[Dict]:
    cache_key = f"news_{symbol.upper()}"
    cached = await cache_get_async(cache_key)
    if cached is not None:
        return cached

    try:
        loop = asyncio.get_running_loop()
        news_items = await _async_yf_call(lambda symbol: getattr(yf.Ticker(symbol), "news", []), symbol)

        articles = []
        for item in news_items:
            if isinstance(item, dict):
                # yfinance 1.2+ format: nested content object
                content = item.get("content", item)
                if isinstance(content, dict):
                    title = content.get("title", "")
                    summary = content.get("summary", "") or content.get("description", "")
                    provider = content.get("provider", {})
                    source = provider.get("displayName", "Yahoo Finance") if isinstance(provider, dict) else "Yahoo Finance"
                    canonical = content.get("canonicalUrl", {})
                    click_url = content.get("clickThroughUrl", {})
                    link = ""
                    if isinstance(canonical, dict):
                        link = canonical.get("url", "")
                    if not link and isinstance(click_url, dict):
                        link = click_url.get("url", "")
                    if not link:
                        link = content.get("link", item.get("link", ""))
                    pub_date = content.get("pubDate", content.get("displayTime", ""))
                else:
                    # Legacy format
                    title = item.get("title", "")
                    summary = item.get("summary", "")
                    source = item.get("publisher", "Yahoo Finance")
                    link = item.get("link", "")
                    pub_time = item.get("providerPublishTime", 0)
                    pub_date = datetime.fromtimestamp(pub_time, tz=timezone.utc).isoformat() if pub_time else ""

                if not title:
                    continue

                # Extract thumbnail
                thumbnail_url = ""
                thumb = content.get("thumbnail") if isinstance(content, dict) else item.get("thumbnail")
                if isinstance(thumb, dict):
                    resolutions = thumb.get("resolutions", [])
                    if resolutions:
                        # Pick a medium-sized resolution (~400px wide)
                        best = resolutions[0]
                        for r in resolutions:
                            if isinstance(r, dict) and 100 < r.get("width", 0) <= 500:
                                best = r
                                break
                        thumbnail_url = best.get("url", "") if isinstance(best, dict) else ""
                    if not thumbnail_url:
                        thumbnail_url = thumb.get("originalUrl", "")
                elif isinstance(thumb, str):
                    thumbnail_url = thumb

                articles.append({
                    "article_id": item.get("id", item.get("uuid", str(hash(title)))),
                    "title": title,
                    "summary": (summary or "")[:500],
                    "source": source,
                    "source_url": link,
                    "published_at": pub_date if pub_date else datetime.now(timezone.utc).isoformat(),
                    "tickers": [symbol.upper()],
                    "category": "stock",
                    "thumbnail_url": thumbnail_url,
                })
        
        if articles:
            # Run fast batch sentiment inference on titles
            titles = [art["title"] for art in articles]
            from ai_service import analyze_sentiments_batch
            sentiments = await analyze_sentiments_batch(titles)
            
            for art, sent in zip(articles, sentiments):
                art["sentiment"] = sent["label"]
                art["sentiment_score"] = sent["score"]

        # Cache for 15 minutes to avoid redundant FinBERT inference on hot reloads
        await cache_set_async(cache_key, articles, expire=900)

        # Embed into semantic news store for agent RAG
        try:
            from agent_tools import embed_and_store_news
            embed_and_store_news(symbol, articles)
        except Exception as e:
            logger.warning(f"News embedding error for {symbol} (non-fatal): {e}")

        return articles
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        return []


def _get_rich_stock_data(symbol: str) -> Dict:
    """Get comprehensive stock data including fundamentals and dividends."""

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        previous_close = info.get("previousClose", 0)
        open_price = info.get("open") or info.get("regularMarketOpen", 0)

        if not current_price:
            hist = ticker.history(period="2d")
            if len(hist) > 0:
                current_price = float(hist["Close"].iloc[-1])
            if len(hist) > 1 and not previous_close:
                previous_close = float(hist["Close"].iloc[-2])

        change = current_price - previous_close if current_price and previous_close else 0
        change_pct = (change / previous_close * 100) if previous_close else 0

        raw_yield = info.get("dividendYield")
        raw_payout = info.get("payoutRatio")

        result = {
            "symbol": symbol,
            "name": info.get("shortName") or info.get("longName", symbol),
            "exchange": info.get("exchange", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),

            "price": round(float(current_price), 2) if current_price else 0,
            "change": round(float(change), 2),
            "change_percent": round(float(change_pct), 2),
            "previous_close": round(float(previous_close), 2) if previous_close else 0,
            "open": round(float(open_price), 2) if open_price else 0,
            "day_high": round(float(info.get("dayHigh", 0) or 0), 2),
            "day_low": round(float(info.get("dayLow", 0) or 0), 2),
            "last_updated": datetime.now(timezone.utc).isoformat(),

            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "dividend_yield": round(float(raw_yield) * 100, 2) if raw_yield is not None and float(raw_yield) < 1 else raw_yield,
            "payout_ratio": round(float(raw_payout) * 100, 2) if raw_payout is not None and float(raw_payout) < 1 else raw_payout,
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", 0),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", 0),
            "volume": info.get("volume", 0),
            "avg_volume": info.get("averageVolume", 0),

            "revenue_ttm": info.get("totalRevenue"),
            "net_income": info.get("netIncomeToCommon"),
            "profit_margin": info.get("profitMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "book_value": info.get("bookValue"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_margins": info.get("operatingMargins"),
            "gross_margins": info.get("grossMargins"),
            "earnings_growth": info.get("earningsGrowth"),
            "revenue_growth": info.get("revenueGrowth"),

            "last_dividend_value": info.get("lastDividendValue"),
            "last_dividend_date": info.get("lastDividendDate"),
            "ex_dividend_date": info.get("exDividendDate"),
            "five_year_avg_dividend_yield": info.get("fiveYearAvgDividendYield"),

            "description": info.get("longBusinessSummary", "")[:800],

            # Analyst price targets
            "target_mean_price": info.get("targetMeanPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
            "recommendation_mean": info.get("recommendationMean"),
            "recommendation_key": info.get("recommendationKey"),
        }

        # Insider transactions
        try:
            insider_df = ticker.insider_transactions
            if insider_df is not None and not insider_df.empty:
                type_col = None
                for col in ['Transaction', 'transactionType', 'Type', 'transaction']:
                    if col in insider_df.columns:
                        type_col = col
                        break
                
                type_map = {
                    'S-Sale': 'Sell', 'S': 'Sell', 
                    'P-Purchase': 'Buy', 'P': 'Buy',
                    'S-Sale+OE': 'Sell', 'A-Award': 'Award',
                    'M-Exempt': 'Exercise', 'F-InKind': 'Tax Withhold',
                    'G-Gift': 'Gift', 'J-Other': 'Other',
                    'S-SaleToLossSecurity': 'Sell',
                }

                insider_list = []
                for _, row in insider_df.head(8).iterrows():
                    raw_type = str(row.get(type_col, "")) if type_col else ""
                    clean_type = type_map.get(raw_type.strip(), raw_type.strip())
                    
                    import math
                    val = row.get("Value", 0)
                    clean_val = 0
                    try:
                        if val is not None:
                            f_val = float(val)
                            if not math.isnan(f_val):
                                clean_val = f_val
                    except Exception:
                        pass
                    
                    insider_list.append({
                        "date": str(row.get("Start Date", row.get("Date", ""))),
                        "insider_name": str(row.get("Insider Trading", row.get("Insider", ""))),
                        "title": str(row.get("Position", row.get("Title", ""))),
                        "transaction_type": clean_type,
                        "shares": int(row.get("Shares", 0)) if row.get("Shares") and str(row.get("Shares")).replace('-','').isdigit() else 0,
                        "value": clean_val,
                    })

                result["insider_transactions"] = insider_list
            else:
                result["insider_transactions"] = []
        except Exception:
            result["insider_transactions"] = []

        # Institutional holders
        try:
            inst_df = ticker.institutional_holders
            if inst_df is not None and not inst_df.empty:
                inst_list = []
                for _, row in inst_df.head(5).iterrows():
                    inst_list.append({
                        "holder": str(row.get("Holder", "")),
                        "shares": int(row.get("Shares", 0)) if row.get("Shares") else 0,
                        "pct_held": float(row.get("pctHeld", row.get("% Out", 0))) if row.get("pctHeld", row.get("% Out")) else 0,
                        "value": float(row.get("Value", 0)) if row.get("Value") else 0,
                        "date_reported": str(row.get("Date Reported", "")),
                    })
                result["institutional_holders"] = inst_list
            else:
                result["institutional_holders"] = []
        except Exception:
            result["institutional_holders"] = []

        return result
    except Exception as e:
        logger.error(f"Error fetching rich data for {symbol}: {e}", exc_info=True)
        # Return a shell object rather than failing completely with 500
        return {"symbol": symbol, "name": symbol, "price": 0, "error": str(e)}


def _analyze_price_moves(symbol: str, days: int = 90) -> Dict:
    """Analyze recent price history for significant moves and drawdowns."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{days}d")

        if hist.empty:
            return {"significant_daily_moves": [], "multi_day_moves": [], "max_drawdown_pct": 0}

        closes = hist["Close"].values
        dates = hist.index

        # Daily moves > 2%
        daily_moves = []
        for i in range(1, len(closes)):
            pct = (closes[i] - closes[i-1]) / closes[i-1] * 100
            if abs(pct) >= 2.0:
                daily_moves.append({
                    "date": dates[i].strftime("%Y-%m-%d"),
                    "close": round(float(closes[i]), 2),
                    "prev_close": round(float(closes[i-1]), 2),
                    "change_pct": round(float(pct), 2),
                    "type": "gain" if pct > 0 else "drop"
                })

        # Max drawdown
        peak = closes[0]
        max_dd = 0
        for close in closes:
            if close > peak:
                peak = close
            dd = (close - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd

        # Multi-day moves (5-day rolling)
        multi_day = []
        for i in range(5, len(closes)):
            pct = (closes[i] - closes[i-5]) / closes[i-5] * 100
            if abs(pct) >= 5.0:
                multi_day.append({
                    "start_date": dates[i-5].strftime("%Y-%m-%d"),
                    "end_date": dates[i].strftime("%Y-%m-%d"),
                    "start_price": round(float(closes[i-5]), 2),
                    "end_price": round(float(closes[i]), 2),
                    "change_pct": round(float(pct), 2),
                })

        # Recent history summary (last 30 days of daily data)
        recent_history = []
        for i in range(max(0, len(closes)-30), len(closes)):
            recent_history.append({
                "date": dates[i].strftime("%Y-%m-%d"),
                "close": round(float(closes[i]), 2),
                "high": round(float(hist["High"].values[i]), 2),
                "low": round(float(hist["Low"].values[i]), 2),
                "volume": int(hist["Volume"].values[i]),
            })

        return {
            "significant_daily_moves": daily_moves[-10:],
            "multi_day_moves": multi_day[-5:],
            "max_drawdown_pct": round(float(max_dd), 2),
            "period_high": round(float(max(closes)), 2),
            "period_low": round(float(min(closes)), 2),
            "current_vs_high_pct": round(float((closes[-1] - max(closes)) / max(closes) * 100), 2),
            "recent_history": recent_history,
        }
    except Exception as e:
        logger.error(f"Error analyzing moves for {symbol}: {e}")
        return {"significant_daily_moves": [], "multi_day_moves": [], "max_drawdown_pct": 0, "recent_history": []}


async def get_rich_stock_data(symbol: str) -> Dict:
    cache_key = f"rich_{symbol}"
    cached = await cache_get_async(cache_key)
    if cached: return cached
    res = await _async_yf_call(_get_rich_stock_data, symbol)
    if not res or not res.get("price"):
        raise HTTPException(404, "Stock symbol not found")
    await cache_set_async(cache_key, res)
    return res


async def get_price_analysis(symbol: str, days: int = 90) -> Dict:
    cache_key = f"analysis_{symbol}_{days}"
    cached = await cache_get_async(cache_key)
    if cached: return cached
    res = await _async_yf_call(_analyze_price_moves, symbol, days)
    await cache_set_async(cache_key, res)
    return res


def _filter_universe(filters: Dict) -> List[Dict]:
    """Apply structured Finviz filters AND custom local filtering against the market. Returns enriched stock data."""
    from finvizfinance.screener.overview import Overview
    try:
        foverview = Overview()
        fdict = filters.get("finviz_filters_dict") or filters.get("filters_dict") or {}
        custom = filters.get("custom_filters") or {}
        
        if fdict:
            foverview.set_filter(filters_dict=fdict)
            
        df = foverview.screener_view(verbose=0)
        
        if df is None or df.empty:
            return []
            
        # Post-process for exact numeric custom_filters
        if custom:
            pe_max = custom.get("pe_max")
            pe_min = custom.get("pe_min")
            
            def valid_row(row):
                try:
                    # P/E checks
                    pe = str(row.get("P/E", "0")).replace(',', '')
                    if pe == "-": return False
                    pe_val = float(pe)
                    if pe_val <= 0 and pe_max is not None: return False # Exclude negative PE if asking for max PE
                    if pe_max is not None and pe_val > pe_max: return False
                    if pe_min is not None and pe_val < pe_min: return False
                    
                    return True
                except Exception:
                    return False

            df = df[df.apply(valid_row, axis=1)]

        if df.empty:
            return []

        results = []
        for _, row in df.iterrows():
            change_str = str(row.get("Change", "0")).replace("%", "")
            try:
                change_pct = float(change_str)
            except:
                change_pct = 0
                
            price_str = str(row.get("Price", "0")).replace(',', '')
            pe_str = str(row.get("P/E", "0")).replace(',', '')
            vol_str = str(row.get("Volume", "0")).replace(',', '')
            
            results.append({
                "symbol": str(row.get("Ticker", "")),
                "name": str(row.get("Company", "")),
                "sector": str(row.get("Sector", "")),
                "industry": str(row.get("Industry", "")),
                "price": float(price_str) if price_str.replace('.','',1).isdigit() else 0,
                "change_percent": change_pct,
                # Finviz nicely returns formatted caps e.g. "1.50B"
                "market_cap": str(row.get("Market Cap", "")), 
                "pe_ratio": float(pe_str) if pe_str.replace('.','',1).isdigit() else None,
                "dividend_yield": str(row.get("Dividend", "")),
                "volume": int(vol_str) if vol_str.isdigit() else 0
            })
            
        return results
    except Exception as e:
        logger.error(f"Finviz screen error: {e}")
        return []


async def filter_stocks_from_universe(filters: Dict) -> List[Dict]:
    return await asyncio.to_thread(_filter_universe, filters)


def _search_all_tickers(query: str) -> List[Dict]:
    """Search using yfinance Search API for natural company name lookup."""
    try:
        search = yf.Search(query, max_results=10)
        results = []
        if hasattr(search, 'quotes') and search.quotes:
            for q in search.quotes:
                if not q.get('symbol'):
                    continue
                results.append({
                    "symbol": q.get("symbol", ""),
                    "name": q.get("shortname") or q.get("longname", ""),
                    "sector": q.get("sectorDisp") or q.get("sector", ""),
                    "exchange": q.get("exchDisp") or q.get("exchange", ""),
                    "type": q.get("typeDisp") or q.get("quoteType", ""),
                    "industry": q.get("industryDisp") or q.get("industry", ""),
                })
        return results[:15]
    except Exception as e:
        logger.error(f"yfinance Search error: {e}")
        # Fallback to simple ticker matching
        query_upper = query.upper()
        results = []
        all_tickers = list(set(FULL_UNIVERSE + POPULAR_TICKERS))
        for symbol in all_tickers:
            if query_upper in symbol:
                try:
                    cached_val = cache.get(f"ticker_{symbol}")
                    cached = cached_val[0] if cached_val and isinstance(cached_val, tuple) else None
                except Exception:
                    cached = None
                name = cached.get("name", symbol) if cached else symbol
                sector = cached.get("sector", "") if cached else ""
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "sector": sector,
                    "exchange": "",
                    "type": "Equity",
                    "industry": "",
                })
        results.sort(key=lambda x: (0 if x["symbol"] == query_upper else 1, x["symbol"]))
        return results[:15]


async def search_all_stocks(query: str) -> List[Dict]:
    return await _async_yf_call(_search_all_tickers, query)
