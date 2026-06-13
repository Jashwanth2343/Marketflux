# PRD: LangGraph Migration

> **Status — updated 2026-06-13 (post-PR #30):** ⏸️ **NOT PURSUED — superseded by a simpler design.**
> The copilot did **not** migrate to LangGraph. Instead the architecture settled on a **manual ReAct
> loop over Gemini function calling** (`copilot_agent.py`) plus **parallel `asyncio` tool fan-out**
> (`multi_agent.py`; PR #30's `8a39280` extended this to read-tool fan-out). The human-in-the-loop
> approval gate is enforced **deterministically** by `compliance_engine.py` (PASS/WARN/BLOCK) rather
> than a graph `interrupt()`. The observability intent survives via the audit tables
> (`copilot_debates`, `copilot_reviews`). Kept for historical context; acceptance criteria below
> intentionally remain unchecked. Revisit only if graph-based checkpointing becomes a real need.

## Problem Statement
The current multi-agent orchestration uses raw `asyncio.gather()` which works but lacks state management, checkpointing, traceability, and the human-in-the-loop primitives needed for the approval-gated trading copilot.

## Scope

### Phase E (In Scope — First)
- Migrate strategy swarm from asyncio.gather to LangGraph StateGraph
- Preserve existing `run_swarm()` function signature
- Preserve SSE streaming to frontend
- Add agent_runs + agent_run_steps observability tables
- Define LangGraph tools wrapping existing capabilities

### Phase F (Deferred — Later)
- Migrate pilot proposal workflow to LangGraph
- LangGraph `interrupt()` for human approval checkpoint
- Full scan → debate → synthesize → policy → approve → execute graph
- Position monitoring graph

## Agent Graph: Strategy Swarm

```
                    ┌─────────────────┐
                    │ enrich_context   │
                    │ (macro regime,   │
                    │  ticker data)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────┴────┐  ┌─────┴─────┐  ┌────┴────┐
         │ Bull    │  │ Value     │  │ Risk    │
         │ Agent   │  │ Agent     │  │ Officer │
         └────┬────┘  └─────┬─────┘  └────┬────┘
              │    ┌────┴────┐    │
              │    │ Bear    │    │
              │    │ Agent   │    │
              │    └────┬────┘    │
              │    ┌────┴────┐    │
              │    │Momentum │    │
              │    │ Agent   │    │
              │    └────┬────┘    │
              └──────────┼────────┘
                         │
                ┌────────┴────────┐
                │   synthesize    │
                │ (reasoning LLM) │
                └────────┬────────┘
                         │
                ┌────────┴────────┐
                │ evaluate_policy │
                └─────────────────┘
```

## LangGraph Tools

| Tool | Wraps | Purpose |
|------|-------|---------|
| `get_stock_info` | market_data.py | Current price, technicals, fundamentals |
| `get_positions` | alpaca_client | Current portfolio positions |
| `submit_order` | alpaca_client | Execute paper trade (Phase F only) |
| `evaluate_policy` | policy_engine | Check trade against risk rules |
| `get_macro_regime` | engines.py | Current macro regime classification |
| `get_evidence` | evidence_service | Thesis evidence blocks |

## Observability Tables

```sql
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    graph_name TEXT NOT NULL,
    user_id TEXT NOT NULL,
    input_payload JSONB NOT NULL,
    output_payload JSONB,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE agent_run_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES agent_runs(id),
    node_name TEXT NOT NULL,
    input_payload JSONB NOT NULL,
    output_payload JSONB,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Files to Create/Modify

| File | Action |
|------|--------|
| `backend/vnext/graphs/__init__.py` | Create |
| `backend/vnext/graphs/state.py` | Create (~30 lines) |
| `backend/vnext/graphs/trading_swarm_graph.py` | Create (~200 lines) |
| `backend/vnext/graphs/tools.py` | Create (~100 lines) |
| `backend/vnext/strategy_swarm.py` | Modify (use graph internally) |
| `supabase/migrations/20260515000002_agent_runs.sql` | Create |

## Dependencies
- `langgraph>=0.2`
- `langchain-core>=0.3`

## Acceptance Criteria
- [ ] Strategy terminal produces same quality output as before
- [ ] SSE streaming still works for real-time agent debate
- [ ] `run_swarm()` signature unchanged (callers unaffected)
- [ ] Agent runs persisted to agent_runs table
- [ ] Step-level traces in agent_run_steps
- [ ] No regression in response latency (within 10%)
