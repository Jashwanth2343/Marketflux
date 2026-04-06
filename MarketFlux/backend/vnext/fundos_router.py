from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .fundos_service import (
    build_audit_feed,
    build_fundos_overview,
    build_paper_portfolio,
    build_strategy_queue,
    fundos_store_configured,
    search_fundos,
)

# Import quant_agent at module level (backend root is already on sys.path when
# the FastAPI app starts from the backend directory).
from quant_agent import run_autonomous_research, run_backtest
import alpaca_service


def build_fundos_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/fundos", tags=["marketflux-fundos"])

    @router.get("/overview")
    async def fundos_overview(request: Request):
        user = await get_current_user(request)
        return await build_fundos_overview(db, user)

    @router.get("/search")
    async def fundos_search(request: Request, q: str = ""):
        user = await get_current_user(request)
        return await search_fundos(db, user, q)

    @router.get("/strategies/queue")
    async def strategy_queue(request: Request, limit: int = 50):
        user = await get_current_user(request)
        return await build_strategy_queue(db, user, limit=max(1, min(limit, 100)))

    @router.get("/portfolio/paper")
    async def paper_portfolio(request: Request):
        user = await get_current_user(request)
        return await build_paper_portfolio(user)

    @router.get("/audit-feed")
    async def audit_feed(request: Request, limit: int = 20):
        user = await get_current_user(request)
        return await build_audit_feed(db, user, limit=max(1, min(limit, 100)))

    @router.post("/terminal/sessions")
    async def create_terminal_session(request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to create a Fund OS terminal session.")
            
        data = await request.json()
        prompt = data.get("prompt", "")
        # Fallback if UI sends "query"
        if not prompt:
            prompt = data.get("query", "")
        tickers = data.get("tickers", [])
        
        # Get regime
        from .adapter_helpers import collect_regime_inputs, classify_regime
        try:
            inputs = await collect_regime_inputs()
            regime = classify_regime(inputs)
        except Exception:
            regime = {"regime": "unknown"}
            
        async def stream_generator():
            import asyncio
            import json
            import re
            from .strategy_swarm import run_swarm
            from .fundos_pg_client import get_pg_connection
            
            q = asyncio.Queue()
            async def yield_cb(msg):
                await q.put(msg)
                
            async def worker():
                try:
                    res = await run_swarm(
                        prompt=prompt,
                        regime_context=regime,
                        tickers=tickers,
                        user_id=user["user_id"],
                        yield_callback=yield_cb
                    )
                    
                    try:
                        conn = await get_pg_connection()
                        final_text = res["final_strategy"]
                        def extract_field(key: str) -> str:
                            match = re.search(f"{key}:?\\s*(.*?)(?=\\n[A-Z]+:|$)", final_text, re.DOTALL)
                            return match.group(1).strip() if match else ""
                            
                        title = "Swarm Strategy Analysis"
                        if tickers:
                            title += f" for {tickers[0]}"
                        
                        conv_str = extract_field("CONVICTION")
                        confidence = int(conv_str) * 10 if conv_str.isdigit() and int(conv_str) <= 10 else 50
                        if confidence < 10 and conv_str.isdigit():
                             confidence = int(conv_str) * 10
                             
                        await conn.execute("""
                            INSERT INTO strategy_proposals (
                                owner_user_id, strategy_type, ticker, tickers, title, thesis,
                                entry, target, stop, confidence, invalidation,
                                evidence, market_context, is_paper, execution_status, model_trace
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                        """, 
                        user["user_id"], "swarm_direct", tickers[0] if tickers else None, tickers,
                        title, extract_field("THESIS") or extract_field("VERDICT"), extract_field("ENTRY"), extract_field("TARGET"),
                        extract_field("STOP"), confidence, extract_field("INVALIDATION"),
                        json.dumps(res["agents_output"]), json.dumps(res["regime_used"]), True, "pending_approval",
                        json.dumps({"raw_output": final_text})
                        )
                        await conn.close()
                    except Exception as pg_err:
                        import logging
                        logging.getLogger(__name__).error(f"Postgres insert failed: {pg_err}")
                    
                    await q.put({"type": "done", "status": "ok", "strategy": res})
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    await q.put({"type": "error", "message": f"Swarm error: {str(e)}"})
                finally:
                    await q.put(None)
                    
            asyncio.create_task(worker())
            
            while True:
                item = await q.get()
                if item is None:
                    break
                # Server sent events mapping
                import json
                yield f"data: {json.dumps(item)}\n\n"
                
        from fastapi.responses import StreamingResponse
        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    @router.get("/strategies/{strategy_id}")
    async def get_strategy(strategy_id: str, request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required")
            
        from .fundos_pg_client import get_pg_connection
        import json
        
        try:
            conn = await get_pg_connection()
            row = await conn.fetchrow("""
                SELECT * FROM strategy_proposals 
                WHERE id = $1::uuid AND owner_user_id = $2
            """, strategy_id, user["user_id"])
            await conn.close()
            
            if not row:
                raise HTTPException(404, "Strategy not found")
                
            data = dict(row)
            data["evidence"] = json.loads(data["evidence"]) if isinstance(data["evidence"], str) else data["evidence"]
            data["market_context"] = json.loads(data["market_context"]) if isinstance(data["market_context"], str) else data["market_context"]
            data["model_trace"] = json.loads(data["model_trace"]) if isinstance(data["model_trace"], str) else data["model_trace"]
            data["id"] = str(data["id"])
            if data["session_id"]:
                data["session_id"] = str(data["session_id"])
            if data["created_at"]:
                data["created_at"] = data["created_at"].isoformat()
            if data["updated_at"]:
                data["updated_at"] = data["updated_at"].isoformat()
            if data["approved_at"]:
                data["approved_at"] = data["approved_at"].isoformat()
                
            return data
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            import traceback
            traceback.print_exc()
            raise HTTPException(500, "Failed to load strategy")

    @router.post("/strategies/{strategy_id}/approve")
    async def approve_strategy(strategy_id: str, request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to approve a strategy.")
            
        from .fundos_pg_client import get_pg_connection
        try:
            conn = await get_pg_connection()
            # Update strategy proposals table
            # Since id is a UUID, we must parse or cast strategy_id
            await conn.execute(
                "UPDATE strategy_proposals SET execution_status = 'approved', approved_by = $1, approved_at = NOW() WHERE id = $2::uuid", 
                user["user_id"], strategy_id
            )
            await conn.close()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Approval failed: {e}")
            raise HTTPException(500, "Failed to update strategy approval status.")
            
        return {"status": "ok"}

    @router.post("/strategies/{strategy_id}/reject")
    async def reject_strategy(strategy_id: str, request: Request):
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required to reject a strategy.")
            
        from .fundos_pg_client import get_pg_connection
        try:
            conn = await get_pg_connection()
            await conn.execute(
                "UPDATE strategy_proposals SET execution_status = 'rejected' WHERE id = $2::uuid", 
                user["user_id"], strategy_id
            )
            await conn.close()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Rejection failed: {e}")
            raise HTTPException(500, "Failed to update strategy rejection status.")
            
        return {"status": "ok"}

    # -----------------------------------------------------------------------
    # Quant Agent — autonomous research + backtest endpoints
    # -----------------------------------------------------------------------

    @router.post("/quant-agent/run")
    async def quant_agent_run(request: Request):
        """
        Stream an autonomous quant research session as Server-Sent Events.

        Request body JSON:
          ticker        str   required  e.g. "NVDA"
          capital       float optional  default 100000
          risk_profile  str   optional  "conservative" | "balanced" | "aggressive"
        """
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(422, "Invalid JSON body")

        ticker = (body.get("ticker") or "").strip().upper()
        if not ticker:
            raise HTTPException(422, "ticker is required")

        capital = float(body.get("capital") or 100_000)
        risk_profile = str(body.get("risk_profile") or "balanced")
        user_id = user.get("user_id")

        return StreamingResponse(
            run_autonomous_research(
                ticker=ticker,
                capital=capital,
                risk_profile=risk_profile,
                user_id=user_id,
                db=db,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post("/quant-agent/backtest")
    async def quant_agent_backtest(request: Request):
        """
        Run a single named backtest and return the full result as JSON.

        Request body JSON:
          ticker    str   required
          strategy  str   optional  "sma_crossover" | "rsi_mean_reversion" | "momentum"
          period    str   optional  yfinance period string, default "2y"
          capital   float optional  default 100000
          params    dict  optional  strategy-specific parameters
        """
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(422, "Invalid JSON body")

        ticker = (body.get("ticker") or "").strip().upper()
        if not ticker:
            raise HTTPException(422, "ticker is required")

        strategy = str(body.get("strategy") or "sma_crossover")
        period = str(body.get("period") or "2y")
        capital = float(body.get("capital") or 100_000)
        params = body.get("params") or {}

        import asyncio
        try:
            result = await asyncio.to_thread(
                run_backtest, ticker, strategy, period, capital, params
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, f"Backtest execution failed: {exc}") from exc

        if "error" in result:
            raise HTTPException(400, result["error"])
        return result

    # -----------------------------------------------------------------------
    # Alpaca paper-trading connectivity
    # -----------------------------------------------------------------------

    @router.get("/alpaca/status")
    async def alpaca_status(request: Request):
        """Return whether Alpaca credentials are configured and the account summary."""
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        configured = alpaca_service.is_configured()
        if not configured:
            return {"configured": False, "account": None}
        import asyncio
        account = await asyncio.to_thread(alpaca_service.get_account_info)
        if "error" in account:
            raise HTTPException(503, f"Alpaca account fetch failed: {account['error']}")
        return {"configured": True, "account": account}

    @router.get("/alpaca/positions")
    async def alpaca_positions(request: Request):
        """Return open positions in the Alpaca paper account."""
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")
        import asyncio
        return await asyncio.to_thread(alpaca_service.get_positions)

    @router.get("/alpaca/orders")
    async def alpaca_orders(request: Request, status: str = "all", limit: int = 20):
        """Return recent orders from the Alpaca paper account."""
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")
        if limit < 1 or limit > 100:
            raise HTTPException(422, "limit must be between 1 and 100")
        import asyncio
        return await asyncio.to_thread(alpaca_service.get_orders, status, limit)

    @router.post("/alpaca/order")
    async def alpaca_submit_order(request: Request):
        """
        Submit a paper trade to Alpaca after human approval.

        Request body JSON:
          symbol          str   required
          qty             float required
          side            str   required   "buy" | "sell"
          order_type      str   optional   "market" | "limit"  (default "market")
          time_in_force   str   optional   "day" | "gtc"       (default "day")
          limit_price     float optional   required when order_type == "limit"
          strategy_id     str   optional   reference tag
          approved        bool  required   must be true — human approval gate
        """
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(422, "Invalid JSON body")

        # Human approval gate — the frontend must send approved=true explicitly
        if not body.get("approved"):
            raise HTTPException(403, "Trade not approved: set approved=true to confirm")

        symbol = (body.get("symbol") or "").strip().upper()
        if not symbol:
            raise HTTPException(422, "symbol is required")

        try:
            qty = float(body["qty"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, "qty must be a positive number")
        if qty <= 0:
            raise HTTPException(422, "qty must be positive")

        side = str(body.get("side") or "").lower()
        if side not in ("buy", "sell"):
            raise HTTPException(422, "side must be 'buy' or 'sell'")

        order_type = str(body.get("order_type") or "market").lower()
        time_in_force = str(body.get("time_in_force") or "day").lower()
        limit_price = body.get("limit_price")
        strategy_id = body.get("strategy_id")

        import asyncio
        try:
            result = await asyncio.to_thread(
                alpaca_service.submit_paper_order,
                symbol, qty, side, order_type, time_in_force, limit_price, strategy_id,
            )
        except Exception as exc:
            raise HTTPException(503, f"Order submission failed: {exc}") from exc

        if "error" in result:
            raise HTTPException(400, result["error"])
        return result

    return router
