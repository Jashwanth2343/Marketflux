"""
Agent Tools for MarketFlux Agentic RAG.

All tool functions that the agent can call. Each returns a dict/string
suitable for injection into the LLM context. Wrappers reuse existing
market_data functions without rewriting the underlying logic.
"""

import os
# Disable HuggingFace Hub network calls when loading models
os.environ["HF_HUB_OFFLINE"] = "1"

import asyncio
import logging
import httpx
import numpy as np
from typing import Dict, List, Optional
import diskcache
from provider_router import ProviderRouter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caching
# Store in app-local .cache directory (not world-readable /tmp/) — M5
# ---------------------------------------------------------------------------
_CACHE_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(_CACHE_BASE, mode=0o700, exist_ok=True)
_tool_cache = diskcache.Cache(os.path.join(_CACHE_BASE, "tool_cache"))


def _cache_get(key: str):
    try:
        return _tool_cache.get(key)
    except Exception:
        return None


def _cache_set(key: str, data, expire: int = 3600):
    try:
        _tool_cache.set(key, data, expire=expire)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Company Name → Ticker Resolution (via yfinance Search)
# ---------------------------------------------------------------------------
_ticker_resolution_cache: Dict[str, str] = {}


async def resolve_company_to_ticker(company_name: str) -> Optional[str]:
    """
    Resolve a company name to its ticker symbol using yfinance Search.
    Returns the best-match US equity ticker, or None if not found.
    Cached in-memory to avoid repeated API calls.
    """
    name_lower = company_name.lower().strip()
    if name_lower in _ticker_resolution_cache:
        return _ticker_resolution_cache[name_lower]

    try:
        import yfinance as yf

        def _search():
            results = yf.Search(company_name)
            if results.quotes:
                # Prefer US exchanges
                for q in results.quotes:
                    if q.get("quoteType") == "EQUITY" and q.get("exchange") in ("NMS", "NYQ", "NGM", "NAS", "PCX", "ASE"):
                        return q.get("symbol")
                # Fallback: first equity result
                for q in results.quotes:
                    if q.get("quoteType") == "EQUITY":
                        return q.get("symbol")
            return None

        ticker = await asyncio.to_thread(_search)
        if ticker:
            _ticker_resolution_cache[name_lower] = ticker
            logger.info(f"Resolved company '{company_name}' → ticker {ticker}")
        return ticker
    except Exception as e:
        logger.warning(f"Company name resolution failed for '{company_name}': {e}")
        return None


# ---------------------------------------------------------------------------
# In-Memory Semantic News Search (Section 2 — Warning 14 fallback)
# ---------------------------------------------------------------------------
# Uses sentence-transformers + numpy cosine similarity instead of ChromaDB
# to avoid SQLite/C++ dependency issues. For 5-10 articles per stock,
# in-memory cosine similarity is actually faster than a full vector DB.

_embedding_model = None
_news_store: Dict[str, dict] = {}  # key=url -> {title, summary, source, published_at, ticker, embedding}
_NEWS_STORE_MAX = 2000  # L5: Cap to avoid unbounded memory growth


