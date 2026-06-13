# PRD: MarketFlux (Product-Level)

> Master product requirements. Feature-level PRDs (`prd-copilot-agent.md`, `prd-copilot-godtier.md`,
> `prd-copilot-trading.md`, `prd-backtest-lab.md`, `prd-intelligence-hub.md`, `prd-supabase-setup.md`,
> `prd-langgraph-migration.md`) drill into individual surfaces. Technical requirements live in
> [`trd-marketflux.md`](./trd-marketflux.md); the live plan is [`roadmap-lean-v1.md`](./roadmap-lean-v1.md).

> **Status — updated 2026-06-13 (post-PR #30):** The product is mid **lean-v1 cut** (roadmap Phase 1
> done): dead UI/deps removed, npm standardized, IA trimmed to **Dashboard · Intelligence · Copilot ·
> Ledger · Backtest · Portfolio · Leaderboard**, and the UI reskinned to the **warm-ink** theme
> (see [`FRONTEND_SPEC.md`](./FRONTEND_SPEC.md)). The Copilot reached "god-tier" (**35 tools** + a
> deterministic `compliance_engine` gate, [`prd-copilot-godtier.md`](prd-copilot-godtier.md)), gained a
> **golden-query eval harness** (roadmap Phase 3 started), a **terminal command line** in the search bar,
> and had its **trust path migrated to Supabase Postgres**. Stack today: React/Tailwind/Recharts (CRA+craco)
> · FastAPI :8000 · **Gemini 2.5 Flash** · Supabase Postgres (+ legacy Mongo being retired) · Alpaca paper.

## 1. Vision

MarketFlux is an **AI-native quant research terminal** for an individual operating like a one-person
hedge fund. AI agents do the heavy lifting — research, debate, backtest, stress-test, propose — but
**every trade idea passes through a human approval gate and executes only as paper (Alpaca)**. The
product's promise is *traceability*: no idea is a black box; each carries its evidence, debate, risk
verdict, and policy verdict.

## 2. Target User & Personas

- **The Operator (primary)** — a technically literate solo investor/quant building conviction-driven
  strategies with limited compute. Wants leverage from AI without surrendering judgment.
- **The Pilot (AI persona)** — a configurable AI portfolio manager (mandate, universe, risk policy,
  cadence) that proposes trades and accrues memory. Multiple pilots can run and be compared.
- **The Reviewer (future/social)** — viewers of public pilot leaderboards and profiles.

## 3. Problem Statement

Retail/solo quant tooling forces a choice between (a) opaque "AI stock picker" black boxes and
(b) raw data terminals with no reasoning layer. Neither gives a **traceable, backtestable,
approval-gated** workflow from idea → evidence → backtest → proposal → (paper) execution → review.
MarketFlux is that missing connective tissue.

## 4. Goals & Non-Goals

### Goals
- G1 — Turn any AI idea into a traceable artifact (thesis/proposal with evidence + debate + verdicts).
- G2 — Keep a human in the loop: nothing executes without explicit approval.
- G3 — Make ideas testable before commitment (backtest, walk-forward, Monte Carlo).
- G4 — Accumulate institutional memory per pilot (semantic, decaying).
- G5 — Paper-trade end to end via a real broker API (Alpaca), server-side only.

### Non-Goals
- N1 — **No real-money execution.** Paper only; no live brokerage money path.
- N2 — Not investment advice (explicit disclaimers throughout).
- N3 — Not a social trading network (leaderboards are read-only surfacing, not copy-trading).
- N4 — Not a market-data vendor (data is sourced from yfinance/Finviz/feeds, may be delayed).

## 5. Feature Areas (current product)

| # | Area | What it does | Primary surface |
|---|------|--------------|-----------------|
| F1 | **Market Intelligence** | Overview, movers, heatmap, rich stock detail (fundamentals, insiders, institutions, analyst targets), AI stock digest | Dashboard, Stock Detail |
| F2 | **Intelligence Hub** | News feed, AI screener, research signals, macro regime dashboard, theses | `/intelligence` |
| F3 | **Trading Copilot** | Chat copilot (SSE), strategy studio, AI trade proposals with debate transcripts, paper portfolio | `/copilot` |
| F4 | **Pilots** | Configurable AI personas: mandate, universe, risk policy, cadence; propose/approve/reject; journal & drift; semantic memory | `/copilot`, `/leaderboard` |
| F5 | **Thesis Engine** | Structured theses (claim, why-now, invalidation), revisions, evidence blocks, AI memos, policy rules | `/intelligence`, `/copilot` |
| F6 | **Backtest Lab** | Strategy DSL editor, run/validate, walk-forward, Monte Carlo, benchmark, AI critique/parse | `/backtest` |
| F7 | **Risk & Portfolio** | Holdings, risk analytics, portfolio diagnostics (concentration, macro sensitivity) | `/portfolio` |
| F8 | **Paper Execution** | Approval-gated Alpaca paper orders/positions; audit trail | backend `/api/alpaca`, copilot |
| F9 | **Strategy Swarm** | 5-agent debate (bull/bear/value/momentum/risk) + synthesized verdict | strategy terminal |

