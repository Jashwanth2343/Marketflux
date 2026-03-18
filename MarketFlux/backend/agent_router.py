"""
Agent Router for MarketFlux Agentic RAG.

Handles:
- Intent classification via Gemini Flash
- Parallel tool execution
- SSE event streaming pipeline
- Web search fallback for unknown tickers
"""

import re
import json
import asyncio
import logging
from typing import Dict, List, Any, AsyncGenerator, Optional
from datetime import datetime, timezone

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from agent_tools import (
    TOOL_REGISTRY, QUERY_TYPE_TOOLS,
    get_stock_snapshot, web_search, resolve_company_to_ticker,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt with Section 13 behavioral rules
# ---------------------------------------------------------------------------
AGENT_SYSTEM_PROMPT = """You are MarketFlux AI — a premium financial research assistant.
Your goal is to provide deep, analytical, and visually stunning responses.

═══════════════════════════════════════
COMMAND: EXECUTION OVER DESCRIPTION
═══════════════════════════════════════

- LIVE DATA IS ALWAYS AVAILABLE: You have access to a real-time market snapshot (Indices, VIX, Fear & Greed) which is injected into your context. Use THESE exact numbers if the user asks any macro or market questions.
- DATA IS MANDATORY: Never describe what a report *would* contain. You MUST populate every section with actual numbers from the live tools results provided below.
- NO META-DESCRIPTION: Never say "I have already analyzed this" or "Here is what I can show you." Just show the data.
- ANALYTICAL PROSE: Every section must start with a 1-sentence expert takeaway. Use professional finance terminology.

═══════════════════════════════════════
PREMIUM DESIGN PRINCIPLES
═══════════════════════════════════════

1. VISUAL EXCELLENCE: Use rich Markdown (##, ###, bold, clear spacing). Format like a Goldman Sachs research note.

2. TABLES ARE MANDATORY FOR DATA: Every numerical metric (Price, P/E, Macro indicators) MUST be in a table. Use `|`.

3. STRUCTURED SECTIONS:
   - Use H3 headers (###) for major sections.
   - For stocks, use: ### 📊 Price Performance, ### 📈 Technical Outlook, ### 💰 Fundamentals & Valuation, ### 📰 Market Sentiment.
   - For macro, use: ### 🌍 Economic Indicators, ### 🎙️ Key News Impact, ### 💡 Market Context.
   - For company info: ### 🏢 Company Profile.

4. MACRO QUESTIONS: Every macro/market response MUST use the live index/VIX/Fear & Greed data provided in the snapshot. Do not say "the market is volatile" without citing the VIX number.

5. COMPANY INFO & FACTUAL DATA: It is NEVER appropriate to add an investment disclaimer to company_info or price_lookup queries. See specific rules below.

6. NO REFUSALS: Provide data-driven analysis for investment queries. End with "This is not financial advice."

═══════════════════════════════════════
RESPONSE LENGTH RULES — NON-NEGOTIABLE:
═══════════════════════════════════════

You are a precision instrument, not a research report generator. Match your response length exactly to what was asked. More words do not mean better answers.

company_info queries (CEO, headquarters, founded date, employee count, website, leadership):
→ Maximum: 2 sentences OR one small table (3 rows max)
→ Only include the specific person/place/date asked for
→ NEVER add financial metrics, P/E, revenue, or margins
→ NEVER add the investment disclaimer
→ Correct: "Tim Cook has been Apple's CEO since 2011."
→ Wrong: anything with a fundamentals table attached

price_lookup queries (current price, single metric):
→ State the number in the first sentence always
→ One sentence of context maximum
→ No tables unless the user asked to compare tickers
→ NEVER add the investment disclaimer

The investment disclaimer ending with "Always do your own research before investing" is ONLY for:
deep_analysis, stock_analysis, comparison queries.

It is NEVER appropriate for: company_info, price_lookup, factual, general_chat, macro_overview queries.
Attaching an investment disclaimer to "who is the CEO" is like a restaurant adding a health warning to a glass of water. It signals the system is not smart enough to know context.

End every report with: "This analysis is based on available data. Always do your own research before investing." (ONLY IF APPLICABLE PER RULES ABOVE)
"""

INTENT_PROMPTS = {
    "comparison": """
### ⚔️ Side-by-Side Comparison
Use a single Markdown table to compare all mentioned symbols across Price, P/E, Revenue Growth, and Margins.
Add a 'Winner' column for each metric based on the data.
""",
    "portfolio_review": """
### 🛡️ Portfolio Risk Assessment
Analyze the user's holdings for concentration risk and sector exposure.
Provide a 'Stress Test' table showing how this portfolio might perform in a 10% market correction.
""",
    "technical_analysis": """
### 📉 Technical Deep Dive
Focus heavily on RSI, MACD, and Moving Average crossovers.
Explicitly state if the asset is Overbought, Oversold, or Neutral.
""",
    "earnings_query": """
### 📢 Earnings Insight
Focus on the most recent quarter's EPS vs Estimates and Guidance.
Analyze management tone (if news sentiment is available).
""",
    "company_info": """
### 🏢 Factual Quick-Response
Provide ONLY the requested factual data (CEO, HQ, etc.) from `get_company_profile`. 
- DO NOT provide any financial performance data (P/E, Revenue, Market Cap), stock charts, or valuation analysis unless specifically asked.
- Max length: 3 sentences or 1 simple table.
- If multiple stocks share a ticker (e.g. SEI vs SEIC), add one brief clarification sentence.
""",
}


# ---------------------------------------------------------------------------
# Intent Classification
# ---------------------------------------------------------------------------
async def classify_intent(message: str, ticker_hint: Optional[str] = None) -> dict:
    """
    Classify user query into intent type and determine which tools to call.
    Uses the cheapest/fastest model tier (Gemini Flash).
    """
    from ai_service import configure_gemini
    configure_gemini()

    # Build classifier prompt
    classifier_prompt = f"""Classify this financial query and extract any stock symbols mentioned.

User query: "{message}"
{f'Current page ticker: {ticker_hint}' if ticker_hint else ''}

Return a JSON object with:
- "symbols": list of stock ticker symbols mentioned or implied (e.g. ["AVGO"]). Resolve company NAMES to tickers.
- "query_type": one of: "price_lookup", "stock_analysis", "technical_analysis", "market_overview", "news_query", "insider_activity", "company_info", "deep_analysis", "comparison", "portfolio_review", "earnings_query"
- "tools_needed": list of tool names to call
- "needs": a boolean map of data requirements: {{"price": bool, "fundamentals": bool, "news": bool, "technicals": bool, "macro": bool}}

Query type rules:
- "comparison": Comparing 2 or more stocks (e.g. "AAPL vs MSFT")
- "portfolio_review": Assessing multiple holdings (e.g. "Review my portfolio of AAPL, TSLA, and NVDA")
- "earnings_query": About earnings dates, EPS, or calls
- "price_lookup": Just the price
- "stock_analysis": General analysis
- "technical_analysis": RSI, MACD, etc.
- "market_overview": General market/macro context
- "news_query": Recent news/headlines
- "insider_activity": Buying/selling by executives
- "company_info": CEO, HQ, employees, profile

Return ONLY valid JSON, nothing else."""

    try:
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        model = genai.GenerativeModel(
            "gemini-flash-latest",  # Reliable tier for classification
            safety_settings=safety_settings,
        )

        response = await asyncio.to_thread(model.generate_content, classifier_prompt)
        response_text = response.text.strip()

        # Parse JSON from response
        if "```" in response_text:
            parts = response_text.split("```")
            for part in parts:
                clean = part.strip()
                if clean.startswith("json"):
                    clean = clean[4:].strip()
                if clean.startswith("{"):
                    response_text = clean
                    break

        result = json.loads(response_text)

        # Validate and fill defaults
        if "symbols" not in result:
            result["symbols"] = []
        if "tools_needed" not in result:
            result["tools_needed"] = QUERY_TYPE_TOOLS.get(result["query_type"], ["get_stock_snapshot"])
        if "needs" not in result:
            result["needs"] = {"price": True, "fundamentals": True, "news": True, "technicals": False, "macro": False}

        # If ticker_hint provided and no symbols detected, use hint
        if ticker_hint and not result["symbols"]:
            result["symbols"] = [ticker_hint.upper()]

        # Investment questions MUST include technical indicators
        _INVEST_PHRASES = ["should i sell", "should i buy", "should i invest",
                           "should sell", "should buy", "worth buying", "worth investing",
                           "entry point", "entry position", "good time to buy",
                           "good time to sell", "time to sell", "time to buy"]
        msg_lower = message.lower()
        if any(phrase in msg_lower for phrase in _INVEST_PHRASES):
            for tool in ["get_technical_indicators", "get_stock_snapshot", "get_fundamentals", "get_analyst_targets", "get_news"]:
                if tool not in result["tools_needed"]:
                    result["tools_needed"].append(tool)

        return result

    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        # Fallback: simple heuristic classification
        return await _heuristic_classify(message, ticker_hint)


async def _heuristic_classify(message: str, ticker_hint: Optional[str] = None) -> dict:
    """Fallback heuristic classifier when LLM classification fails."""
    msg_lower = message.lower()

    # Detect symbols from message (case-insensitive)
    symbols = re.findall(r'\b([A-Z]{1,5})\b', message.upper())
    _SKIP = {"I", "A", "THE", "AND", "OR", "FOR", "IN", "OF", "TO", "IS", "IT", "AT",
             "AI", "PE", "EPS", "CEO", "IPO", "ETF", "GDP", "US", "UK", "EU", "USD",
             "NEWS", "BUY", "SELL", "HOLD", "NOT", "HOW", "WHY", "WHAT", "ARE", "CAN",
             "DO", "YOU", "YOUR", "MY", "ME", "WE", "SO", "IF", "ON", "UP", "AN", "AS",
             "BE", "BY", "GO", "NO", "HE", "HIS", "HER", "ITS", "ALL", "ANY", "FEW",
             "DOES", "DID", "HAS", "HAD", "HAVE", "BEEN", "BEEN", "WITH", "THIS", "THAT",
             "THEY", "THEM", "ALSO", "THAN", "THEN", "FROM", "SOME", "MOST", "VERY",
             "WILL", "MUCH", "JUST", "LIKE", "GOOD", "BEST", "LONG", "WHEN", "OVER",
             "SELL", "BUY", "HOLD", "NOT", "RSI", "MACD", "SMA", "EMA", "YOY",
             "ABOUT", "WOULD", "COULD", "THINK", "SHOULD", "WHERE", "WHICH",
             "YES", "NOW", "GET", "OUT", "WAS", "BUT", "MAY", "TOP", "LOW",
             "DAY", "NEW", "OLD", "OWN", "SET", "WAY", "WELL","HIGH", "RATE",
             "SURE", "TELL", "GIVE", "TAKE", "MAKE", "HELP", "LOOK", "WANT",
             "ENTRY", "POINT", "WORTH", "RIGHT", "TIME", "EVEN", "BEEN", "EACH",
             "NEED", "BEEN", "ONLY", "FIND", "SAME", "YEAR", "FULL", "TYPE",
             "MADE", "DEAL", "DEALS", "MUCH", "DOWN", "WORK", "DONE", "PLAN",
             "MOVE", "REAL", "LIVE", "LATE", "DATA", "OPEN", "SHOW", "VIEW"}
    symbols = [s for s in symbols if s not in _SKIP][:3]

    # If no symbols found, try to resolve company names from the message
    if not symbols:
        # Extract potential company names (words that aren't in _SKIP and are 3+ chars)
        words = re.findall(r'\b([a-zA-Z]{3,})\b', message.lower())
        _COMMON = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
                   "her", "was", "one", "our", "out", "day", "get", "has", "him", "his",
                   "how", "its", "may", "new", "now", "old", "see", "way", "who", "did",
                   "got", "let", "say", "she", "too", "use", "any", "big", "few", "own",
                   "why", "about", "after", "some", "what", "with", "have", "this",
                   "will", "your", "from", "they", "been", "make", "like", "long",
                   "look", "many", "most", "much", "over", "such", "take", "than",
                   "them", "then", "that", "want", "when", "also", "back", "come",
                   "made", "find", "here", "know", "last", "think", "should", "would",
                   "could", "stock", "stocks", "sell", "buy", "hold", "invest",
                   "price", "market", "deal", "deals", "news", "data", "good", "best"}
        candidate_names = [w for w in words if w not in _COMMON]
        
        for name in candidate_names:
            resolved = await resolve_company_to_ticker(name)
            if resolved:
                symbols.append(resolved)
                break  # Use the first successful resolution

    if ticker_hint and not symbols:
        symbols = [ticker_hint.upper()]

    # Classify query type
    if any(w in msg_lower for w in ["price", "how much", "trading at", "current price"]):
        query_type = "price_lookup"
    elif any(w in msg_lower for w in ["technical", "rsi", "macd", "sma", "oversold", "overbought", "chart"]):
        query_type = "technical_analysis"
    elif any(w in msg_lower for w in ["insider", "insider buying", "insider selling", "insider activity"]):
        query_type = "insider_activity"
    elif any(w in msg_lower for w in ["news", "headline", "what's happening", "recent news"]):
        query_type = "news_query"
    # Detect company_info
    _PROFILE_PATTERNS = ["ceo", "leadership", "headquarters", "hq", "employee", "profile", "about", "who is", "where is", "founded"]
    if any(p in msg_lower for p in _PROFILE_PATTERNS):
        return {
            "symbols": list(set(symbols + ([ticker_hint.upper()] if ticker_hint else []))),
            "query_type": "company_info",
            "tools_needed": ["get_company_profile"]
        }

    # Market overview
    elif any(w in msg_lower for w in ["market", "indices", "s&p", "dow", "nasdaq", "moving the market", "macro"]):
        query_type = "market_overview"
    elif any(w in msg_lower for w in ["comprehensive", "deep analysis", "full analysis", "everything about"]):
        query_type = "deep_analysis"
    elif any(w in msg_lower for w in ["should i sell", "should i buy", "should i invest", "entry point", "good time to buy",
                                       "should sell", "should buy", "worth buying", "worth investing",
                                       "time to sell", "time to buy", "good time to sell"]):
        query_type = "stock_analysis"
    else:
        query_type = "stock_analysis"

    tools = list(QUERY_TYPE_TOOLS.get(query_type, ["get_stock_snapshot"]))

    # Investment questions MUST include technical indicators
    _INVEST_PHRASES = ["should i sell", "should i buy", "should i invest",
                       "should sell", "should buy", "worth buying", "worth investing",
                       "entry point", "entry position", "good time to buy",
                       "good time to sell", "time to sell", "time to buy"]
    if any(phrase in msg_lower for phrase in _INVEST_PHRASES):
        for tool in ["get_technical_indicators", "get_stock_snapshot", "get_fundamentals", "get_analyst_targets", "get_news"]:
            if tool not in tools:
                tools.append(tool)

    return {
        "symbols": symbols,
        "query_type": query_type,
        "tools_needed": tools,
        "needs": {
            "price": "get_stock_snapshot" in tools,
            "fundamentals": "get_fundamentals" in tools,
            "news": "get_news" in tools,
            "technicals": "get_technical_indicators" in tools,
            "macro": "get_macro_context" in tools or "get_market_overview" in tools
        }
    }