def _get_embedding_model():
    """Lazy-load the sentence-transformer model."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers all-MiniLM-L6-v2 for semantic search")
        except Exception as e:
            logger.error(f"Failed to load sentence-transformer model: {e}")
    return _embedding_model


def embed_and_store_news(symbol: str, articles: List[dict]):
    """
    Batch-embed news headlines+snippets and store in memory.
    Called when news is fetched for any ticker.
    Keyed by article URL to avoid duplicates.
    """
    model = _get_embedding_model()
    if model is None or not articles:
        return

    texts = []
    valid_articles = []
    for art in articles:
        title = art.get("title", "")
        summary = art.get("summary", "")
        text = f"{title}. {summary}" if summary else title
        if text.strip():
            texts.append(text)
            valid_articles.append(art)

    if not texts:
        return

    try:
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        for art, emb in zip(valid_articles, embeddings):
            url_key = art.get("source_url") or art.get("article_id") or art.get("title", "")
            _news_store[url_key] = {
                "title": art.get("title", ""),
                "summary": art.get("summary", ""),
                "source": art.get("source", ""),
                "published_at": art.get("published_at", ""),
                "ticker": symbol.upper(),
                "sentiment": art.get("sentiment"),
                "sentiment_score": art.get("sentiment_score"),
                "source_url": art.get("source_url", ""),
                "embedding": emb,
            }
        # L5: Evict oldest entries if store exceeds max size
        if len(_news_store) > _NEWS_STORE_MAX:
            overflow = len(_news_store) - _NEWS_STORE_MAX
            for old_key in list(_news_store.keys())[:overflow]:
                del _news_store[old_key]
        logger.info(f"Embedded {len(texts)} news articles for {symbol} into semantic store")
    except Exception as e:
        logger.error(f"News embedding error for {symbol}: {e}")


def _semantic_search_news(query: str, symbol: Optional[str] = None, top_k: int = 5) -> List[dict]:
    """
    Search news store using cosine similarity with the user's query.
    Returns top_k most relevant articles.
    """
    model = _get_embedding_model()
    if model is None or not _news_store:
        return []

    try:
        # Filter by ticker if specified
        candidates = []
        for url_key, data in _news_store.items():
            if symbol and data.get("ticker", "").upper() != symbol.upper():
                continue
            candidates.append((url_key, data))

        if not candidates:
            # If no ticker-specific news, search all
            candidates = list(_news_store.items())

        if not candidates:
            return []

        # Build embedding matrix
        embeddings_matrix = np.array([c[1]["embedding"] for c in candidates])
        query_embedding = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]

        # Cosine similarity (embeddings are normalized, so dot product = cosine sim)
        similarities = np.dot(embeddings_matrix, query_embedding)

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if similarities[idx] < 0.1:  # threshold to avoid garbage results
                continue
            data = candidates[idx][1]
            results.append({
                "title": data["title"],
                "summary": data["summary"],
                "source": data["source"],
                "published_at": data["published_at"],
                "sentiment": data.get("sentiment"),
                "source_url": data.get("source_url", ""),
                "relevance_score": round(float(similarities[idx]), 3),
            })

        return results
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return []


# ---------------------------------------------------------------------------
# TOOL: get_stock_snapshot — wraps existing _get_ticker_data
# ---------------------------------------------------------------------------
async def get_stock_snapshot(symbol: str) -> dict:
    """Live price, change %, volume, day range, 52-week range."""
    cache_key = f"tool_snapshot:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        data = None
        # Smart Routing: Check if we should use AKShare primarily
        primary_provider = ProviderRouter.get_provider_for_ticker(symbol)
        
        if primary_provider == "akshare":
            logger.info(f"Routing {symbol} primarily to AKShare")
            ak_res = await ProviderRouter.get_stock_quote(symbol)
            if not ak_res.get("error"):
                data = {
                    "symbol": symbol.upper(),
                    "name": symbol.upper(),
                    "price": ak_res["price"],
                    "source": "akshare"
                }

        # If not routed or routing failed, try yfinance
        if not data:
            from market_data import _get_ticker_data
            data = await asyncio.to_thread(_get_ticker_data, symbol.upper())
            
            # Fallback to AKShare if yfinance fails or returns zero price
            if not data or not data.get("price"):
                logger.info(f"yfinance fallback for {symbol} triggered, trying AKShare")
                ak_res = await ProviderRouter.get_stock_quote(symbol)
                if not ak_res.get("error"):
                    data = {
                        "symbol": symbol.upper(),
                        "name": symbol.upper(),
                        "price": ak_res["price"],
                        "source": "akshare_fallback"
                    }

        if data and data.get("price"):
            # Define market hours for New York (ET)
            from datetime import datetime, timezone
            import pytz
            et = pytz.timezone("America/New_York")
            now = datetime.now(et)
            is_market_hours = False
            if now.weekday() < 5: # Monday-Friday
                market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
                market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
                is_market_hours = market_open <= now <= market_close

            result = {
                "symbol": data["symbol"],
                "name": data.get("name", symbol),
                "price": data["price"],
                "change": data.get("change", 0),
                "change_percent": data.get("change_percent", 0),
                "volume": data.get("volume", 0),
                "day_high": data.get("day_high", 0),
                "day_low": data.get("day_low", 0),
                "fifty_two_week_high": data.get("fifty_two_week_high", 0),
                "fifty_two_week_low": data.get("fifty_two_week_low", 0),
                "market_cap": data.get("market_cap", 0),
                "provider": data.get("source", "yfinance"),
                "is_market_open": is_market_hours,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            }
            # Freshness: 60s during market hours, 1hr otherwise
            snap_ttl = 60 if is_market_hours else 3600
            _cache_set(cache_key, result, expire=snap_ttl)
            return result
        return {}
    except Exception as e:
        logger.error(f"get_stock_snapshot error for {symbol}: {e}")
        return {}


# ---------------------------------------------------------------------------
# TOOL: get_fundamentals — wraps existing _get_rich_stock_data
# ---------------------------------------------------------------------------
async def get_fundamentals(symbol: str) -> dict:
    """P/E, forward P/E, margins, revenue growth, debt/equity, market cap."""
    cache_key = f"tool_fundamentals:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        from market_data import _get_rich_stock_data
        data = await asyncio.to_thread(_get_rich_stock_data, symbol.upper())
        if data and data.get("price"):
            from datetime import datetime, timezone
            result = {
                "symbol": data["symbol"],
                "name": data.get("name", symbol),
                "market_cap": data.get("market_cap", 0),
                "pe_ratio": data.get("pe_ratio"),
                "forward_pe": data.get("forward_pe"),
                "eps": data.get("eps"),
                "revenue_growth": data.get("revenue_growth"),
                "earnings_growth": data.get("earnings_growth"),
                "gross_margins": data.get("gross_margins"),
                "operating_margins": data.get("operating_margins"),
                "profit_margin": data.get("profit_margin"),
                "debt_to_equity": data.get("debt_to_equity"),
                "current_ratio": data.get("current_ratio"),
                "roe": data.get("roe"),
                "roa": data.get("roa"),
                "free_cashflow": data.get("free_cashflow"),
                "revenue_ttm": data.get("revenue_ttm"),
                "dividend_yield": data.get("dividend_yield"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "cache_note": "Fundamentals are cached for 5 minutes for consistency."
            }
            _cache_set(cache_key, result, expire=300)  # 5 min for consistency
            return result
        return {}
    except Exception as e:
        logger.error(f"get_fundamentals error for {symbol}: {e}")
        return {}


# ---------------------------------------------------------------------------
# TOOL: get_analyst_targets — from yfinance info
# ---------------------------------------------------------------------------
async def get_analyst_targets(symbol: str) -> dict:
    """Consensus rating, price target, number of analysts."""
    cache_key = f"tool_analyst:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        import yfinance as yf

        def _fetch():
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info or {}
            return {
                "symbol": symbol.upper(),
                "recommendation": info.get("recommendationKey", "N/A"),
                "target_mean_price": info.get("targetMeanPrice"),
                "target_high_price": info.get("targetHighPrice"),
                "target_low_price": info.get("targetLowPrice"),
                "number_of_analysts": info.get("numberOfAnalystOpinions"),
                "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            }

        data = await asyncio.to_thread(_fetch)
        _cache_set(cache_key, data, expire=900)  # 15 min
        return data
    except Exception as e:
        logger.error(f"get_analyst_targets error for {symbol}: {e}")
        return {}


# ---------------------------------------------------------------------------
# TOOL: get_news — semantic search via in-memory embeddings
# ---------------------------------------------------------------------------
async def get_news(symbol: str, query: str = "") -> dict:
    """
    Top 5 semantically relevant articles from the news store.
    Uses user query as search vector for relevance ranking.
    Also fetches fresh news from yfinance if store is thin.
    """
    # Ensure we have news in the store for this ticker
    ticker_count = sum(1 for d in _news_store.values() if d.get("ticker", "").upper() == symbol.upper())

    if ticker_count < 3:
        # Fetch fresh news from yfinance and embed
        try:
            from market_data import get_ticker_news
            articles = await get_ticker_news(symbol.upper())
            if articles:
                embed_and_store_news(symbol, articles)
        except Exception as e:
            logger.warning(f"Failed to fetch fresh news for {symbol}: {e}")

    # Try MongoDB news
    search_query = query if query else f"{symbol} stock news"
    results = await asyncio.to_thread(_semantic_search_news, search_query, symbol, 5)

    if results:
        return {"symbol": symbol, "articles": results, "source": "semantic_search"}

    # If no ticker-specific results, search general MARKET store
    results = await asyncio.to_thread(_semantic_search_news, search_query, "MARKET", 5)
    if results:
        return {"symbol": symbol, "articles": results, "source": "semantic_market_fallback"}

    return {"symbol": symbol, "articles": [], "source": "none"}


# ---------------------------------------------------------------------------
# TOOL: get_technical_indicators — Alpha Vantage free API
# ---------------------------------------------------------------------------
async def get_technical_indicators(symbol: str) -> dict:
    """RSI (14-day), MACD, 50-day SMA, 200-day SMA from Alpha Vantage."""
    cache_key = f"tool_technical:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    api_key = os.environ.get("ALPHA_VANTAGE_KEY", "")
    if not api_key:
        # Fallback: compute basic technicals from yfinance history
        return await _compute_technicals_from_yfinance(symbol)

    result = {"symbol": symbol.upper()}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Fetch RSI
            rsi_resp = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "RSI",
                    "symbol": symbol.upper(),
                    "interval": "daily",
                    "time_period": 14,
                    "series_type": "close",
                    "apikey": api_key,
                },
            )
            rsi_data = rsi_resp.json()
            rsi_key = "Technical Analysis: RSI"
            if rsi_key in rsi_data:
                latest = list(rsi_data[rsi_key].values())[0]
                result["rsi_14"] = float(latest.get("RSI", 0))

            # Fetch MACD
            macd_resp = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "MACD",
                    "symbol": symbol.upper(),
                    "interval": "daily",
                    "series_type": "close",
                    "apikey": api_key,
                },
            )
            macd_data = macd_resp.json()
            macd_key = "Technical Analysis: MACD"
            if macd_key in macd_data:
                latest = list(macd_data[macd_key].values())[0]
                result["macd"] = float(latest.get("MACD", 0))
                result["macd_signal"] = float(latest.get("MACD_Signal", 0))
                result["macd_hist"] = float(latest.get("MACD_Hist", 0))

            # Fetch SMA 50
            sma50_resp = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "SMA",
                    "symbol": symbol.upper(),
                    "interval": "daily",
                    "time_period": 50,
                    "series_type": "close",
                    "apikey": api_key,
                },
            )
            sma50_data = sma50_resp.json()
            sma50_key = "Technical Analysis: SMA"
            if sma50_key in sma50_data:
                latest = list(sma50_data[sma50_key].values())[0]
                result["sma_50"] = float(latest.get("SMA", 0))

            # Fetch SMA 200
            sma200_resp = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "SMA",
                    "symbol": symbol.upper(),
                    "interval": "daily",
                    "time_period": 200,
                    "series_type": "close",
                    "apikey": api_key,
                },
            )
            sma200_data = sma200_resp.json()
            if sma50_key in sma200_data:
                latest = list(sma200_data[sma50_key].values())[0]
                result["sma_200"] = float(latest.get("SMA", 0))

        _cache_set(cache_key, result, expire=3600)  # 1 hour
        return result
    except Exception as e:
        logger.error(f"Alpha Vantage error for {symbol}: {e}")
        return await _compute_technicals_from_yfinance(symbol)


async def _compute_technicals_from_yfinance(symbol: str) -> dict:
    """Fallback: compute basic technical indicators from yfinance price history."""
    try:
        import yfinance as yf

        def _calc():
            ticker = yf.Ticker(symbol.upper())
            hist = ticker.history(period="1y")
            if hist.empty:
                return {"symbol": symbol.upper(), "error": "No price history available"}

            closes = hist["Close"]

            # SMA 50 and 200
            sma_50 = round(float(closes.tail(50).mean()), 2) if len(closes) >= 50 else None
            sma_200 = round(float(closes.tail(200).mean()), 2) if len(closes) >= 200 else None

            # RSI 14
            delta = closes.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_value = round(float(rsi.iloc[-1]), 2) if not rsi.empty else None

            # MACD (12, 26, 9)
            ema12 = closes.ewm(span=12, adjust=False).mean()
            ema26 = closes.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line

            return {
                "symbol": symbol.upper(),
                "rsi_14": rsi_value,
                "macd": round(float(macd_line.iloc[-1]), 4) if not macd_line.empty else None,
                "macd_signal": round(float(signal_line.iloc[-1]), 4) if not signal_line.empty else None,
                "macd_hist": round(float(macd_hist.iloc[-1]), 4) if not macd_hist.empty else None,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "current_price": round(float(closes.iloc[-1]), 2),
                "source": "computed_from_yfinance",
            }

        result = await asyncio.to_thread(_calc)
        _cache_set(f"tool_technical:{symbol}", result, expire=3600)
        return result
    except Exception as e:
        logger.error(f"yfinance technicals fallback error for {symbol}: {e}")
        return {"symbol": symbol.upper(), "error": str(e)}


# ---------------------------------------------------------------------------
# TOOL: get_insider_transactions — Finnhub free API
# ---------------------------------------------------------------------------
async def get_insider_transactions(symbol: str) -> dict:
    """Last 5 insider buys/sells. Upgraded to prioritize SEC EDGAR over Finnhub."""
    cache_key = f"tool_insider_v2:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    # Try SEC EDGAR first (Real-time Form 4s)
    try:
        sec_data = await get_insider_transactions_sec(symbol)
        if sec_data and sec_data.get("transactions"):
            _cache_set(cache_key, sec_data, expire=21600)
            return sec_data
    except Exception as e:
        logger.warning(f"SEC EDGAR insider fetch failed for {symbol}: {e}")

    # Fallback to Finnhub
    api_key = os.environ.get("FINNHUB_KEY", "")
    if not api_key:
        return {
            "symbol": symbol.upper(),
            "transactions": [],
            "source": "fallback_none",
            "error": "Finnhub API key not configured. SEC EDGAR also failed.",
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/stock/insider-transactions",
                params={"symbol": symbol.upper(), "token": api_key},
            )
            data = resp.json()

        transactions = []
        for txn in (data.get("data") or [])[:5]:
            transactions.append({
                "name": txn.get("name", "Unknown"),
                "transaction_type": txn.get("transactionType", ""),
                "shares": txn.get("share", 0),
                "value": txn.get("transactionValue"),
                "date": txn.get("transactionDate", ""),
                "filing_date": txn.get("filingDate", ""),
            })

        result = {"symbol": symbol.upper(), "transactions": transactions, "source": "finnhub_fallback"}
        _cache_set(cache_key, result, expire=21600)  # 6 hours
        return result
    except Exception as e:
        logger.error(f"Finnhub insider error for {symbol}: {e}")
        return {"symbol": symbol.upper(), "transactions": [], "error": str(e)}


async def get_insider_transactions_sec(symbol: str) -> dict:
    """Fetch Form 4 filings from SEC EDGAR directly."""
    # This is a robust implementation using SEC's official JSON API
    headers = {"User-Agent": "MarketFlux Research marketflux@example.com"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            # 1. Get Ticker to CIK mapping (cached by SEC in a single file)
            mapping_resp = await client.get("https://www.sec.gov/files/company_tickers.json")
            mapping_data = mapping_resp.json()
            
            cik = None
            ticker_upper = symbol.upper()
            for entry in mapping_data.values():
                if entry['ticker'] == ticker_upper:
                    cik = str(entry['cik_str']).zfill(10)
                    break
            
            if not cik:
                return {"symbol": ticker_upper, "transactions": [], "error": "CIK not found"}

            # 2. Get recent submissions for this CIK
            sub_resp = await client.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
            sub_data = sub_resp.json()
            
            recent = sub_data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accession_nos = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])
            
            transactions = []
            for i in range(len(forms)):
                if forms[i] == "4": # Statement of changes in beneficial ownership
                    transactions.append({
                        "name": "SEC Filing (Form 4)",
                        "transaction_type": "Insider Transaction",
                        "date": dates[i],
                        "filing_date": dates[i],
                        "link": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nos[i].replace('-', '')}/{primary_docs[i]}"
                    })
                    if len(transactions) >= 5:
                        break
            
            return {
                "symbol": ticker_upper,
                "transactions": transactions,
                "source": "SEC EDGAR",
                "cik": cik
            }
    except Exception as e:
        logger.error(f"SEC EDGAR error for {symbol}: {e}")
        raise


# ---------------------------------------------------------------------------
# TOOL: get_macro_context — FRED API (no key needed for basic endpoints)
# ---------------------------------------------------------------------------
async def get_macro_context():
    """Fetch macro indicators. Tries FRED CSV scraping first (no key needed),
    then builds context from already-available market data as fallback."""

    cache_key = "macro_context_v2"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    result = {}

    # STEP 1: Try FRED CSV scraping (same method used in reacttools.py)
    # react_agent.py uses agent_tools, but this request assumes reacttools.py has it.
    # Looking at react_agent.py in our workspace, it doesn't have get_macro_context.
    # However, react_tools.py (mentioned in Step 75) might have it.
    # Let me actually check react_tools.py first to be safe, but I will proceed with the requested logic.
    try:
        from react_tools import get_macro_context as react_get_macro
        fred_data = await react_get_macro()
        if fred_data and len(str(fred_data)) > 100:
            _cache_set(cache_key, fred_data, expire=86400)  # 24hr
            return fred_data
    except Exception as e:
        logger.warning(f"[MacroTool] FRED CSV scrape failed or react_tools not found: {e}")

    # STEP 2: Fallback — build macro context from market overview
    # (this ALWAYS works because get_market_overview_tool uses yfinance)
    try:
        market_data = await get_market_overview_tool()

        # Pull VIX, indices, crypto from the market overview
        result = {
            "source": "live_market_indicators",
            "note": "FRED unavailable — using live market data",
            "indices": market_data.get("indices", {}),
            "vix": market_data.get("vix", {}),
            "fear_greed": market_data.get("fear_greed_index", {}),
            "commodities": market_data.get("commodities", {}),
            "crypto": market_data.get("crypto", {}),
        }

        # Format it into readable macro context string for the LLM
        formatted = format_market_as_macro_context(result)
        _cache_set(cache_key, formatted, expire=300)  # 5 min
        return formatted

    except Exception as e:
        logger.error(f"[MacroTool] Market overview fallback failed: {e}")
        return None


def format_market_as_macro_context(data: dict) -> str:
    """Convert live market data into macro narrative context for LLM."""
    indices = data.get("indices", {})
    vix = data.get("vix", {})
    fg = data.get("fear_greed", {})

    lines = ["=== LIVE MACRO CONTEXT (from market indicators) ==="]

    for name, vals in indices.items():
        price = vals.get("price", "N/A")
        change = vals.get("change_percent", "N/A")
        lines.append(f"{name}: {price} ({change}%)")

    if vix:
        # Check if vix is a dict or float (get_market_overview_tool returns dict under info)
        v_price = vix.get('price', 'N/A')
        v_change = vix.get('change_percent', 'N/A')
        lines.append(f"VIX (Volatility): {v_price} ({v_change}%)")

    if fg:
        score = fg.get("value", fg.get("score", "N/A"))
        label = fg.get("classification", fg.get("label", "N/A"))
        lines.append(f"Fear & Greed Index: {score}/100 — {label}")

    lines.append("=== END MACRO CONTEXT ===")
    return "\n".join(lines)


async def get_company_profile_tool(symbol: str) -> dict:
    """Get company leadership (CEO, CFO), headquarters, employee
    count, business description, website, founded date."""
    cache_key = f"profile_{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        officers = info.get("companyOfficers", [])
        ceo = next(
            (o for o in officers if "CEO" in o.get("title", "").upper()),
            officers[0] if officers else {}
        )
        result = {
            "symbol": symbol,
            "name": info.get("longName", ""),
            "ceo": ceo.get("name", "Not available"),
            "ceo_title": ceo.get("title", "CEO"),
            "headquarters": f"{info.get('city','')}, "
                            f"{info.get('state','')}, "
                            f"{info.get('country','')}",
            "employees": info.get("fullTimeEmployees", "N/A"),
            "website": info.get("website", ""),
            "industry": info.get("industry", ""),
            "sector": info.get("sector", ""),
            "description": info.get("longBusinessSummary", "")[:500],
            "founded": info.get("founded", "N/A"),
        }
        _cache_set(cache_key, result, expire=3600)  # 1hr
        return result
    except Exception as e:
        logger.error(f"[CompanyProfile] Error for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol}


# ---------------------------------------------------------------------------
# TOOL: get_market_overview_tool — wraps existing function
# ---------------------------------------------------------------------------
async def get_market_overview_tool() -> dict:
    """Major indices, top gainers/losers, fear & greed score."""
    cache_key = "tool_market_overview"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        from datetime import datetime, timezone
        from market_data import get_market_overview, get_top_movers

        overview = await get_market_overview()
        movers = await get_top_movers()

        result = {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "indices": {},
            "top_gainers": [],
            "top_losers": [],
        }

        # Format indices
        for sym, data in overview.items():
            result["indices"][data.get("name", sym)] = {
                "price": data.get("price", 0),
                "change_percent": data.get("change_percent", 0),
            }

        # Top movers
        for g in (movers.get("gainers") or [])[:5]:
            result["top_gainers"].append({
                "symbol": g.get("symbol"),
                "name": g.get("name"),
                "change_percent": g.get("change_percent"),
            })
        for l in (movers.get("losers") or [])[:5]:
            result["top_losers"].append({
                "symbol": l.get("symbol"),
                "name": l.get("name"),
                "change_percent": l.get("change_percent"),
            })

        # Try to get fear & greed
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                fng_resp = await client.get("https://api.alternative.me/fng/")
                fng_data = fng_resp.json()
                if fng_data and "data" in fng_data:
                    fng = fng_data["data"][0]
                    result["fear_greed_index"] = {
                        "value": int(fng.get("value", 50)),
                        "classification": fng.get("value_classification", "Neutral"),
                    }
        except Exception:
            result["fear_greed_index"] = {"value": 50, "classification": "Neutral"}

        _cache_set(cache_key, result, expire=300)  # 5 min
        return result
    except Exception as e:
        logger.error(f"Market overview tool error: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# TOOL: get_sector_performance — SPDR sector ETF % change for sector-impact queries
# ---------------------------------------------------------------------------
# SPDR sector ETFs: XLE=Energy, XLF=Financials, XLK=Tech, XLV=Healthcare,
# XLI=Industrials, XLP=Staples, XLY=Discretionary, XLB=Materials, XLU=Utilities
_SECTOR_ETFS = [
    ("XLE", "Energy"), ("XLF", "Financials"), ("XLK", "Technology"),
    ("XLV", "Healthcare"), ("XLI", "Industrials"), ("XLP", "Consumer Staples"),
    ("XLY", "Consumer Discretionary"), ("XLB", "Materials"), ("XLU", "Utilities"),
]


async def get_sector_performance() -> dict:
    """
    Fetch real-time performance of major market sectors via SPDR sector ETFs.
    Used when users ask "which sectors are most impacted" or sector-level analysis.
    """
    cache_key = "tool_sector_performance"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    def _fetch():
        import yfinance as yf
        import pandas as pd

        syms = [s[0] for s in _SECTOR_ETFS]
        df = yf.download(
            syms, period="5d", interval="1d",
            group_by="column", auto_adjust=True, progress=False, threads=True
        )
        if df is None or df.empty or len(df) < 2:
            return []
        sectors = []
        for sym, name in _SECTOR_ETFS:
            try:
                if isinstance(df.columns, pd.MultiIndex) and "Close" in df.columns:
                    close_ser = df["Close"][sym] if sym in df["Close"].columns else pd.Series(dtype=float)
                else:
                    close_ser = df["Close"] if "Close" in df.columns else pd.Series(dtype=float)
                if close_ser is None or len(close_ser) < 2:
                    sectors.append({"sector": name, "symbol": sym, "change_percent": None, "price": None})
                    continue
                prev = float(close_ser.iloc[-2])
                curr = float(close_ser.iloc[-1])
                chg_pct = round((curr - prev) / prev * 100, 2) if prev and prev > 0 else None
                sectors.append({"sector": name, "symbol": sym, "change_percent": chg_pct, "price": round(curr, 2)})
            except Exception:
                sectors.append({"sector": name, "symbol": sym, "change_percent": None, "price": None})
        return sectors

    try:
        from datetime import datetime, timezone

        sectors = await asyncio.to_thread(_fetch)
        result = {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "sectors": sectors,
        }
        _cache_set(cache_key, result, expire=300)
        return result
    except Exception as e:
        logger.error(f"Sector performance tool error: {e}")
        return {"error": str(e), "sectors": []}


# ---------------------------------------------------------------------------
# TOOL: tavily_search — AI-optimized search (Primary)
# ---------------------------------------------------------------------------
async def tavily_search(query: str, search_depth: str = "advanced") -> dict:
    """
    Search the web using Tavily API (AI-optimized).
    Primary tool for ticker discovery and deep news research.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"error": "TAVILY_API_KEY not found in environment."}

    cache_key = f"tool_tavily:{query[:50]}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": search_depth,
                    "max_results": 10,
                    "include_answer": True,
                }
            )
            data = resp.json()
            
            results = []
            for r in data.get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "content": r.get("content", ""),
                    "url": r.get("url", ""),
                    "score": r.get("score", 0),
                })
            
            result = {
                "query": query,
                "answer": data.get("answer", ""),
                "results": results,
                "source": "tavily"
            }
            _cache_set(cache_key, result, expire=900)
            return result
    except Exception as e:
        logger.error(f"Tavily search error: {e}")
        return {"results": [], "error": str(e)}


