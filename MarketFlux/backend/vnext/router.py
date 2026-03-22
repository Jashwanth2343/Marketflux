from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .engines import (
    build_command_center,
    build_compare_view,
    build_daily_brief,
    build_portfolio_diagnostics,
    build_signal_feed,
    build_ticker_workspace,
    build_watchlist_board,
)
from .repository import get_daily_brief, get_saved_theses, save_daily_brief, save_thesis
from .schemas import MiroFishReportStatusRequest, MiroFishScenarioCreate, StrategyTerminalRequest, ThesisCreate
from .mirofish_bridge import MiroFishBridgeClient
from .strategy_terminal import run_strategy_terminal


def build_vnext_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/vnext", tags=["marketflux-vnext"])

    @router.get("/briefing/today")
    async def briefing_today(request: Request, refresh: bool = False):
        user = await get_current_user(request)
        user_id = user.get("user_id") if user else None
        today = date.today().isoformat()
        if not refresh:
            cached = await get_daily_brief(db, today, user_id)
            if cached:
                return cached

        payload = await build_daily_brief(db, user)
        saved = await save_daily_brief(db, payload, user_id)
        return saved

    @router.get("/signals/feed")
    async def signals_feed(limit: int = 12):
        return {
            "as_of": date.today().isoformat(),
            "signals": await build_signal_feed(db, max(1, min(limit, 20))),
        }

    @router.get("/command-center")
    async def command_center(request: Request):
        user = await get_current_user(request)
        return await build_command_center(db, user)

    @router.get("/research/ticker/{ticker}")
    async def ticker_workspace(ticker: str):
        return await build_ticker_workspace(ticker)

    @router.get("/watchlists/board")
    async def watchlist_board(request: Request):
        user = await get_current_user(request)
        return await build_watchlist_board(db, user)

    @router.get("/portfolio/diagnostics")
    async def portfolio_diagnostics(request: Request):
        user = await get_current_user(request)
        return await build_portfolio_diagnostics(db, user)

    @router.get("/compare")
    async def compare_tickers(tickers: str):
        parsed = [ticker.strip().upper() for ticker in tickers.split(",") if ticker.strip()]
        if len(parsed) < 2:
            raise HTTPException(422, "Please provide at least two comma-separated tickers.")
        return await build_compare_view(parsed)

    @router.get("/methodology")
    async def methodology():
        return {
            "product_identity": "AI-native Quant Research OS for serious retail investors",
            "guardrails": {
                "research_only": True,
                "trade_execution": False,
                "broker_routing": False,
                "evidence_required": True,
            },
            "engines": [
                "Macro Regime Engine",
                "Cross-Asset Engine",
                "Filing Intelligence Engine",
                "Earnings Intelligence Engine",
                "Insider Cluster Engine",
                "Research Synthesis Engine",
            ],
            "freshness_policy": "Every artifact should expose timestamps, citations, and confidence so users can separate live evidence from stale narrative.",
        }

    @router.get("/mirofish/status")
    async def mirofish_status():
        client = MiroFishBridgeClient()
        status = await client.health()
        status["integration_mode"] = "external service bridge"
        status["licensing_note"] = "MiroFish is AGPL-3.0, so MarketFlux integrates it via service boundary rather than vendoring source code."
        return status

    @router.post("/mirofish/scenario-lab")
    async def mirofish_scenario_lab(payload: MiroFishScenarioCreate):
        client = MiroFishBridgeClient()
        return await client.create_financial_scenario(**payload.model_dump())

    @router.post("/mirofish/report-status")
    async def mirofish_report_status(payload: MiroFishReportStatusRequest):
        client = MiroFishBridgeClient()
        return await client.get_report_status(**payload.model_dump())

    @router.post("/terminal/strategy/stream")
    async def terminal_strategy_stream(payload: StrategyTerminalRequest, request: Request):
        user = await get_current_user(request)
        return StreamingResponse(
            run_strategy_terminal(
                db=db,
                request_payload=payload.model_dump(),
                user=user,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.get("/theses")
    async def list_saved_theses(request: Request, ticker: Optional[str] = None):
        user = await get_current_user(request)
        user_id = user.get("user_id") if user else None
        return {"items": await get_saved_theses(db, user_id, ticker=ticker)}

    @router.post("/theses")
    async def create_saved_thesis(request: Request, payload: ThesisCreate):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to save a thesis.")
        doc = await save_thesis(db, user["user_id"], payload.model_dump())
        return {"item": doc}

    return router