# ---------------------------------------------------------------------------
# Tool Execution (Parallel)
# ---------------------------------------------------------------------------
async def execute_tools(
    tools_needed: List[str],
    symbols: List[str],
    query: str,
) -> Dict[str, Any]:
    """Run all selected tools in PARALLEL. Returns dict of tool_name -> result."""
    tasks = {}

    for tool_name in tools_needed:
        tool_info = TOOL_REGISTRY.get(tool_name)
        if not tool_info:
            continue

        fn = tool_info["fn"]

        if tool_info.get("needs_symbol") and tool_info.get("needs_query"):
            # Tools like get_news that need both symbol and query
            for sym in (symbols or ["MARKET"]):
                task_key = f"{tool_name}:{sym}"
                tasks[task_key] = fn(sym, query)
        elif tool_info.get("needs_symbol"):
            for sym in (symbols or []):
                task_key = f"{tool_name}:{sym}"
                tasks[task_key] = fn(sym)
        elif tool_info.get("needs_query"):
            tasks[tool_name] = fn(query)
        else:
            tasks[tool_name] = fn()

    if not tasks:
        return {}

    # Execute all tasks in parallel
    keys = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    tool_results = {}
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            logger.error(f"Tool {key} failed: {result}")
            tool_results[key] = {"error": str(result)}
        else:
            tool_results[key] = result

    return tool_results