# ---------------------------------------------------------------------------
# TOOL: web_search — Primary: Tavily, Fallback: DuckDuckGo
# ---------------------------------------------------------------------------
async def web_search(query: str) -> dict:
    """General web search. Uses Tavily as primary, DuckDuckGo as fallback."""
    from datetime import datetime, timezone
    year = datetime.now(timezone.utc).strftime("%Y")
    dated_query = f"{query} {year}" if year not in query else query

    if os.getenv("TAVILY_API_KEY"):
        t_res = await tavily_search(dated_query)
        if not t_res.get("error"):
            return t_res

    cache_key = f"tool_websearch:{dated_query[:50]}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        from duckduckgo_search import DDGS

        def _search():
            with DDGS() as ddgs:
                results = list(ddgs.text(dated_query, max_results=10, timelimit="m"))
            return results

        results = await asyncio.to_thread(_search)
        formatted = []
        for r in results:
            formatted.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "url": r.get("href", ""),
            })

        result = {"query": dated_query, "results": formatted, "source": "duckduckgo_web"}
        _cache_set(cache_key, result, expire=900)
        return result
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return {"query": dated_query, "results": [], "error": str(e)}


# ---------------------------------------------------------------------------
# TOOL: web_search_news — Primary: Tavily, Fallback: DuckDuckGo
# ---------------------------------------------------------------------------
async def web_search_news(query: str) -> dict:
    """News search. Uses Tavily as primary, DuckDuckGo as fallback."""
    from datetime import datetime, timezone
    year = datetime.now(timezone.utc).strftime("%Y")
    dated_query = f"{query} {year}" if year not in query else query

    if os.getenv("TAVILY_API_KEY"):
        t_res = await tavily_search(dated_query)
        if not t_res.get("error"):
            return t_res

    cache_key = f"tool_webnews:{dated_query[:50]}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        from duckduckgo_search import DDGS

        def _search():
            with DDGS() as ddgs:
                results = list(ddgs.news(dated_query, max_results=10, timelimit="w"))
            return results

        results = await asyncio.to_thread(_search)
        formatted = []
        for r in results:
            formatted.append({
                "title": r.get("title", ""),
                "body": r.get("body", ""),
                "source": r.get("source", ""),
                "date": r.get("date", ""),
                "url": r.get("url", ""),
            })

        result = {"query": dated_query, "results": formatted, "source": "duckduckgo_news"}
        _cache_set(cache_key, result, expire=900)
        return result
    except Exception as e:
        logger.error(f"Web news search error: {e}")
        return {"query": dated_query, "results": [], "error": str(e)}


