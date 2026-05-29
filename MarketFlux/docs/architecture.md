# MarketFlux — System Architecture & Design

> Authoritative architecture, design rationale, and operational notes for MarketFlux.
> For the data model see [`backend-schema.md`](./backend-schema.md). For product/eng requirements
> see [`prd-marketflux.md`](./prd-marketflux.md) and [`trd-marketflux.md`](./trd-marketflux.md).

---

## 1. Product Vision

An **agentic trading cockpit** where every AI-generated idea becomes a traceable, backtestable,
approval-gated trading workflow. MarketFlux is built as an AI-native quant research terminal:
the human stays the decision-maker, while a swarm of AI agents researches, debates, stress-tests,
and proposes — never executes without an explicit human approval gate.

Design pillars:

1. **Traceability** — every proposal carries its debate transcript, signal snapshot, risk verdict,
   and policy verdict. Nothing is a black box.
2. **Approval-gated execution** — AI proposes; a human approves; the *backend* executes server-side.
   The browser never holds broker credentials.
3. **Memory** — pilots accumulate institutional knowledge (pgvector semantic memory with decay).
4. **Paper-first** — all execution flows through Alpaca paper trading. No real money path exists.

---

## 2. Navigation (Frontend Surface)

| Route | Page | Purpose |
|-------|------|---------|
| `/` | Dashboard | Market overview, portfolio summary, key alerts |
| `/intelligence` | Intelligence Hub | News, Screener, Research, Macro, Theses (sub-tabs) |
| `/copilot` | Trading Copilot | AI copilot chat, Strategy Studio, Proposals, Paper Portfolio |
| `/backtest` | Backtest Lab | Strategy DSL editor, equity curves, walk-forward, Monte Carlo |
| `/portfolio` | Portfolio & Risk | Holdings, risk analytics |
| `/leaderboard` | Leaderboard | Pilot personality rankings, public profiles |
| `/stock/:ticker` | Stock Detail | Rich fundamentals, chart, insiders, institutions, AI digest |
| `/auth` | Auth | Supabase email/password + Google OAuth |

Frontend pages (CRA + Craco): `Dashboard`, `Intelligence`, `Copilot`, `Backtest`, `Portfolio`,
`PortfolioRisk`, `RiskConsole`, `Theses`, `ThesisNew`, `ThesisWorkspace`, `ThesisTradeLab`,
`AIScreener`, `NewsFeed`, `MacroDashboard`, `ResearchCenter`, `PilotLeaderboard`,
`PilotPublicProfile`, `StockDetail`, `Auth`.

---

## 3. Service Architecture

```
                     ┌─────────────────────────────────────────────┐
   Browser           │  React SPA (CRA + Craco, port 3000)          │
   (user)            │  - Supabase JS client (auth)                 │
                     │  - axios `api` instance (REST, XHR)          │
                     │  - fetch (SSE streams: chat, research, swarm)│
                     └───────────────┬─────────────────────────────┘
                                     │  HTTPS / Bearer JWT
                                     v
                     ┌─────────────────────────────────────────────┐
                     │  FastAPI Backend (uvicorn, port 8000)        │
                     │  prefix /api  + sub-routers (see §7)         │
                     └───┬───────┬───────┬───────┬───────┬──────────┘
                         │       │       │       │       │
          ┌──────────────┘       │       │       │       └───────────────┐
          v                      v       v       v                       v
   ┌─────────────┐      ┌──────────────┐ │  ┌──────────┐         ┌───────────────┐
   │ Legacy Mongo│      │  Supabase    │ │  │  Redis   │         │  External APIs│
   │ fallback /  │      │  Postgres    │ │  │ (cache,  │         │  - yfinance   │
   │ mirrors     │      │  + pgvector  │ │  │  optional)│        │  - Gemini LLM │
   └─────────────┘      └──────────────┘ │  └──────────┘         │  - Alpaca     │
                                          │                       │  - Finviz     │
                        ┌─────────────────┘                       │  - DuckDuckGo │
                        v                                         │  - RSS/feeds  │
                ┌──────────────┐                                  └───────────────┘
                │ Supabase Auth│  (GoTrue: signup/login/JWT/OAuth)
                └──────────────┘
```