# ---------------------------------------------------------------------------
# Format tool results into context for LLM
# ---------------------------------------------------------------------------
def _format_tool_context(tool_results: Dict) -> str:
    """Format tool results into a structured context string for the LLM."""
    sections = []

    for tool_key, data in tool_results.items():
        if isinstance(data, dict) and data.get("error"):
            sections.append(f"[{tool_key}] Error: {data['error']}")
            continue

        tool_name = tool_key.split(":")[0]

        if tool_name == "get_stock_snapshot":
            if isinstance(data, dict) and data.get("price"):
                sections.append(
                    f"=== {data.get('symbol', '')} PRICE SNAPSHOT ===\n"
                    f"Name: {data.get('name', '')}\n"
                    f"Price: ${data.get('price', 0):.2f}\n"
                    f"Change: {data.get('change', 0):+.2f} ({data.get('change_percent', 0):+.2f}%)\n"
                    f"Volume: {data.get('volume', 0):,}\n"
                    f"Day Range: ${data.get('day_low', 0):.2f} - ${data.get('day_high', 0):.2f}\n"
                    f"52-Week Range: ${data.get('fifty_two_week_low', 0):.2f} - ${data.get('fifty_two_week_high', 0):.2f}\n"
                    f"Market Cap: {data.get('market_cap', 0):,}"
                )

        elif tool_name == "get_fundamentals":
            if isinstance(data, dict) and data.get("symbol"):
                lines = [f"=== {data['symbol']} FUNDAMENTALS ==="]
                for key in ["pe_ratio", "forward_pe", "eps", "revenue_growth", "earnings_growth",
                             "gross_margins", "operating_margins", "profit_margin",
                             "debt_to_equity", "current_ratio", "roe", "roa", "dividend_yield"]:
                    val = data.get(key)
                    if val is not None:
                        label = key.replace("_", " ").title()
                        if "margin" in key or "growth" in key or key in ["roe", "roa", "dividend_yield"]:
                            lines.append(f"{label}: {float(val)*100:.2f}%")
                        else:
                            lines.append(f"{label}: {val}")
                sections.append("\n".join(lines))

        elif tool_name == "get_analyst_targets":
            if isinstance(data, dict):
                sections.append(
                    f"=== {data.get('symbol', '')} ANALYST TARGETS ===\n"
                    f"Recommendation: {data.get('recommendation', 'N/A').upper()}\n"
                    f"Target Price (Mean): ${data.get('target_mean_price', 'N/A')}\n"
                    f"Target Price (High): ${data.get('target_high_price', 'N/A')}\n"
                    f"Target Price (Low): ${data.get('target_low_price', 'N/A')}\n"
                    f"Number of Analysts: {data.get('number_of_analysts', 'N/A')}"
                )

        elif tool_name == "get_news":
            if isinstance(data, dict):
                articles = data.get("articles", [])
                if articles:
                    lines = [f"=== {data.get('symbol', '')} RELEVANT NEWS (via {data.get('source', 'search')}) ==="]
                    for art in articles[:5]:
                        sent = f" [{art.get('sentiment', '')}]" if art.get("sentiment") else ""
                        lines.append(f"- {art.get('title', '')}{sent} — {art.get('source', '')} ({art.get('published_at', '')[:10]})")
                    sections.append("\n".join(lines))
                else:
                    sections.append(f"=== {data.get('symbol', '')} NEWS ===\nNo relevant news found.")

        elif tool_name == "get_technical_indicators":
            if isinstance(data, dict) and not data.get("error"):
                sections.append(
                    f"=== {data.get('symbol', '')} TECHNICAL INDICATORS ===\n"
                    f"RSI (14): {data.get('rsi_14', 'N/A')}\n"
                    f"MACD: {data.get('macd', 'N/A')}\n"
                    f"MACD Signal: {data.get('macd_signal', 'N/A')}\n"
                    f"MACD Histogram: {data.get('macd_hist', 'N/A')}\n"
                    f"SMA 50: {data.get('sma_50', 'N/A')}\n"
                    f"SMA 200: {data.get('sma_200', 'N/A')}\n"
                    f"Source: {data.get('source', 'Alpha Vantage')}"
                )

        elif tool_name == "get_insider_transactions":
            if isinstance(data, dict):
                txns = data.get("transactions", [])
                if txns:
                    lines = [f"=== {data.get('symbol', '')} INSIDER TRANSACTIONS ==="]
                    for t in txns:
                        val_str = f"${t.get('value', 0):,.0f}" if t.get("value") else "N/A"
                        lines.append(f"- {t.get('name', 'Unknown')}: {t.get('transaction_type', '')} "
                                     f"{t.get('shares', 0):,} shares ({val_str}) on {t.get('date', '')}")
                    sections.append("\n".join(lines))
                else:
                    error = data.get("error", "")
                    sections.append(f"=== {data.get('symbol', '')} INSIDER TRANSACTIONS ===\nNo recent insider transactions found. {error}")

        elif tool_name == "get_macro_context":
            if isinstance(data, dict):
                lines = ["=== MACRO CONTEXT ==="]
                for key in ["fed_funds_rate", "cpi_yoy", "unemployment_rate"]:
                    val = data.get(key, {})
                    if isinstance(val, dict):
                        lines.append(f"{key.replace('_', ' ').title()}: {val.get('value', 'N/A')} (as of {val.get('date', 'N/A')})")
                if data.get("note"):
                    lines.append(f"Note: {data['note']}")
                sections.append("\n".join(lines))

        elif tool_name in ["get_market_overview", "get_market_overview_tool"]:
            if isinstance(data, dict):
                lines = ["=== MARKET OVERVIEW ==="]
                for name, info in (data.get("indices") or {}).items():
                    lines.append(f"{name}: {info.get('price', 0):,.2f} ({info.get('change_percent', 0):+.2f}%)")
                if data.get("top_gainers"):
                    lines.append("\nTop Gainers:")
                    for g in data["top_gainers"]:
                        lines.append(f"  {g.get('symbol', '')} ({g.get('name', '')}): {g.get('change_percent', 0):+.2f}%")
                if data.get("top_losers"):
                    lines.append("\nTop Losers:")
                    for l in data["top_losers"]:
                        lines.append(f"  {l.get('symbol', '')} ({l.get('name', '')}): {l.get('change_percent', 0):+.2f}%")
                if data.get("fear_greed_index"):
                    fng = data["fear_greed_index"]
                    lines.append(f"\nFear & Greed Index: {fng.get('value', 50)} ({fng.get('classification', 'Neutral')})")
                sections.append("\n".join(lines))

        elif tool_name in ["web_search", "web_search_news"]:
            if isinstance(data, dict):
                results = data.get("results", [])
                if results:
                    source_label = "WEB SEARCH" if tool_name == "web_search" else "WEB NEWS SEARCH"
                    lines = [f"=== {source_label} RESULTS ==="]
                    for r in results:
                        lines.append(f"- {r.get('title', '')}: {r.get('body', '')[:200]}")
                    sections.append("\n".join(lines))

    return "\n\n".join(sections) if sections else "No data available from tools."