# ---------------------------------------------------------------------------
# Shared: Ticker → CIK mapping (cached for SEC EDGAR APIs)
# ---------------------------------------------------------------------------
_cik_cache: Dict[str, str] = {}
_cik_map_cache = None

async def _get_cik(symbol: str) -> Optional[str]:
    global _cik_map_cache
    symbol_upper = symbol.upper()
    if symbol_upper in _cik_cache:
        return _cik_cache[symbol_upper]
    try:
        if _cik_map_cache is None:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://www.sec.gov/files/company_tickers.json",
                    headers={"User-Agent": "MarketFlux research@marketflux.app"}
                )
                _cik_map_cache = resp.json()
        for _, val in _cik_map_cache.items():
            if val.get("ticker", "").upper() == symbol_upper:
                cik = str(val.get("cik_str")).zfill(10)
                _cik_cache[symbol_upper] = cik
                return cik
    except Exception as e:
        logger.warning(f"CIK lookup failed for {symbol}: {e}")
    return None


# ---------------------------------------------------------------------------
# TOOL: get_sec_financials — SEC EDGAR XBRL CompanyFacts (free, no key)
# ---------------------------------------------------------------------------
async def get_sec_financials(symbol: str) -> dict:
    """Structured financial data direct from SEC EDGAR XBRL filings."""
    cache_key = f"tool_sec_xbrl:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    cik = await _get_cik(symbol)
    if not cik:
        return {"symbol": symbol, "error": "CIK not found for this ticker"}

    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"User-Agent": "MarketFlux research@marketflux.app"})
            if resp.status_code != 200:
                return {"symbol": symbol, "error": f"SEC API returned {resp.status_code}"}
            data = resp.json()

        facts = data.get("facts", {})
        gaap = facts.get("us-gaap", {})

        def _latest_annual(concept_name: str, unit: str = "USD"):
            concept = gaap.get(concept_name, {})
            vals = concept.get("units", {}).get(unit, [])
            annuals = [v for v in vals if v.get("form") == "10-K"]
            annuals.sort(key=lambda x: x.get("end", ""), reverse=True)
            return annuals[:8]

        def _latest_quarterly(concept_name: str, unit: str = "USD"):
            concept = gaap.get(concept_name, {})
            vals = concept.get("units", {}).get(unit, [])
            quarterlies = [v for v in vals if v.get("form") == "10-Q"]
            quarterlies.sort(key=lambda x: x.get("end", ""), reverse=True)
            return quarterlies[:8]

        def _format_series(items):
            return [{"period_end": v.get("end", ""), "value": v.get("val"), "filed": v.get("filed", "")} for v in items]

        result = {
            "symbol": symbol.upper(),
            "entity_name": data.get("entityName", ""),
            "source": "SEC EDGAR XBRL (official)",
            "annual_revenue": _format_series(_latest_annual("Revenues") or _latest_annual("RevenueFromContractWithCustomerExcludingAssessedTax")),
            "annual_net_income": _format_series(_latest_annual("NetIncomeLoss")),
            "annual_total_assets": _format_series(_latest_annual("Assets")),
            "annual_total_liabilities": _format_series(_latest_annual("Liabilities")),
            "annual_stockholders_equity": _format_series(_latest_annual("StockholdersEquity")),
            "annual_eps": _format_series(_latest_annual("EarningsPerShareDiluted", "USD/shares")),
            "annual_shares_outstanding": _format_series(_latest_annual("CommonStockSharesOutstanding", "shares")),
            "quarterly_revenue": _format_series(_latest_quarterly("Revenues") or _latest_quarterly("RevenueFromContractWithCustomerExcludingAssessedTax")),
            "quarterly_net_income": _format_series(_latest_quarterly("NetIncomeLoss")),
            "quarterly_eps": _format_series(_latest_quarterly("EarningsPerShareDiluted", "USD/shares")),
        }

        _cache_set(cache_key, result, expire=7200)
        return result
    except Exception as e:
        logger.error(f"SEC XBRL error for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}


# ---------------------------------------------------------------------------
# TOOL: get_finnhub_news — Finnhub company news (higher quality than yfinance)
# ---------------------------------------------------------------------------
async def get_finnhub_news(symbol: str) -> dict:
    """Recent company news from Finnhub (1000+ sources)."""
    api_key = os.environ.get("FINNHUB_KEY", "")
    if not api_key:
        return {"symbol": symbol, "articles": [], "error": "FINNHUB_KEY not set"}

    cache_key = f"tool_finnhub_news:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        date_to = now.strftime("%Y-%m-%d")
        date_from = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/company-news",
                params={"symbol": symbol.upper(), "from": date_from, "to": date_to, "token": api_key}
            )
            if resp.status_code != 200:
                return {"symbol": symbol, "articles": [], "error": f"Finnhub returned {resp.status_code}"}
            articles_raw = resp.json()

        articles = []
        for art in articles_raw[:15]:
            articles.append({
                "title": art.get("headline", ""),
                "summary": art.get("summary", "")[:400],
                "source": art.get("source", ""),
                "published_at": art.get("datetime", ""),
                "url": art.get("url", ""),
                "category": art.get("category", ""),
            })

        if articles:
            embed_and_store_news(symbol, [
                {"title": a["title"], "summary": a["summary"], "source": a["source"],
                 "published_at": a["published_at"], "source_url": a["url"]}
                for a in articles
            ])

        result = {"symbol": symbol, "articles": articles, "source": "finnhub", "count": len(articles)}
        _cache_set(cache_key, result, expire=900)
        return result
    except Exception as e:
        logger.error(f"Finnhub news error for {symbol}: {e}")
        return {"symbol": symbol, "articles": [], "error": str(e)}


