from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, BackgroundTasks, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import hashlib
import logging
import uuid
import asyncio
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import httpx
from fastapi.responses import StreamingResponse
from database import initialize_indexes
from cache import cache_get as redis_cache_get, cache_set as redis_cache_set

from news_scraper import fetch_all_feeds, store_articles
from market_data import (
    get_market_overview, get_top_movers, get_stock_info,
    get_stock_chart, search_tickers, get_ticker_news,
    get_rich_stock_data, get_price_analysis,
    filter_stocks_from_universe, search_all_stocks,
    get_heatmap_data
)
from ai_service import (
    generate_summary, ai_chat, ai_screen_stocks, generate_screener_summary, rebalance_portfolio
)
from agent_router import run_agent_pipeline

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import certifi

# MongoDB
mongo_url = os.environ['MONGO_URL']
if "mongodb+srv" in mongo_url:
    client = AsyncIOMotorClient(mongo_url, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
else:
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
db = client[os.environ['DB_NAME']]

# JWT — fail HARD at startup if secret is missing or weak
_raw_jwt_secret = os.environ.get('JWT_SECRET') or os.environ.get('JWT_SECRET_KEY')
if not _raw_jwt_secret or len(_raw_jwt_secret) < 32:
    raise RuntimeError(
        "SECURITY: JWT_SECRET env var is missing or too short (must be ≥32 chars). "
        "Generate one with: python3 -c 'import secrets; print(secrets.token_hex(32))'"
    )
JWT_SECRET = _raw_jwt_secret
JWT_ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------
_TICKER_RE = re.compile(r'^[A-Z0-9.\-\^]{1,10}$')

def validate_ticker(ticker: str) -> str:
    """Validate and normalise a ticker symbol. Raises 422 if invalid."""
    t = ticker.upper().strip()
    if not _TICKER_RE.match(t):
        raise HTTPException(422, f"Invalid ticker symbol: {ticker!r}")
    return t

def _hash_ip(ip: str) -> str:
    """Return a SHA-256 prefix of an IP for anonymous user IDs (GDPR-safe)."""
    return "anon_" + hashlib.sha256(ip.encode()).hexdigest()[:16]

from starlette.middleware.base import BaseHTTPMiddleware
class LimitRequestSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(("/api/ai/", "/api/portfolio", "/api/streams", "/api/parse")):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > 1048576:
                return Response("Request too large", status_code=413)
        return await call_next(request)

app = FastAPI()
app.add_middleware(LimitRequestSizeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def warmup_models():
    asyncio.create_task(_warmup_finbert())

async def _warmup_finbert():
    await asyncio.sleep(5)  # Let server finish starting first
    from ai_service import _get_sentiment_pipeline
    await asyncio.to_thread(_get_sentiment_pipeline)
    logger.info("FinBERT pre-warmed and ready")

@app.get("/")
def read_root():
    return {
        "status": "MarketFlux API is running", 
        "message": "Backend is active. Please use the frontend application at http://localhost:3000 to interact with MarketFlux."
    }

api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ===== Models =====
class UserRegister(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[str] = None
    ticker: Optional[str] = None

class ScreenerQuery(BaseModel):
    query: str

class PortfolioHolding(BaseModel):
    ticker: str
    shares: float
    avg_price: float

class PortfolioData(BaseModel):
    holdings: List[PortfolioHolding]

class StreamCreate(BaseModel):
    name: str
    filters: Dict

class WatchlistAdd(BaseModel):
    ticker: str


# ===== Auth Helpers =====
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request) -> Optional[Dict]:
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    if not session_token:
        return None

    # Try JWT first
    try:
        payload = jwt.decode(session_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"user_id": payload["user_id"]}, {"_id": 0})
        return user
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        pass

    # Try session-based auth
    session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if session:
        expires_at = session.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                return None
        user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
        return user

    return None

async def check_and_increment_ai_usage(request: Request) -> bool:
    user = await get_current_user(request)
    if user:
        return True
    client_ip = request.client.host if request.client else "unknown"
    now_utc = datetime.now(timezone.utc)
    current_minute = now_utc.strftime("%Y%m%d%H%M")
    
    # 1. Per-minute limit
    minute_key = f"{client_ip}_min_{current_minute}"
    minute_doc = await db.ai_usage.find_one_and_update(
        {"ip": minute_key},
        {
            "$inc": {"count": 1},
            "$setOnInsert": {"date": now_utc.replace(tzinfo=None), "type": "per_minute"}
        },
        upsert=True,
        return_document=True
    )
    if minute_doc and minute_doc.get("count", 0) > 30:
        return False

    # 2. Daily limit
    daily_key = client_ip
    daily_doc = await db.ai_usage.find_one_and_update(
        {"ip": daily_key},
        {
            "$inc": {"count": 1},
            "$set": {"last_used": now_utc.isoformat()},
            "$setOnInsert": {"date": now_utc.replace(tzinfo=None), "type": "daily"}
        },
        upsert=True,
        return_document=True
    )
    if daily_doc and daily_doc.get("count", 0) > 50:
        return False

    return True


# ===== Auth Routes =====
@api_router.post("/auth/register")
async def register(data: UserRegister, response: Response):
    existing = await db.users.find_one({"email": data.email}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Email already registered")

    user_id = f"user_{uuid.uuid4().hex}"  # Full 128-bit UUID for maximum entropy
    user_doc = {
        "user_id": user_id,
        "email": data.email,
        "name": data.name,
        "password_hash": hash_password(data.password),
        "auth_type": "jwt",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)

    token = create_jwt_token(user_id)
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*3600)
    return {"token": token, "user": {"user_id": user_id, "email": data.email, "name": data.name}}

@api_router.post("/auth/login")
async def login(data: UserLogin, response: Response, request: Request):
    # Brute-force protection: 5 failed attempts per IP per minute
    client_ip = request.client.host if request.client else "unknown"
    fail_key = f"login_fail:{client_ip}:{data.email}"
    fail_doc = await db.auth_rate_limit.find_one({"key": fail_key}, {"_id": 0})
    if fail_doc and fail_doc.get("count", 0) >= 5:
        last_attempt = fail_doc.get("last_attempt")
        if isinstance(last_attempt, str):
            last_attempt = datetime.fromisoformat(last_attempt)
        if last_attempt and last_attempt.tzinfo is None:
            last_attempt = last_attempt.replace(tzinfo=timezone.utc)
        if last_attempt and (datetime.now(timezone.utc) - last_attempt) < timedelta(minutes=1):
            raise HTTPException(429, "Too many failed login attempts. Please wait 1 minute.")

    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(data.password, user["password_hash"]):
        # Record failed attempt (consistent path regardless of email existence — prevents enumeration)
        await db.auth_rate_limit.update_one(
            {"key": fail_key},
            {"$inc": {"count": 1}, "$set": {"last_attempt": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        raise HTTPException(401, "Invalid credentials")

    # Clear failed attempts on success
    await db.auth_rate_limit.delete_one({"key": fail_key})

    token = create_jwt_token(user["user_id"])
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*3600)
    return {"token": token, "user": {"user_id": user["user_id"], "email": user["email"], "name": user["name"], "picture": user.get("picture", "")}}

@api_router.post("/auth/google-session")
async def google_session(request: Request, response: Response):
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(400, "session_id required")

    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    async with httpx.AsyncClient() as http_client:
        resp = await http_client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        if resp.status_code != 200:
            raise HTTPException(401, "Invalid session")
        google_data = resp.json()

    email = google_data["email"]
    user = await db.users.find_one({"email": email}, {"_id": 0})

    if not user:
        user_id = f"user_{uuid.uuid4().hex}"  # Full 128-bit UUID
        user = {
            "user_id": user_id,
            "email": email,
            "name": google_data.get("name", ""),
            "picture": google_data.get("picture", ""),
            "auth_type": "google",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
    else:
        user_id = user["user_id"]

    session_token = google_data.get("session_token", str(uuid.uuid4()))
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    response.set_cookie("session_token", session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7*24*3600)
    return {"user": {"user_id": user_id, "email": email, "name": user.get("name", ""), "picture": user.get("picture", "")}, "token": session_token}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return {"user_id": user["user_id"], "email": user["email"], "name": user.get("name", ""), "picture": user.get("picture", "")}

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("session_token", path="/")
    return {"message": "Logged out"}


# ===== Market Routes =====
def is_market_open() -> bool:
    from datetime import datetime
    import pytz
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close

@api_router.get("/market/overview")
async def market_overview(response: Response):
    cache_key = "market_overview"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        # Since is_market_open relies on time, recalculate it
        cached["is_market_open"] = is_market_open()
        if "as_of" not in cached:
            cached["as_of"] = datetime.now(timezone.utc).isoformat()
        return cached
    try:
        data = await get_market_overview()
        result = {"indices": data, "is_market_open": is_market_open(), "as_of": datetime.now(timezone.utc).isoformat()}
        redis_cache_set(cache_key, result, ttl=30)
        response.headers["X-Cache"] = "MISS"
        return result
    except Exception as e:
        logger.error(f"Market overview error: {e}")
        return {"indices": {}, "is_market_open": is_market_open(), "as_of": datetime.now(timezone.utc).isoformat()}

@api_router.get("/market/movers")
async def market_movers():
    try:
        data = await get_top_movers()
        return data
    except Exception as e:
        logger.error(f"Top movers error: {e}")
        return {"gainers": [], "losers": []}

@api_router.get("/market/heatmap")
async def market_heatmap():
    try:
        data = await get_heatmap_data()
        return data
    except Exception as e:
        logger.error(f"Market heatmap error: {e}")
        return {}

@api_router.get("/market/stock/{ticker}")
async def stock_detail(ticker: str, response: Response):
    ticker = validate_ticker(ticker)
    cache_key = f"stock:{ticker}"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached
    try:
        info = await get_stock_info(ticker)
        redis_cache_set(cache_key, info, ttl=60)
        response.headers["X-Cache"] = "MISS"
        return info
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, f"Stock {ticker} not found")

# Whitelist valid period/interval values to prevent abuse
_VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
_VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"}

@api_router.get("/market/chart/{ticker}")
async def stock_chart(ticker: str, period: str = "1mo", interval: str = "1d"):
    ticker = validate_ticker(ticker)
    if period not in _VALID_PERIODS:
        raise HTTPException(422, f"Invalid period. Must be one of: {', '.join(sorted(_VALID_PERIODS))}")
    if interval not in _VALID_INTERVALS:
        raise HTTPException(422, f"Invalid interval. Must be one of: {', '.join(sorted(_VALID_INTERVALS))}")
    try:
        data = await get_stock_chart(ticker, period, interval)
        return {"data": data}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, "Chart data not found")

@api_router.get("/market/stock/{ticker}/rich")
async def stock_rich(ticker: str, response: Response):
    """Get comprehensive stock data with fundamentals, dividends, and analysis."""
    ticker = validate_ticker(ticker)
    cache_key = f"stock_rich:{ticker}"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached
    try:
        stock_data, analysis = await asyncio.gather(
            get_rich_stock_data(ticker),
            get_price_analysis(ticker, 90)
        )
        stock_data["recent_moves"] = analysis.get("significant_daily_moves", [])
        stock_data["multi_day_moves"] = analysis.get("multi_day_moves", [])
        stock_data["max_drawdown_pct"] = analysis.get("max_drawdown_pct", 0)
        stock_data["period_high"] = analysis.get("period_high", 0)
        stock_data["period_low"] = analysis.get("period_low", 0)
        stock_data["current_vs_high_pct"] = analysis.get("current_vs_high_pct", 0)
        redis_cache_set(cache_key, stock_data, ttl=60)
        response.headers["X-Cache"] = "MISS"
        return stock_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rich stock error for {ticker}: {e}", exc_info=True)
        raise HTTPException(500, f"Error processing request for {ticker}")
    finally:
        # Final safety cleanup for any non-serializable numbers
        from market_data import sanitize_for_json
        if 'stock_data' in locals():
            return sanitize_for_json(stock_data)

@api_router.get("/market/stock/{ticker}/analysis")
async def stock_analysis(ticker: str, days: int = 90):
    """Get price move analysis for a ticker."""
    ticker = validate_ticker(ticker)
    if days < 1 or days > 365:
        raise HTTPException(422, "days must be between 1 and 365")
    try:
        analysis = await get_price_analysis(ticker, days)
        return analysis
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, "Analysis not found")

@api_router.get("/market/search")
async def search_market(q: str = ""):
    if not q or len(q) < 1:
        return {"results": []}
    results = await search_tickers(q)
    return {"results": results}


@api_router.get("/search-stocks")
async def search_stocks_endpoint(q: str = ""):
    """Global search endpoint for stock autocomplete."""
    if not q or len(q) < 1:
        return {"results": []}
    results = await search_all_stocks(q)
    return {"results": results}


# ===== News Routes =====
@api_router.get("/news/feed")
async def news_feed(
    request: Request,
    keyword: str = "",
    ticker: str = "",
    sentiment: str = "",
    category: str = "",
    page: int = 1,
    limit: int = 20,
    watchlist: bool = False,
):
    # --- Input validation & sanitization ---
    page = max(1, page)
    limit = max(1, min(limit, 100))  # Cap at 100 to prevent memory exhaustion (M2)

    query = {}
    if keyword:
        # Escape regex special chars to prevent ReDoS attacks (C2)
        keyword_safe = re.escape(keyword[:200])
        query["$or"] = [
            {"title": {"$regex": keyword_safe, "$options": "i"}},
            {"summary": {"$regex": keyword_safe, "$options": "i"}},
        ]
        
    if watchlist:
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to view watchlist news")
        wl = await db.watchlists.find_one({"user_id": user["user_id"]}, {"_id": 0})
        if wl and wl.get("tickers"):
            query["tickers"] = {"$in": wl["tickers"]}
        else:
            # Empty watchlist means no news matches
            return {"articles": [], "total": 0, "page": page, "has_more": False}
    elif ticker:
        query["tickers"] = {"$in": [ticker.upper()]}
        
    if sentiment:
        query["sentiment"] = sentiment
    if category:
        query["category"] = category
    
    include_duplicates = request.query_params.get("include_duplicates", "false").lower() == "true"
    if not include_duplicates:
        query["is_duplicate"] = {"$ne": True}

    skip = (page - 1) * limit
    articles = await db.news_articles.find(query, {"_id": 0}).sort("published_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.news_articles.count_documents(query)

    return {"articles": articles, "total": total, "page": page, "has_more": total > page * limit}

@api_router.get("/news/ticker/{ticker}")
async def ticker_news(ticker: str, response: Response):
    ticker = validate_ticker(ticker)
    cache_key = f"news:{ticker}"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached

    db_articles = await db.news_articles.find(
        {"tickers": {"$in": [ticker]}}, {"_id": 0}
    ).sort("published_at", -1).limit(20).to_list(20)

    yf_articles = await get_ticker_news(ticker.upper())

    seen_ids = {a["article_id"] for a in db_articles}
    for article in yf_articles:
        if article["article_id"] not in seen_ids:
            db_articles.append(article)

    db_articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    result = {"articles": db_articles[:30]}
    redis_cache_set(cache_key, result, ttl=300)
    response.headers["X-Cache"] = "MISS"
    return result

@api_router.post("/news/refresh")
async def refresh_news(request: Request, background_tasks: BackgroundTasks):
    # C3: Require authentication — prevents unauthenticated abuse of external API quotas
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Authentication required to trigger news refresh")
    background_tasks.add_task(fetch_and_store_news)
    return {"message": "News refresh started"}


# ===== Sentiment Routes =====
from market_data import cache_get_async, cache_set_async

@api_router.get("/sentiment/mood")
async def market_mood():
    """Returns the CNN Fear & Greed Index mapped to Bearish/Neutral/Bullish"""
    cache_key = "market_mood_fng"
    cached_mood = await cache_get_async(cache_key)
    if cached_mood:
        return cached_mood

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://api.alternative.me/fng/")
            data = response.json()
            
            if data and "data" in data and len(data["data"]) > 0:
                fng_value = int(data["data"][0]["value"])
                
                # Map CNN Fear & Greed (0-100) to our widgets (Bearish/Neutral/Bullish)
                if fng_value <= 40:
                    dominant = "bearish"
                elif fng_value <= 60:
                    dominant = "neutral"
                else:
                    dominant = "bullish"
                
                mood = {
                    "bullish": fng_value if dominant == "bullish" else (100 - fng_value) // 2,
                    "bearish": (100 - fng_value) if dominant == "bearish" else (100 - fng_value) // 2,
                    "neutral": 50 if dominant == "neutral" else 20,
                    "total": 100,
                    "fng_index": fng_value,
                    "dominant": dominant
                }
                
                # Cache for 1 hour
                await cache_set_async(cache_key, mood, expire=3600)
                return mood
                
    except Exception as e:
        logger.error(f"Failed to fetch Fear & Greed, returning fallback mood: {e}")
        
    # Safe Fallback if API is down
    fallback_mood = {"bullish": 33, "bearish": 33, "neutral": 34, "total": 100, "fng_index": 50, "dominant": "neutral"}
    return fallback_mood

@api_router.get("/sentiment/ticker/{ticker}")
async def ticker_sentiment(ticker: str):
    ticker = validate_ticker(ticker)
    articles = await db.news_articles.find(
        {"tickers": {"$in": [ticker]}, "sentiment": {"$ne": None}},
        {"_id": 0, "title": 1, "sentiment": 1, "sentiment_score": 1, "published_at": 1}
    ).sort("published_at", -1).limit(50).to_list(50)
    return {"ticker": ticker, "sentiment_data": articles}


# ===== AI Routes =====
@api_router.post("/ai/chat")
async def ai_chat_endpoint(data: ChatMessage, request: Request):
    if len(data.message) > 2000:
        raise HTTPException(400, "Message exceeds 2000 characters limit")
    data.message = ''.join(c for c in data.message if c.isprintable())

    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached. Please login for unlimited access.")

    # Build stock context if ticker provided
    stock_context = None
    if data.ticker:
        try:
            ticker_sym = data.ticker.upper()  # localise so type-checker knows it's str
            stock_data, analysis = await asyncio.gather(
                get_rich_stock_data(ticker_sym),
                get_price_analysis(ticker_sym, 90)
            )
            stock_data["recent_moves"] = analysis.get("significant_daily_moves", [])
            stock_data["multi_day_moves"] = analysis.get("multi_day_moves", [])
            stock_data["max_drawdown_pct"] = analysis.get("max_drawdown_pct", 0)

            # Fetch recent news for context — escape ticker to prevent ReDoS
            ticker_re = re.escape(ticker_sym)
            db_news = await db.news_articles.find(
                {"$or": [
                    {"tickers": {"$in": [ticker_sym]}},
                    {"title": {"$regex": ticker_re, "$options": "i"}}
                ]},
                {"_id": 0, "title": 1, "source": 1, "published_at": 1, "sentiment": 1}
            ).sort("published_at", -1).limit(10).to_list(10)
            stock_data["news"] = db_news

            stock_context = stock_data
        except Exception as e:
            logger.error(f"Context build error: {e}")

    user = await get_current_user(request)
    # H4: Hash raw IP before storing — IP addresses are PII under GDPR/CCPA
    _raw_ip = request.client.host if request.client else "unknown"
    user_id_for_db = user["user_id"] if user else _hash_ip(_raw_ip)
    sess_id = data.session_id or str(uuid.uuid4())
    
    # Fetch history
    history = await db.chat_messages.find({"user_id": user_id_for_db, "session_id": sess_id}).sort("created_at", -1).limit(10).to_list(10)
    history.reverse()

    response_text = await ai_chat(
        data.message,
        sess_id,
        db,
        data.context or "",
        stock_context=stock_context,
        history=history
    )

    await db.chat_messages.insert_one({
        "user_id": user_id_for_db,
        "session_id": sess_id,
        "message": data.message,
        "response": response_text,
        "created_at": datetime.now(timezone.utc),
    })

    return {"response": response_text}

@api_router.post("/ai/chat/stream")
async def ai_chat_stream_endpoint(data: ChatMessage, request: Request):
    if len(data.message) > 2000:
        raise HTTPException(400, "Message exceeds 2000 characters limit")
    data.message = ''.join(c for c in data.message if c.isprintable())

    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached. Please login for unlimited access.")

    user = await get_current_user(request)
    _raw_ip = request.client.host if request.client else "unknown"
    user_id_for_db = user["user_id"] if user else _hash_ip(_raw_ip)
    sess_id = data.session_id or str(uuid.uuid4())
    
    history = await db.chat_messages.find({"user_id": user_id_for_db, "session_id": sess_id}).sort("created_at", -1).limit(10).to_list(10)
    history.reverse()

    return StreamingResponse(
        run_agent_pipeline(
            message=data.message,
            ticker=data.ticker,
            history=history,
            db=db,
            user_id=user_id_for_db,
            session_id=sess_id,
            context=data.context or "",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

@api_router.get("/ai/screen/history")
async def ai_screen_history(request: Request):
    user = await get_current_user(request)
    _raw_ip = request.client.host if request.client else "unknown"
    user_id_for_db = user["user_id"] if user else _hash_ip(_raw_ip)
    history = await db.screener_history.find(
        {"user_id": user_id_for_db}, 
        {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    return {"history": history}

@api_router.post("/ai/screen")
async def ai_screen_endpoint(data: ScreenerQuery, request: Request):
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached. Please login for unlimited access.")

    filters = await ai_screen_stocks(data.query)
    stocks = await filter_stocks_from_universe(filters)
    summary = await generate_screener_summary(data.query, stocks, filters)

    suggestion = None
    if len(stocks) > 50:
        suggestion = "Too many results? Try adding criteria like 'revenue growth over 20%' or 'dividend yield above 2%'"
    elif len(stocks) == 0:
        suggestion = "No results found. The most restrictive filter was likely your market cap or P/E bounds. Try relaxing it."

    user = await get_current_user(request)
    _raw_ip = request.client.host if request.client else "unknown"
    user_id_for_db = user["user_id"] if user else _hash_ip(_raw_ip)
    
    await db.screener_history.insert_one({
        "user_id": user_id_for_db,
        "query": data.query,
        "result_count": len(stocks),
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    finviz_dict = filters.get("finviz_filters_dict") or filters.get("filters_dict") or {}
    custom_dict = filters.get("custom_filters") or {}
    
    applied = []
    for k, v in finviz_dict.items():
        if k not in ["Sector", "Market Cap."]:
            applied.append(f"{k}: {v}")
    for k, v in custom_dict.items():
        applied.append(f"Custom {k.replace('_', ' ')}: {v}")
            
    return {
        "query": data.query,
        "interpreted_as": {
            "sector": finviz_dict.get("Sector", "All"),
            "market_cap_range": finviz_dict.get("Market Cap.", "Any"),
            "filters_applied": applied,
            "filters_excluded": []
        },
        "stocks": stocks,
        "result_count": len(stocks),
        "summary": summary,
        "suggestion": suggestion
    }

@api_router.get("/ai/usage")
async def ai_usage(request: Request):
    user = await get_current_user(request)
    if user:
        return {"remaining": -1, "unlimited": True}
    client_ip = request.client.host if request.client else "unknown"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = await db.ai_usage.find_one({"ip": client_ip, "date": today}, {"_id": 0})
    count = usage.get("count", 0) if usage else 0
    return {"remaining": max(0, 3 - count), "unlimited": False}

@api_router.post("/ai/summarize")
async def ai_summarize(request: Request):
    body = await request.json()
    title = body.get("title", "")
    content = body.get("content", "")
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached.")
    summary = await generate_summary(title, content)
    return {"summary": summary}


# ===== Portfolio Routes =====
@api_router.get("/portfolio")
async def get_portfolio(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required for portfolio")
    portfolio = await db.portfolios.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return portfolio or {"user_id": user["user_id"], "holdings": []}

@api_router.post("/portfolio")
async def save_portfolio(data: PortfolioData, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    for h in data.holdings:
        validate_ticker(h.ticker)
    holdings = [h.model_dump() for h in data.holdings]
    await db.portfolios.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"user_id": user["user_id"], "holdings": holdings, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"message": "Portfolio saved", "holdings": holdings}

@api_router.post("/portfolio/rebalance")
async def rebalance_portfolio_endpoint(data: PortfolioData, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required for portfolio analysis")

    market_data = {}
    for holding in data.holdings:
        try:
            info = await get_stock_info(holding.ticker)
            market_data[holding.ticker] = info
        except Exception:
            pass

    portfolio_info = {
        "holdings": [
            {
                "ticker": h.ticker,
                "shares": h.shares,
                "avg_price": h.avg_price,
                "current_price": market_data.get(h.ticker, {}).get("price", 0),
                "current_value": market_data.get(h.ticker, {}).get("price", 0) * h.shares,
                "sector": market_data.get(h.ticker, {}).get("sector", "Unknown"),
            }
            for h in data.holdings
        ]
    }

    analysis = await rebalance_portfolio(portfolio_info, market_data)
    return {"analysis": analysis, "market_data": market_data}

@api_router.get("/portfolio-prices")
async def portfolio_prices(tickers: str = "", response: Response = None):
    """Batch fetch current prices for portfolio tickers."""
    if not tickers:
        return {}
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        return {}

    # Validate tickers
    for t in ticker_list:
        validate_ticker(t)

    sorted_key = ",".join(sorted(ticker_list))
    cache_key = f"portfolio_prices:{sorted_key}"
    cached = redis_cache_get(cache_key)
    if cached:
        if response:
            response.headers["X-Cache"] = "HIT"
        return cached

    prices = {}
    for t in ticker_list:
        try:
            info = await get_stock_info(t)
            prices[t] = {
                "price": info.get("price", 0),
                "change": info.get("change", 0),
                "change_percent": info.get("change_percent", 0),
            }
        except Exception:
            prices[t] = {"price": 0, "change": 0, "change_percent": 0}

    redis_cache_set(cache_key, prices, ttl=60)
    if response:
        response.headers["X-Cache"] = "MISS"
    return prices


@api_router.get("/stock-digest/{ticker}")
async def stock_digest(ticker: str, request: Request, refresh: bool = False, response: Response = None):
    """Generate an AI stock digest (Robinhood Cortex style)."""
    ticker = validate_ticker(ticker)
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached.")
    cache_key = f"digest:{ticker}"

    if not refresh:
        cached = redis_cache_get(cache_key)
        if cached:
            if response:
                response.headers["X-Cache"] = "HIT"
            return cached

    try:
        # Gather data for the digest concurrently
        stock_data, news_articles = await asyncio.gather(
            get_rich_stock_data(ticker),
            get_ticker_news(ticker)
        )
        headlines = [a.get("title", "") for a in news_articles[:5]]

        price = stock_data.get("price", 0)
        change_pct = stock_data.get("change_percent", 0)
        rec_key = stock_data.get("recommendation_key", "N/A")
        target_mean = stock_data.get("target_mean_price", "N/A")
        target_high = stock_data.get("target_high_price", "N/A")
        target_low = stock_data.get("target_low_price", "N/A")
        num_analysts = stock_data.get("number_of_analyst_opinions", "N/A")

        prompt = f"""You are a financial analyst. Given the following data for {ticker}, write a 3-paragraph stock digest like a professional research note.
Paragraph 1: What is happening with the stock today and why (price movement + news context).
Paragraph 2: What analysts are saying (consensus rating + price targets).
Paragraph 3: Key risks and opportunities to watch.
Keep it under 200 words total. Be direct and data-driven.

Data:
- Current Price: ${price}
- Daily Change: {change_pct}%
- Analyst Consensus: {rec_key}
- Price Targets: Low ${target_low}, Mean ${target_mean}, High ${target_high}
- Number of Analysts: {num_analysts}
- Recent Headlines: {'; '.join(headlines) if headlines else 'No recent news'}
"""

        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        ai_response = model.generate_content(prompt)
        digest_text = ai_response.text

        result = {
            "digest": digest_text,
            "ticker": ticker,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price": price,
            "change_percent": change_pct,
        }

        redis_cache_set(cache_key, result, ttl=900)
        if response:
            response.headers["X-Cache"] = "MISS"
        return result

    except Exception as e:
        logger.error(f"Stock digest error for {ticker}: {e}")
        return {
            "digest": f"Unable to generate digest for {ticker} at this time. Please try again later.",
            "ticker": ticker,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": True,
        }


@api_router.post("/parse-portfolio-image")
async def parse_portfolio_image(file: UploadFile = File(...)):
    if file.content_type not in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
        raise HTTPException(400, "Only PNG, JPEG, and WebP images are supported")
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(413, "Image must be under 5MB")

    import google.generativeai as genai
    import base64
    import json
    import os
    try:
        b64_image = base64.b64encode(contents).decode("utf-8")
        mime_type = file.content_type  # e.g. "image/png"
        
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content([
            {
                "mime_type": mime_type,
                "data": b64_image
            },
            'Look at this portfolio screenshot. Extract all stock holdings you can see. Return ONLY a valid JSON array with no explanation, no markdown, no code blocks, no backticks. Each object must have exactly these keys: ticker (string), shares (number), avgPrice (number, use 0 if not visible). Example: [{"ticker":"AAPL","shares":10,"avgPrice":195.50}]'
        ])
        
        raw = response.text.strip()
        # Strip any markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        
        holdings = json.loads(raw)
        return {"success": True, "holdings": holdings}
    except json.JSONDecodeError:
        return {"success": False, "error": "Could not parse holdings from image. Try a clearer screenshot."}
    except Exception as e:
        logger.error(f"Portfolio image parse error: {e}")
        return {"success": False, "error": "Failed to parse portfolio image. Please try a clearer screenshot."}

@api_router.post("/ai/follow-up")
async def ai_follow_up(request: Request):
    """Generate follow-up question suggestions based on conversation context."""
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached.")
    body = await request.json()
    last_response = body.get("last_response", "")
    topic = body.get("topic", "finance")

    if not last_response:
        return {"questions": []}

    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = f"""Given this conversation context and the last response about {topic}, suggest 3 short follow-up questions a retail investor would ask. Return ONLY a JSON array of 3 strings, no explanation. Example: ["What is the earnings date?", "How does this compare to last year?", "What are the main risks?"]

Last response snippet: {last_response[:500]}"""

        response = model.generate_content(prompt)
        import json as json_mod
        response_text = response.text.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        questions = json_mod.loads(response_text)

        if isinstance(questions, list) and len(questions) >= 3:
            return {"questions": questions[:3]}
        return {"questions": []}

    except Exception as e:
        logger.error(f"Follow-up generation error: {e}")
        return {"questions": []}

@api_router.get("/watchlist")
async def get_watchlist(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    watchlist = await db.watchlists.find_one({"user_id": user["user_id"]}, {"_id": 0})
    tickers = (watchlist or {}).get("tickers", [])
    stocks = []
    for ticker in tickers:
        try:
            info = await get_stock_info(ticker)
            stocks.append(info)
        except Exception:
            stocks.append({"symbol": ticker, "price": 0, "change_percent": 0})
    return {"tickers": tickers, "stocks": stocks}

@api_router.post("/watchlist")
async def add_to_watchlist(data: WatchlistAdd, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    validated = validate_ticker(data.ticker)
    await db.watchlists.update_one(
        {"user_id": user["user_id"]},
        {"$addToSet": {"tickers": validated}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"message": f"{validated} added to watchlist"}

@api_router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    await db.watchlists.update_one(
        {"user_id": user["user_id"]},
        {"$pull": {"tickers": ticker.upper()}},
    )
    return {"message": f"{ticker.upper()} removed from watchlist"}


# ===== Streams Routes =====
@api_router.get("/streams")
async def get_streams(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    streams = await db.streams.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(50)
    return {"streams": streams}

@api_router.post("/streams")
async def create_stream(data: StreamCreate, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    stream_id = f"stream_{uuid.uuid4().hex[:12]}"
    stream = {
        "stream_id": stream_id,
        "user_id": user["user_id"],
        "name": data.name,
        "filters": data.filters,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.streams.insert_one(stream)
    saved = await db.streams.find_one({"stream_id": stream_id}, {"_id": 0})
    return saved

@api_router.delete("/streams/{stream_id}")
async def delete_stream(stream_id: str, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    await db.streams.delete_one({"stream_id": stream_id, "user_id": user["user_id"]})
    return {"message": "Stream deleted"}


# ===========================================================================
# ===== Hedge Fund Research Routes (FundOS) =====
# ===========================================================================

class ResearchMemoRequest(BaseModel):
    ticker: str
    force_refresh: bool = False

class RiskAnalysisRequest(BaseModel):
    holdings: List[PortfolioHolding]

class ThematicRequest(BaseModel):
    theme: str

class SignalScanRequest(BaseModel):
    tickers: List[str]


# --- Quantitative Signal Endpoints ---

@api_router.get("/research/signals/{ticker}")
async def get_quant_signals(ticker: str, request: Request, response: Response):
    """Get 20+ quantitative signals for a ticker with composite score."""
    ticker = validate_ticker(ticker)
    cache_key = f"signals:{ticker}"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached

    try:
        from signal_engine import compute_signals
        result = await compute_signals(ticker, db=db)
        redis_cache_set(cache_key, result, ttl=900)  # 15 min cache
        response.headers["X-Cache"] = "MISS"
        return result
    except Exception as e:
        logger.error(f"Signal computation error for {ticker}: {e}")
        raise HTTPException(500, f"Signal computation failed: {str(e)}")


@api_router.post("/research/signals/scan")
async def scan_signals(data: SignalScanRequest, request: Request):
    """Batch signal scan across a list of tickers."""
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached. Please login for unlimited access.")

    tickers = [validate_ticker(t) for t in data.tickers[:20]]  # cap at 20
    try:
        from signal_engine import scan_universe
        results = await scan_universe(tickers, db=db, concurrency=3)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Signal scan error: {e}")
        raise HTTPException(500, f"Signal scan failed: {str(e)}")


# --- Research Memo Endpoints ---

@api_router.post("/research/memo")
async def generate_research_memo(data: ResearchMemoRequest, request: Request):
    """Generate a full Goldman Sachs-style research memo using multi-agent AI."""
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached. Please login for unlimited access.")

    ticker = validate_ticker(data.ticker)
    cache_key = f"research_memo:{ticker}"

    if not data.force_refresh:
        cached = redis_cache_get(cache_key)
        if cached:
            return cached

    try:
        from multi_agent import run_multi_agent_research
        result = await run_multi_agent_research(ticker, db=db)

        # Cache for 6 hours (fundamentals don't change hourly)
        redis_cache_set(cache_key, result, ttl=21600)

        # Persist to MongoDB for research history
        await db.research_memos.replace_one(
            {"symbol": ticker},
            {**result, "created_at": datetime.now(timezone.utc).isoformat()},
            upsert=True,
        )

        return result
    except Exception as e:
        logger.error(f"Research memo error for {ticker}: {e}")
        raise HTTPException(500, f"Research memo generation failed: {str(e)}")


@api_router.get("/research/memo/{ticker}/stream")
async def stream_research_memo(ticker: str, request: Request):
    """Stream a research memo generation with live SSE events."""
    ticker = validate_ticker(ticker)
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached. Please login for unlimited access.")

    from multi_agent import stream_multi_agent_research
    return StreamingResponse(
        stream_multi_agent_research(ticker, db=db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@api_router.get("/research/memo/history")
async def get_research_history(request: Request):
    """Get list of previously generated research memos."""
    memos = await db.research_memos.find(
        {}, {"_id": 0, "symbol": 1, "name": 1, "signal_score": 1, "signal_label": 1, "created_at": 1}
    ).sort("created_at", -1).limit(20).to_list(20)
    return {"memos": memos}


# --- Macro Dashboard Endpoint ---

@api_router.get("/macro/dashboard")
async def macro_dashboard(response: Response):
    """Full macro dashboard: yield curve, VIX regime, sectors, calendar."""
    cache_key = "macro_dashboard"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached

    try:
        from macro_data import get_macro_dashboard
        result = await get_macro_dashboard(db=db)
        redis_cache_set(cache_key, result, ttl=300)  # 5 min cache
        response.headers["X-Cache"] = "MISS"
        return result
    except Exception as e:
        logger.error(f"Macro dashboard error: {e}")
        raise HTTPException(500, f"Macro dashboard failed: {str(e)}")


# --- Risk Engine Endpoints ---

@api_router.post("/risk/portfolio")
async def portfolio_risk_analysis(data: RiskAnalysisRequest, request: Request):
    """Comprehensive portfolio risk analysis: beta, correlation, stress tests, VaR."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required for portfolio risk analysis")

    holdings_dicts = [h.model_dump() for h in data.holdings]

    try:
        from risk_engine import analyze_portfolio_risk
        result = await analyze_portfolio_risk(holdings_dicts, db=db)
        return result
    except Exception as e:
        logger.error(f"Portfolio risk analysis error: {e}")
        raise HTTPException(500, f"Risk analysis failed: {str(e)}")


@api_router.get("/risk/stock/{ticker}")
async def stock_risk_profile(ticker: str, response: Response):
    """Single stock risk profile: beta, VaR, drawdown, position sizing."""
    ticker = validate_ticker(ticker)
    cache_key = f"stock_risk:{ticker}"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached

    try:
        from risk_engine import analyze_single_stock_risk
        result = await analyze_single_stock_risk(ticker)
        redis_cache_set(cache_key, result, ttl=3600)  # 1 hr cache
        response.headers["X-Cache"] = "MISS"
        return result
    except Exception as e:
        logger.error(f"Stock risk profile error for {ticker}: {e}")
        raise HTTPException(500, f"Risk profile failed: {str(e)}")


# --- Earnings Intelligence Endpoints ---

@api_router.get("/research/earnings/{ticker}")
async def earnings_intelligence(ticker: str, request: Request, response: Response):
    """Earnings intelligence: pre/post analysis, beat rate, surprise probability."""
    ticker = validate_ticker(ticker)
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached. Please login for unlimited access.")

    cache_key = f"earnings_intel:{ticker}"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached

    try:
        from earnings_intel import get_earnings_intelligence
        result = await get_earnings_intelligence(ticker, db=db)
        redis_cache_set(cache_key, result, ttl=3600)  # 1 hr cache
        response.headers["X-Cache"] = "MISS"
        return result
    except Exception as e:
        logger.error(f"Earnings intelligence error for {ticker}: {e}")
        raise HTTPException(500, f"Earnings intelligence failed: {str(e)}")


@api_router.post("/research/earnings/calendar")
async def earnings_calendar(data: SignalScanRequest):
    """Get upcoming earnings dates for a list of tickers."""
    tickers = [validate_ticker(t) for t in data.tickers[:30]]
    try:
        from earnings_intel import get_earnings_calendar
        result = await get_earnings_calendar(tickers)
        return {"calendar": result}
    except Exception as e:
        logger.error(f"Earnings calendar error: {e}")
        raise HTTPException(500, f"Earnings calendar failed: {str(e)}")


# --- Idea Generation / Research Ideas Endpoint ---

@api_router.get("/research/ideas")
async def get_research_ideas(request: Request, response: Response):
    """Get today's morning briefing with top ideas, anomalies, and macro context."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_key = f"morning_briefing:{today}"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached

    # Check MongoDB first
    db_briefing = await db.morning_briefings.find_one({"date": today}, {"_id": 0})
    if db_briefing:
        redis_cache_set(cache_key, db_briefing, ttl=1800)
        response.headers["X-Cache"] = "DB_HIT"
        return db_briefing

    # Generate fresh (auth required for full generation)
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached. Please login for unlimited access.")

    try:
        from nightly_batch import generate_morning_briefing
        result = await generate_morning_briefing(db=db)
        redis_cache_set(cache_key, result, ttl=1800)
        response.headers["X-Cache"] = "GENERATED"
        return result
    except Exception as e:
        logger.error(f"Morning briefing error: {e}")
        raise HTTPException(500, f"Ideas generation failed: {str(e)}")


# --- Thematic Research Endpoint ---

@api_router.post("/research/thematic")
async def thematic_research(data: ThematicRequest, request: Request):
    """Thematic research engine: given a theme, score related stocks and produce ideas."""
    can_use = await check_and_increment_ai_usage(request)
    if not can_use:
        raise HTTPException(429, "AI usage limit reached. Please login for unlimited access.")

    if not data.theme or len(data.theme.strip()) < 3:
        raise HTTPException(400, "Theme must be at least 3 characters")

    # Sanitise theme input
    theme = data.theme.strip()[:200]
    theme = ''.join(c for c in theme if c.isprintable())

    cache_key = f"thematic:{hash(theme.lower())}"
    cached = redis_cache_get(cache_key)
    if cached:
        return cached

    try:
        from nightly_batch import run_thematic_research
        result = await run_thematic_research(theme, db=db)
        redis_cache_set(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        logger.error(f"Thematic research error: {e}")
        raise HTTPException(500, f"Thematic research failed: {str(e)}")


# --- Anomaly Detection Endpoint ---

@api_router.get("/research/anomalies")
async def market_anomalies(response: Response):
    """Scan top stocks for volume anomalies, breakouts, RSI extremes."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_key = f"anomalies:{today}"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached

    try:
        from nightly_batch import detect_anomalies, SP500_WATCHLIST
        results = await detect_anomalies(SP500_WATCHLIST[:50])
        redis_cache_set(cache_key, {"anomalies": results, "scanned": len(SP500_WATCHLIST[:50])}, ttl=1800)
        response.headers["X-Cache"] = "MISS"
        return {"anomalies": results, "scanned": len(SP500_WATCHLIST[:50])}
    except Exception as e:
        logger.error(f"Anomaly detection error: {e}")
        raise HTTPException(500, f"Anomaly detection failed: {str(e)}")


# --- Sector Rotation Endpoint ---

@api_router.get("/research/sector-rotation")
async def sector_rotation(response: Response):
    """Get current sector rotation analysis and phase classification."""
    cache_key = "sector_rotation"
    cached = redis_cache_get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        return cached

    try:
        from nightly_batch import analyze_sector_rotation
        result = await analyze_sector_rotation()
        redis_cache_set(cache_key, result, ttl=1800)
        response.headers["X-Cache"] = "MISS"
        return result
    except Exception as e:
        logger.error(f"Sector rotation error: {e}")
        raise HTTPException(500, f"Sector rotation analysis failed: {str(e)}")


# ===========================================================================
# ===== End Hedge Fund Research Routes =====
# ===========================================================================


# ===== Background Tasks =====
async def fetch_and_store_news():
    try:
        articles = await fetch_all_feeds()
        stored = await store_articles(db, articles)

        # Articles already have sentiment computed via fetch_all_feeds
        unanalyzed = await db.news_articles.find(
            {"sentiment": None}, {"_id": 0}
        ).sort("published_date", -1).limit(50).to_list(50)

        if unanalyzed:
            titles = [article["title"] for article in unanalyzed]
            
            # Using our robust imported ai_service batch processor
            from ai_service import analyze_sentiments_batch
            sentiments = await analyze_sentiments_batch(titles)
            
            for article, sentiment in zip(unanalyzed, sentiments):
                try:
                    await db.news_articles.update_one(
                        {"article_id": article["article_id"]},
                        {"$set": {
                            "sentiment": sentiment["label"],
                            "sentiment_score": sentiment["score"],
                        }}
                    )
                except Exception as e:
                    logger.error(f"Sentiment DB update error: {e}")

        logger.info(f"News refresh: {stored} new, {len(unanalyzed)} retro-analyzed")
    except Exception as e:
        logger.error(f"News fetch error: {e}")

async def periodic_news_fetch():
    while True:
        await fetch_and_store_news()
        await asyncio.sleep(600)

@app.on_event("startup")
async def startup():
    # JWT_SECRET is already validated at module load time (C1).
    # Additional production environment checks:
    if os.environ.get('NODE_ENV') == 'production' and "localhost" in os.environ.get('MONGO_URL', ''):
        logger.warning("WARNING: App is running in production with a localhost MongoDB URL!")

    await initialize_indexes(db)

    # Ensure TTL index on auth_rate_limit so old keys auto-expire after 5 minutes
    try:
        await db.auth_rate_limit.create_index("last_attempt", expireAfterSeconds=300)
    except Exception:
        pass

    try:
        from vnext.fundos_pg_client import get_pg_pool, is_pg_configured

        if is_pg_configured():
            await get_pg_pool()
            logger.info("Shared vNext Postgres pool initialized")
        else:
            logger.info("Shared vNext Postgres pool skipped: MARKETFLUX_VNEXT_DATABASE_URL/FUNDOS_DATABASE_URL not configured")
    except Exception as exc:
        logger.warning(f"Postgres pool initialization failed: {exc}")

    asyncio.create_task(periodic_news_fetch())
    logger.info("MarketFlux backend started")

@app.on_event("shutdown")
async def shutdown():
    try:
        from vnext.fundos_pg_client import close_pg_pool

        await close_pg_pool()
    except Exception:
        pass
    client.close()

app.include_router(api_router)

from vnext.router import build_vnext_router
from vnext.adapter import build_adapter_router
from vnext.fundos_router import build_fundos_router

app.include_router(build_vnext_router(db, get_current_user))
app.include_router(build_adapter_router(db, get_current_user))
app.include_router(build_fundos_router(db, get_current_user))
