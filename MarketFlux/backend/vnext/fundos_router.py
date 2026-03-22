from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request

from .fundos_service import (
    build_audit_feed,
    build_fundos_overview,
    build_paper_portfolio,
    build_strategy_queue,
    fundos_store_configured,
    search_fundos,
)


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

    return router