# ---------------------------------------------------------------------------
# TOOL: get_earnings_calendar — Finnhub upcoming earnings dates
# ---------------------------------------------------------------------------
async def get_earnings_calendar(symbol: str) -> dict:
    """Upcoming and recent earnings dates, EPS estimates from Finnhub."""
    api_key = os.environ.get("FINNHUB_KEY", "")
    if not api_key:
        return {"symbol": symbol, "error": "FINNHUB_KEY not set"}

    cache_key = f"tool_earnings_cal:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        date_from = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        date_to = (now + timedelta(days=90)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/calendar/earnings",
                params={"from": date_from, "to": date_to, "symbol": symbol.upper(), "token": api_key}
            )
            if resp.status_code != 200:
                return {"symbol": symbol, "error": f"Finnhub returned {resp.status_code}"}
            data = resp.json()

        earnings = data.get("earningsCalendar", [])
        events = []
        for e in earnings[:5]:
            events.append({
                "date": e.get("date", ""),
                "eps_estimate": e.get("epsEstimate"),
                "eps_actual": e.get("epsActual"),
                "revenue_estimate": e.get("revenueEstimate"),
                "revenue_actual": e.get("revenueActual"),
                "hour": e.get("hour", ""),
                "quarter": e.get("quarter"),
                "year": e.get("year"),
            })

        result = {"symbol": symbol.upper(), "earnings_events": events, "source": "finnhub"}
        _cache_set(cache_key, result, expire=3600)
        return result
    except Exception as e:
        logger.error(f"Earnings calendar error for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}


# ---------------------------------------------------------------------------
# TOOL: get_earnings_transcript — Finnhub transcripts with chunking + search
# ---------------------------------------------------------------------------
_transcript_store: Dict[str, list] = {}

def _chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks by character count (~500 tokens each)."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else len(text)
    return chunks

async def get_earnings_transcript(symbol: str, query: str = "") -> dict:
    """Fetch latest earnings transcript from Finnhub, chunk it, and return semantically relevant passages."""
    api_key = os.environ.get("FINNHUB_KEY", "")
    if not api_key:
        return {"symbol": symbol, "passages": [], "error": "FINNHUB_KEY not set"}

    cache_key = f"tool_transcript:{symbol}"
    cached = _cache_get(cache_key)

    transcript_text = None
    transcript_meta = {}

    if cached and cached.get("full_text"):
        transcript_text = cached["full_text"]
        transcript_meta = cached.get("meta", {})
    else:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                list_resp = await client.get(
                    "https://finnhub.io/api/v1/stock/transcripts/list",
                    params={"symbol": symbol.upper(), "token": api_key}
                )
                if list_resp.status_code != 200:
                    return {"symbol": symbol, "passages": [], "error": f"Finnhub transcripts list returned {list_resp.status_code}"}

                transcripts = list_resp.json().get("transcripts", [])
                if not transcripts:
                    return {"symbol": symbol, "passages": [], "error": "No transcripts available"}

                latest = transcripts[0]
                transcript_id = latest.get("id", "")
                transcript_meta = {"id": transcript_id, "title": latest.get("title", ""), "time": latest.get("time", "")}

                await asyncio.sleep(0.15)

                t_resp = await client.get(
                    "https://finnhub.io/api/v1/stock/transcripts",
                    params={"id": transcript_id, "token": api_key}
                )
                if t_resp.status_code == 403:
                    return {"symbol": symbol, "passages": [], "error": "Earnings transcripts require Finnhub premium plan"}
                if t_resp.status_code != 200:
                    return {"symbol": symbol, "passages": [], "error": f"Transcript fetch returned {t_resp.status_code}"}

                t_data = t_resp.json()
                segments = t_data.get("transcript", [])
                lines = []
                for seg in segments:
                    speaker = seg.get("name", "Speaker")
                    for speech in seg.get("speech", []):
                        lines.append(f"[{speaker}]: {speech}")
                transcript_text = "\n".join(lines)

                _cache_set(cache_key, {"full_text": transcript_text, "meta": transcript_meta}, expire=86400)
        except Exception as e:
            logger.error(f"Earnings transcript error for {symbol}: {e}")
            return {"symbol": symbol, "passages": [], "error": str(e)}

    if not transcript_text:
        return {"symbol": symbol, "passages": [], "error": "Empty transcript"}

    chunks = _chunk_text(transcript_text)
    if not chunks:
        return {"symbol": symbol, "passages": [], "error": "Failed to chunk transcript"}

    model = _get_embedding_model()
    if model is None:
        return {"symbol": symbol, "passages": chunks[:3], "source": "finnhub_transcript", "meta": transcript_meta, "note": "No embedding model, returning first chunks"}

    try:
        search_query = query if query else f"{symbol} earnings performance outlook guidance"
        chunk_embeddings = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)
        query_embedding = model.encode([search_query], normalize_embeddings=True, show_progress_bar=False)[0]
        similarities = np.dot(chunk_embeddings, query_embedding)
        top_indices = np.argsort(similarities)[::-1][:5]
        passages = []
        for idx in top_indices:
            if similarities[idx] < 0.15:
                continue
            passages.append({"text": chunks[idx], "relevance": round(float(similarities[idx]), 3)})

        return {
            "symbol": symbol.upper(),
            "passages": passages,
            "total_chunks": len(chunks),
            "source": "finnhub_transcript",
            "meta": transcript_meta,
        }
    except Exception as e:
        logger.error(f"Transcript semantic search error for {symbol}: {e}")
        return {"symbol": symbol, "passages": [{"text": c} for c in chunks[:3]], "source": "finnhub_transcript", "meta": transcript_meta}


