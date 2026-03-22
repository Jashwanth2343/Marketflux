from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional
import uuid

from agent_tools import (
    get_earnings_transcript,
    get_insider_transactions,
    get_sec_financials,
    get_sector_performance,
)
from market_data import (
    get_market_overview,
    get_rich_stock_data,
    get_stock_chart,
    get_stock_info,
    get_ticker_news,
    get_top_movers,
)

from .repository import (
    get_portfolio_holdings,
    get_recent_signal_events,
    get_recent_strategy_runs,
    get_saved_theses,
    get_watchlist_tickers,
    save_signal_events,
)
from .adapter_helpers import classify_regime, collect_regime_inputs
from .mirofish_bridge import MiroFishBridgeClient


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _citation(label: str, source: str, url: Optional[str] = None, note: Optional[str] = None) -> Dict[str, Any]:
    return {
        "label": label,
        "source": source,
        "url": url,
        "timestamp": _utcnow_iso(),
        "note": note,
    }


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "N/A", "."):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _indicator_value(fred_payload: Dict[str, Any], label: str) -> Optional[float]:
    indicator = (fred_payload.get("indicators") or {}).get(label) or {}
    return _safe_float(indicator.get("latest_value"))


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def _estimate_model_lane(depth: str) -> Dict[str, Any]:
    lanes = {
        "briefing": {
            "tier": 0,
            "lane": "deterministic + cached research graph",
            "estimated_cost_usd": 0.0,
        },
        "signals": {
            "tier": 0,
            "lane": "deterministic signal engine",
            "estimated_cost_usd": 0.0,
        },
        "workspace": {
            "tier": 2,
            "lane": "retrieval-backed synthesis",
            "estimated_cost_usd": 0.01,
        },
        "deep_dive": {
            "tier": 3,
            "lane": "long-context filing/transcript analysis",
            "estimated_cost_usd": 0.03,
        },
    }
    return lanes.get(depth, lanes["briefing"])


async def _cross_asset_snapshots() -> List[Dict[str, Any]]:
    assets = [
        ("UUP", "Dollar"),
        ("TLT", "Long Bonds"),
        ("^VIX", "Volatility"),
        ("GLD", "Gold"),
        ("USO", "Oil"),
        ("CPER", "Copper"),
        ("HYG", "High Yield Credit"),
        ("SPY", "US Equities"),
        ("QQQ", "Nasdaq 100"),
    ]
    snapshots: List[Dict[str, Any]] = []
    for ticker, label in assets:
        try:
            snapshot = await get_stock_info(ticker)
            snapshots.append(
                {
                    "ticker": ticker,
                    "label": label,
                    "price": snapshot.get("price"),
                    "change_percent": snapshot.get("change_percent"),
                }
            )
        except Exception:
            snapshots.append({"ticker": ticker, "label": label, "price": None, "change_percent": None})
    return snapshots