Three runtime tiers: **React SPA** → **FastAPI** → **(Supabase Postgres/Auth | Redis | external data/LLM/broker)**, with legacy Mongo compatibility paths still present in code.

---

## 4. Data Layer

MarketFlux is **Supabase-first**: Supabase Auth and Supabase Postgres/pgvector are the primary durable data layer. The codebase still contains legacy Mongo mirrors/fallbacks from the pre-Supabase era, so references to Mongo should be treated as compatibility debt unless a feature explicitly still depends on that path.

| Store | Driver | Owns | Notes |
|-------|--------|------|-------|
| **Supabase Postgres** | asyncpg / supabase-py | Auth (`auth.users`), `profiles`, copilot domain (`personalities`, `trade_proposals`, audit/activity), `pilot_memory` (pgvector), journal/drift/snapshots, agent checkpoints, vnext domain (theses, paper trading, policies, evidence, memos, backtests) | Primary durable store; relational/vector data; RLS where configured |
| **Legacy MongoDB** | Motor (async) | Older mirrors/fallbacks for news, chat history, usage, watchlists, portfolios, legacy users, `pilot_*`, research/strategy runs | Compatibility only; do not use for new domains |
| **Redis** | redis-py | Market-data cache (~1h TTL), API response cache (~5min TTL), session/usage cache | Optional — app degrades gracefully when offline (no caching) |

### 4.1 Known duplication (migration debt)

The same domain concept currently lives in two places. This is the single biggest source of
data-model confusion and should be removed or consolidated behind Supabase (see TRD §"Data Consolidation"):

| Concept | MongoDB | Supabase Postgres |
|---------|---------|-------------------|
| AI personas | `pilot_personalities` | `personalities` |
| Trade proposals | `pilot_trade_proposals` | `trade_proposals` |
| Audit / activity | `pilot_audit_events`, `pilot_activity_events` | `audit_events`, `activity_events` |
| Consent | `pilot_user_consent` | `user_consent` |
| Journal / drift | `pilot_journal`, `pilot_drift_flags` | `journal_entries`, `drift_flags` |
| Saved theses | `saved_theses` | `saved_theses` (+ richer `theses`) |
| Signals / briefs | `signal_events`, `daily_briefs` | `signal_events`, `daily_briefs` |

> See [`backend-schema.md`](./backend-schema.md) for the full field-level model of every store.

---

## 5. Authentication Architecture

Auth was migrated from **MongoDB + bcrypt + custom JWT** to **Supabase Auth (GoTrue)**. The backend
supports three credential types, tried in priority order inside `get_current_user(request)`:

1. **Supabase JWT** (primary) — verified via `get_service_client().auth.get_user(token)`. On first
   sight, the user is auto-provisioned into MongoDB (`users` collection) for app-data joins.
2. **Legacy JWT** (transitional) — the old custom-signed tokens, still accepted.
3. **Session cookie** (fallback) — `withCredentials` cookie-based session.

```
Frontend                         Backend                       Supabase
   │ signInWithPassword/signUp      │                              │
   ├───────────────────────────────────────────────────────────► GoTrue /auth/v1/*
   │ ◄─── access_token (JWT) ───────────────────────────────────┤
   │ axios.defaults.Authorization = Bearer <jwt>                  │
   │ GET /api/... (Bearer)          │                             │
   ├──────────────────────────────► get_current_user()            │
   │                                ├── verify Supabase JWT ─────► auth.get_user(token)
   │                                ├── (else) legacy JWT          │
   │                                └── (else) session cookie      │
```

Frontend auth state lives in `contexts/AuthContext.js` (Supabase session + `onAuthStateChange`
listener). The Supabase client is a **single singleton** in `lib/supabase.js`; both `AuthContext`
and `AuthCallback` import it. See §10 for the auth-fetch hardening that this design required.

