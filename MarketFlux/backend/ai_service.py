import os
import re
import json
import logging
import asyncio
from typing import Dict, List, Optional, AsyncGenerator
from datetime import datetime, timezone, timedelta
import diskcache
import yfinance as yf

# Disable HuggingFace Hub network calls when loading models
os.environ["HF_HUB_OFFLINE"] = "1"

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from transformers import pipeline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Disk cache — valid ticker lookups are cached for 1 hour
# Store in app-local .cache directory (not world-readable /tmp/) — M5
# ---------------------------------------------------------------------------
_CACHE_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(_CACHE_BASE, mode=0o700, exist_ok=True)
_ticker_cache = diskcache.Cache(os.path.join(_CACHE_BASE, "ticker_cache"))
_usage_cache = diskcache.Cache(os.path.join(_CACHE_BASE, "usage_cache"))


_sentiment_pipeline = None

def _get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        try:
            logger.info("Lazy-loading FinBERT sentiment pipeline...")
            _sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")
            logger.info("FinBERT loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load FinBERT: {e}")
    return _sentiment_pipeline

# We defer genai configuration to lazily use the env var
_gemini_configured = False

def configure_gemini():
    global _gemini_configured
    if not _gemini_configured:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("No Gemini API key found (GEMINI_API_KEY). AI features will fail.")
        else:
            genai.configure(api_key=api_key)
            _gemini_configured = True

GEMINI_FLASH = "gemini-2.5-flash"
GEMINI_PRO = "gemini-2.5-pro"