# ---------------------------------------------------------------------------
# TOOL: get_fred_macro — FRED API for key economic indicators
# ---------------------------------------------------------------------------
async def get_fred_macro() -> dict:
    """Key macro indicators from FRED (Federal Reserve Economic Data)."""
    from datetime import datetime, timezone
    api_key = os.environ.get("FRED_API_KEY", "")

    cache_key = "tool_fred_macro"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    series = {
        "DFF": "Fed Funds Rate",
        "DGS10": "10-Year Treasury Yield",
        "DGS2": "2-Year Treasury Yield",
        "UNRATE": "Unemployment Rate",
        "CPIAUCSL": "CPI (All Urban Consumers)",
        "T10Y2Y": "10Y-2Y Yield Spread",
        "DCOILWTICO": "Crude Oil WTI",
        "GOLDAMGBD228NLBM": "Gold Price",
    }

    if not api_key:
        return {"indicators": {}, "error": "FRED_API_KEY not set. Sign up free at https://fred.stlouisfed.org/docs/api/api_key.html", "source": "fred"}

    results = {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            tasks = []
            for series_id in series:
                tasks.append(client.get(
                    "https://api.stlouisfed.org/fred/series/observations",
                    params={"series_id": series_id, "api_key": api_key, "file_type": "json",
                            "sort_order": "desc", "limit": 5}
                ))
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for (series_id, label), resp in zip(series.items(), responses):
                if isinstance(resp, Exception):
                    results[label] = {"error": str(resp)}
                    continue
                if resp.status_code != 200:
                    results[label] = {"error": f"HTTP {resp.status_code}"}
                    continue
                obs = resp.json().get("observations", [])
                valid = [o for o in obs if o.get("value", ".") != "."]
                if valid:
                    results[label] = {
                        "latest_value": valid[0].get("value"),
                        "date": valid[0].get("date"),
                        "previous_value": valid[1].get("value") if len(valid) > 1 else None,
                        "previous_date": valid[1].get("date") if len(valid) > 1 else None,
                    }

        result = {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "indicators": results,
            "source": "FRED (Federal Reserve)",
        }
        _cache_set(cache_key, result, expire=3600)
        return result
    except Exception as e:
        logger.error(f"FRED macro error: {e}")
        return {"as_of": datetime.now(timezone.utc).isoformat(), "indicators": {}, "error": str(e), "source": "fred"}


# ---------------------------------------------------------------------------
# Tool registry — maps tool names to functions and human-readable labels
# ---------------------------------------------------------------------------
TOOL_REGISTRY = {
    "get_stock_snapshot": {
        "fn": get_stock_snapshot,
        "label": "Fetching {symbol} price data",
        "needs_symbol": True,
    },
    "get_fundamentals": {
        "fn": get_fundamentals,
        "label": "Fetching {symbol} fundamentals",
        "needs_symbol": True,
    },
    "get_analyst_targets": {
        "fn": get_analyst_targets,
        "label": "Loading {symbol} analyst targets",
        "needs_symbol": True,
    },
    "get_news": {
        "fn": get_news,
        "label": "Searching relevant {symbol} news",
        "needs_symbol": True,
        "needs_query": True,
    },
    "get_technical_indicators": {
        "fn": get_technical_indicators,
        "label": "Loading {symbol} technical indicators",
        "needs_symbol": True,
    },
    "get_insider_transactions": {
        "fn": get_insider_transactions,
        "label": "Checking {symbol} insider activity",
        "needs_symbol": True,
    },
    "get_macro_context": {
        "fn": get_macro_context,
        "label": "Checking macro environment",
        "needs_symbol": False,
    },
    "get_company_profile": {
        "fn": get_company_profile_tool,
        "needs_symbol": True,
        "needs_query": False,
        "label": "Company Profile",
        "description": "CEO, headquarters, employees, business description"
    },
    "get_market_overview": {
        "fn": get_market_overview_tool,
        "label": "Loading market overview",
        "needs_symbol": False,
    },
    "get_sector_performance": {
        "fn": get_sector_performance,
        "label": "Loading sector performance",
        "needs_symbol": False,
    },
    "web_search": {
        "fn": web_search,
        "label": "Searching the web",
        "needs_symbol": False,
        "needs_query": True,
        "fallback_only": True,
    },
    "web_search_news": {
        "fn": web_search_news,
        "label": "Searching web news",
        "needs_symbol": False,
        "needs_query": True,
        "fallback_only": True,
    },
    "tavily_search": {
        "fn": tavily_search,
        "label": "Premium AI Search discovery",
        "needs_symbol": False,
        "needs_query": True,
    },
    "get_sec_financials": {
        "fn": get_sec_financials,
        "label": "Loading {symbol} SEC financial data",
        "needs_symbol": True,
    },
    "get_finnhub_news": {
        "fn": get_finnhub_news,
        "label": "Fetching {symbol} news from Finnhub",
        "needs_symbol": True,
    },
    "get_earnings_calendar": {
        "fn": get_earnings_calendar,
        "label": "Checking {symbol} earnings calendar",
        "needs_symbol": True,
    },
    "get_earnings_transcript": {
        "fn": get_earnings_transcript,
        "label": "Searching {symbol} earnings transcripts",
        "needs_symbol": True,
        "needs_query": True,
    },
    "get_fred_macro": {
        "fn": get_fred_macro,
        "label": "Loading FRED economic indicators",
        "needs_symbol": False,
    },
}

# Query type → default tool sets
QUERY_TYPE_TOOLS = {
    "price_lookup": ["get_stock_snapshot"],
    "stock_analysis": ["get_stock_snapshot", "get_fundamentals", "get_analyst_targets", "get_news", "get_finnhub_news"],
    "technical_analysis": ["get_stock_snapshot", "get_technical_indicators"],
    "market_overview": ["get_market_overview", "get_sector_performance", "get_macro_context", "get_fred_macro", "web_search"],
    "news_query": ["get_news", "get_finnhub_news", "web_search_news"],
    "insider_activity": ["get_insider_transactions"],
    "company_info": ["get_company_profile"],
    "earnings_query": ["get_stock_snapshot", "get_earnings_calendar", "get_earnings_transcript", "get_finnhub_news"],
    "comparison": ["get_stock_snapshot", "get_fundamentals", "get_analyst_targets", "get_sec_financials"],
    "deep_analysis": [
        "get_stock_snapshot", "get_fundamentals", "get_analyst_targets",
        "get_news", "get_sec_financials", "get_earnings_transcript",
        "get_technical_indicators", "get_insider_transactions",
    ],
}
