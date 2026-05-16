"""HTTP surface for the backtester.

Endpoints (all under ``/api/backtest``):

* ``POST /run``               – single in-sample backtest.
* ``POST /walk-forward``      – walk-forward analysis (train/test windows).
* ``POST /validate``          – static validation of a strategy DSL payload.
* ``GET  /example``           – returns a runnable example strategy.
* ``POST /benchmark``         – buy-and-hold equity curve for a ticker.
* ``POST /monte-carlo``       – Monte Carlo reshuffling of trade returns.
* ``POST /ai-critique``       – AI-generated quant analysis of backtest results.
* ``POST /ai-parse-strategy`` – natural language → strategy DSL via AI.
* ``GET  /market-context``    – current VIX, SPY trend, and SPY price.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .data import load_ohlcv
from .dsl import Strategy, validate_strategy
from .metrics import cagr as compute_cagr
from .runner import run_backtest, run_walk_forward

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

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


class BenchmarkRequest(BaseModel):
    ticker: str = "SPY"
    start: str = Field(..., description="ISO date YYYY-MM-DD")
    end: str = Field(..., description="ISO date YYYY-MM-DD")
    initial_capital: float = 100_000.0


class MonteCarloRequest(BaseModel):
    trades: List[Dict[str, Any]] = Field(..., description="List of trade dicts with return_pct")
    initial_capital: float = 100_000.0
    num_simulations: int = 500


class AICritiqueRequest(BaseModel):
    strategy: Dict[str, Any]
    metrics: Dict[str, Any]
    trades_summary: Dict[str, Any] = Field(
        ..., description='{"total": N, "winners": N, "losers": N}'
    )


class AIParseStrategyRequest(BaseModel):
    description: str = Field(..., description="Natural language strategy description")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _sanitize_float(v: float) -> float:
    """Replace NaN / Inf with 0.0 so JSON serialization never blows up."""
    if v != v or math.isinf(v):
        return 0.0
    return v


_DSL_SCHEMA_DESCRIPTION = """\
The strategy DSL is a JSON object with these keys:
- "name": string (strategy name)
- "universe": list of ticker strings, e.g. ["AAPL", "MSFT"]
- "indicators": dict mapping indicator name -> config, e.g.:
    {"rsi14": {"type": "rsi", "period": 14}, "sma200": {"type": "sma", "period": 200}}
  Supported indicator types: sma, ema, rsi, bbands, macd, atr, adx, stoch, obv, vwap
- "entry": a boolean expression dict using combinators and comparators:
    Combinators: {"all": [...]}, {"any": [...]}, {"not": {...}}
    Comparators: {"lt": [lhs, rhs]}, {"lte": [...]}, {"gt": [...]}, {"gte": [...]},
                 {"eq": [...]}, {"neq": [...]}, {"crosses_above": [...]}, {"crosses_below": [...]}
    Operands are either numbers or column/indicator names (e.g. "close", "rsi14", "sma200")
- "exit": same expression syntax as entry, plus trade-state predicates:
    {"hold_days_gte": N}, {"profit_pct_gte": x}, {"loss_pct_gte": x}
