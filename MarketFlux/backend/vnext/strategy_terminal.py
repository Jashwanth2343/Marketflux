from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from .engines import build_macro_regime_view, build_signal_feed, build_ticker_workspace
from .model_router import StrategyLLMRouter
from .repository import save_strategy_run


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sse_event(event_type: str, payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


def _thinking(step: str, message: str) -> str:
    return _sse_event("thinking", {"step": step, "message": message})


def _agent_event(agent: Dict[str, Any]) -> str:
    return _sse_event("agent", {"agent": agent})


def _done(payload: Dict[str, Any]) -> str:
    return _sse_event("done", payload)


_SKIP_TICKERS = {
    "AND", "THE", "WITH", "THAT", "THIS", "FROM", "WHAT", "WHEN", "YOUR", "FUND", "OS",
    "LONG", "SHORT", "MODE", "RISK", "SELL", "BUY", "HOLD", "OPEN", "HIGH", "LOW",
    "PLAN", "REAL", "LIVE", "DATA", "CHAT", "MARKET", "TRADE", "STRATEGY",
}


def _extract_tickers(prompt: str) -> List[str]:
    tickers = []
    seen = set()
    for match in re.findall(r"\b[A-Z]{1,5}\b", prompt.upper()):
        if match in _SKIP_TICKERS or match in seen:
            continue
        seen.add(match)
        tickers.append(match)
    return tickers[:3]


def _safe_confidence(value: Any, fallback: int = 50) -> int:
    try:
        if isinstance(value, str):
            value = value.split("/")[0].strip()
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return fallback


def _workspace_excerpt(workspace: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = workspace.get("snapshot") or {}
    thesis = workspace.get("thesis") or {}
    technicals = workspace.get("technicals") or {}
    return {
        "ticker": workspace.get("ticker"),
        "price": snapshot.get("price"),
        "change_percent": snapshot.get("change_percent"),
        "sector": snapshot.get("sector"),
        "industry": snapshot.get("industry"),
        "pe_ratio": snapshot.get("pe_ratio"),
        "revenue_growth": snapshot.get("revenue_growth"),
        "target_mean_price": snapshot.get("target_mean_price"),
        "trend": technicals.get("trend"),
        "price_vs_20dma": technicals.get("price_vs_20dma"),
        "price_vs_50dma": technicals.get("price_vs_50dma"),
        "bull_case": thesis.get("bull_case") or [],
        "bear_case": thesis.get("bear_case") or [],
        "open_questions": workspace.get("open_questions") or [],
        "filing_summary": (workspace.get("filings") or {}).get("summary"),
        "transcript_summary": (workspace.get("transcripts") or {}).get("summary"),
        "insider_signal": (workspace.get("insider") or {}).get("signal"),
        "macro_context": workspace.get("macro_context") or {},
    }


def _build_terminal_context(
    *,
    prompt: str,
    request: Dict[str, Any],
    macro: Dict[str, Any],
    signals: List[Dict[str, Any]],
    workspaces: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "as_of": _utcnow_iso(),
        "prompt": prompt,
        "mode": request.get("mode", "swing"),
        "risk_profile": request.get("risk_profile", "balanced"),
        "capital_base": request.get("capital_base", 100000.0),
        "allow_short": request.get("allow_short", True),
        "macro_regime": {
            "regime": macro.get("regime"),
            "confidence": macro.get("confidence"),
            "summary": macro.get("summary"),
            "cross_asset_signal": macro.get("cross_asset_signal"),
        },
        "signals": [
            {
                "title": signal.get("title"),
                "signal_type": signal.get("signal_type"),
                "severity": signal.get("severity"),
                "summary": signal.get("summary"),
                "tickers": signal.get("tickers"),
                "evidence": signal.get("evidence"),
            }
            for signal in signals[:6]
        ],
        "workspaces": [_workspace_excerpt(workspace) for workspace in workspaces],
    }


async def _run_agent(
    router: StrategyLLMRouter,
    *,
    agent_id: str,
    agent_name: str,
    role_brief: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "You are one specialist agent inside an AI-native hedge fund OS. "
                "Return JSON only with keys: agent_id, name, stance, summary, trade_expression, confidence, "
                "evidence, risks, invalidation. "
                "Confidence must be an integer 0-100. evidence and risks must be arrays of short strings."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Agent: {agent_name}\n"
                f"Role: {role_brief}\n"
                f"Live market context JSON:\n{json.dumps(context, ensure_ascii=True)}\n\n"
                "Challenge assumptions, stay data-bound, and propose one concrete trade expression."
            ),
        },
    ]
    raw = await router.complete_json(messages=messages, reasoning=True, max_tokens=900, temperature=0.15)
    return {
        "agent_id": raw.get("agent_id") or agent_id,
        "name": raw.get("name") or agent_name,
        "stance": raw.get("stance") or "neutral",
        "summary": raw.get("summary") or "No summary returned.",
        "trade_expression": raw.get("trade_expression") or "No trade structure returned.",
        "confidence": _safe_confidence(raw.get("confidence"), 50),
        "evidence": raw.get("evidence") or [],
        "risks": raw.get("risks") or [],
        "invalidation": raw.get("invalidation") or "Further review required.",
    }


