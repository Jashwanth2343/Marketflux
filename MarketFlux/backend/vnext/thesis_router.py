from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from market_data import get_stock_info

from .evidence_service import collect_evidence_background
from .memo_service import generate_change_summary, generate_memo_from_workspace
from .policy_engine import evaluate_paper_trade, get_next_earnings_event
from .repository import get_portfolio_holdings
from .schemas import (
    MemoRequest,
    PaperTradeCreate,
    PaperTradeUpdate,
    PolicyUpsertRequest,
    ThesisWorkspaceCreate,
    ThesisWorkspaceRevision,
)
from .thesis_repository import (
    create_memo,
    create_paper_trade,
    create_revision,
    create_thesis,
    get_paper_trade,
    get_policies,
    get_workspace,
    list_open_paper_trades,
    list_theses,
    update_paper_trade,
    upsert_policies,
)


def build_thesis_router(db, get_current_user: Callable[[Request], Any]) -> APIRouter:
    router = APIRouter(tags=["marketflux-vnext-theses"])

    async def require_user(request: Request) -> dict:
        user = await get_current_user(request)
        if not user:
            raise HTTPException(401, "Login required.")
        return user

    @router.get("/theses")
    async def thesis_list(request: Request):
        user = await require_user(request)
        return {"items": await list_theses(user["user_id"])}

    @router.post("/theses")
    async def thesis_create(request: Request, payload: ThesisWorkspaceCreate, background_tasks: BackgroundTasks):
        user = await require_user(request)
        workspace = await create_thesis(user["user_id"], payload.model_dump())
        latest_revision = workspace.get("latest_revision") or {}
        background_tasks.add_task(
            collect_evidence_background,
            db,
            workspace["thesis"]["id"],
            latest_revision.get("id"),
            workspace["thesis"]["ticker"],
        )
        return {"item": workspace}

    @router.get("/theses/{thesis_id}")
    async def thesis_detail(thesis_id: str, request: Request):
        user = await require_user(request)
        workspace = await get_workspace(user["user_id"], thesis_id)
        if not workspace:
            raise HTTPException(404, "Thesis not found.")
        return {"item": workspace}

    @router.post("/theses/{thesis_id}/revise")
    async def thesis_revise(
        thesis_id: str,
        request: Request,
        payload: ThesisWorkspaceRevision,
        background_tasks: BackgroundTasks,
    ):
        user = await require_user(request)
        current_workspace = await get_workspace(user["user_id"], thesis_id)
        if not current_workspace:
            raise HTTPException(404, "Thesis not found.")

        revision_payload = payload.model_dump(exclude_none=True)
        if payload.auto_generate_summary and not revision_payload.get("change_summary"):
            revision_payload["change_summary"] = await generate_change_summary(current_workspace["thesis"], revision_payload)

        updated_workspace = await create_revision(user["user_id"], thesis_id, revision_payload)
        latest_revision = updated_workspace.get("latest_revision") or {}
        background_tasks.add_task(
            collect_evidence_background,
            db,
            thesis_id,
            latest_revision.get("id"),
            updated_workspace["thesis"]["ticker"],
        )
        return {"item": updated_workspace}

    @router.post("/theses/{thesis_id}/memo")
    async def thesis_memo(thesis_id: str, request: Request, payload: MemoRequest):
        user = await require_user(request)
        workspace = await get_workspace(user["user_id"], thesis_id)
        if not workspace:
            raise HTTPException(404, "Thesis not found.")

        latest_revision = workspace.get("latest_revision") or {}
        if payload.mode == "save":
            if not payload.body:
                raise HTTPException(422, "Memo body is required when saving a memo.")
            summary = payload.summary or payload.body.splitlines()[0][:140]
            memo = await create_memo(
                user["user_id"],
                thesis_id,
                latest_revision.get("id"),
                summary,
                payload.body,
                "user",
                {"mode": "save"},
            )
            return {"item": memo}

        summary, body = await generate_memo_from_workspace(workspace)
        memo = await create_memo(
            user["user_id"],
            thesis_id,
            latest_revision.get("id"),
            summary,
            body,
            "ai",
            {"mode": "generate"},
        )
        return {"item": memo}

    @router.get("/policies")
    async def policy_list(request: Request):
        user = await require_user(request)
        return await get_policies(user["user_id"])

    @router.post("/policies")
    async def policy_upsert(request: Request, payload: PolicyUpsertRequest):
        user = await require_user(request)
        return await upsert_policies(
            user["user_id"],
            [item.model_dump() for item in payload.items],
        )

    @router.post("/theses/{thesis_id}/paper-trades")
    async def paper_trade_open(thesis_id: str, request: Request, payload: PaperTradeCreate):
        user = await require_user(request)
        workspace = await get_workspace(user["user_id"], thesis_id)
        if not workspace:
            raise HTTPException(404, "Thesis not found.")

        ticker = workspace["thesis"]["ticker"]
        quote = await get_stock_info(ticker)
        policies = await get_policies(user["user_id"])
        open_trades = await list_open_paper_trades(user["user_id"])
        holdings = await get_portfolio_holdings(db, user["user_id"])
        earnings_event = await get_next_earnings_event(ticker)
        policy_result = evaluate_paper_trade(
            ticker=ticker,
            proposed_side=payload.side,
            proposed_size=payload.size,
            current_price=float(quote.get("price") or 0),
            effective_policies=policies["effective"],
            open_trades=open_trades,
            evidence_blocks=workspace.get("evidence_blocks", []),
            portfolio_holdings=holdings,
            earnings_event=earnings_event,
        )
        if not policy_result["allowed"]:
            raise HTTPException(
                422,
                detail={
                    "message": "Paper trade blocked by policy checks.",
                    "policy_result": policy_result,
                },
            )

        latest_revision = workspace.get("latest_revision") or {}
        trade = await create_paper_trade(
            user["user_id"],
            thesis_id,
            latest_revision.get("id"),
            ticker,
            payload.side,
            payload.size,
            float(quote.get("price") or 0),
            payload.notes,
            policy_result,
        )
        return {"item": trade, "policy_result": policy_result}

    @router.patch("/paper-trades/{trade_id}")
    async def paper_trade_patch(trade_id: str, request: Request, payload: PaperTradeUpdate):
        user = await require_user(request)
        trade = await get_paper_trade(user["user_id"], trade_id)
        if not trade:
            raise HTTPException(404, "Paper trade not found.")

        exit_price = None
        if payload.status == "closed":
            quote = await get_stock_info(trade["ticker"])
            exit_price = float(quote.get("price") or 0)

        updated = await update_paper_trade(
            user["user_id"],
            trade_id,
            payload.status,
            exit_price,
            payload.notes,
        )
        if not updated:
            raise HTTPException(404, "Paper trade not found.")
        return {"item": updated}

    return router