---

## 6. AI & Agent Architecture

### 6.1 Provider routing
LLM calls flow through a provider router (`provider_router.py` / `vnext/model_router.py`) that
selects a model "lane" per task: **Google Gemini** (primary), with **Nvidia NIM** and **OpenRouter**
as alternates. Model usage is metered (`model_usage_events`, Mongo `ai_usage`).

### 6.2 Strategy Swarm (5 agents + synthesis)
```
User Prompt + Macro Regime Context
        │  (parallel fan-out)
        ├── Bull Case Agent
        ├── Bear Case Agent
        ├── Value Agent
        ├── Momentum Agent
        └── Risk Officer
        │  (synthesis via reasoning model)
        v
Structured Verdict: VERDICT / CONVICTION / ENTRY / TARGET / STOP / SIZE / THESIS
```
Implemented across `multi_agent.py`, `vnext/strategy_swarm.py`, `vnext/strategy_terminal.py`.
A separate **ReAct agent** (`react_agent.py` + `react_tools.py` + `agent_tools.py`) handles
tool-using research loops; runs are traced into `agent_runs` / `agent_run_steps`.

### 6.3 Pilot memory (pgvector)
`pilot_memory` stores layered institutional knowledge (`hot`/`warm`/`cold`) with 1536-dim
embeddings. Retrieval (`retrieve_memory` SQL function) combines **importance × time-decay × cosine
similarity**, where decay half-life depends on layer (hot=1d, warm=7d, cold=90d). `pg_cron`
functions `cleanup_expired_memory` and `promote_warm_to_cold` maintain the store.

### 6.4 Trade lifecycle (the conviction loop)
```
Signal/Research → Thesis → Backtest → Agent Debate → Policy Check
   → Human Approval → Paper Execution (Alpaca) → Monitoring → Journal/Drift
```

### 6.5 Copilot approval flow
1. AI generates a trade proposal (backend).
2. Frontend renders it with approve/reject controls.
3. On approve, backend **re-checks** policy + live account state.
4. Backend submits the Alpaca order **server-side** (browser never holds keys).
5. Audit trail persisted (`audit_events`).

---

## 7. API Surface (~154 endpoints)

| Prefix | Router (file) | Domain | ~Routes |
|--------|---------------|--------|---------|
| `/api` | `server.py` (`api_router`) | Auth, market data, news, sentiment, AI chat/screen, portfolio, watchlist, streams, research, macro, risk, earnings | 54 |
| `/api/pilot` | `vnext/pilot_router.py` | Personalities, proposals, sweep, activity, journal, drift, memory, leaderboard, public profiles | 32 |
| `/api/vnext` | `vnext/router.py` | Daily briefing, signals feed, command center, ticker research, watchlist board, portfolio diagnostics, MiroFish, strategy terminal stream | 12 |
| `/api/alpaca` | `vnext/alpaca_router.py` | Account, orders, positions, liquidate, portfolio history, assets | 12 |
| `/api` (theses) | `vnext/thesis_router.py` | Theses CRUD, revisions, memos, policies, paper-trades | 9 |
| `/api/fundos` | `vnext/fundos_router.py` | Fund-OS overview, search, strategy queue, paper portfolio, audit feed, terminal sessions | 9 |
| `/api/backtest` | `backtest/router.py` | Validate, run, walk-forward, benchmark, Monte Carlo, AI critique/parse | 9 |
| `/api/vnext-adapter` | `vnext/adapter_router.py` | Live-data adapter envelopes (regime inputs, etc.) | 8 |
| `/api/webhooks/alpaca` | `vnext/alpaca_webhooks.py` | Broker fill/trade webhooks | — |
| `/api/health/*` | inline | DB/Mongo/Redis health | — |

Notable public/unauthenticated endpoints: `/api/market/stock/{ticker}/rich`,
`/api/market/chart/{ticker}`, `/api/news/ticker/{ticker}`. Watchlist and all
`/pilot`, `/vnext`, `/alpaca`, theses, and fundos routes require auth.