def _render_strategy_markdown(strategy: Dict[str, Any], agents: List[Dict[str, Any]], provider_plan: Dict[str, Any]) -> str:
    why_now = "\n".join(f"- {item}" for item in (strategy.get("why_now") or []))
    checklist = "\n".join(f"- {item}" for item in (strategy.get("execution_checklist") or []))
    risk_flags = "\n".join(f"- {item}" for item in (strategy.get("risk_flags") or []))
    agent_blocks = []
    for agent in agents:
        evidence_lines = "\n".join(f"- {item}" for item in (agent.get("evidence") or []))
        risk_lines = "\n".join(f"- {item}" for item in (agent.get("risks") or []))
        agent_blocks.append(
            f"### {agent['name']}\n"
            f"Stance: **{agent['stance']}** ({agent['confidence']}/100)\n\n"
            f"{agent['summary']}\n\n"
            f"Trade expression: {agent['trade_expression']}\n\n"
            f"Evidence:\n{evidence_lines or '- None returned'}\n\n"
            f"Risks:\n{risk_lines or '- None returned'}\n\n"
            f"Invalidation: {agent['invalidation']}"
        )

    return (
        f"# {strategy.get('title', 'Fund OS Strategy Output')}\n\n"
        f"## Setup\n"
        f"- Direction: {strategy.get('direction', '--')}\n"
        f"- Strategy type: {strategy.get('strategy_type', '--')}\n"
        f"- Tickers: {', '.join(strategy.get('tickers') or []) or '--'}\n"
        f"- Entry: {strategy.get('entry', '--')}\n"
        f"- Target: {strategy.get('target', '--')}\n"
        f"- Stop: {strategy.get('stop', '--')}\n"
        f"- Horizon: {strategy.get('time_horizon', '--')}\n"
        f"- Position sizing: {strategy.get('position_sizing', '--')}\n"
        f"- Confidence: {strategy.get('confidence', '--')}/100\n\n"
        f"## Thesis\n{strategy.get('thesis', 'No thesis returned.')}\n\n"
        f"## Why Now\n{why_now or '- No catalysts returned'}\n\n"
        f"## Execution Checklist\n{checklist or '- No checklist returned'}\n\n"
        f"## Risk Flags\n{risk_flags or '- No risk flags returned'}\n\n"
        f"## Agent Debate\n\n" + "\n\n".join(agent_blocks) + "\n\n"
        f"## Provider Plan\n"
        f"- Provider: {provider_plan.get('provider')}\n"
        f"- Reasoning model: {provider_plan.get('reasoning_model')}\n"
        f"- Cost profile: {provider_plan.get('cost_profile')}\n"
    )