def _classify_cross_asset_signal(snapshots: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    by_ticker = {item["ticker"]: item for item in snapshots}
    uup = _safe_float((by_ticker.get("UUP") or {}).get("change_percent")) or 0.0
    tlt = _safe_float((by_ticker.get("TLT") or {}).get("change_percent")) or 0.0
    vix = _safe_float((by_ticker.get("^VIX") or {}).get("change_percent")) or 0.0
    gld = _safe_float((by_ticker.get("GLD") or {}).get("change_percent")) or 0.0
    uso = _safe_float((by_ticker.get("USO") or {}).get("change_percent")) or 0.0
    cper = _safe_float((by_ticker.get("CPER") or {}).get("change_percent")) or 0.0
    hyg = _safe_float((by_ticker.get("HYG") or {}).get("change_percent")) or 0.0
    spy = _safe_float((by_ticker.get("SPY") or {}).get("change_percent")) or 0.0

    if uup > 0.5 and tlt > 0.4 and vix > 2 and gld > 0.4:
        return {
            "signal": "risk_off",
            "summary": "Dollar, bonds, volatility, and gold are rising together, a classic defensive alignment.",
        }
    if uup < 0 and tlt < 0 and vix < 0 and cper > 0.4 and spy > 0:
        return {
            "signal": "risk_on",
            "summary": "Dollar, bonds, and volatility are easing while copper and equities are firming, which supports a growth-on tape.",
        }
    if tlt < -0.4 and gld > 0.4 and uso > 0.7 and hyg <= 0:
        return {
            "signal": "stagflation_watch",
            "summary": "Rates pressure and rising defensive inflation hedges are showing up together, which is a stagflation-style caution signal.",
        }
    if spy > 0.4 and hyg < -0.3:
        return {
            "signal": "credit_equity_divergence",
            "summary": "Equities are pushing higher while credit is lagging, which often precedes a lower-quality risk rally.",
        }
    return {
        "signal": "mixed",
        "summary": "Cross-asset signals are mixed and do not yet support a strong high-conviction regime call.",
    }


async def build_macro_regime_view() -> Dict[str, Any]:
    regime_inputs, sector_data, cross_asset = await asyncio.gather(
        collect_regime_inputs(),
        get_sector_performance(),
        _cross_asset_snapshots(),
    )

    classification = classify_regime(regime_inputs)
    vix_level = _safe_float(regime_inputs.get("vix"))
    ten_two = _safe_float(regime_inputs.get("ten_two_spread"))
    unemployment = _safe_float(regime_inputs.get("unemployment_rate"))
    fed_funds = _safe_float(regime_inputs.get("fed_funds_rate"))
    cross_asset_signal = _classify_cross_asset_signal(cross_asset)
    regime = classification["regime"]
    confidence = classification["confidence"]
    summary = classification["summary"]
    warnings = classification.get("warnings", [])

    sectors = (sector_data.get("sectors") or [])[:5]
    sector_implications = [
        {
            "sector": sector.get("sector"),
            "outlook": "favorable" if (sector.get("change_percent") or 0) > 0 else "cautious",
            "change_percent": sector.get("change_percent"),
        }
        for sector in sectors
    ]

    key_indicators = [
        {"name": "Fed Funds Rate", "value": fed_funds, "signal": "policy"},
        {"name": "10Y-2Y Spread", "value": ten_two, "signal": "curve"},
        {"name": "Unemployment Rate", "value": unemployment, "signal": "labor"},
        {"name": "VIX", "value": vix_level, "signal": "volatility"},
        {"name": "Cross-Asset", "value": cross_asset_signal["signal"], "signal": "regime"},
    ]

    citations = [
        _citation("Market overview", "Yahoo Finance market data"),
        _citation("Macro indicators", "FRED"),
        _citation("Sector rotation snapshot", "SPDR sector ETF performance"),
    ]

    return {
        "regime": regime,
        "confidence": confidence,
        "summary": summary,
        "regime_inputs": regime_inputs,
        "sector_implications": sector_implications,
        "key_indicators": key_indicators,
        "cross_asset_view": cross_asset,
        "citations": citations,
        "as_of": regime_inputs.get("data_as_of") or _utcnow_iso(),
        "cross_asset_signal": cross_asset_signal,
        "volatility_change": vix_level,
        "warnings": warnings,
    }


async def build_signal_feed(db, limit: int = 12, persist: bool = True) -> List[Dict[str, Any]]:
    macro_view, movers, overview = await asyncio.gather(
        build_macro_regime_view(),
        get_top_movers(),
        get_market_overview(),
    )

    signals: List[Dict[str, Any]] = []
    cross_asset_signal = macro_view.get("cross_asset_signal", {})
    signals.append(
        {
            "signal_type": "macro_regime",
            "asset_scope": "market",
            "severity": "high" if macro_view["confidence"] >= 70 else "medium",
            "title": f"{macro_view['regime'].replace('_', ' ').title()} regime",
            "summary": macro_view["summary"],
            "tickers": ["SPY", "QQQ", "TLT", "UUP"],
            "evidence": [
                f"Cross-asset state: {cross_asset_signal.get('signal', 'mixed')}",
                f"Macro confidence: {macro_view['confidence']} / 100",
            ],
            "freshness": macro_view["as_of"],
            "citations": macro_view["citations"],
            "created_at": _utcnow_iso(),
        }
    )

    top_gainer = (movers.get("gainers") or [{}])[0]
    if top_gainer.get("symbol"):
        signals.append(
            {
                "signal_type": "price_momentum",
                "asset_scope": "single_stock",
                "severity": "medium",
                "title": f"{top_gainer['symbol']} leading upside momentum",
                "summary": f"{top_gainer['symbol']} is the strongest gainer in the tracked universe, which makes it worth checking for catalyst-backed strength rather than headline-only momentum.",
                "tickers": [top_gainer["symbol"]],
                "evidence": [f"Daily move: {_format_pct(top_gainer.get('change_percent'))}"],
                "freshness": _utcnow_iso(),
                "citations": [_citation("Top movers", "Yahoo Finance screener data")],
                "created_at": _utcnow_iso(),
            }
        )

    top_loser = (movers.get("losers") or [{}])[0]
    if top_loser.get("symbol"):
        signals.append(
            {
                "signal_type": "drawdown_watch",
                "asset_scope": "single_stock",
                "severity": "medium",
                "title": f"{top_loser['symbol']} downside pressure",
                "summary": f"{top_loser['symbol']} is the weakest laggard in the tracked universe, which makes it a candidate for event, guidance, or positioning review.",
                "tickers": [top_loser["symbol"]],
                "evidence": [f"Daily move: {_format_pct(top_loser.get('change_percent'))}"],
                "freshness": _utcnow_iso(),
                "citations": [_citation("Top movers", "Yahoo Finance screener data")],
                "created_at": _utcnow_iso(),
            }
        )

    spx = overview.get("^GSPC") or {}
    qqq = overview.get("^IXIC") or {}
    signals.append(
        {
            "signal_type": "market_breadth",
            "asset_scope": "market",
            "severity": "low",
            "title": "Index tape snapshot",
            "summary": "Use the broad index tape as the opening filter before reading any single-stock setup.",
            "tickers": ["^GSPC", "^IXIC", "^VIX"],
            "evidence": [
                f"S&P 500 move: {_format_pct(spx.get('change_percent'))}",
                f"Nasdaq move: {_format_pct(qqq.get('change_percent'))}",
            ],
            "freshness": _utcnow_iso(),
            "citations": [_citation("Market overview", "Yahoo Finance market data")],
            "created_at": _utcnow_iso(),
        }
    )

    signals = signals[:limit]
    if persist:
        await save_signal_events(db, signals)
        recent = await get_recent_signal_events(db, limit)
        return recent or signals
    return signals


async def _load_chart_technicals(ticker: str) -> Dict[str, Any]:
    try:
        chart = await get_stock_chart(ticker, period="6mo", interval="1d")
    except Exception:
        return {
            "trend": "unknown",
            "price_vs_20dma": None,
            "price_vs_50dma": None,
            "support_zone": None,
            "resistance_zone": None,
        }

    closes = [row.get("close") for row in chart if row.get("close") is not None]
    if len(closes) < 50:
        return {
            "trend": "limited_history",
            "price_vs_20dma": None,
            "price_vs_50dma": None,
            "support_zone": None,
            "resistance_zone": None,
        }

    current = closes[-1]
    ma20 = mean(closes[-20:])
    ma50 = mean(closes[-50:])
    support = min(closes[-20:])
    resistance = max(closes[-20:])
    if current > ma20 > ma50:
        trend = "uptrend"
    elif current < ma20 < ma50:
        trend = "downtrend"
    else:
        trend = "mixed"
    return {
        "trend": trend,
        "price_vs_20dma": round(((current / ma20) - 1) * 100, 2),
        "price_vs_50dma": round(((current / ma50) - 1) * 100, 2),
        "support_zone": round(support, 2),
        "resistance_zone": round(resistance, 2),
    }


def _build_thesis(snapshot: Dict[str, Any], technicals: Dict[str, Any], insider: Dict[str, Any], filings: Dict[str, Any]) -> Dict[str, Any]:
    bull_case: List[str] = []
    bear_case: List[str] = []
    base_case: List[str] = []

    revenue_growth = _safe_float(snapshot.get("revenue_growth"))
    analyst_target = _safe_float(snapshot.get("target_mean_price"))
    current_price = _safe_float(snapshot.get("price"))
    debt_to_equity = _safe_float(snapshot.get("debt_to_equity"))

    if revenue_growth is not None and revenue_growth > 0.08:
        bull_case.append("Revenue growth remains strong enough to support a premium multiple if execution holds.")
    if analyst_target and current_price and analyst_target > current_price:
        bull_case.append("Consensus targets still imply upside versus spot pricing.")
    if (insider.get("signal") or "").startswith("bullish"):
        bull_case.append("Insider activity is skewing constructive rather than defensive.")
    if technicals.get("trend") == "uptrend":
        bull_case.append("Trend structure is positive with price holding above medium-term moving averages.")

    if debt_to_equity is not None and debt_to_equity > 180:
        bear_case.append("Balance-sheet leverage is elevated enough to compress flexibility in a tougher macro tape.")
    if technicals.get("trend") == "downtrend":
        bear_case.append("Price structure is deteriorating and momentum is working against fresh long exposure.")
    if snapshot.get("recommendation_key") == "sell":
        bear_case.append("Street sentiment is already leaning defensive.")
    if filings.get("red_flags"):
        bear_case.append("Recent filings surface issues that need direct document review before raising conviction.")

    base_case.append("The highest-quality setup is to combine macro regime context with fresh filing, transcript, and catalyst review before changing conviction.")
    base_case.append("Treat the workspace as a repeatable research process, not as a single-answer oracle.")

    confidence = 58 + min(len(bull_case), 2) * 6 - min(len(bear_case), 2) * 4
    confidence = max(35, min(82, confidence))

    return {
        "bull_case": bull_case[:4],
        "base_case": base_case[:3],
        "bear_case": bear_case[:4],
        "confidence": confidence,
        "stance": "constructive" if len(bull_case) >= len(bear_case) else "balanced_caution",
    }


async def build_ticker_workspace(ticker: str) -> Dict[str, Any]:
    ticker = ticker.upper()
    snapshot, news, filings, insider, transcript, macro_context, technicals = await asyncio.gather(
        get_rich_stock_data(ticker),
        get_ticker_news(ticker),
        get_sec_financials(ticker),
        get_insider_transactions(ticker),
        get_earnings_transcript(ticker, query=f"{ticker} guidance margins demand capital allocation"),
        build_macro_regime_view(),
        _load_chart_technicals(ticker),
    )

    filing_highlights: List[str] = []
    annual_revenue = filings.get("annual_revenue") or []
    if len(annual_revenue) >= 2:
        latest = _safe_float(annual_revenue[0].get("value"))
        prior = _safe_float(annual_revenue[1].get("value"))
        if latest is not None and prior not in (None, 0):
            change_pct = ((latest / prior) - 1) * 100
            filing_highlights.append(f"Latest annual revenue is tracking at {change_pct:.2f}% versus the prior comparable filing.")

    insider_txns = insider.get("transactions") or []
    insider_buys = sum(1 for txn in insider_txns if "purchase" in str(txn.get("transaction_type", "")).lower() or txn.get("transaction_type") == "Buy")
    insider_sells = sum(1 for txn in insider_txns if "sell" in str(txn.get("transaction_type", "")).lower())
    insider_signal = "neutral"
    if insider_buys >= 2 and insider_buys > insider_sells:
        insider_signal = "bullish_cluster"
    elif insider_sells >= 3 and insider_sells > insider_buys:
        insider_signal = "bearish_distribution"

    insider_view = {
        "signal": insider_signal,
        "transactions": insider_txns[:6],
        "summary": "Insider activity is sparse right now." if not insider_txns else f"Observed {len(insider_txns[:6])} recent insider filings in the current view.",
    }

    transcript_view = {
        "meta": transcript.get("meta", {}),
        "highlights": [passage.get("text", "") for passage in (transcript.get("passages") or [])[:3]],
        "summary": "Transcript retrieval is available for quote extraction and management-tone review." if transcript.get("passages") else transcript.get("error", "Transcript coverage unavailable."),
    }

    filings_view = {
        "summary": "Structured SEC data is available for filing-based trend review." if not filings.get("error") else filings.get("error"),
        "highlights": filing_highlights,
        "annual_revenue": annual_revenue[:4],
        "quarterly_eps": (filings.get("quarterly_eps") or [])[:4],
        "red_flags": [filings.get("error")] if filings.get("error") else [],
    }

    thesis = _build_thesis(snapshot, technicals, insider_view, filings_view)
    citations = [
        _citation("Ticker snapshot", "Yahoo Finance rich stock data"),
        _citation("Ticker news", "Yahoo Finance news feed"),
        _citation("SEC financials", "EDGAR company facts"),
        _citation("Insider activity", "SEC / Finnhub insider feed"),
        _citation("Transcript highlights", "Finnhub transcript search"),
    ]

    return {
        "ticker": ticker,
        "as_of": _utcnow_iso(),
        "snapshot": snapshot,
        "technicals": technicals,
        "macro_context": {
            "regime": macro_context["regime"],
            "summary": macro_context["summary"],
            "cross_asset_signal": macro_context.get("cross_asset_signal", {}),
        },
        "filings": filings_view,
        "transcripts": transcript_view,
        "insider": insider_view,
        "thesis": thesis,
        "news": news[:6],
        "open_questions": [
            "What changed in the most recent filing versus the prior filing?",
            "Is management language becoming more precise or more defensive?",
            "Does the current macro regime help or hurt this company's margin structure?",
        ],
        "citations": citations,
        "model_lane": _estimate_model_lane("workspace"),
    }


async def build_watchlist_board(db, user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    user_id = user.get("user_id") if user else None
    tickers = await get_watchlist_tickers(db, user_id)
    saved_theses = await get_saved_theses(db, user_id)
    watchlist = tickers[:12]

    async def _build_watchlist_item(ticker: str) -> Dict[str, Any]:
        try:
            snapshot, news = await asyncio.gather(
                get_rich_stock_data(ticker),
                get_ticker_news(ticker),
            )
            latest_article = news[0] if news else {}
            return {
                "ticker": ticker,
                "name": snapshot.get("name", ticker),
                "price": snapshot.get("price"),
                "change_percent": snapshot.get("change_percent"),
                "priority": "high" if abs(snapshot.get("change_percent") or 0) >= 3 else "normal",
                "tags": [snapshot.get("sector")] if snapshot.get("sector") else [],
                "latest_headline": latest_article.get("title"),
                "latest_sentiment": latest_article.get("sentiment"),
                "next_step": "Open workspace and refresh the evidence stack.",
            }
        except Exception:
            return {
                "ticker": ticker,
                "name": ticker,
                "price": None,
                "change_percent": None,
                "priority": "normal",
                "tags": [],
                "latest_headline": None,
                "latest_sentiment": None,
                "next_step": "Data refresh required.",
            }

    items = await asyncio.gather(*[_build_watchlist_item(ticker) for ticker in watchlist]) if watchlist else []

    return {
        "as_of": _utcnow_iso(),
        "watchlist_id": user_id or "public",
        "items": items,
        "saved_theses": saved_theses,
        "citations": [
            _citation("Watchlist prices", "Yahoo Finance"),
            _citation("Saved research state", "MarketFlux user research memory"),
        ],
    }


async def build_portfolio_diagnostics(db, user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    user_id = user.get("user_id") if user else None
    holdings = await get_portfolio_holdings(db, user_id)
    if not holdings:
        return {
            "as_of": _utcnow_iso(),
            "total_value": 0.0,
            "concentration_risk": "No holdings on file yet.",
            "macro_sensitivity": "Unavailable",
            "sector_exposure": [],
            "holdings": [],
            "insights": [
                "Add holdings to unlock concentration, sector, and macro sensitivity diagnostics.",
            ],
            "citations": [_citation("Portfolio state", "MarketFlux stored holdings")],
        }

    async def _enrich_holding(holding: Dict[str, Any]) -> Dict[str, Any]:
        ticker = str(holding.get("ticker", "")).upper()
        shares = _safe_float(holding.get("shares")) or 0.0
        try:
            snapshot = await get_rich_stock_data(ticker)
            current_price = _safe_float(snapshot.get("price")) or 0.0
            value = round(current_price * shares, 2)
            sector = snapshot.get("sector") or "Unclassified"
            return {
                "ticker": ticker,
                "shares": shares,
                "price": current_price,
                "value": value,
                "sector": sector,
                "change_percent": snapshot.get("change_percent"),
            }
        except Exception:
            return {
                "ticker": ticker,
                "shares": shares,
                "price": None,
                "value": 0.0,
                "sector": "Unclassified",
                "change_percent": None,
            }

    enriched = await asyncio.gather(*[_enrich_holding(holding) for holding in holdings])
    total_value = 0.0
    sector_totals: Dict[str, float] = {}

    for holding in enriched:
        total_value += holding["value"]
        sector = holding["sector"]
        sector_totals[sector] = sector_totals.get(sector, 0.0) + holding["value"]

    sector_exposure = []
    top_weight = 0.0
    for sector, value in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True):
        weight = round((value / total_value) * 100, 2) if total_value else 0.0
        sector_exposure.append({"sector": sector, "weight": weight})
        top_weight = max(top_weight, weight)

    concentration_risk = "Balanced"
    if top_weight >= 35:
        concentration_risk = "High concentration"
    elif top_weight >= 20:
        concentration_risk = "Moderate concentration"

    cyclicals = sum(item["weight"] for item in sector_exposure if item["sector"] in {"Technology", "Consumer Discretionary", "Industrials"})
    defensives = sum(item["weight"] for item in sector_exposure if item["sector"] in {"Healthcare", "Consumer Staples", "Utilities"})
    if cyclicals > defensives + 10:
        macro_sensitivity = "Growth-sensitive"
    elif defensives > cyclicals + 10:
        macro_sensitivity = "Defensive"
    else:
        macro_sensitivity = "Mixed"

    insights = [
        f"Top sector exposure is {sector_exposure[0]['sector']} at {sector_exposure[0]['weight']:.2f}%." if sector_exposure else "Sector exposure is still forming.",
        "Tie each major holding to a saved thesis and catalyst list to make the portfolio research-aware.",
        "Use the signal feed to separate market-driven drawdowns from thesis-breaking drawdowns.",
    ]

    return {
        "as_of": _utcnow_iso(),
        "total_value": round(total_value, 2),
        "concentration_risk": concentration_risk,
        "macro_sensitivity": macro_sensitivity,
        "sector_exposure": sector_exposure,
        "holdings": enriched,
        "insights": insights,
        "citations": [_citation("Portfolio prices", "Yahoo Finance"), _citation("Holdings", "MarketFlux stored holdings")],
    }


async def build_compare_view(tickers: List[str]) -> Dict[str, Any]:
    normalized = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
    rows: List[Dict[str, Any]] = []
    for ticker in normalized[:6]:
        snapshot = await get_rich_stock_data(ticker)
        rows.append(
            {
                "ticker": ticker,
                "name": snapshot.get("name"),
                "sector": snapshot.get("sector"),
                "price": snapshot.get("price"),
                "change_percent": snapshot.get("change_percent"),
                "market_cap": snapshot.get("market_cap"),
                "pe_ratio": snapshot.get("pe_ratio"),
                "revenue_growth": snapshot.get("revenue_growth"),
                "recommendation_key": snapshot.get("recommendation_key"),
                "target_mean_price": snapshot.get("target_mean_price"),
            }
        )

    return {
        "as_of": _utcnow_iso(),
        "tickers": normalized,
        "rows": rows,
        "citations": [_citation("Compare data", "Yahoo Finance rich stock data")],
    }


def _score_from_severity(severity: str) -> int:
    return {"low": 48, "medium": 64, "high": 78}.get(severity, 55)


def _dedupe_tickers(signals: List[Dict[str, Any]], fallback: Optional[List[str]] = None) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for signal in signals:
        for ticker in signal.get("tickers") or []:
            normalized = str(ticker).upper()
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
    for ticker in fallback or []:
        normalized = str(ticker).upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _build_agent_swarm(
    macro_regime: Dict[str, Any],
    signals: List[Dict[str, Any]],
    watchlist_board: Dict[str, Any],
    portfolio_diagnostics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    focus_tickers = _dedupe_tickers(signals, fallback=["NVDA", "MSFT", "AVGO"])
    watchlist_items = watchlist_board.get("items") or []
    concentration = portfolio_diagnostics.get("concentration_risk", "Balanced")
    cross_asset_state = (macro_regime.get("cross_asset_signal") or {}).get("signal", "mixed")
    lead_signal = signals[0] if signals else {}

    return [
        {
            "agent_id": "fundamental-core",
            "name": "Fundamental Agent",
            "status": "building_thesis",
            "focus": focus_tickers[0] if focus_tickers else "NVDA",
            "confidence": min(82, _score_from_severity(lead_signal.get("severity", "medium")) + 8),
            "next_action": "Refresh filing deltas and compare management claims to current valuation.",
            "model_version": "fundamental-v0.3",
            "updated_at": _utcnow_iso(),
        },
        {
            "agent_id": "macro-regime",
            "name": "Macro Agent",
            "status": "monitoring_regime",
            "focus": macro_regime.get("regime", "transitional"),
            "confidence": macro_regime.get("confidence", 58),
            "next_action": f"Track cross-asset alignment while regime is {macro_regime.get('regime', 'transitional')}.",
            "model_version": "macro-v0.2",
            "updated_at": _utcnow_iso(),
        },
        {
            "agent_id": "event-scan",
            "name": "Event-Driven Agent",
            "status": "screening_catalysts",
            "focus": focus_tickers[1] if len(focus_tickers) > 1 else focus_tickers[0] if focus_tickers else "SMCI",
            "confidence": 63 if any(signal.get("signal_type") == "drawdown_watch" for signal in signals) else 57,
            "next_action": "Route mover names into transcript, filing, and headline catalyst review.",
            "model_version": "event-v0.2",
            "updated_at": _utcnow_iso(),
        },
        {
            "agent_id": "stat-arb",
            "name": "Stat-Arb Agent",
            "status": "measuring_dispersion",
            "focus": "single-name dispersion",
            "confidence": 61 if len(focus_tickers) >= 2 else 54,
            "next_action": "Measure widening spread between strongest gainers and weakest laggards.",
            "model_version": "statarb-v0.1",
            "updated_at": _utcnow_iso(),
        },
        {
            "agent_id": "narrative-sentiment",
            "name": "Narrative Agent",
            "status": "challenging_consensus",
            "focus": (watchlist_items[0] or {}).get("ticker") if watchlist_items else cross_asset_state,
            "confidence": 59 if watchlist_items else 52,
            "next_action": "Map headlines and management language against price reaction to catch narrative drift.",
            "model_version": "narrative-v0.2",
            "updated_at": _utcnow_iso(),
        },
        {
            "agent_id": "risk-guardian",
            "name": "Risk Agent",
            "status": "guardrails_live",
            "focus": concentration,
            "confidence": 76,
            "next_action": "Raise alerts when portfolio overlap or macro sensitivity drifts outside guardrails.",
            "model_version": "risk-v0.3",
            "updated_at": _utcnow_iso(),
        },
    ]


def _build_strategy_lab(
    macro_regime: Dict[str, Any],
    signals: List[Dict[str, Any]],
    watchlist_board: Dict[str, Any],
) -> List[Dict[str, Any]]:
    focus_tickers = _dedupe_tickers(signals, fallback=["NVDA", "MSFT", "SMCI"])
    watchlist_items = watchlist_board.get("items") or []
    cross_asset_state = (macro_regime.get("cross_asset_signal") or {}).get("signal", "mixed")
    lead_signal = signals[0] if signals else {}
    lead_ticker = focus_tickers[0] if focus_tickers else "NVDA"
    hedge_ticker = focus_tickers[1] if len(focus_tickers) > 1 else "TLT"
    watchlist_focus = (watchlist_items[0] or {}).get("ticker") if watchlist_items else lead_ticker

    return [
        {
            "strategy_id": "regime-rotation-stack",
            "name": "Regime Rotation Stack",
            "archetype": "macro-adaptive allocation",
            "summary": f"Use the {macro_regime.get('regime', 'transitional')} backdrop to rebalance between growth beta and duration hedges.",
            "edge": f"Cross-asset state is {cross_asset_state}, which creates a regime-aware allocation edge rather than a single-ticker bet.",
            "confidence": macro_regime.get("confidence", 58),
            "invalidation": "Break the thesis if cross-asset alignment flips for two consecutive refreshes.",
            "signals": [macro_regime.get("regime", "transitional"), cross_asset_state, "risk budget"],
            "model_version": "strategy-regime-v0.2",
        },
        {
            "strategy_id": "dispersion-catalyst-pairs",
            "name": "Dispersion Catalyst Pairs",
            "archetype": "event-driven relative value",
            "summary": f"Pair upside leaders with downside laggards to isolate catalyst-driven dispersion instead of raw market beta.",
            "edge": f"Current tape highlights {lead_ticker} versus {hedge_ticker} style dispersion that can be debated by separate agents.",
            "confidence": max(57, _score_from_severity(lead_signal.get('severity', 'medium'))),
            "invalidation": "Stand down if the mover spread compresses and headline catalysts fail to explain the move.",
            "signals": ["price momentum", "drawdown watch", "dispersion"],
            "model_version": "strategy-dispersion-v0.1",
        },
        {
            "strategy_id": "watchlist-thesis-refinement",
            "name": "Watchlist Thesis Refinement",
            "archetype": "human-supervised idea factory",
            "summary": f"Promote {watchlist_focus} and adjacent names into a structured bull/base/bear debate with explicit invalidation triggers.",
            "edge": "Turns passive saved tickers into a compounding research memory and recommendation queue.",
            "confidence": 62 if watchlist_items else 51,
            "invalidation": "Pause if no fresh evidence lands from filings, price, or narrative changes.",
            "signals": ["watchlist", "saved thesis", "evidence chain"],
            "model_version": "strategy-memory-v0.2",
        },
        {
            "strategy_id": "risk-fracture-monitor",
            "name": "Risk Fracture Monitor",
            "archetype": "alpha preservation",
            "summary": "Continuously test whether credit, volatility, and equities are diverging enough to justify tighter gross exposure.",
            "edge": "Protects capital by spotting market structure breaks before a single-name thesis gets blamed for systemic risk.",
            "confidence": 60 if cross_asset_state != "mixed" else 54,
            "invalidation": "Deactivate when credit, volatility, and equities stop diverging in the same direction.",
            "signals": ["cross-asset", "volatility", "credit"],
            "model_version": "strategy-risk-v0.2",
        },
    ]


def _build_recommendation_queue(
    macro_regime: Dict[str, Any],
    signals: List[Dict[str, Any]],
    watchlist_board: Dict[str, Any],
) -> List[Dict[str, Any]]:
    watchlist_items = watchlist_board.get("items") or []
    queue: List[Dict[str, Any]] = []
    for signal in signals[:4]:
        tickers = signal.get("tickers") or []
        action = "research_long"
        owner = "research-supervisor"
        if signal.get("signal_type") == "drawdown_watch":
            action = "risk_review"
            owner = "risk-officer"
        elif signal.get("signal_type") == "macro_regime":
            action = "rebalance_risk_budget"
            owner = "portfolio-manager"
        elif signal.get("signal_type") == "market_breadth":
            action = "tighten_market_exposure"
            owner = "risk-officer"

        queue.append(
            {
                "title": signal.get("title"),
                "action": action,
                "owner": owner,
                "tickers": tickers,
                "summary": signal.get("summary"),
                "confidence": _score_from_severity(signal.get("severity", "medium")),
                "horizon": "intraday to 5D" if signal.get("asset_scope") == "single_stock" else "1D to 2W",
                "invalidation": "Stand down if the next refresh removes the signal or the evidence chain weakens.",
                "evidence": signal.get("evidence") or [],
            }
        )

    if watchlist_items:
        top_item = watchlist_items[0]
        queue.append(
            {
                "title": f"{top_item['ticker']} watchlist refresh",
                "action": "open_workspace",
                "owner": "research-supervisor",
                "tickers": [top_item["ticker"]],
                "summary": "Tie the watchlist name to a saved thesis, catalysts, and current signal state.",
                "confidence": 58,
                "horizon": "today",
                "invalidation": "Skip if there is no new catalyst, filing, or price move to review.",
                "evidence": [top_item.get("latest_headline") or "No fresh headline recorded."],
            }
        )

    return queue[:5]


def _build_risk_overview(
    macro_regime: Dict[str, Any],
    portfolio_diagnostics: Dict[str, Any],
    signals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    concentration = portfolio_diagnostics.get("concentration_risk", "Balanced")
    macro_sensitivity = portfolio_diagnostics.get("macro_sensitivity", "Mixed")
    risk_signal_count = sum(1 for signal in signals if signal.get("signal_type") in {"market_breadth", "drawdown_watch", "macro_regime"})

    return {
        "gross_exposure": "paper + recommendation mode",
        "net_bias": "growth long bias" if macro_regime.get("regime") in {"goldilocks", "expansion"} else "defensive",
        "drawdown_guardrail": "Escalate at -4% daily portfolio move or two consecutive high-severity risk signals.",
        "liquidity_state": "normal" if risk_signal_count <= 2 else "tightening",
        "concentration_risk": concentration,
        "macro_sensitivity": macro_sensitivity,
        "roles": ["admin", "portfolio-manager", "risk-officer", "compliance-viewer", "research-supervisor"],
        "approval_mode": "human approval required before execution or capital reallocation.",
    }


def _build_terminal_events(
    macro_regime: Dict[str, Any],
    agent_swarm: List[Dict[str, Any]],
    recommendation_queue: List[Dict[str, Any]],
    strategy_lab: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    events = [
        {
            "timestamp": _utcnow_iso(),
            "level": "info",
            "agent": "macro-regime",
            "message": f"Regime classified as {macro_regime.get('regime', 'transitional')} with confidence {macro_regime.get('confidence', 58)}/100.",
        }
    ]
    for agent in agent_swarm[:3]:
        events.append(
            {
                "timestamp": _utcnow_iso(),
                "level": "info",
                "agent": agent["agent_id"],
                "message": f"{agent['name']} is {agent['status'].replace('_', ' ')} on {agent['focus']}.",
            }
        )
    for strategy in strategy_lab[:2]:
        events.append(
            {
                "timestamp": _utcnow_iso(),
                "level": "alpha",
                "agent": strategy["strategy_id"],
                "message": f"{strategy['name']} updated to model version {strategy['model_version']}.",
            }
        )
    for recommendation in recommendation_queue[:2]:
        events.append(
            {
                "timestamp": _utcnow_iso(),
                "level": "risk" if recommendation["action"] in {"risk_review", "tighten_market_exposure"} else "queue",
                "agent": recommendation["owner"],
                "message": f"Queued {recommendation['title']} for {recommendation['owner']}.",
            }
        )
    return events


async def build_command_center(db, user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    user_id = user.get("user_id") if user else None
    macro_regime, signals, watchlist_board, portfolio_diagnostics, recent_strategy_runs = await asyncio.gather(
        build_macro_regime_view(),
        build_signal_feed(db, limit=8),
        build_watchlist_board(db, user),
        build_portfolio_diagnostics(db, user),
        get_recent_strategy_runs(db, user_id, limit=4),
    )
    agent_swarm = _build_agent_swarm(macro_regime, signals, watchlist_board, portfolio_diagnostics)
    strategy_lab = _build_strategy_lab(macro_regime, signals, watchlist_board)
    recommendation_queue = _build_recommendation_queue(macro_regime, signals, watchlist_board)
    risk_overview = _build_risk_overview(macro_regime, portfolio_diagnostics, signals)
    terminal_events = _build_terminal_events(macro_regime, agent_swarm, recommendation_queue, strategy_lab)
    spotlight_tickers = _dedupe_tickers(signals, fallback=["NVDA", "MSFT", "AVGO"])

    live_metrics = {
        "active_agents": len(agent_swarm),
        "live_signals": len(signals),
        "strategies_live": len(strategy_lab),
        "recommendations": len(recommendation_queue),
        "live_strategy_runs": len(recent_strategy_runs),
        "refresh_interval_seconds": 25,
        "latency_target_ms": 450,
    }

    audit_events = [
        {
            "timestamp": _utcnow_iso(),
            "event_type": "strategy_versioned",
            "owner": "research-supervisor",
            "summary": "Signal graph refreshed and queued strategies re-scored.",
        },
        {
            "timestamp": _utcnow_iso(),
            "event_type": "risk_guardrail_checked",
            "owner": "risk-officer",
            "summary": f"Concentration risk is {risk_overview['concentration_risk']} with {risk_overview['macro_sensitivity']} macro sensitivity.",
        },
        {
            "timestamp": _utcnow_iso(),
            "event_type": "human_approval_required",
            "owner": "portfolio-manager",
            "summary": "Execution remains gated behind human approval and audit logging.",
        },
    ]

    return {
        "as_of": _utcnow_iso(),
        "product_identity": "AI-native hedge fund operating system",
        "market_regime": macro_regime,
        "live_metrics": live_metrics,
        "agent_swarm": agent_swarm,
        "strategy_lab": strategy_lab,
        "recommendation_queue": recommendation_queue,
        "risk_overview": risk_overview,
        "terminal_events": terminal_events,
        "audit_events": audit_events,
        "watchlist": watchlist_board,
        "portfolio": portfolio_diagnostics,
        "signals": signals,
        "recent_strategy_runs": recent_strategy_runs,
        "scenario_lab": {
            "provider": "MiroFish",
            "configured": MiroFishBridgeClient().configured,
            "mode": "external scenario simulation service",
            "best_fit": "Narrative, policy, and event-path simulations before capital deployment.",
            "why_not_core_execution": "MiroFish is strongest for swarm simulation and what-if rehearsal, not for low-latency market-feed execution.",
        },
        "spotlight": {"ticker": spotlight_tickers[0] if spotlight_tickers else "NVDA"},
        "citations": [
            _citation("Macro regime", "MarketFlux macro engine"),
            _citation("Signal queue", "MarketFlux deterministic signal engine"),
            _citation("Risk overview", "MarketFlux portfolio diagnostics"),
        ],
    }


async def build_daily_brief(db, user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    macro_regime, top_signals, top_movers, watchlist_board = await asyncio.gather(
        build_macro_regime_view(),
        build_signal_feed(db),
        get_top_movers(),
        build_watchlist_board(db, user),
    )

    today = date.today().isoformat()
    return {
        "id": f"brief_{today}_{uuid.uuid4().hex[:8]}",
        "date": today,
        "generated_at": _utcnow_iso(),
        "macro_regime": macro_regime,
        "top_signals": top_signals[:6],
        "watchlist_updates": watchlist_board.get("items", [])[:6],
        "top_movers": top_movers,
        "citations": [
            _citation("Macro regime", "FRED + market overview"),
            _citation("Signals", "MarketFlux deterministic signal engine"),
            _citation("Watchlist updates", "MarketFlux watchlist intelligence"),
        ],
        "methodology": {
            "research_only": True,
            "evidence_required": True,
            "model_lane": _estimate_model_lane("briefing"),
        },
    }