def select_model_id(message: str, intent: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """
    Route to the right Gemini model based on task complexity.
    Uses Flash for simple tasks and Pro for deep analysis.
    Falls back to Flash if Pro fails or is rate-limited.
    """
    selected_model = GEMINI_FLASH

    pro_intents = {"comparison", "portfolio_review", "deep_analysis", "macro_stress_test"}
    if intent in pro_intents:
        selected_model = GEMINI_PRO

    if selected_model == GEMINI_FLASH:
        trigger_words = {"compare", "vs", "deep dive", "forecast", "valuation", "stress test"}
        message_lower = message.lower()
        is_complex = len(message.split()) > 50 or any(word in message_lower for word in trigger_words)
        if is_complex:
            selected_model = GEMINI_PRO

    if selected_model == GEMINI_PRO:
        if user_id:
            usage_key = f"pro_usage:{user_id}:{datetime.now().strftime('%Y-%m-%d')}"
            count = _usage_cache.get(usage_key, 0)
            if count >= 20:
                logger.info(f"User {user_id} reached Pro limit. Falling back to Flash.")
                selected_model = GEMINI_FLASH
            else:
                _usage_cache.set(usage_key, count + 1, expire=86400)

    logger.info(f"[ModelSelector] Selected {selected_model} for intent={intent}")
    return selected_model

def get_gemini_model(model_id: str = GEMINI_FLASH, system_instruction: Optional[str] = None):
    configure_gemini()
    
    # Safety settings to avoid blocking financial analysis
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    if system_instruction:
        return genai.GenerativeModel(model_id, system_instruction=system_instruction, safety_settings=safety_settings)
    return genai.GenerativeModel(model_id, safety_settings=safety_settings)


async def analyze_sentiments_batch(headlines: List[str]) -> List[Dict]:
    """
    Use open-source FinBERT for batch news sentiment analysis.
    Truncates to 512 chars and only classifies if confidence > 0.65.
    """
    try:
        global _sentiment_pipeline
        if not _sentiment_pipeline:
            return [{"label": "LOADING", "score": 0.0} for _ in headlines]
            
        if not headlines:
            return []

        # Truncate all headlines to 512 chars for FinBERT Tokenizer limits
        truncated_headlines = [h[:512] for h in headlines]

        # Use asyncio.to_thread()
        results = await asyncio.to_thread(_sentiment_pipeline, truncated_headlines)
        
        processed_results = []
        for res in results:
            label = res['label'].upper()
            score = round(res['score'], 2)
            
            # Fallback to Neutral if the model isn't confident enough
            if score < 0.65:
                label = 'NEUTRAL'
                
            processed_results.append({
                "label": label,
                "score": score
            })
            
        return processed_results
    except Exception as e:
        logger.error(f"Sentiment analysis batch error: {e}")
        return [{"label": "NEUTRAL", "score": 0.0} for _ in headlines]


async def generate_summary(title: str, content: str) -> str:
    try:
        model = get_gemini_model(system_instruction="You are a financial news summarizer for traders. Generate a 1-2 sentence factual summary focused on market impact. Return ONLY the summary text, nothing else.")
        response = await asyncio.to_thread(
            model.generate_content,
            f"Title: {title}\nContent: {content[:1000]}"
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Summary generation error: {e}")
        return ""


# ---------------------------------------------------------------------------
# Step 1 — Ticker Detection
# ---------------------------------------------------------------------------

def _validate_ticker_sync(symbol: str) -> bool:
    """Blocking validation — run in a thread executor."""
    cache_key = f"ticker_valid:{symbol}"
    cached = _ticker_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        info = yf.Ticker(symbol).info
        valid = bool(info.get("shortName") or info.get("longName"))
    except Exception:
        valid = False
    _ticker_cache.set(cache_key, valid, expire=3600)  # 1-hour TTL
    return valid


def detect_tickers(message: str) -> list:
    """Return up to 3 validated stock tickers found in *message*."""
    # Match 1-5 uppercase-letter sequences (not in the middle of a word)
    candidates = re.findall(r'\b([A-Z]{1,5})\b', message)
    # Deduplicate while preserving order
    seen, unique = set(), []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    # Common English words / finance terms to skip
    _SKIP = {
        "I", "A", "THE", "AND", "OR", "FOR", "IN", "OF", "TO", "BE",
        "IS", "IT", "AT", "BY", "AN", "AS", "ON", "IF", "DO", "SO",
        "AI", "PE", "EPS", "CEO", "IPO", "ETF", "GDP", "US", "UK",
        "EU", "USD", "LIVE", "NEWS", "BUY", "SELL", "HOLD", "ESG",
        "ROE", "ROA", "FCF", "TTM", "YOY", "QOQ", "CAGR"
    }
    filtered = [t for t in unique if t not in _SKIP]
    return filtered[:3]  # cap at 3


# ---------------------------------------------------------------------------
# Step 2 — Context Enrichment
# ---------------------------------------------------------------------------

FIELDS_TO_FETCH = [
    "currentPrice", "previousClose", "dayHigh", "dayLow",
    "marketCap", "trailingPE", "forwardPE",
    "revenueGrowth", "grossMargins", "operatingMargins",
    "debtToEquity", "currentRatio",
    "recommendationKey", "targetMeanPrice",
    "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    "longBusinessSummary", "shortName",
]


def _fetch_yf_info_sync(symbol: str) -> dict:
    """Blocking yfinance fetch — run in executor."""
    cache_key = f"yf_info:{symbol}"
    cached = _ticker_cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        raw = yf.Ticker(symbol).info
        data = {k: raw.get(k) for k in FIELDS_TO_FETCH}
        _ticker_cache.set(cache_key, data, expire=900)  # 15-min TTL for live data
        return data
    except Exception as e:
        logger.warning(f"yfinance fetch failed for {symbol}: {e}")
        return {}


def _fmt(val, prefix="", suffix="", decimals=2, scale=1):
    """Safely format a number, returning empty string on None/error."""
    try:
        if val is None:
            return "N/A"
        v = float(val) * scale
        return f"{prefix}{v:,.{decimals}f}{suffix}"
    except Exception:
        return "N/A"


def _fmt_mcap(val):
    try:
        v = float(val)
        if v >= 1e12:
            return f"${v/1e12:.2f}T"
        if v >= 1e9:
            return f"${v/1e9:.2f}B"
        if v >= 1e6:
            return f"${v/1e6:.2f}M"
        return f"${v:,.0f}"
    except Exception:
        return "N/A"


async def enrich_context(tickers: list, db) -> str:
    """Build a rich context string for each ticker using yfinance + MongoDB news."""
    sections = []
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    for symbol in tickers:
        info = await asyncio.to_thread(_fetch_yf_info_sync, symbol)
        if not info:
            continue

        # --- A) Live price & metrics ---
        price = info.get("currentPrice")
        prev = info.get("previousClose")
        change_pct = ""
        if price is not None and prev:
            try:
                change_pct = f"{((float(price) - float(prev)) / float(prev)) * 100:+.2f}%"
            except Exception:
                change_pct = "N/A"

        meta_lines = [
            f"=== {symbol} LIVE DATA ===",
            f"Name: {info.get('shortName', symbol)}",
            f"Price: {_fmt(price, '$')}  ({change_pct})",
            f"Day range: {_fmt(info.get('dayLow'), '$')} – {_fmt(info.get('dayHigh'), '$')}",
            f"52-week range: {_fmt(info.get('fiftyTwoWeekLow'), '$')} – {_fmt(info.get('fiftyTwoWeekHigh'), '$')}",
            f"Market cap: {_fmt_mcap(info.get('marketCap'))}",
            f"Trailing P/E: {_fmt(info.get('trailingPE'), decimals=1)}",
            f"Forward P/E: {_fmt(info.get('forwardPE'), decimals=1)}",
            f"Revenue growth (YoY): {_fmt(info.get('revenueGrowth'), suffix='%', scale=100, decimals=1)}",
            f"Gross margin: {_fmt(info.get('grossMargins'), suffix='%', scale=100, decimals=1)}",
            f"Operating margin: {_fmt(info.get('operatingMargins'), suffix='%', scale=100, decimals=1)}",
            f"Debt/Equity: {_fmt(info.get('debtToEquity'), decimals=2)}",
            f"Current ratio: {_fmt(info.get('currentRatio'), decimals=2)}",
            f"Analyst consensus: {info.get('recommendationKey', 'N/A').upper()}",
            f"Analyst price target: {_fmt(info.get('targetMeanPrice'), '$')}",
        ]
        sections.append("\n".join(meta_lines))

        # --- B) Recent MongoDB news ---
        try:
            news_docs = await db.news_articles.find(
                {
                    "$or": [
                        {"tickers": {"$in": [symbol]}},
                        {"title": {"$regex": re.escape(symbol), "$options": "i"}}
                    ],
                    "published_at": {"$gte": seven_days_ago}
                },
                {"_id": 0, "title": 1, "source": 1, "published_at": 1}
            ).sort("published_at", -1).limit(5).to_list(5)

            if news_docs:
                news_lines = [f"=== RECENT NEWS ({symbol}) ==="]
                for art in news_docs:
                    pub = art.get("published_at")
                    pub_str = pub.strftime("%b %d") if isinstance(pub, datetime) else str(pub)[:10]
                    news_lines.append(f"- {art.get('title', '?')} — {art.get('source', '?')}, {pub_str}")
                sections.append("\n".join(news_lines))
            else:
                sections.append(f"=== RECENT NEWS ({symbol}) ===\nNo recent news found in local database.")
        except Exception as e:
            logger.warning(f"News fetch error for {symbol}: {e}")
            sections.append(f"=== RECENT NEWS ({symbol}) ===\nUnable to fetch news.")

        # --- C) Business summary ---
        summary = info.get("longBusinessSummary", "")
        if summary:
            sections.append(f"=== COMPANY CONTEXT ({symbol}) ===\n{summary[:300]}...")

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Shared system prompt builder
# ---------------------------------------------------------------------------

def _build_system_prompt(enriched_context: str = "") -> str:
    base = (
        "You are MarketFlux AI, a premium financial research assistant. "
        "Your responses should be analytical, professional, and visually stunning.\n\n"
        "═══ PREMIUM FORMATTING RULES ═══\n"
        "1. VISUAL EXCELLENCE: Use rich Markdown (##, ###, bold, clear spacing).\n"
        "2. MANDATORY TABLES: Whenever reporting numerical metrics (prices, ratios, macro data), "
        "ALWAYS use Markdown tables (`|`). Never list numbers in plain text.\n"
        "3. DYNAMIC SUMMARIES: Start every section with a 1-sentence takeaway.\n"
        "4. STRUCTURED SECTIONS: Use H3 headers (###) for: Price Data, Technicals, Fundamentals, News.\n"
        "5. NO REFUSALS: Provide data-driven analysis for investment questions. End with 'This is not financial advice.'\n\n"
        "When LIVE CONTEXT DATA is provided, use those numbers to give grounded answers. "
        "Cite sources as (Live Data) or (Recent News).\n\n"
        "Structure for Stock Analysis:\n"
        "### 📊 Market Snapshot\n(price/volume table)\n"
        "### 💰 Metrics & Valuation\n(fundamental table)\n"
        "### 📰 Relevant News\n(bullet points)\n"
        "### 💡 Verdict\n(summary insight)\n\n"
        "End with: 'This analysis is based on available data. Always do your own research before investing.'\n"
    )
    if enriched_context.strip():
        base += f"\n\n--- LIVE CONTEXT DATA ---\n{enriched_context}\n--- END LIVE CONTEXT DATA ---"
    return base


# ---------------------------------------------------------------------------
# Sliding-window history trimmer (shared)
# ---------------------------------------------------------------------------

def _trim_history(history: list, message: str) -> tuple:
    """Return (trimmed_history, context_summary_line)."""
    context_line = ""
    if history and len(history) > 10:
        import collections
        old_msgs = history[:-10]
        words = " ".join(
            [m.get("message", "") + " " + m.get("response", "") for m in old_msgs]
        ).split()
        most_common = [w[0] for w in collections.Counter(words).most_common(20) if len(w[0]) > 4][:5]
        if most_common:
            context_line = f"Earlier in this conversation the user asked about: {', '.join(most_common)}\n"
        history = history[-10:]

    while history:
        total_chars = sum(len(m.get("message", "")) + len(m.get("response", "")) for m in history) + len(message)
        if (total_chars / 4) > 30000:
            logger.warning("Trimming chat history due to token limit")
            history = history[-max(len(history)-2, 4):]
        else:
            break
    return history, context_line


async def stream_ai_chat(
    message: str,
    session_id: str,
    db,
    user_id_for_db: str,
    context: str = "",
    stock_context: Optional[dict] = None,
    history: Optional[list] = None
) -> AsyncGenerator[str, None]:
    try:
        # --- Ticker detection & enrichment ---
        tickers = await asyncio.to_thread(detect_tickers, message)
        enriched_context = ""
        if tickers:
            logger.info(f"stream_ai_chat enriching context for tickers: {tickers}")
            enriched_context = await enrich_context(tickers, db)

        # Legacy stock_context (passed from endpoint) — still appended if present
        system_msg = _build_system_prompt(enriched_context)
        if stock_context and not tickers:
            system_msg += (
                f"\n\n[Stock Snapshot: "
                f"{json.dumps({k: v for k, v in stock_context.items() if k in ('symbol', 'price', 'change_percent')})}]"
            )

        history = history or []
        history, context_line = _trim_history(history, message)

        gemini_history = []
        for h in history:
            gemini_history.append({"role": "user", "parts": [h.get('message', '')]})
            gemini_history.append({"role": "model", "parts": [h.get('response', '')]})

        final_user_text = context_line
        if context:
            final_user_text += f"User context: {context}\n\n"
        final_user_text += f"User: {message}"

        model = get_gemini_model(system_instruction=system_msg)
        chat = model.start_chat(history=gemini_history)

        full_response = ""
        try:
            response_stream = await asyncio.to_thread(chat.send_message, final_user_text, stream=True)
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
                    full_response += chunk.text
                    await asyncio.sleep(0.01)
        except Exception as e:
            logger.warning(f"Stream generation error: {e}")
            try:
                response = await asyncio.to_thread(chat.send_message, final_user_text, stream=False)
                txt = (response.text or "").strip()
                if txt:
                    full_response = txt
                    for i in range(0, len(txt), 50):
                        chunk = txt[i : i + 50]
                        yield chunk
                        await asyncio.sleep(0.005)
            except Exception as e2:
                logger.error(f"Retry failed: {e2}")
                if not full_response:
                    yield "I'm having trouble generating a response right now. Please try again."
                    return

        await db.chat_messages.insert_one({
            "user_id": user_id_for_db,
            "session_id": session_id,
            "message": message,
            "response": full_response,
            "created_at": datetime.now(timezone.utc)
        })

    except Exception as e:
        logger.error(f"Stream error: {e}")
        yield "I'm having trouble generating a response right now. Please try again."


async def ai_chat(
    message: str,
    session_id: str,
    db,
    context: str = "",
    stock_context: Optional[dict] = None,
    history: Optional[list] = None
) -> str:
    """Non-streaming fallback — also enriches context from live data."""
    try:
        # --- Ticker detection & enrichment ---
        tickers = await asyncio.to_thread(detect_tickers, message)
        enriched_context = ""
        if tickers:
            logger.info(f"ai_chat enriching context for tickers: {tickers}")
            enriched_context = await enrich_context(tickers, db)

        system_msg = _build_system_prompt(enriched_context)
        if stock_context and not tickers:
            system_msg += (
                f"\n\n[Stock Snapshot: "
                f"{json.dumps({k: v for k, v in stock_context.items() if k in ('symbol', 'price', 'change_percent')})}]"
            )

        history = history or []
        history, context_line = _trim_history(history, message)

        gemini_history = []
        for h in history:
            gemini_history.append({"role": "user", "parts": [h.get('message', '')]})
            gemini_history.append({"role": "model", "parts": [h.get('response', '')]})

        final_user_text = context_line
        if context:
            final_user_text += f"User context: {context}\n\n"
        final_user_text += f"User: {message}"

        model = get_gemini_model(system_instruction=system_msg)
        chat = model.start_chat(history=gemini_history)

        response = await asyncio.to_thread(chat.send_message, final_user_text)
        return response.text.strip()
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return "I'm having trouble processing your request. Please try again."


async def ai_screen_stocks(query: str) -> Dict:
    try:
        model = get_gemini_model(system_instruction="""You are a stock screening filter generator. Your ONLY job is to convert a natural language stock query into a JSON filter object containing "finviz_filters_dict" (for Finviz API) and "custom_filters" (for exact local post-processing).

Example output:
{
  "finviz_filters_dict": {
    "Market Cap.": "Small ($300mln to $2bln)",
    "Sector": "Financial",
    "P/E": "Under 15",
    "Dividend Yield": "Positive (>0%)"
  },
  "custom_filters": {
    "pe_max": 12,
    "div_yield_min": 4.0
  },
  "explanation": "Filtering for small cap financial stocks with P/E under 12."
}

RULES for finviz_filters_dict keys and values (MUST match exactly):
- "Market Cap.": "Mega ($200bln and over)", "Large ($10bln to $200bln)", "Mid ($2bln to $10bln)", "Small ($300mln to $2bln)", "Micro ($50mln to $300mln)", "Nano (under $50mln)"
- "Sector": "Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Energy", "Financial", "Healthcare", "Industrials", "Real Estate", "Technology", "Utilities"
- "P/E": "Profitable (>0)", "Low (<15)", "High (>50)", "Under 5", "Under 10", "Under 15", "Under 20", "Under 25", "Under 30", "Under 35", "Under 40", "Under 45", "Under 50", "Over 5", "Over 10", "Over 15", "Over 20", "Over 25", "Over 30", "Over 35", "Over 40", "Over 45", "Over 50"
- "Dividend Yield": "None (0%)", "Positive (>0%)", "High (>5%)", "Very High (>10%)", "Over 1%", "Over 2%", "Over 3%", "Over 4%", "Over 5%", "Over 6%", "Over 7%", "Over 8%", "Over 9%", "Over 10%"
- "Current Volume": "Over 100K", "Over 500K", "Over 1M", "Over 5M", "Over 10M", "Over 20M"

CRITICAL RULES FOR FILTER LOGIC:
1. Exact Numbers: Finviz has big gaps (e.g. Under 10, Under 15). If the user asks for "P/E under 12", map finviz_filters_dict to the NEXT BROADEST valid Finviz filter (e.g. "Under 15") so no stocks are missed, and then add "pe_max": 12 in custom_filters.
2. Sector-Relative P/E: "low P/E" means something different per sector. If they ask for "low P/E" without numbers:
   - Technology: Use "P/E": "Under 25"
   - Energy/Financial/Utilities: Use "P/E": "Under 15"
   - Else: "Low (<15)".
3. Profitable: If the user explicitly asks for "profitable" companies, MUST INCLUDE "P/E": "Profitable (>0)" in finviz_filters_dict (unless superseded by a stricter P/E rule).
4. Do NOT hallucinate Finviz values. Only use the listed options for finviz_filters_dict. custom_filters can contain exact floats or ints.
custom_filters keys can be: pe_max, pe_min, div_yield_min, div_yield_max. Let percentages be floats (e.g. 4% = 4.0).
No markdown, no extra text, ONLY the JSON object.""")
        
        response = await asyncio.to_thread(model.generate_content, f"Convert to filters: {query}")
        response_text = response.text.strip()
        
        if "```" in response_text:
            parts = response_text.split("```")
            for part in parts:
                clean = part.strip()
                if clean.startswith("json"):
                    clean = clean[4:].strip()
                if clean.startswith("{"):
                    response_text = clean
                    break

        return json.loads(response_text)
    except Exception as e:
        logger.error(f"Stock screening error: {e}")
        return {"filters_dict": {}, "explanation": "Could not parse query. Try rephrasing."}

async def generate_screener_summary(query: str, stocks: list, filters: Dict) -> str:
    try:
        stock_table = ""
        for s in stocks[:10]:
            stock_table += f"- {s.get('symbol','?')}: ${s.get('price',0):.2f}, P/E={s.get('pe_ratio','N/A')}, MCap={s.get('market_cap',0)}, Sector={s.get('sector','?')}, Change={s.get('change_percent',0):.2f}%\n"

        model = get_gemini_model(system_instruction="""You are a senior equity research analyst.
Given the stock screening query and results, provide a deep, professional 1-paragraph analytical summary.
- Highlight the strongest themes or outliers in the results.
- Use professional finance terminology (e.g., "valuation multiples", "sectoral tailwinds").
- Use bold text for key tickers and metrics.
- End with a clear "Analytical Takeaway" line.
- End with "This is not investment advice."
""")

        response = await asyncio.to_thread(model.generate_content, f"Query: {query}\nFilters applied: {json.dumps(filters)}\nResults ({len(stocks)} stocks):\n{stock_table}")
        return response.text.strip()
    except Exception as e:
        logger.error(f"Screener summary error: {e}")
        return ""


async def rebalance_portfolio(portfolio_data: Dict, market_data: Dict) -> str:
    try:
        model = get_gemini_model(system_instruction="""You are a premium Portfolio Strategist.
Analyze the given portfolio and provide a high-end research report.

═══════════════════════════════════════
REPORT STRUCTURE
═══════════════════════════════════════
1. **Executive Summary** - 1 analytical paragraph on overall health.
2. **Current Allocation** - Use a clean Markdown table (Ticker, Shares, Value, % Weight).
3. **Risk Profile** - High-level assessment (Conservative/Moderate/Aggressive) with specific drivers.
4. **Diversification & Concentration** - Analyze sector/thematic exposure.
5. **Rebalancing Logic** - Provide specific, data-backed suggestions.
6. **Key Risk Factors** - Top 3 specific risks.

Use professional, sophisticated prose. Bold key metrics. Use tables for all numerical comparisons.
End with: "This analysis is for educational purposes only and is not financial advice."
""")

        response = await asyncio.to_thread(model.generate_content, f"Portfolio:\n{json.dumps(portfolio_data, indent=2)}\n\nMarket Data:\n{json.dumps(market_data, indent=2)}")
        return response.text.strip()
    except Exception as e:
        logger.error(f"Portfolio rebalance error: {e}")
        return "Unable to analyze portfolio at this time. Please try again."
