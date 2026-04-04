from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent_tools import get_sec_financials
from market_data import get_rich_stock_data, get_stock_chart, get_ticker_news

from .engines import build_macro_regime_view
from .thesis_repository import insert_evidence_blocks

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


def _safe_links(raw_links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [link for link in raw_links if link.get("url") or link.get("source_url")]


async def _build_filing_block(ticker: str) -> Optional[Dict[str, Any]]:
    payload = await get_sec_financials(ticker)
    if payload.get("error"):
        return None

    filings = payload.get("filings") or []
    key_metrics = payload.get("financials") or payload
    latest = filings[0] if filings else {}
    summary = latest.get("summary") or f"Pulled SEC-backed filing context for {ticker}."
    links = []
    if latest.get("link"):
        links.append({"label": latest.get("form", "SEC filing"), "url": latest["link"]})

    return {
        "source": "filing",
        "summary": summary,
        "payload": {
            "ticker": ticker,
            "latest_filing": latest,
            "financials": key_metrics,
        },
        "confidence": 86,
        "freshness": _utcnow(),
        "links": _safe_links(links),
        "observed_at": _utcnow(),
    }


async def _build_news_block(ticker: str) -> Optional[Dict[str, Any]]:
    articles = await get_ticker_news(ticker)
    if not articles:
        return None

    top_articles = articles[:5]
    summary = top_articles[0].get("title") or f"Recent news coverage was collected for {ticker}."
    links = [
        {
            "label": article.get("title", "News article"),
            "url": article.get("source_url") or article.get("link"),
            "source": article.get("source"),
        }
        for article in top_articles
        if article.get("source_url") or article.get("link")
    ]

    return {
        "source": "news",
        "summary": summary,
        "payload": {
            "ticker": ticker,
            "articles": top_articles,
        },
        "confidence": 64,
        "freshness": _utcnow(),
        "links": _safe_links(links),
        "observed_at": _utcnow(),
    }


async def _build_macro_block() -> Optional[Dict[str, Any]]:
    macro = await build_macro_regime_view()
    citations = macro.get("citations") or []
    links = [
        {
            "label": citation.get("label"),
            "url": citation.get("url"),
            "source": citation.get("source"),
        }
        for citation in citations
        if citation.get("url")
    ]

    return {
        "source": "macro",
        "summary": macro.get("summary", "Macro regime context was refreshed."),
        "payload": macro,
        "confidence": macro.get("confidence", 70),
        "freshness": _utcnow(),
        "links": _safe_links(links),
        "observed_at": _utcnow(),
    }


async def _build_price_action_block(ticker: str) -> Optional[Dict[str, Any]]:
    snapshot, chart = await asyncio.gather(
        get_rich_stock_data(ticker),
        get_stock_chart(ticker, period="1mo", interval="1d"),
    )
    if not snapshot:
        return None

    month_change = None
    if chart and len(chart) >= 2:
        first_close = float(chart[0].get("close") or 0)
        last_close = float(chart[-1].get("close") or 0)
        if first_close:
            month_change = ((last_close / first_close) - 1) * 100

    summary = (
        f"{ticker} is trading at ${snapshot.get('price', 0):,.2f} with a "
        f"{snapshot.get('change_percent', 0):+.2f}% daily move."
    )
    if month_change is not None:
        summary += f" One-month price change: {month_change:+.2f}%."

    return {
        "source": "price_action",
        "summary": summary,
        "payload": {
            "ticker": ticker,
            "snapshot": snapshot,
            "chart": chart[-20:] if chart else [],
            "one_month_change_percent": month_change,
        },
        "confidence": 72,
        "freshness": _utcnow(),
        "links": [],
        "observed_at": _utcnow(),
    }


async def collect_evidence_background(mongo_db, thesis_id: str, revision_id: Optional[str], ticker: str) -> None:
    try:
        results = await asyncio.gather(
            _build_filing_block(ticker),
            _build_news_block(ticker),
            _build_macro_block(),
            _build_price_action_block(ticker),
            return_exceptions=True,
        )
        blocks: List[Dict[str, Any]] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Evidence collection failed for %s: %s", ticker, result)
                continue
            if result:
                blocks.append(result)

        if blocks:
            await insert_evidence_blocks(thesis_id, revision_id, blocks)
    except Exception as exc:
        logger.exception("Background evidence collection failed for thesis %s: %s", thesis_id, exc)
