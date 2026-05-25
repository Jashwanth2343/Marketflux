# TRD: MarketFlux (Technical Requirements)

> Technical requirements & design decisions. Pairs with [`prd-marketflux.md`](./prd-marketflux.md)
> (product) and [`backend-schema.md`](./backend-schema.md) (data model). Architecture narrative and
> incident history in [`architecture.md`](./architecture.md).

## 1. System Context

```
React SPA (CRA+Craco :3000) ──HTTPS/Bearer──► FastAPI (uvicorn :8001)
                                                 ├─ MongoDB (Motor)        app data + pilot mirror
                                                 ├─ Supabase Postgres      auth/copilot/memory + vnext
                                                 │   └─ pgvector, RLS, pg_cron
                                                 ├─ Redis (optional)       cache
                                                 ├─ Supabase Auth (GoTrue) signup/login/JWT/OAuth
                                                 └─ External: yfinance, Finviz, RSS, DuckDuckGo,
                                                    Gemini/NIM/OpenRouter, Alpaca
```

## 2. Tech Stack (pinned floors from `requirements.txt` / `package.json`)

- **Backend:** FastAPI ≥0.115, uvicorn ≥0.32, Motor ≥3.6, asyncpg ≥0.29, SQLAlchemy ≥2.0,
  psycopg[binary] ≥3.2, pgvector ≥0.3.5, httpx ≥0.27, supabase ≥2.0, PyJWT ≥2.9, bcrypt ≥4.2,
  pydantic ≥2.9.
- **AI/data:** google-generativeai ≥0.8, sentence-transformers ≥3.3, numpy ≥2.1, pandas ≥2.2,
  yfinance ≥0.2.43, finvizfinance ≥0.14, feedparser ≥6.0, duckduckgo-search ≥6.3,
  alpaca-py ≥0.26, redis ≥5.2.
- **Frontend:** React (CRA + Craco), `@supabase/supabase-js` v2, axios, Recharts, Tailwind,
  shadcn/ui, Framer Motion, DOMPurify.

## 3. Architecture Decisions (ADR summary)

| ID | Decision | Rationale | Consequence |
|----|----------|-----------|-------------|
| ADR-1 | Supabase Auth (GoTrue) replaces Mongo/bcrypt/JWT | Managed auth, OAuth, JWT verification | Backend keeps 3-way `get_current_user` for transition |
| ADR-2 | Hybrid persistence (Mongo + Supabase PG) | Incremental migration; Mongo for fast-moving app data, PG for durable relational/vector | Duplication debt (must consolidate) |
| ADR-3 | pgvector for memory & RAG | Native semantic retrieval with SQL scoring | HNSW index; 1536-dim embeddings |
| ADR-4 | Server-side broker execution only | Security: keys never in browser | All Alpaca calls behind auth on backend |
| ADR-5 | Native-fetch isolation for Supabase client | Hosting platforms (Emergent) wrap `window.fetch` and drain bodies | `lib/supabase.js` uses iframe-sourced fetch |
| ADR-6 | SSE for chat/research/terminal | Token streaming UX | Streaming responses must bypass any body-buffering |
| ADR-7 | LLM provider routing (lanes) | Cost/latency/capability trade-offs | Gemini primary; NIM/OpenRouter alternates; usage metered |

## 4. Data Architecture & Consolidation Plan

Current state: three stores, two ownership models, known duplication (see
[`backend-schema.md` §0/§6](./backend-schema.md)).

**Target:** Supabase Postgres as the single system of record for durable domain data; MongoDB
retained only for high-churn/append data (news, chat, usage). 

**Consolidation sequence:**
1. Choose PG as canonical for personas/proposals/journal/drift/consent; treat Mongo `pilot_*` as
   a deprecated mirror (read-through, stop new writes).
2. Unify ownership: standardize on `auth.users(id)` UUID FKs; migrate vnext `owner_user_id TEXT`
   → `owner_user_id UUID` with FK + backfill; add **RLS** to all vnext tables.
3. Backfill `theses.legacy_saved_thesis_id` from Mongo `saved_theses`; deprecate the duplicates
   (`saved_theses`, `signal_events`, `daily_briefs`) in Mongo.
4. Collapse the three paper-trading models (`trade_proposals` vs `paper_trades` vs
   `paper_orders`/`paper_positions`) behind one execution service interface.
5. Run migrations via `supabase/migrations/*`; gate destructive steps behind a verified backup.

**Migration discipline:** every schema change is a timestamped file in `supabase/migrations/`;
`GET /api/health/db` must report `tables_ok: true` + `vector_ext: true` post-migration.

## 5. API Design

- Base prefix `/api`; sub-routers mounted by domain (see [`architecture.md` §7](./architecture.md)).
- ~154 endpoints across `server.py` (54), pilot (32), vnext (12), alpaca (12), theses (9),
  fundos (9), backtest (9), adapter (8) + webhooks/health.
- Conventions: JSON request/response (Pydantic models in `vnext/schemas.py`); auth via `Bearer`
  resolved by `get_current_user`; SSE endpoints return `text/event-stream`.
- Public reads: `/market/stock/{ticker}/rich`, `/market/chart/{ticker}`, `/news/ticker/{ticker}`.
- Error contract: HTTP status + JSON `{detail|msg|error}`; clients surface `err.message`.

## 6. Security Requirements

