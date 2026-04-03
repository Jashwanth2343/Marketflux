"""
Multi-Agent Research System for FundOS.

Architecture:
  ResearchDirector
    ├── FundamentalsAnalyst  (DCF, comps, earnings quality)
    ├── TechnicalAnalyst     (momentum, breakout, volume)
    ├── MacroAnalyst         (rate sensitivity, sector rotation)
    ├── SentimentAnalyst     (news, insider, options flow signals)
    └── RiskAnalyst          (VaR proxy, drawdown, beta, position sizing)

All specialist agents run in parallel via asyncio.gather().
The Director synthesises their outputs into a final structured memo.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional

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
# Specialist Agent Prompts
# ---------------------------------------------------------------------------

_FUNDAMENTALS_PROMPT = """You are a buy-side Fundamentals Analyst. Using ONLY the data provided, write a concise analysis section.

DATA:
{data}

Write a 3-5 sentence Fundamentals section covering:
- Valuation (P/E, EV/EBITDA, FCF yield) vs sector norms
- Revenue/earnings growth trajectory
- Balance sheet strength (debt, cash, interest coverage)
- Key risks to the fundamental thesis

Be specific. Use exact numbers from the data. Professional Goldman Sachs tone. No filler."""

_TECHNICAL_PROMPT = """You are a Technical Analyst at a quantitative hedge fund. Using ONLY the data provided, write a concise technical analysis section.

DATA:
{data}

Write a 3-5 sentence Technical section covering:
- Current trend (above/below key MAs, trend strength)
- RSI reading and implication (overbought/oversold/neutral)
- MACD signal
- Key support/resistance levels (52w high, 52w low, SMA50, SMA200)
- Volume conviction

Be specific. Use exact numbers from the data. No filler."""

_MACRO_PROMPT = """You are a Macro Strategist at a hedge fund. Using ONLY the data provided, write a concise macro analysis section.

DATA:
{data}

Write a 3-5 sentence Macro section covering:
- How this stock's sector typically responds to current rate environment
- Any relevant macro tailwinds or headwinds (USD strength, commodity prices if relevant)
- VIX regime context and what it means for risk appetite in this sector
- Relative sector performance context

Be specific and insightful. Avoid generic commentary."""

_SENTIMENT_PROMPT = """You are a Sentiment & Flow Analyst at a hedge fund. Using ONLY the data provided, write a concise sentiment section.

DATA:
{data}

Write a 3-5 sentence Sentiment section covering:
- Recent news sentiment trend (bullish/bearish/mixed) with notable catalysts
- Insider activity (net buying or selling, significance)
- Analyst consensus and recent rating changes
- Overall sentiment signal label and conviction level

Be specific. Reference actual data points."""

_RISK_PROMPT = """You are a Risk Analyst at a hedge fund. Using ONLY the data provided, write a concise risk section.

DATA:
{data}

Write a 3-5 sentence Risk section covering:
- Beta vs market and implied volatility
- Max drawdown in past year and recovery pattern
- Key downside scenarios (bear case triggers)
- Suggested position sizing guidance (conservative/moderate/aggressive) based on risk profile
- Stop-loss level recommendation

Be specific. Use exact numbers from the data."""

_DIRECTOR_PROMPT = """You are the Head of Research at a premier hedge fund (Goldman Sachs / Citadel quality).
Synthesise the specialist analyst reports below into a professional Investment Research Note.

COMPANY: {symbol} — {name}
SECTOR: {sector}
CURRENT PRICE: ${price}
COMPOSITE SIGNAL SCORE: {signal_score}/100 ({signal_label})

--- SPECIALIST REPORTS ---

### FUNDAMENTALS ANALYST:
{fundamentals}

### TECHNICAL ANALYST:
{technical}

### MACRO ANALYST:
{macro}

### SENTIMENT ANALYST:
{sentiment}

### RISK ANALYST:
{risk}

---

Write a complete Investment Research Note with these exact sections:

## Executive Summary
[3 sentences: company snapshot, investment thesis in one line, overall signal]

## Investment Thesis
[Bull case and Bear case as two short paragraphs]

