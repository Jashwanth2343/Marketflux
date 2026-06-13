---
name: MarketFlux Project Guidelines
description: Current architecture, design language, conventions, and the PRD/doc index for MarketFlux (post lean-v1 cut, 2026-06-13)
---

# MarketFlux — Project Guidelines & Doc Index

> Rebuilt 2026-06-13 after the lean-v1 cut (PR #30). This file replaces the original `skills.md`,
> which described the retired neon-cyberpunk theme and the Mongo/`:8001` stack. It is the single entry
> point: current architecture + conventions, then an index into the feature PRDs. The live execution
> plan is [`MarketFlux/docs/roadmap-lean-v1.md`](MarketFlux/docs/roadmap-lean-v1.md).

## What MarketFlux is

An **AI-native quant research terminal** for a solo operator running like a one-person hedge fund.
AI agents research, debate, backtest, stress-test, and propose — but **every trade idea passes a human
approval gate and executes only as paper (Alpaca)**. The promise is *traceability, not latency*: each
idea carries its evidence, debate, risk verdict, and policy verdict.

**North-star loop:** ask the Copilot → get a proposal with evidence + debate + risk/policy verdicts →
approve → paper-execute → the conviction ledger records the receipt. Every workstream either
strengthens that loop or removes weight around it.

## Architecture (current)

- **Frontend** (port 3000): React 19, Tailwind CSS, Recharts, `framer-motion`, `sonner`. Build is
  **CRA + craco** (Vite migration is on the roadmap). Package manager is **npm** (yarn removed).
  Dev server must use `craco.config.dev.js`.
- **Backend** (port 8000): FastAPI (async, Python 3.11+). Strictly non-blocking — `httpx` for HTTP,
  `asyncpg` for Postgres, `motor` for legacy Mongo. Perf drop-ins: `uvloop`, `httptools`, `orjson`.
- **LLM**: **Gemini 2.5 Flash** via `google.generativeai`, driven by a manual **ReAct loop** with
  function calling (`copilot_agent.py`); parallel `asyncio` tool fan-out for read tools.
- **Data & auth**: **Supabase** is primary — Postgres (system of record, `pgvector` for embeddings)
  and Supabase Auth (backend accepts Supabase JWT). **Legacy MongoDB is being retired** (chat/copilot
  fall open when it's unreachable). **Redis** for market-data/EDGAR caching (optional).
- **Trading**: **Alpaca paper account**, server-side only — broker keys never reach the browser.
- **Compliance**: a pure, deterministic pre-trade gate (`compliance_engine.py`) returns
  PASS / WARN / BLOCK independent of the model's intent; a BLOCK is never staged or executed.

## Information architecture (nav)

`Dashboard · Intelligence · Copilot · Ledger · Backtest · Portfolio · Leaderboard`
(Leaderboard stays behind a flag until real track records exist.)

- **Dashboard** `/` — market command center (movers, heatmap, indices, earnings, news preview).
- **Intelligence** `/intelligence` — tabbed hub: Research · News · Screener · Macro · Theses
  (`?tab=` synced, legacy routes redirect in). A **terminal command line** lives in the global search
  bar (inline AI reads, ask-handoff to Copilot, nav commands).
- **Copilot** `/copilot` — conversational + autonomous paper-trading workspace (Agent · Studio ·
  Auto-Pilot · Portfolio). 35 tools wired to the signal/risk/backtest/regime/debate engines.
- **Ledger** `/ledger` — conviction ledger (decision receipts).
- **Backtest** `/backtest` — visual strategy builder + metrics + equity/drawdown + trade log.
- **Portfolio** `/portfolio` — Holdings · Risk Analytics.
- **Stock Detail** `/stock/:ticker`, **Auth** `/auth`, **Leaderboard** `/leaderboard`.

## Design language (warm-ink)

> Full spec: [`MarketFlux/docs/FRONTEND_SPEC.md`](MarketFlux/docs/FRONTEND_SPEC.md).

- **Theme:** "a financial terminal that feels like a well-made object." Calm authority, precision,
  warmth — substance over spectacle; data density with breathing room. **Dark mode default**, light
  toggle in header.
- **Color:** champagne-gold accent `#E3B85F` is the single brand accent; green/red are **price-semantic
  only**. Warm near-black canvas (dark) / warm cream paper (light).
- **Type:** DM Serif Display (headings), DM Sans (UI/body), JetBrains Mono (code/numbers, tabular figures).
- **Shape/motion:** rounded corners (`--radius: 0.75rem`); depth from borders + card steps, not
  drop-shadows; smooth purposeful transitions (~150–200ms), **no glitch effects**.
- Use design tokens, never hardcoded colors (PR #30 mapped 250+ hardcoded values to tokens for
  light-mode legibility).

## Conventions & constraints

- **Human-in-the-loop is non-negotiable** — the AI never executes; the backend re-checks policy +
  account on approve, then submits server-side. **Paper only, no real money.** Disclaimers throughout.
- **Only tool-returned numbers are real** — prompts forbid using LLM training-data prices (guards
  against the "Profit Mirage" leakage failure mode).
- **`data-testid`** on interactive elements; backend code stays async (no blocking calls).
- **Canonical backend venv** is `MarketFlux/backend/venv` (must have `alpaca-py`, etc.). A missing
  requirements dep is the usual cause of "copilot not working" with no error.
- **Tests**: `MarketFlux/backend/tests/` (incl. `test_compliance_engine.py`, `test_copilot_store_pg.py`,
  `test_copilot_parallel.py`) and frontend page tests. Integration tests skip cleanly when their
  backing service (Postgres, Alpaca) isn't reachable.
- **Local Postgres for tests**: `docker-compose.vnext.yml` spins up `pgvector/pgvector:pg16` as
  `marketflux-postgres` (volume `marketflux_postgres_data`). The running app uses hosted Supabase, so
  that container is throwaway test infra.

## PRD & doc index

| Doc | Scope | Status |
|-----|-------|--------|
| [`docs/roadmap-lean-v1.md`](MarketFlux/docs/roadmap-lean-v1.md) | Live plan: prototype → sellable product | Phase 1 done; 2–5 in progress |
| [`docs/prd-marketflux.md`](MarketFlux/docs/prd-marketflux.md) | Master product PRD | Current |
| [`docs/prd-intelligence-hub.md`](MarketFlux/docs/prd-intelligence-hub.md) | Consolidated `/intelligence` hub | ✅ Shipped |
| [`docs/prd-copilot-godtier.md`](MarketFlux/docs/prd-copilot-godtier.md) | God-tier agent: 35 tools, compliance gate, closed loop | In progress (round 4 shipped) |
| [`docs/prd-copilot-agent.md`](MarketFlux/docs/prd-copilot-agent.md) | Base conversational trading agent | ✅ Shipped, extended by god-tier |
| [`docs/prd-copilot-trading.md`](MarketFlux/docs/prd-copilot-trading.md) | Copilot cockpit (proposals/approval) | ✅ Shipped/superseded |
| [`docs/prd-backtest-lab.md`](MarketFlux/docs/prd-backtest-lab.md) | Visual backtester `/backtest` | ✅ Shipped |
| [`docs/prd-supabase-setup.md`](MarketFlux/docs/prd-supabase-setup.md) | Supabase data foundation + DSN/health | ✅ Foundation shipped; Mongo→PG migration in progress |
| [`docs/prd-langgraph-migration.md`](MarketFlux/docs/prd-langgraph-migration.md) | LangGraph orchestration | ⏸️ Not pursued (manual ReAct loop chosen) |
| [`docs/trd-marketflux.md`](MarketFlux/docs/trd-marketflux.md) | Technical requirements | Reference |
| [`docs/architecture.md`](MarketFlux/docs/architecture.md) · [`docs/backend-schema.md`](MarketFlux/docs/backend-schema.md) · [`docs/copilot-development-spec.md`](MarketFlux/docs/copilot-development-spec.md) | Deep architecture / schema / copilot internals | Reference |