- **SR1** — Broker (Alpaca) and service keys are backend-only; never shipped to the client.
- **SR2** — RLS on all `schema.sql` tables (`auth.uid()`); `workflow_checkpoints` service-role only.
  **Gap:** vnext tables lack RLS → must add (see §4).
- **SR3** — `handle_new_user()` is `SECURITY DEFINER` with pinned `search_path = public` and an
  exception guard (post-incident hardening).
- **SR4** — Frontend sanitizes AI/markdown HTML with DOMPurify before render.
- **SR5** — Approval gate: server re-validates policy + account state before any order submission.
- **SR6** — Secrets via env only (`.env`, `.env.local`); never committed.
- **SR7** — Paper-only invariant enforced at DB layer (CHECK: live trades require `approved_by`).

## 7. AI / Agent Technical Design

- **Providers:** `provider_router.py` / `vnext/model_router.py` select model lanes; Gemini primary.
- **Embeddings:** sentence-transformers → `vector(1536)` (`pilot_memory`, `research_documents`).
- **Agents:** ReAct loop (`react_agent.py`, `react_tools.py`, `agent_tools.py`); multi-agent swarm
  (`multi_agent.py`, `vnext/strategy_swarm.py`, `vnext/strategy_terminal.py`).
- **State:** `workflow_checkpoints` persists LangGraph-compatible agent state; `agent_runs` /
  `agent_run_steps` trace runs.
- **Memory retrieval:** `retrieve_memory()` SQL: `importance × exp(-0.693·age_days/halflife) ×
  cosine_sim`; half-life hot 1d / warm 7d / cold 90d; `pg_cron` cleanup + warm→cold promotion.
- **Cost control:** `model_usage_events` (PG) + `ai_usage` (Mongo, TTL 1d) meter tokens/cost.

## 8. Performance & Caching

- **NFR-perf:** Stock Detail initial paint should not block on auth-gated calls — `StockDetail.js`
  uses `Promise.allSettled` so a `/watchlist` 401 cannot blank the page (post-incident fix).
- **Caching:** Redis market-data ~1h TTL, API response ~5min TTL; **all read paths must tolerate
  Redis offline** (degrade to direct fetch, no error).
- **Client cache:** chart periods cached in-memory per ticker; common periods pre-warmed.
- **DB pools:** asyncpg pool min 1 / max 5; Mongo background index builds.

## 9. Observability

- `GET /api/health/db` → `{postgres:{connected,tables_ok,vector_ext}, mongo:{connected},
  redis:{connected}}`.
- Audit trail: `audit_events` (immutable) per proposal; `activity_events` for live agent stream.
- Run tracing: `agent_runs`/`agent_run_steps`; backtests in `backtest_runs`.
- LLM metering: `model_usage_events`, `ai_usage`.

## 10. Deployment & Config

- Frontend: `npm start` (Craco) on :3000; env `REACT_APP_SUPABASE_URL`,
  `REACT_APP_SUPABASE_ANON_KEY`, `REACT_APP_BACKEND_URL`.
- Backend: `uvicorn server:app --host 0.0.0.0 --port 8001 --reload`; env `SUPABASE_URL`,
  `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, DSN chain (`SUPABASE_DB_URL` >
  `MARKETFLUX_VNEXT_DATABASE_URL` > `FUNDOS_DATABASE_URL`), `MONGO_URL`, Alpaca + LLM keys.
- Supabase project `etanlxohfiwhdwkbqyzq`; schema in `backend/supabase/schema.sql`; migrations in
  `supabase/migrations/`.
- **Repo note:** the Supabase build lives on `main` checked out in a git **worktree**; the default
  working directory is a pre-migration branch. Run/serve from the worktree.

## 11. Testing Strategy

- Backend unit/integration tests under `backend/tests/` (backtest, p0 features, pilot smoke,
  policy engine, thesis router/backfill, news upgrade) + ad-hoc `test_*.py` diagnostics.
- Frontend: `thesis-pages.test.jsx` (RTL).
- **Required gates:** `/api/health/db` green; signup→login→proposal happy path; SSE stream
  completion; Stock Detail renders with `/watchlist` failing (allSettled invariant).

## 12. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| Availability degradation | App functional with Redis offline and with stale market data |
| Auth | Supabase JWT verified server-side; graceful 401 (never blanks unrelated UI) |
| Isolation | Per-user data isolation enforced (RLS where present; app-filter elsewhere — to be RLS'd) |
| Streaming | Chat/research/terminal stream tokens via SSE without buffering |
| Security | No secrets/broker keys client-side; paper-only invariant at DB layer |
| Data freshness | Market data may be ≤15 min delayed; disclaimers shown |

## 13. Known Tech Debt & Remediation

| Item | Remediation |
|------|-------------|
| Mongo↔Postgres duplication | §4 consolidation; one system of record per domain |
| vnext tables lack RLS | Add RLS + UUID FK ownership |
| Three paper-trading models | Unify behind one execution service |
| `pilot_activity_events` no TTL (string timestamps) | Store BSON `Date`, then add TTL |
| Benign `public_slug_1` Mongo index conflict warning | Reconcile `partialFilterExpression` |
| Global `window.fetch` patch (removed) | Keep removed; rely on native-fetch isolation in `lib/supabase.js` |
| `tables_ok: false` on unmigrated projects | Apply `supabase/migrations/*`; verify health endpoint |