## Fundamentals & Valuation
[Use fundamentals analyst content, add a valuation summary table with: Metric | Value | vs Sector]

## Technical Outlook
[Use technical analyst content, state: Trend direction, Key levels, RSI status, MACD]

## Macro Environment
[Use macro analyst content]

## Market Sentiment & Positioning
[Use sentiment analyst content, add insider activity summary]

## Risk Assessment
[Use risk analyst content, add a Risk Matrix table with: Risk | Probability | Impact | Mitigation]

## Price Target & Recommendation
[State: Rating (BUY/HOLD/SELL), 12-month price target range, conviction level (Low/Medium/High)]

---
*Research generated by FundOS AI — {timestamp}. Not financial advice. Always do your own research.*

Use Goldman Sachs formatting: precise, data-driven, no fluff. Every section must have real numbers."""


# ---------------------------------------------------------------------------
# Data assembler
# ---------------------------------------------------------------------------

async def _assemble_data(symbol: str, db=None) -> Dict:
    """Gather all data for the specialist agents in parallel."""
    from agent_tools import (
        get_stock_snapshot, get_fundamentals, get_analyst_targets,
        get_technical_indicators, get_news, get_insider_transactions,
        get_macro_context,
    )
    from signal_engine import compute_signals

    tasks = {
        "snapshot": get_stock_snapshot(symbol),
        "fundamentals": get_fundamentals(symbol),
        "analyst": get_analyst_targets(symbol),
        "technicals": get_technical_indicators(symbol),
        "news": get_news(symbol, f"{symbol} latest news analysis"),
        "insider": get_insider_transactions(symbol),
        "macro": get_macro_context(),
        "signals": compute_signals(symbol, db=db),
    }

    keys = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    data = {}
    for k, r in zip(keys, results):
        data[k] = r if not isinstance(r, Exception) else {}

    return data


# ---------------------------------------------------------------------------
# Specialist agent runners
# ---------------------------------------------------------------------------

async def _run_specialist(model: genai.GenerativeModel, prompt: str) -> str:
    """Call Gemini Flash for one specialist report."""
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text.strip()
    except Exception as e:
        logger.warning(f"Specialist agent error: {e}")
        return f"Data unavailable — {str(e)[:100]}"


def _fmt(data: dict) -> str:
    """Format data dict as compact JSON string for prompts."""
    try:
        return json.dumps(data, indent=2, default=str)[:3000]
    except Exception:
        return str(data)[:3000]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_multi_agent_research(
    symbol: str,
    db=None,
) -> Dict:
    """
    Run all 5 specialist agents in parallel, then synthesise with Director.

    Returns a dict with:
      - memo_markdown: full research note as Markdown
      - specialist_reports: individual agent outputs
      - signals: quantitative signal scores
      - data_snapshot: raw data used
      - generated_at: ISO timestamp
    """
    from ai_service import configure_gemini
    configure_gemini()

    symbol = symbol.upper().strip()

    # Step 1: Gather all data
    data = await _assemble_data(symbol, db=db)

    signals = data.get("signals") or {}
    snapshot = data.get("snapshot") or {}
    fundamentals = data.get("fundamentals") or {}
    analyst = data.get("analyst") or {}
    technicals = data.get("technicals") or {}
    news_data = data.get("news") or {}
    insider = data.get("insider") or {}
    macro = data.get("macro") or {}

    price = snapshot.get("price", 0)
    name = snapshot.get("name") or signals.get("name") or symbol
    sector = signals.get("sector", "Unknown")
    signal_score = signals.get("composite_score", 0)
    signal_label = signals.get("signal_label", "NEUTRAL")

    # Step 2: Build context strings for each specialist
    fundamentals_ctx = {
        "fundamentals": fundamentals,
        "analyst_targets": analyst,
        "price": price,
    }
    technical_ctx = {
        "technicals": technicals,
        "snapshot": snapshot,
        "signal_technical": signals.get("categories", {}).get("technical", {}),
    }
    macro_ctx = {
        "macro": macro,
        "sector": sector,
        "signal_momentum": signals.get("categories", {}).get("momentum", {}),
    }
    sentiment_ctx = {
        "news": news_data.get("articles", [])[:8],
        "insider": insider,
        "analyst": analyst,
        "signal_sentiment": signals.get("categories", {}).get("sentiment", {}),
    }
    risk_ctx = {
        "snapshot": snapshot,
        "technicals": technicals,
        "fundamentals": fundamentals,
        "signal_score": signal_score,
        "categories": signals.get("categories", {}),
    }

    # Flash model for specialist agents (fast + cheap)
    specialist_model = genai.GenerativeModel(
        "gemini-flash-latest",
        safety_settings=SAFETY_OFF,
    )

    # Step 3: Run all 5 specialists IN PARALLEL
    specialist_prompts = [
        _FUNDAMENTALS_PROMPT.format(data=_fmt(fundamentals_ctx)),
        _TECHNICAL_PROMPT.format(data=_fmt(technical_ctx)),
        _MACRO_PROMPT.format(data=_fmt(macro_ctx)),
        _SENTIMENT_PROMPT.format(data=_fmt(sentiment_ctx)),
        _RISK_PROMPT.format(data=_fmt(risk_ctx)),
    ]

    specialist_results = await asyncio.gather(
        *[_run_specialist(specialist_model, p) for p in specialist_prompts],
        return_exceptions=True,
    )

    specialist_reports = {
        "fundamentals": specialist_results[0] if not isinstance(specialist_results[0], Exception) else "N/A",
        "technical":    specialist_results[1] if not isinstance(specialist_results[1], Exception) else "N/A",
        "macro":        specialist_results[2] if not isinstance(specialist_results[2], Exception) else "N/A",
        "sentiment":    specialist_results[3] if not isinstance(specialist_results[3], Exception) else "N/A",
        "risk":         specialist_results[4] if not isinstance(specialist_results[4], Exception) else "N/A",
    }

    # Step 4: Director synthesis (Pro model for quality)
    director_model = genai.GenerativeModel(
        "gemini-flash-latest",   # Use Flash for speed/cost; swap to Pro for max quality
        safety_settings=SAFETY_OFF,
    )

    director_prompt = _DIRECTOR_PROMPT.format(
        symbol=symbol,
        name=name,
        sector=sector,
        price=f"{price:,.2f}" if price else "N/A",
        signal_score=signal_score,
        signal_label=signal_label,
        fundamentals=specialist_reports["fundamentals"],
        technical=specialist_reports["technical"],
        macro=specialist_reports["macro"],
        sentiment=specialist_reports["sentiment"],
        risk=specialist_reports["risk"],
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    try:
        director_resp = await asyncio.to_thread(director_model.generate_content, director_prompt)
        memo_markdown = director_resp.text.strip()
    except Exception as e:
        logger.error(f"Director synthesis error for {symbol}: {e}")
        memo_markdown = "\n\n".join([
            f"# {symbol} Research Note\n",
            f"**Price:** ${price:,.2f}\n**Signal:** {signal_label} ({signal_score})\n",
            "## Fundamentals\n" + specialist_reports["fundamentals"],
            "## Technical\n" + specialist_reports["technical"],
            "## Macro\n" + specialist_reports["macro"],
            "## Sentiment\n" + specialist_reports["sentiment"],
            "## Risk\n" + specialist_reports["risk"],
        ])

    return {
        "symbol": symbol,
        "name": name,
        "sector": sector,
        "memo_markdown": memo_markdown,
        "specialist_reports": specialist_reports,
        "signals": signals,
        "price": price,
        "signal_score": signal_score,
        "signal_label": signal_label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def stream_multi_agent_research(
    symbol: str,
    db=None,
) -> AsyncGenerator[str, None]:
    """
    SSE-compatible streaming wrapper around run_multi_agent_research.
    Yields JSON-encoded SSE events for frontend consumption.
    """
    import json

    def _sse(event_type: str, data: dict) -> str:
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"

    symbol = symbol.upper().strip()
    yield _sse("thinking", {"step": "init", "message": f"🚀 Initialising multi-agent research for {symbol}..."})

    # Gather data
    yield _sse("thinking", {"step": "data", "message": "📡 Gathering market data, fundamentals, and signals in parallel..."})
    data = await _assemble_data(symbol, db=db)
    signals = data.get("signals") or {}
    snapshot = data.get("snapshot") or {}

    price = snapshot.get("price", 0)
    name = snapshot.get("name") or signals.get("name") or symbol
    sector = signals.get("sector", "Unknown")
    signal_score = signals.get("composite_score", 0)
    signal_label = signals.get("signal_label", "NEUTRAL")

    yield _sse("signal_scores", {
        "symbol": symbol,
        "score": signal_score,
        "label": signal_label,
        "categories": signals.get("categories", {}),
    })

    # Run specialists
    yield _sse("thinking", {"step": "specialists", "message": "🤖 Running 5 specialist agents in parallel: Fundamentals, Technical, Macro, Sentiment, Risk..."})

    from ai_service import configure_gemini
    configure_gemini()

    specialist_model = genai.GenerativeModel("gemini-flash-latest", safety_settings=SAFETY_OFF)

    fundamentals_ctx = {"fundamentals": data.get("fundamentals", {}), "analyst": data.get("analyst", {}), "price": price}
    technical_ctx = {"technicals": data.get("technicals", {}), "snapshot": snapshot}
    macro_ctx = {"macro": data.get("macro", {}), "sector": sector}
    sentiment_ctx = {"news": (data.get("news") or {}).get("articles", [])[:8], "insider": data.get("insider", {})}
    risk_ctx = {"snapshot": snapshot, "technicals": data.get("technicals", {}), "signal_score": signal_score}

    specialist_prompts = [
        _FUNDAMENTALS_PROMPT.format(data=_fmt(fundamentals_ctx)),
        _TECHNICAL_PROMPT.format(data=_fmt(technical_ctx)),
        _MACRO_PROMPT.format(data=_fmt(macro_ctx)),
        _SENTIMENT_PROMPT.format(data=_fmt(sentiment_ctx)),
        _RISK_PROMPT.format(data=_fmt(risk_ctx)),
    ]

    specialist_results = await asyncio.gather(
        *[_run_specialist(specialist_model, p) for p in specialist_prompts],
        return_exceptions=True,
    )

    agent_names = ["fundamentals", "technical", "macro", "sentiment", "risk"]
    specialist_reports = {}
    for i, (name_k, result) in enumerate(zip(agent_names, specialist_results)):
        specialist_reports[name_k] = result if not isinstance(result, Exception) else "N/A"
        yield _sse("agent_complete", {"agent": name_k, "content": specialist_reports[name_k]})

    # Director synthesis — stream tokens
    yield _sse("thinking", {"step": "synthesis", "message": "📝 Director synthesising final research memo..."})

    director_model = genai.GenerativeModel("gemini-flash-latest", safety_settings=SAFETY_OFF)
    director_prompt = _DIRECTOR_PROMPT.format(
        symbol=symbol,
        name=name,
        sector=sector,
        price=f"{price:,.2f}" if price else "N/A",
        signal_score=signal_score,
        signal_label=signal_label,
        fundamentals=specialist_reports.get("fundamentals", ""),
        technical=specialist_reports.get("technical", ""),
        macro=specialist_reports.get("macro", ""),
        sentiment=specialist_reports.get("sentiment", ""),
        risk=specialist_reports.get("risk", ""),
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    full_memo = ""
    try:
        response_stream = await asyncio.to_thread(
            director_model.generate_content, director_prompt, stream=True
        )
        for chunk in response_stream:
            try:
                text = chunk.text
                if text:
                    yield _sse("token", {"content": text})
                    full_memo += text
                    await asyncio.sleep(0.01)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Director stream error: {e}")
        yield _sse("token", {"content": "\n\n*Error generating synthesis. Specialist reports available above.*"})

    yield _sse("memo_complete", {
        "symbol": symbol,
        "memo": full_memo,
        "signals": signals,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
    yield _sse("done", {})