- "position_sizing": {"type": "fixed_pct", "pct": 0.10} or {"type": "fixed_dollar", "amount": 1000} or {"type": "equal_weight"}
- "max_positions": int (default 10)
- "stop_loss_pct": float or null (e.g. 0.08 for 8%)
- "take_profit_pct": float or null (e.g. 0.20 for 20%)
"""


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def build_backtest_router(get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/backtest", tags=["backtest"])

    # ------------------------------------------------------------------
    # Existing endpoints
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # POST /benchmark — buy-and-hold equity curve
    # ------------------------------------------------------------------

    @router.post("/benchmark")
    async def benchmark(payload: BenchmarkRequest, request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to run benchmark")

        try:
            df = await asyncio.to_thread(
                load_ohlcv, payload.ticker, payload.start, payload.end
            )
        except Exception as exc:
            logger.exception("benchmark data load failed")
            raise HTTPException(500, detail=f"Failed to load data for {payload.ticker}: {exc}")

        if df is None or df.empty:
            raise HTTPException(422, detail=f"No data for {payload.ticker} in the given range")

        close = df["close"].dropna()
        if close.empty:
            raise HTTPException(422, detail=f"No close prices for {payload.ticker}")

        shares = payload.initial_capital / float(close.iloc[0])
        equity = close * shares

        total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
        cagr_val = compute_cagr(equity)

        return {
            "equity_curve": [
                {"date": idx.isoformat(), "equity": _sanitize_float(float(val))}
                for idx, val in equity.items()
            ],
            "total_return": _sanitize_float(total_return),
            "cagr": _sanitize_float(cagr_val),
        }

    # ------------------------------------------------------------------
    # POST /monte-carlo — reshuffled trade simulations
    # ------------------------------------------------------------------

    @router.post("/monte-carlo")
    async def monte_carlo(payload: MonteCarloRequest, request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to run Monte Carlo simulation")

        if not payload.trades:
            raise HTTPException(422, detail="No trades provided")

        def _run_mc() -> dict:
            rng = np.random.default_rng()
            returns = np.array(
                [float(t.get("return_pct", 0.0)) for t in payload.trades]
            )
            n_trades = len(returns)
            n_sims = max(1, min(payload.num_simulations, 10_000))
            capital = float(payload.initial_capital)

            all_final: List[float] = []
            all_curves: List[List[float]] = []

            for _ in range(n_sims):
                shuffled = rng.permutation(returns)
                equity = capital
                curve = [equity]
                for r in shuffled:
                    equity *= (1.0 + float(r))
                    curve.append(equity)
                all_final.append(equity)
                all_curves.append(curve)

            all_curves_arr = np.array(all_curves)
            p5 = np.percentile(all_curves_arr, 5, axis=0).tolist()
            p50 = np.percentile(all_curves_arr, 50, axis=0).tolist()
            p95 = np.percentile(all_curves_arr, 95, axis=0).tolist()

            profitable = sum(1 for f in all_final if f > capital)
            win_pct = profitable / n_sims

            return {
                "percentile_5": [_sanitize_float(v) for v in p5],
                "percentile_50": [_sanitize_float(v) for v in p50],
                "percentile_95": [_sanitize_float(v) for v in p95],
                "win_pct": win_pct,
            }

        try:
            return await asyncio.to_thread(_run_mc)
        except Exception as exc:
            logger.exception("Monte Carlo simulation failed")
            raise HTTPException(500, detail=f"Monte Carlo failed: {exc}")

    # ------------------------------------------------------------------
    # POST /ai-critique — quant analyst review
    # ------------------------------------------------------------------

    @router.post("/ai-critique")
    async def ai_critique(payload: AICritiqueRequest, request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required for AI critique")

        try:
            from ai_service import get_gemini_model
        except ImportError:
            raise HTTPException(503, detail="AI service unavailable")

        system_prompt = (
            "You are a senior quantitative analyst reviewing backtest results. "
            "Write in a professional, data-driven voice. Be specific about numbers. "
            "Format your response as JSON with keys: narrative, strengths, weaknesses, "
            "suggestions, confidence_score."
        )

        user_prompt = (
            f"Strategy: {json.dumps(payload.strategy)}\n\n"
            f"Metrics: {json.dumps(payload.metrics)}\n\n"
            f"Trade summary: {json.dumps(payload.trades_summary)}\n\n"
            "Provide your analysis as the specified JSON."
        )

        try:
            model = get_gemini_model(system_instruction=system_prompt)
            response = await asyncio.to_thread(model.generate_content, user_prompt)
            text = response.text.strip()
            if "```" in text:
                parts = text.split("```")
                for part in parts:
                    cleaned = part.strip()
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:].strip()
                    if cleaned.startswith("{"):
                        text = cleaned
                        break
            result = json.loads(text)
            for key in ("narrative", "strengths", "weaknesses", "suggestions", "confidence_score"):
                if key not in result:
                    result[key] = [] if key in ("strengths", "weaknesses", "suggestions") else ("" if key == "narrative" else 5)
            return result
        except json.JSONDecodeError:
            logger.warning("AI critique returned non-JSON, wrapping raw text")
            return {
                "narrative": text if 'text' in dir() else "Analysis unavailable",
                "strengths": [],
                "weaknesses": [],
                "suggestions": [],
                "confidence_score": 5,
            }
        except Exception as exc:
            logger.exception("AI critique failed")
            raise HTTPException(503, detail=f"AI critique unavailable: {exc}")

    # ------------------------------------------------------------------
    # POST /ai-parse-strategy — natural language to DSL
    # ------------------------------------------------------------------

    @router.post("/ai-parse-strategy")
    async def ai_parse_strategy(payload: AIParseStrategyRequest, request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required for AI strategy parsing")

        try:
            from ai_service import get_gemini_model
        except ImportError:
            raise HTTPException(503, detail="AI service unavailable")

        system_prompt = (
            "You are a quantitative trading strategy parser. Convert natural language "
            "strategy descriptions into valid JSON strategy DSL objects. "
            "Return ONLY a valid JSON object, no markdown, no explanation.\n\n"
            f"DSL Schema:\n{_DSL_SCHEMA_DESCRIPTION}"
        )

        user_prompt = (
            f"Convert this strategy description to a valid DSL JSON:\n\n"
            f"{payload.description}\n\n"
            "Return ONLY the JSON object."
        )

        try:
            model = get_gemini_model(system_instruction=system_prompt)
            response = await asyncio.to_thread(model.generate_content, user_prompt)
            text = response.text.strip()
            if "```" in text:
                parts = text.split("```")
                for part in parts:
                    cleaned = part.strip()
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:].strip()
                    if cleaned.startswith("{"):
                        text = cleaned
                        break
            strategy = json.loads(text)
            validate_strategy(strategy)
            return {"strategy": strategy}
        except json.JSONDecodeError:
            raise HTTPException(422, detail="AI returned invalid JSON. Try rephrasing your strategy.")
        except ValueError as exc:
            raise HTTPException(422, detail=f"AI-generated strategy has validation errors: {exc}")
        except Exception as exc:
            logger.exception("AI strategy parsing failed")
            raise HTTPException(503, detail=f"AI parsing unavailable: {exc}")

    # ------------------------------------------------------------------
    # GET /market-context — VIX, SPY trend, SPY price
    # ------------------------------------------------------------------

    @router.get("/market-context")
    async def market_context(request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required for market context")

        def _fetch_context() -> dict:
            import yfinance as yf

            result: Dict[str, Any] = {}

            try:
                vix = yf.Ticker("^VIX")
                vix_hist = vix.history(period="1d")
                if not vix_hist.empty:
                    result["vix"] = _sanitize_float(float(vix_hist["Close"].iloc[-1]))
                else:
                    result["vix"] = None
            except Exception as exc:
                logger.warning("Failed to fetch VIX: %s", exc)
                result["vix"] = None

            try:
                spy = yf.Ticker("SPY")
                spy_hist = spy.history(period="1y")
                if not spy_hist.empty:
                    close = spy_hist["Close"]
                    result["spy_price"] = _sanitize_float(float(close.iloc[-1]))
                    sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
                    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
                    result["spy_sma50"] = _sanitize_float(sma50) if sma50 is not None else None
                    result["spy_sma200"] = _sanitize_float(sma200) if sma200 is not None else None
                    if sma50 is not None and sma200 is not None:
                        result["spy_trend"] = "uptrend" if sma50 > sma200 else "downtrend"
                    else:
                        result["spy_trend"] = "unknown"
                else:
                    result["spy_price"] = None
                    result["spy_sma50"] = None
                    result["spy_sma200"] = None
                    result["spy_trend"] = "unknown"
            except Exception as exc:
                logger.warning("Failed to fetch SPY data: %s", exc)
                result["spy_price"] = None
                result["spy_sma50"] = None
                result["spy_sma200"] = None
                result["spy_trend"] = "unknown"

            return result

        try:
            return await asyncio.to_thread(_fetch_context)
        except Exception as exc:
            logger.exception("market context fetch failed")
            raise HTTPException(500, detail=f"Market context unavailable: {exc}")

    return router