# ---------------------------------------------------------------------------
# Format price for direct response (no LLM needed)
# ---------------------------------------------------------------------------
def _format_price_response(snapshot: dict) -> str:
    """Format a price lookup response directly without calling the LLM."""
    if not snapshot or not snapshot.get("price"):
        return "Unable to fetch price data at this time."

    sym = snapshot.get("symbol", "")
    name = snapshot.get("name", sym)
    price = snapshot.get("price", 0)
    change = snapshot.get("change", 0)
    change_pct = snapshot.get("change_percent", 0)
    volume = snapshot.get("volume", 0)
    day_high = snapshot.get("day_high", 0)
    day_low = snapshot.get("day_low", 0)

    direction = "📈" if change >= 0 else "📉"
    sign = "+" if change >= 0 else ""

    return (
        f"**{name} ({sym})** {direction}\n\n"
        f"**Price:** ${price:,.2f} ({sign}{change:,.2f} / {sign}{change_pct:.2f}%)\n\n"
        f"**Day Range:** ${day_low:,.2f} — ${day_high:,.2f}\n\n"
        f"**Volume:** {volume:,}\n\n"
        f"_Data is live from market feeds._"
    )


# ---------------------------------------------------------------------------
# SSE Event Helpers
# ---------------------------------------------------------------------------
def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event line."""
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


def _thinking_event(step: str, message: str) -> str:
    return _sse_event("thinking", {"step": step, "message": message})


def _token_event(content: str) -> str:
    return _sse_event("token", {"content": content})


def _done_event() -> str:
    return _sse_event("done", {})


# ---------------------------------------------------------------------------
# Main Agent Pipeline (SSE Generator)
# ---------------------------------------------------------------------------
async def run_agent_pipeline(
    message: str,
    ticker: Optional[str] = None,
    history: Optional[list] = None,
    db=None,
    user_id: str = "",
    session_id: str = "",
    context: str = "",
) -> AsyncGenerator[str, None]:
    """
    Main agentic pipeline that yields SSE events.

    Flow:
    1. Emit "thinking: intent" → classify intent
    2. For price_lookup: format snapshot directly, skip LLM
    3. For other types: execute tools in parallel, emit thinking per tool
    4. Build focused context from tool results
    5. Stream LLM response as token events
    6. Emit done event
    7. Save to MongoDB
    """
    # H2: Sanitize user message to prevent prompt injection.
    # Strip patterns that could break the LLM trust boundary or hijack instructions.
    _INJECT_PATTERNS = re.compile(
        r'(---+\s*(?:TOOL RESULTS|SYSTEM|END TOOL|LIVE CONTEXT|INSTRUCTION)[^\n]*|'
        r'\[SYSTEM\]|\[ASSISTANT\]|\[USER\]|===+\s*[A-Z\s]+===+)',
        re.IGNORECASE
    )
    message = _INJECT_PATTERNS.sub('', message).strip()
    # Enforce a hard length cap after sanitization
    message = message[:2000]
    full_response = ""

    # Step 1: Intent classification (PRE-FLIGHT)
    yield _thinking_event("intent", "🔍 Classifying intent and routing...")
    
    # Step 0: Follow-up detection — check if this is a context-dependent query
    # (e.g. "give me it in a table", "explain more", "compare those")
    # IMPORTANT: Only treat as follow-up if the message has NO substantive subjects
    _followup_signals = ["it ", "it?", "that ", "this ", "these ", "those ",
                         "them ", "more ", "again",
                         "format", "detail", "explain", "summarize"]
    msg_lower = message.lower().strip()
    words = msg_lower.split()
    
    # Check if message has any substantive nouns (potential company/concept names)
    _FILLER_WORDS = {"can", "you", "give", "me", "it", "in", "a", "the", "that", "this",
                     "these", "those", "them", "more", "please", "show", "make", "put",
                     "do", "tell", "get", "let", "again", "now", "just", "also", "too",
                     "and", "or", "with", "for", "to", "of", "is", "are", "was", "be",
                     "as", "at", "by", "on", "an", "so", "if", "my", "i", "we", "they",
                     "table", "chart", "format", "detail", "summary", "list", "compare",
                     "explain", "summarize", "about", "how", "what", "why", "when"}
    substantive_words = [w for w in words if w not in _FILLER_WORDS and len(w) >= 2]
    has_subjects = len(substantive_words) > 0

    is_followup = (
        len(words) <= 10
        and any(sig in msg_lower for sig in _followup_signals)
        and not has_subjects  # Must NOT have company names, tickers, etc.
        and bool(history)     # Must have previous context
    )

    # Extract previous context from history for follow-ups
    prev_symbols = []
    prev_response = ""
    if history:
        for h in reversed(history):
            prev_msg = h.get("message", "")
            prev_resp = h.get("response", "")
            prev_syms = re.findall(r'\b([A-Z]{1,5})\b', prev_msg + " " + prev_resp)
            _SKIP_BASIC = {"I", "A", "THE", "AND", "OR", "FOR", "IN", "OF", "TO", "IS",
                           "IT", "AT", "AI", "PE", "EPS", "CEO", "IPO", "ETF", "GDP",
                           "US", "UK", "EU", "USD", "NOT", "HOW", "WHY", "WHAT", "ARE",
                           "CAN", "DO", "YOU", "SO", "IF", "ON", "UP", "AN", "AS", "BE",
                           "BY", "GO", "NO", "ALL", "ANY", "BUY", "SELL", "HOLD", "RSI",
                           "MACD", "SMA", "EMA", "NEW", "OLD", "DAY", "HIGH", "LOW",
                           "YES", "GET", "OUT", "WAS", "BUT", "MAY", "TOP", "HAS", "HAD"}
            prev_syms = [s for s in prev_syms if s not in _SKIP_BASIC and len(s) >= 2]
            if prev_syms:
                prev_symbols = prev_syms[:3]
                prev_response = prev_resp
                break

    effective_ticker = ticker
    if is_followup and not ticker and prev_symbols:
        effective_ticker = prev_symbols[0]
        logger.info(f"Follow-up detected, using previous symbol: {effective_ticker}")

    intent = await classify_intent(message, effective_ticker)
    query_type = intent.get("query_type", "stock_analysis")
    symbols = intent.get("symbols", [])
    
    # Fix 1: Determine tool call ceiling
    if query_type in ("company_info", "price_lookup", "factual"):
        max_tool_calls = 1
    elif query_type in ("stock_analysis", "technical_analysis", "news_query", "insider_activity"):
        max_tool_calls = 3
    else:
        max_tool_calls = 5

    # --- ADDITIVE GOD-TIER UPGRADE: ReAct Agent Primary Path ---
    react_succeeded = False
    try:
        from react_agent import run_react_agent
        logger.info(f"Attempting new ReAct Agent pathway with max_tool_calls={max_tool_calls}...")
        has_yielded_token = False
        async for event in run_react_agent(
            message=message,
            history=history,
            db=db,
            user_id=user_id,
            session_id=session_id,
            context_str=context,
            max_tool_calls=max_tool_calls
        ):
            # If we get ANY token other than the initial marker, it means ReAct reached the generation phase
            if "token" in event:
                data = json.loads(event.replace("data: ", ""))
                if data.get("content"):
                    has_yielded_token = True
        if not has_yielded_token:
            logger.error(f"[AgentPipeline] Pro model failed to yield content for: {message[:100]}")
            # Do NOT yield done here, let it fall through to the fallback single-shot pipeline
        else:
            react_succeeded = True
            
    except Exception as e:
        logger.warning(f"ReAct Agent error: {e}")
        if has_yielded_token:
            logger.error("Crash occurred AFTER ReAct started streaming tokens. Aborting to prevent dual responses.")
            yield _token_event("\n\n*Agent encountered an error while writing. Please check the data above.*")
            yield _done_event()
            return
        logger.info("Falling back to single-shot pipeline.")
    # --- END UPGRADE ---

    # If ReAct was perfectly successful and yielded tokens, we are done
    if react_succeeded:
        return
    
    # If we are here, either ReAct crashed before tokens, or it returned blank.
    # Fallback single-shot pipeline follows...

    # STEP 0: Inject live market snapshot into system prompt
    # This ensures even if tools fail, the LLM has basic situational awareness.
    try:
        from agent_tools import get_market_overview_tool
        overview = await get_market_overview_tool()
        snapshot_text = "\n=== LIVE MARKET SNAPSHOT ===\n"
        for name, vals in overview.get("indices", {}).items():
            snapshot_text += f"{name}: {vals.get('price')} ({vals.get('change_percent')}%)\n"
        snapshot_text += f"VIX: {overview.get('vix', {}).get('price')}\n"
        snapshot_text += f"Fear & Greed: {overview.get('fear_greed_index', {}).get('value')} ({overview.get('fear_greed_index', {}).get('classification')})\n"
        snapshot_text += "============================\n"
        
        # We append this to the start of the user message or inject into context
        # In this implementation, we'll prefix it to the first message the LLM sees
        context = f"{snapshot_text}\n{context}"
    except Exception as e:
        logger.warning(f"Failed to inject market snapshot: {e}")

    try:
        effective_ticker = ticker
        if is_followup and not ticker and prev_symbols:
            effective_ticker = prev_symbols[0]

        # (Intent already classified above in pre-flight)
        tools_needed = intent.get("tools_needed", [])
        needs = intent.get("needs", {})

        # Limit tools_needed if it exceeds max_tool_calls for the fallback path
        if len(tools_needed) > max_tool_calls:
            logger.info(f"Slicing tools_needed from {len(tools_needed)} to {max_tool_calls}")
            tools_needed = tools_needed[:max_tool_calls]

        # Select Model based on complexity
        from ai_service import select_model_id
        model_id = select_model_id(message, intent=query_type, user_id=user_id)
        logger.info(f"Routing to model: {model_id}")

        # If still no symbols after classification, use previous context
        if not symbols and prev_symbols:
            symbols = prev_symbols[:2]
            logger.info(f"No symbols in classifier output, using history: {symbols}")

        # Build final system prompt with intent-specific additions
        system_msg = AGENT_SYSTEM_PROMPT
        if query_type in INTENT_PROMPTS:
            system_msg += f"\n\n{INTENT_PROMPTS[query_type]}"
        
        # Add live market context if macro is needed
        if needs.get("macro") or query_type == "market_overview":
             try:
                from agent_tools import get_market_overview_tool
                overview = await get_market_overview_tool()
                snapshot_text = "\n=== LIVE MARKET SNAPSHOT ===\n"
                for name, vals in overview.get("indices", {}).items():
                    snapshot_text += f"{name}: {vals.get('price')} ({vals.get('change_percent')}%)\n"
                snapshot_text += f"VIX: {overview.get('vix', {}).get('price')}\n"
                snapshot_text += f"Fear & Greed: {overview.get('fear_greed_index', {}).get('value')} ({overview.get('fear_greed_index', {}).get('classification')})\n"
                snapshot_text += "============================\n"
                system_msg += f"\n{snapshot_text}"
             except Exception as e:
                logger.warning(f"Failed to inject market snapshot for intent: {e}")

        # For pure formatting follow-ups, skip tool execution and use LLM with context
        if is_followup and prev_response and symbols:
            yield _thinking_event("generate", "✨ Reformatting previous research...")

            from ai_service import configure_gemini
            configure_gemini()

            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            model = genai.GenerativeModel(
                model_id,
                system_instruction=system_msg,
                safety_settings=safety_settings,
            )

            reformat_prompt = (
                f"The user previously asked about {', '.join(symbols)} and received this response:\n\n"
                f"---PREVIOUS RESPONSE---\n{prev_response}\n---END PREVIOUS RESPONSE---\n\n"
                f"The user now says: \"{message}\"\n\n"
                f"Please fulfill their request using the data from the previous response. "
                f"Keep the same data but reformat as requested."
            )

            try:
                response_stream = await asyncio.to_thread(
                    model.generate_content, reformat_prompt, stream=True
                )
                for chunk in response_stream:
                    try:
                        text = chunk.text
                        if text:
                            yield _token_event(text)
                            full_response += text
                            await asyncio.sleep(0.01)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Reformat streaming error: {e}")
                if not full_response:
                    yield _token_event("I'm having trouble reformatting. Please try again.")
                    full_response = "Error reformatting."

            yield _done_event()

            if db:
                try:
                    await db.chat_messages.insert_one({
                        "user_id": user_id,
                        "session_id": session_id,
                        "message": message,
                        "response": full_response,
                        "query_type": "followup_reformat",
                        "symbols": symbols,
                        "created_at": datetime.now(timezone.utc),
                    })
                except Exception as e:
                    logger.error(f"DB save error: {e}")
            return

        logger.info(f"Agent intent: type={query_type}, symbols={symbols}, tools={tools_needed}")

        # Step 2: Price lookup fast path — NO LLM needed
        if query_type == "price_lookup" and symbols:
            symbol = symbols[0]
            yield _thinking_event("tools", f"Fetching {symbol} price data...")
            snapshot = await get_stock_snapshot(symbol)

            if not snapshot or not snapshot.get("price"):
                # Fallback to web search
                yield _thinking_event("tools", f"Searching the web for {symbol}...")
                ws = await web_search(f"{symbol} stock price today")
                full_response = f"Could not find live market data for {symbol}. Here's what I found:\n\n"
                for r in ws.get("results", []):
                    full_response += f"- **{r.get('title', '')}**: {r.get('body', '')[:150]}\n"
                yield _token_event(full_response)
            else:
                full_response = _format_price_response(snapshot)
                yield _token_event(full_response)

            yield _done_event()

            # Save to DB
            if db:
                try:
                    await db.chat_messages.insert_one({
                        "user_id": user_id,
                        "session_id": session_id,
                        "message": message,
                        "response": full_response,
                        "query_type": query_type,
                        "created_at": datetime.now(timezone.utc),
                    })
                except Exception as e:
                    logger.error(f"DB save error: {e}")
            return

        # Step 3: Execute tools in parallel with thinking events
        # First, emit a general tools thinking step
        if symbols:
            sym_str = ", ".join(symbols)
            yield _thinking_event("tools", f"Fetching {sym_str} data...")
        else:
            yield _thinking_event("tools", "Gathering market data...")

        # Check if any symbols fail (trigger web search fallback)
        if symbols and "get_stock_snapshot" in tools_needed:
            snapshot = await get_stock_snapshot(symbols[0])
            if not snapshot or not snapshot.get("price"):
                # Symbol not found in yfinance — trigger web search fallback
                logger.info(f"Symbol {symbols[0]} not found in yfinance, falling back to web search")
                yield _thinking_event("tools", f"Searching the web for {symbols[0]}...")

                tools_needed = ["web_search", "web_search_news"]

        # Emit per-tool thinking events with better icons
        step_map = {
            "get_stock_snapshot": ("price", "💹"),
            "get_fundamentals": ("fundamentals", "📊"),
            "get_news": ("news", "📰"),
            "get_technical_indicators": ("indicators", "📈"),
            "get_macro_context": ("macro", "🌍"),
            "get_market_overview": ("macro", "🌍"),
            "get_insider_transactions": ("insider", "🕴️"),
            "get_analyst_targets": ("analyst", "🎯"),
            "get_company_profile": ("company", "🏢"),
            "web_search": ("web", "🌐"),
            "web_search_news": ("web", "🌐"),
        }

        for tool_name in tools_needed:
            tool_info = TOOL_REGISTRY.get(tool_name, {})
            label = tool_info.get("label", tool_name)
            step_key, icon = step_map.get(tool_name, ("tools", "🛠️"))
            
            if "{symbol}" in label and symbols:
                target = symbols[0]
                label = label.replace("{symbol}", target)
                yield _thinking_event(step_key, f"{icon} Fetching {target} {step_key}...")
            else:
                yield _thinking_event(step_key, f"{icon} {label}...")

        # Execute all tools in parallel
        tool_results = await execute_tools(tools_needed, symbols, message)

        # Step 4: Build Focused Context
        tool_context = _format_tool_context(tool_results)

        # Step 5: Generate LLM response
        yield _thinking_event("generate", "✍️ Finalizing research report...")

        from ai_service import configure_gemini
        configure_gemini()
        model = genai.GenerativeModel(
            model_id,
            system_instruction=system_msg,
            safety_settings=safety_settings,
        )

        chat = model.start_chat(history=[]) # Could add history here if needed
        
        # Build prompt for LLM
        llm_prompt = f"User: {message}\n\n"
        if context:
            llm_prompt += f"System Context: {context}\n\n"
        llm_prompt += f"--- TOOL RESULTS ---\n{tool_context}\n--- END TOOL RESULTS ---"

        try:
            response_stream = await asyncio.to_thread(
                chat.send_message, llm_prompt, stream=True
            )
            for chunk in response_stream:
                try:
                    text = chunk.text
                    if text:
                        yield _token_event(text)
                        full_response += text
                        await asyncio.sleep(0.01)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            yield _token_event("\n\nI'm sorry, I encountered an error while generating the full response.")

        yield _done_event()

        # Save to DB
        if db:
            try:
                await db.chat_messages.insert_one({
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": message,
                    "response": full_response,
                    "query_type": query_type,
                    "symbols": symbols,
                    "model": model_id,
                    "created_at": datetime.now(timezone.utc),
                })
            except Exception as e:
                logger.error(f"DB save error: {e}")

        # Build context from tool results
        tool_context = _format_tool_context(tool_results)

        # Build conversation history for chat
        from ai_service import _trim_history
        history = history or []
        history, context_line = _trim_history(history, message)

        gemini_history = []
        for h in history:
            gemini_history.append({"role": "user", "parts": [h.get("message", "")]})
            gemini_history.append({"role": "model", "parts": [h.get("response", "")]})

        final_user_text = ""
        if context_line:
            final_user_text += context_line
        if context:
            final_user_text += f"Page context: {context}\n\n"
        final_user_text += f"User question: {message}\n\n"
        final_user_text += f"--- TOOL RESULTS (Live Data) ---\n{tool_context}\n--- END TOOL RESULTS ---\n\n"

        # Dynamic format instruction based on query context
        if len(symbols) >= 2:
            final_user_text += (
                f"FORMAT INSTRUCTION: The user is asking about {len(symbols)} stocks "
                f"({', '.join(symbols)}). Create a detailed SIDE-BY-SIDE COMPARISON TABLE "
                f"with metrics like Price, Change%, Market Cap, P/E, Revenue Growth, "
                f"Margins, Analyst Rating, etc. Follow the table with a brief comparative analysis."
            )
        elif len(symbols) == 1:
            final_user_text += (
                f"FORMAT INSTRUCTION: Provide a thorough analysis of {symbols[0]} using "
                f"structured markdown sections with tables for numerical data. "
                f"Include all available data points from the tool results."
            )
        elif "table" in message.lower():
            final_user_text += (
                "FORMAT INSTRUCTION: The user specifically requested table format. "
                "Present ALL available data in well-organized markdown tables."
            )

        # Step 5: Stream LLM response
        from ai_service import configure_gemini
        configure_gemini()

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        model = genai.GenerativeModel(
            "models/gemini-2.0-flash",
            system_instruction=AGENT_SYSTEM_PROMPT,
            safety_settings=safety_settings,
        )

        chat = model.start_chat(history=gemini_history)

        try:
            response_stream = await asyncio.to_thread(
                chat.send_message, final_user_text, stream=True
            )
            for chunk in response_stream:
                try:
                    text = chunk.text
                    if text:
                        yield _token_event(text)
                        full_response += text
                        await asyncio.sleep(0.01)
                except Exception:
                    # Catch ALL chunk-level exceptions: ValueError, StopCandidateException,
                    # IncompleteIterationError, AttributeError, etc.
                    pass
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            if not full_response:
                error_msg = "I'm having trouble generating a response right now. Please try again."
                yield _token_event(error_msg)
                full_response = error_msg
            # If we already have a response, just log the error and move on

        yield _done_event()

        # Step 6: Save to MongoDB
        if db:
            try:
                await db.chat_messages.insert_one({
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": message,
                    "response": full_response,
                    "query_type": query_type,
                    "tools_used": tools_needed,
                    "symbols": symbols,
                    "created_at": datetime.now(timezone.utc),
                })
            except Exception as e:
                logger.error(f"DB save error: {e}")

    except Exception as e:
        logger.error(f"Agent pipeline error: {e}")
        # Only emit error if we haven't already sent a response
        if not full_response:
            yield _token_event("I'm having trouble processing your request. Please try again.")
        yield _done_event()
