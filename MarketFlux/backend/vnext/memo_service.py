from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Tuple

from ai_service import get_gemini_model


def _workspace_prompt(workspace: Dict[str, Any]) -> str:
    thesis = workspace["thesis"]
    evidence_lines = []
    for block in workspace.get("evidence_blocks", [])[:8]:
        evidence_lines.append(
            f"- [{block['source']}] {block['summary']} (confidence={block.get('confidence')}, freshness={block.get('freshness')})"
        )

    return (
        "Create an investment research memo with sections for Thesis, Why Now, Evidence, Risks, "
        "Invalidation, and What To Watch Next. Keep it clear and grounded.\n\n"
        f"Ticker: {thesis['ticker']}\n"
        f"Claim: {thesis['claim']}\n"
        f"Horizon: {thesis['time_horizon']}\n"
        f"Why now: {thesis.get('why_now') or 'Not provided'}\n"
        f"Invalidation: {', '.join(thesis.get('invalidation_conditions') or []) or 'None provided'}\n"
        f"Evidence:\n{chr(10).join(evidence_lines) if evidence_lines else '- No evidence blocks yet.'}\n"
    )


async def generate_memo_from_workspace(workspace: Dict[str, Any]) -> Tuple[str, str]:
    thesis = workspace["thesis"]
    if not os.getenv("GEMINI_API_KEY"):
        summary = f"{thesis['ticker']} thesis memo"
        body = (
            f"# {thesis['ticker']} Thesis Memo\n\n"
            f"## Thesis\n{thesis['claim']}\n\n"
            f"## Why Now\n{thesis.get('why_now') or 'Why-now context has not been filled in yet.'}\n\n"
            f"## Risks And Invalidation\n"
            f"{chr(10).join(f'- {item}' for item in (thesis.get('invalidation_conditions') or [])) or '- No invalidation conditions provided yet.'}\n\n"
            "## Evidence Snapshot\n"
            f"{chr(10).join(f'- [{item['source']}] {item['summary']}' for item in workspace.get('evidence_blocks', [])[:5]) or '- Evidence is still loading.'}"
        )
        return summary, body

    prompt = _workspace_prompt(workspace)
    model = get_gemini_model(
        system_instruction=(
            "You are MarketFlux Memo Writer. Write concise institutional-style research memos with explicit risks "
            "and invalidation. Avoid hype and do not imply financial advice."
        )
    )
    response = await asyncio.to_thread(model.generate_content, prompt)
    body = (response.text or "").strip()
    summary = body.splitlines()[0].replace("#", "").strip() if body else f"{thesis['ticker']} memo"
    return summary, body


async def generate_change_summary(current_thesis: Dict[str, Any], proposed_fields: Dict[str, Any]) -> str:
    next_claim = proposed_fields.get("claim") or current_thesis["claim"]
    next_horizon = proposed_fields.get("time_horizon") or current_thesis["time_horizon"]
    next_status = proposed_fields.get("status") or current_thesis["status"]
    changes = []
    if next_claim != current_thesis["claim"]:
        changes.append("claim updated")
    if next_horizon != current_thesis["time_horizon"]:
        changes.append(f"horizon -> {next_horizon}")
    if next_status != current_thesis["status"]:
        changes.append(f"status -> {next_status}")
    if proposed_fields.get("why_now") is not None and proposed_fields.get("why_now") != current_thesis.get("why_now"):
        changes.append("why-now context revised")
    if proposed_fields.get("invalidation_conditions") is not None:
        changes.append("invalidation conditions updated")

    if not os.getenv("GEMINI_API_KEY"):
        return ", ".join(changes) if changes else "Thesis revision captured."

    model = get_gemini_model(
        system_instruction="Summarize thesis revisions in one short sentence. Return only the sentence."
    )
    prompt = (
        f"Current claim: {current_thesis['claim']}\n"
        f"Updated claim: {next_claim}\n"
        f"Current horizon: {current_thesis['time_horizon']}\n"
        f"Updated horizon: {next_horizon}\n"
        f"Current status: {current_thesis['status']}\n"
        f"Updated status: {next_status}\n"
        f"Change hints: {', '.join(changes) or 'General update'}"
    )
    response = await asyncio.to_thread(model.generate_content, prompt)
    return (response.text or "").strip() or "Thesis revision captured."