## 6. Key User Journeys

1. **Idea → Proposal → Approve → Paper fill** (the conviction loop):
   research/signal → thesis → backtest → agent debate → policy check → **human approve** →
   server-side Alpaca paper order → monitoring → journal/drift review.
2. **Research a ticker:** search → Stock Detail (rich fundamentals + chart + insiders + institutions
   + AI digest + related news).
3. **Run & compare pilots:** create pilot (mandate/universe/risk) → it proposes on cadence →
   approve/reject → review journal, drift flags, and leaderboard standing.
4. **Backtest a strategy:** author/parse DSL → validate → run → walk-forward + Monte Carlo →
   AI critique → save run.

## 7. Functional Requirements (selected)

- FR1 — Auth via Supabase (email/password + Google OAuth); session persists; backend accepts
  Supabase JWT (primary), legacy JWT, and session cookie.
- FR2 — Public, unauthenticated read of market data (`/market/stock/{ticker}/rich`, chart, ticker
  news) so research works pre-login; auth-gated personalization (watchlist, pilots, theses).
- FR3 — Every trade proposal stores: thesis, conviction, invalidation, debate transcript, signal
  snapshot, risk verdict, policy verdict. Audit events are immutable.
- FR4 — Approval gate: AI never executes; backend re-checks policy + account state on approve, then
  submits the order server-side. Broker keys never reach the browser.
- FR5 — Pilot memory: store/retrieve layered (hot/warm/cold) semantic notes/lessons/regimes with
  decay-weighted relevance.
- FR6 — Backtesting: validate DSL, run, walk-forward, Monte Carlo, benchmark; persist results.
- FR7 — Streaming UX for chat, research memo, and strategy terminal (SSE).
- FR8 — Graceful degradation when Redis cache or Supabase vnext tables are unavailable.

## 8. Success Metrics

- Activation: % of new users who complete signup → first thesis or first pilot proposal.
- Conviction-loop completion: # ideas that traverse research → proposal → approval → paper fill.
- Trust/traceability: % of proposals reviewed with their debate/evidence expanded.
- Pilot engagement: active pilots per user; journal entries; drift flags resolved.
- Reliability: auth success rate; `/health/db` green rate; SSE stream completion rate.

## 9. Roadmap

| Phase | Item | Status (as-built signal) |
|-------|------|--------------------------|
| Done (PR #30) | **Lean-v1 cut** (dead UI/28 deps removed, npm), **warm-ink reskin**, **god-tier copilot** (35 tools + compliance gate), **eval harness**, **terminal command line**, **copilot trust path → Supabase Postgres** | Shipped on `chore/lean-v1-cleanup` |
| Now | Auth (Supabase), market intelligence, copilot, theses, paper trading, **backtester**, **strategy swarm** | Implemented (backtest router, swarm agents, pilot subsystem present) |
| Now | **Mongo → Supabase Postgres** migration; retire legacy Mongo fallback | In progress (trust path migrated; remaining collections pending) |
| Next | **Conviction loop** end-to-end polish (signal→thesis→backtest→debate→approve→fill→journal) | Partially wired |
| Next | **Trade journal** (per-pilot reflections + drift) maturation | Tables + endpoints exist (`journal_entries`, drift) |
| Later | **SEC filing scanner** (Form 4 / filings ingestion → evidence) | Insider data present; dedicated scanner TBD |
| Later | **Earnings whisper** (earnings intel + surprise signals) | `earnings_intel.py` present; productize |
| Later | **Strategy swarm** expansion (more agents, tournaments, leaderboard tie-in) | Base swarm shipped |

## 10. Scope Boundaries

**In scope:** paper trading, AI research/debate, backtesting, theses, pilots, risk/portfolio
analytics, news/macro intelligence.
**Out of scope:** real-money trading, custody, payments/billing, options chains execution,
multi-user orgs/teams, mobile-native apps.

## 11. Key Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Data-model duplication (Mongo↔Postgres) causing inconsistency | Consolidation plan in TRD; pick one system of record per domain |
| vnext tables lack RLS (isolation depends on app filtering) | Add RLS or enforce `owner_user_id` in a single data-access layer |
| LLM cost/latency | Provider routing + model lanes + usage metering; cache digests |
| Market-data accuracy/delays | Explicit "delayed up to 15 min / not advice" disclaimers |
| Hosting platforms wrapping `window.fetch` (broke auth once) | Native-fetch isolation for Supabase; documented in architecture §10 |
| Compute constraints (solo, limited GPU) | Embeddings + small models where possible; cache aggressively |