---

## 8. Request Lifecycle (Stock Detail example)

`StockDetail.js` issues four parallel calls via `Promise.allSettled` (so one auth failure can't
blank the page):

```
GET /api/market/stock/{ticker}/rich   (no auth)  → fundamentals, insiders, institutions
GET /api/news/ticker/{ticker}         (no auth)  → news articles
GET /api/watchlist                    (auth)     → is-watched flag (may 401 pre-session)
GET /api/market/chart/{ticker}        (no auth)  → OHLCV series (cached client-side)
+ GET /api/stock-digest/{ticker}      (separate) → AI digest (own loader)
```

Market data is sourced from **yfinance** (+ Finviz for some fundamentals), cached in Redis when
available. The AI digest is generated by the LLM lane and cached.

---

## 9. Deployment, Config & Environments

- **Frontend**: CRA + Craco dev server on `:3000`. Env via `frontend/.env.local`
  (`REACT_APP_SUPABASE_URL`, `REACT_APP_SUPABASE_ANON_KEY`, `REACT_APP_BACKEND_URL`).
  Force-dark-mode bootstrap in `index.js`.
- **Backend**: `uvicorn server:app --host 0.0.0.0 --port 8000 --reload`. Env via `backend/.env`
  (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`/
  `MARKETFLUX_VNEXT_DATABASE_URL`/`FUNDOS_DATABASE_URL`, Alpaca keys, LLM keys).
- **Supabase**: project `etanlxohfiwhdwkbqyzq`. Postgres DSN resolution order:
  `SUPABASE_DB_URL` > `MARKETFLUX_VNEXT_DATABASE_URL` > `FUNDOS_DATABASE_URL`. asyncpg pool
  (min 1 / max 5). Schema in `backend/supabase/schema.sql`; migrations in `supabase/migrations/`.
- **Health**: `GET /api/health/db` → `{ postgres:{connected,tables_ok,vector_ext}, mongo, redis }`.
- **Tooling note**: `main` (with the Supabase migration) is checked out in a git **worktree**;
  the primary working directory is on a different branch that predates the migration. Run the
  Supabase build from the worktree copy.

### Tech stack
- **Frontend**: React (CRA + Craco), shadcn/ui, Tailwind CSS, Recharts, Framer Motion, axios,
  `@supabase/supabase-js`, DOMPurify.
- **Backend**: FastAPI, uvicorn, asyncpg + SQLAlchemy + psycopg, pgvector,
  httpx, supabase-py, PyJWT, bcrypt.
- **AI / data**: Google Gemini (`google-generativeai`), sentence-transformers (embeddings),
  yfinance, finvizfinance, feedparser (RSS), duckduckgo-search, Alpaca (`alpaca-py`).
- **Infra**: Supabase (Postgres + pgvector + GoTrue Auth), Redis, optional legacy Mongo compatibility.

---

## 10. Incident Log — "the mess we went through"

Real, dated-by-sequence account of the MongoDB→Supabase migration fallout and how each issue was
resolved. Kept here deliberately so the next engineer doesn't re-walk these dead ends.

### 10.1 Auth migration scope creep
The original plan (`prd-supabase-setup.md`) explicitly kept **MongoDB auth** ("Out of Scope:
Supabase Auth"). A later change migrated auth to **Supabase GoTrue** anyway. The backend grew a
three-way `get_current_user()` (Supabase JWT → legacy JWT → session) to avoid breaking existing
sessions. Lesson: the dual-write/dual-auth state is the root of most of the confusion below.

### 10.2 Missing `supabase` Python package
`vnext/supabase_client.py` lazily `import`s `from supabase import create_client`, but `supabase`
was absent from `requirements.txt`. Auth verification failed at runtime for every user. **Fix:**
added `supabase>=2.0.0` and installed into the venv.

### 10.3 Crash on missing env vars
`lib/supabase.js` called `createClient(undefined, undefined)` when env vars were absent, crashing
at import before the login page could render. **Fix:** explicit guard that throws an actionable
"Supabase is not configured…" message; documented `.env.local` requirements.

### 10.4 "Failed to execute 'json' on 'Response': body stream already read" (the epic)
This single error consumed the most time. The investigation path:
- **Hypothesis 1 (wrong):** supabase-js double-reads the body. Added a `safeFetch` that buffered the
  body and returned `new Response(body, …)`. Error persisted — because `new Response(string)` still
  creates a *single-read* `ReadableStream`.
- **Hypothesis 2 (wrong):** override `.json()/.text()/.clone()` on the re-wrapped Response so reads
  are re-entrant. Verified correct in Node **and** in a real browser engine with native fetch — yet
  the error *still* reproduced in the app.
- **Root cause (right):** the **Emergent platform injects `emergent-main.js`, which wraps
  `window.fetch` and calls `response.text()` on every non-OK response** (to report it upstream),
  draining the body *before* supabase-js — or any of our patches — could read it. Our global
  `index.js` fetch patch was wrapping Emergent's wrapper and inheriting an already-drained body, so
  it could never recover. A Claude preview tool's network monitor exhibited the identical behavior,
  which briefly produced a misleading repro.
- **Fix:** route all Supabase auth traffic through a **pristine native `fetch` obtained from a
  same-origin iframe** (Emergent only patches the top window). `lib/supabase.js#getNativeFetch`
  bypasses the wrapper entirely; the global `index.js` patch was removed as actively harmful.
  Verified in-browser: login → "Invalid login credentials", signup → real server error, no
  body-stream error, body readable twice.

> **Design rule that fell out of this:** never assume `window.fetch` is native. Hosting/preview
> platforms wrap it and may consume bodies. For libraries that need to read response bodies, use a
> fetch source you control.

### 10.5 Broken stock data pipeline
After the migration, Stock Detail showed only the chart + AI digest; fundamentals/insiders/
institutions were blank. **Cause:** `StockDetail.js` used `Promise.all` across four calls including
the auth-required `/watchlist`; a 401 there rejected the whole batch and wiped the (un-authed,
working) stock + news data. **Fix:** switched to `Promise.allSettled` and handled each result
independently.

### 10.6 Signup 500 — "Database error saving new user"
The body-stream error had been *masking* this. The `on_auth_user_created` trigger calls
`handle_new_user()`, which did `INSERT INTO profiles` **unqualified**. GoTrue fires the trigger as
role `supabase_auth_admin`, whose `search_path` excludes `public`, so `profiles` couldn't be
resolved → the insert raised → the whole `auth.users` insert rolled back → HTTP 500. **Fix**
(`supabase/migrations/20260523000001_fix_handle_new_user_signup.sql`): schema-qualify
`public.profiles`, `SET search_path = public`, `ON CONFLICT DO NOTHING`, and an `EXCEPTION WHEN
OTHERS` guard so profile creation can never again block signup; defensive grants to
`supabase_auth_admin`. After applying, signup + login succeeded.

### 10.7 Still-open items
- `tables_ok: false` historically — vnext tables (`theses`, `strategy_proposals`, `paper_trades`)
  may be unmigrated on a given project; run `supabase/migrations/*`.
- Legacy Mongo↔Supabase **duplication** (§4.1) remains in some paths; Supabase should be the system of record.
- Redis frequently offline in dev → no cache layer (non-fatal).

---

## 11. Cross-Cutting Concerns

- **Security:** broker keys live server-side only; RLS enforces per-user isolation on all Supabase
  tables (`auth.uid()` policies); `workflow_checkpoints` is service-role only.
- **Streaming:** chat, research memo, and strategy-terminal endpoints use SSE
  (`text/event-stream`); these must **not** be buffered by any fetch wrapper.
- **Caching:** Redis is best-effort; all read paths must tolerate a cache miss/offline Redis.
- **Observability:** `agent_runs`/`agent_run_steps` trace agent loops; `audit_events` is an
  immutable proposal trail; `model_usage_events` + `ai_usage` meter LLM spend.