async def run_strategy_terminal(
    *,
    db,
    request_payload: Dict[str, Any],
    user: Optional[Dict[str, Any]],
) -> AsyncGenerator[str, None]:
    router = StrategyLLMRouter()
    provider_plan = router.provider_plan()
    if not router.configured:
        yield _done(
            {
                "status": "provider_unconfigured",
                "message": "Strategy providers are not configured. Set OPENROUTER_API_KEY or NVIDIA_NIM_API_KEY + NVIDIA_NIM_BASE_URL.",
                "provider_plan": provider_plan,
            }
        )
        return

    prompt = request_payload.get("prompt", "").strip()
    requested_tickers = [ticker.strip().upper() for ticker in (request_payload.get("tickers") or []) if ticker.strip()]
    extracted_tickers = _extract_tickers(prompt)
    terminal_tickers = (requested_tickers or extracted_tickers or ["NVDA"])[:2]

    yield _thinking("plan", "Routing the strategy request across live market data, macro state, and ticker workspaces...")
    macro, signals = await asyncio.gather(
        build_macro_regime_view(),
        build_signal_feed(db, limit=6),
    )

    if not requested_tickers:
        signal_tickers = []
        for signal in signals:
            for ticker in signal.get("tickers") or []:
                if ticker.startswith("^"):
                    continue
                if ticker not in signal_tickers:
                    signal_tickers.append(ticker)
        if signal_tickers:
            terminal_tickers = (terminal_tickers + signal_tickers)[:2]

    yield _thinking("context", f"Building live workspaces for {', '.join(terminal_tickers)}...")
    workspace_tasks = [build_ticker_workspace(ticker) for ticker in terminal_tickers]
    workspaces = await asyncio.gather(*workspace_tasks)
    context = _build_terminal_context(
        prompt=prompt,
        request=request_payload,
        macro=macro,
        signals=signals,
        workspaces=workspaces,
    )

    agent_specs = [
        ("macro-agent", "Macro Agent", "Evaluate regime, cross-asset pressure, and macro timing."),
        ("fundamental-agent", "Fundamental Agent", "Evaluate valuation, business quality, filings, and earnings posture."),
        ("market-structure-agent", "Market Structure Agent", "Evaluate trend, momentum, technicals, and trade structuring."),
        ("risk-agent", "Risk Agent", "Challenge the trade, define sizing, kill criteria, and portfolio-level risk."),
    ]
    agent_outputs: List[Dict[str, Any]] = []

    for agent_id, agent_name, role_brief in agent_specs:
        yield _thinking("agents", f"{agent_name} is generating a live thesis...")
        agent_output = await _run_agent(
            router,
            agent_id=agent_id,
            agent_name=agent_name,
            role_brief=role_brief,
            context=context,
        )
        agent_outputs.append(agent_output)
        yield _agent_event(agent_output)

    yield _thinking("synthesis", "Synthesizing agent debate into a single trade plan with explicit risk controls...")
    synthesis_messages = [
        {
            "role": "system",
            "content": (
                "You are the portfolio synthesis agent inside MarketFlux Fund OS. "
                "Return JSON only with keys: title, thesis, strategy_type, direction, tickers, entry, target, stop, "
                "time_horizon, position_sizing, confidence, why_now, invalidation, execution_checklist, risk_flags. "
                "why_now, execution_checklist, and risk_flags must be arrays of short strings."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User request: {prompt}\n"
                f"Mode: {request_payload.get('mode', 'swing')}\n"
                f"Risk profile: {request_payload.get('risk_profile', 'balanced')}\n"
                f"Capital base: {request_payload.get('capital_base', 100000.0)}\n"
                f"Allow short: {request_payload.get('allow_short', True)}\n"
                f"Live context JSON:\n{json.dumps(context, ensure_ascii=True)}\n\n"
                f"Agent outputs JSON:\n{json.dumps(agent_outputs, ensure_ascii=True)}\n\n"
                "Produce one concrete trading strategy with position structure, invalidation, and execution checklist."
            ),
        },
    ]
    strategy = await router.complete_json(messages=synthesis_messages, reasoning=True, max_tokens=1200, temperature=0.18)
    strategy.setdefault("title", "Live Fund OS Strategy")
    strategy.setdefault("direction", "neutral")
    strategy.setdefault("strategy_type", request_payload.get("mode", "swing"))
    strategy.setdefault("tickers", terminal_tickers)
    strategy["confidence"] = _safe_confidence(
        strategy.get("confidence"),
        max(45, round(sum(agent["confidence"] for agent in agent_outputs) / max(len(agent_outputs), 1))),
    )
    if isinstance(strategy.get("tickers"), str):
        strategy["tickers"] = [strategy["tickers"]]
    strategy.setdefault("thesis", "No synthesis thesis returned.")
    strategy.setdefault("entry", "Wait for confirmation in live tape.")
    strategy.setdefault("target", "Dynamic target based on volatility and catalyst path.")
    strategy.setdefault("stop", "Exit on thesis invalidation.")
    strategy.setdefault("time_horizon", request_payload.get("mode", "swing"))
    strategy.setdefault("position_sizing", "Start small and scale only if evidence improves.")
    strategy.setdefault("why_now", [])
    strategy.setdefault("execution_checklist", [])
    strategy.setdefault("risk_flags", [])
    for key in ("why_now", "execution_checklist", "risk_flags"):
        if isinstance(strategy.get(key), str):
            strategy[key] = [strategy[key]]

    markdown = _render_strategy_markdown(strategy, agent_outputs, provider_plan)
    for index in range(0, len(markdown), 120):
        yield _sse_event("token", {"content": markdown[index:index + 120]})
        await asyncio.sleep(0.02)

    user_id = user.get("user_id") if user else None
    saved = await save_strategy_run(
        db,
        user_id,
        {
            "prompt": prompt,
            "tickers": terminal_tickers,
            "mode": request_payload.get("mode", "swing"),
            "risk_profile": request_payload.get("risk_profile", "balanced"),
            "provider_plan": provider_plan,
            "strategy": strategy,
            "agent_outputs": agent_outputs,
            "context_summary": {
                "macro_regime": context["macro_regime"],
                "signals": context["signals"],
                "workspaces": context["workspaces"],
            },
        },
    )

    yield _done(
        {
            "status": "ok",
            "provider_plan": provider_plan,
            "strategy_run_id": saved["strategy_run_id"],
            "strategy": strategy,
            "agent_outputs": agent_outputs,
        }
    )
