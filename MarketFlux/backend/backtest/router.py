"""HTTP surface for the backtester.

Endpoints (all under ``/api/backtest``):

* ``POST /run``           – single in-sample backtest.
* ``POST /walk-forward``  – walk-forward analysis (train/test windows).
* ``POST /validate``      – static validation of a strategy DSL payload (**login required**).
* ``GET  /example``       – returns a runnable example strategy (**login required**).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .dsl import Strategy, validate_strategy
from .runner import run_backtest, run_walk_forward

logger = logging.getLogger(__name__)


class CostsPayload(BaseModel):
    commission_per_share: float = 0.0
    commission_min: float = 0.0
    commission_pct: float = 0.0005
    slippage_bps: float = 5.0


class BacktestRequest(BaseModel):
    strategy: Dict[str, Any] = Field(..., description="Strategy DSL payload")
    start: str = Field(..., description="ISO date YYYY-MM-DD")
    end: str = Field(..., description="ISO date YYYY-MM-DD")
    initial_capital: float = 100_000.0
    costs: Optional[CostsPayload] = None


class WalkForwardRequest(BacktestRequest):
    train_months: int = 36
    test_months: int = 12
    step_months: Optional[int] = None


def _example_strategy() -> Dict[str, Any]:
    return {
        "name": "RSI mean reversion w/ trend filter",
        "universe": ["AAPL", "MSFT", "NVDA"],
        "indicators": {
            "rsi14": {"type": "rsi", "period": 14},
            "sma200": {"type": "sma", "period": 200},
        },
        "entry": {
            "all": [
                {"lt": ["rsi14", 30]},
                {"gt": ["close", "sma200"]},
            ]
        },
        "exit": {
            "any": [
                {"gt": ["rsi14", 65]},
                {"hold_days_gte": 20},
            ]
        },
        "position_sizing": {"type": "fixed_pct", "pct": 0.10},
        "max_positions": 5,
        "stop_loss_pct": 0.08,
        "take_profit_pct": 0.20,
    }


def build_backtest_router(get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/backtest", tags=["backtest"])

    @router.get("/example")
    async def example(request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to load example strategies")

        return {"strategy": _example_strategy()}

    @router.post("/validate")
    async def validate(payload: Dict[str, Any], request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to validate strategies")

        try:
            validate_strategy(payload)
            Strategy.from_dict(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"ok": True}

    @router.post("/run")
    async def run(payload: BacktestRequest, request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to run backtests")

        try:
            result = await asyncio.to_thread(
                run_backtest,
                payload.strategy,
                payload.start,
                payload.end,
                payload.initial_capital,
                payload.costs.model_dump() if payload.costs else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:
            logger.exception("backtest run failed")
            raise HTTPException(status_code=500, detail=f"backtest failed: {exc}")
        return result.as_dict()

    @router.post("/walk-forward")
    async def walk_forward(payload: WalkForwardRequest, request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to run walk-forward analysis")

        try:
            return await asyncio.to_thread(
                run_walk_forward,
                payload.strategy,
                payload.start,
                payload.end,
                payload.train_months,
                payload.test_months,
                payload.step_months,
                payload.initial_capital,
                payload.costs.model_dump() if payload.costs else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:
            logger.exception("walk-forward run failed")
            raise HTTPException(status_code=500, detail=f"walk-forward failed: {exc}")

    return router
