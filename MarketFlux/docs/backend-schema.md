# MarketFlux — Backend Data Schema

> Supabase is the primary data/auth layer. This document also records legacy Mongo mirrors/fallbacks that still exist in code so they can be retired deliberately. Companion to [`architecture.md`](./architecture.md). Sources of truth: `backend/supabase/schema.sql` (auth/copilot/memory), `backend/sql/vnext_pgvector_schema.sql` + `supabase/migrations/*` (vnext domain), and `backend/database.py` for legacy Mongo indexes.

---

## 0. Store Map & Ownership Models

MarketFlux is Supabase-first. Critically, the two Postgres domains still use **different ownership conventions** — a key inconsistency to be aware of:

| Domain | Store | Ownership column | Isolation mechanism |
|--------|-------|------------------|---------------------|
| Auth / Copilot / Memory | Supabase PG (`schema.sql`) | `user_id UUID` → `auth.users(id)` | **RLS** via `auth.uid()` |
| vnext (theses, paper trading, strategy) | Supabase PG (`vnext_pgvector_schema.sql`) | `owner_user_id TEXT` (no FK) | **App-layer filtering** (no RLS) |
| Legacy app mirrors/fallbacks | MongoDB | `user_id` (string) | App-layer filtering |

> ⚠️ **Two ownership models + no RLS on vnext tables** is the most important schema risk. See
> [`architecture.md` §4.1](./architecture.md) for the duplication map and the TRD for the
> consolidation plan.

---

## 1. Legacy MongoDB Collections

Async access via Motor remains in some compatibility paths. Indexes are from `backend/database.py::initialize_indexes`. Documents are schemaless; the columns below are fields older app paths read/write in practice. Do not use these collections for new product work.

### Core app collections

| Collection | Key fields | Indexes | Purpose |
|-----------|-----------|---------|---------|
| `users` | `user_id`, `email`, `name`, `provider` | unique `email` | Legacy auth + auto-provisioned mirror of Supabase users |
| `news_articles` | `url`, `ticker`, `title`, `summary`, `published_date`, `tickers[]`, `is_duplicate` | `(ticker, published_date desc)`, unique `url`, TTL `published_date` (7d), `is_duplicate` | Aggregated news (RSS + scrapers) |
| `chat_messages` | `user_id`, `role`, `content`, `created_at` | `(user_id, created_at desc)` | Copilot chat history |
| `watchlists` | `user_id`, `tickers[]` | `user_id` | Per-user watchlist |
| `portfolios` | `user_id`, holdings | `user_id` | Manual/imported portfolio |
| `ai_usage` | `user_id`, `date`, token/cost counters | `(user_id, date)`, TTL `date` (1d) | LLM usage metering / rate limits |
| `streams` | `user_id` | `user_id` | Saved live "streams" |
| `daily_briefs` | `date`, `user_id` | `(date desc, user_id)` | Daily market brief (Mongo copy) |
| `signal_events` | `created_at` | `created_at` | Research signal events (Mongo copy) |
| `saved_theses` | `owner_user_id`, `ticker`, `updated_at` | `(owner_user_id, ticker, updated_at desc)` | Saved theses (Mongo copy) |
| `research_runs` | `owner_user_id`, `created_at` | `(owner_user_id, created_at desc)` | ReAct/research run history (Mongo copy) |
| `strategy_runs` | `owner_user_id`, `created_at` | `(owner_user_id, created_at desc)` | Strategy terminal run history |

### Pilot subsystem (legacy MongoDB mirror)

These mirror the Supabase copilot tables (see §2). Supabase should be treated as canonical.

| Collection | Key fields | Indexes |
|-----------|-----------|---------|
| `pilot_personalities` | `id`, `user_id`, `public_slug`, `public_visibility` | unique `id`, `user_id`, unique-sparse `public_slug`, `public_visibility` |
| `pilot_trade_proposals` | `id`, `user_id`, `status`, `created_at` | unique `id`, `(user_id, status, created_at desc)` |
| `pilot_audit_events` | `proposal_id`, `timestamp` | `(proposal_id, timestamp)` |
| `pilot_activity_events` | `personality_id`, `timestamp` | `(personality_id, timestamp desc)` — *no TTL: timestamps stored as strings* |
| `pilot_user_consent` | `user_id` | unique `user_id` |
| `pilot_journal` | `id`, `personality_id`, `date` | unique `id`, `(personality_id, date desc)` |
| `pilot_drift_flags` | `id`, `personality_id`, `ticker`, `severity` | unique `id`, `(personality_id, ticker)`, `severity` |

> Note: a deliberate decision was made **not** to TTL `pilot_activity_events.timestamp` because it
> is stored as an ISO string, and MongoDB TTL indexes only expire BSON `Date` values.

---

## 2. Supabase Postgres — Auth, Copilot & Memory (`schema.sql`)

Extensions: `vector` (pgvector), `pg_cron`, `moddatetime`. **RLS enabled on every table.**

### `profiles` — extends `auth.users`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | FK → `auth.users(id)` ON DELETE CASCADE |
| `email`, `display_name`, `avatar_url` | TEXT | |
| `alpaca_account_id` | TEXT | broker mode: per-user sub-account |
| `alpaca_mode` | TEXT | default `'trading'` |
| `preferences` | JSONB | default `{}` |
| `created_at`, `updated_at` | TIMESTAMPTZ | `updated_at` via `moddatetime` trigger |

Auto-created on signup by `handle_new_user()` (see §5). **RLS:** `id = auth.uid()`.

### `user_consent` — pilot paper-trading agreement
`user_id` (UNIQUE FK), `accept_paper_only`, `accept_not_advice`, `accept_audit_logging` (bool),
`kill_phrase` TEXT, `granted_at`. **RLS:** `user_id = auth.uid()`.

### `personalities` — AI portfolio-manager personas
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID | FK → `auth.users(id)`; null for seeds |
| `is_seed`, `public`, `paused` | BOOL | |
| `slug` | TEXT UNIQUE | |
| `name`, `mandate` | TEXT NOT NULL | |
| `universe` | TEXT[] | tradable tickers |
| `signal_weights`, `risk_policy` | JSONB | strategy config |
| `cadence` | TEXT | default `'daily'` |
| `initial_capital_usd` | FLOAT | default 25000 |
| `accent_color`, `avatar_glyph` | TEXT | UI |
| `blocked_tickers`, `blackout_dates`, `user_notes` | TEXT[] | guardrails |

Indexes: `user_id`, `slug`. **RLS:** read if `user_id = auth.uid() OR is_seed OR public`; write if owner.

### `trade_proposals` — core copilot artifact
ENUM `proposal_status`: `pending|approved|rejected|executed|failed|expired`.

| Group | Columns |
|-------|---------|
| Identity | `id`, `user_id` (FK), `personality_id` (FK), `personality_name`, `ticker` |
| Order | `side` (buy/sell), `qty`, `order_type`, `quote_price`, `proposed_notional`, `stop_loss_price`, `take_profit_price`, `time_in_force` |
| Reasoning | `thesis`, `conviction` INT, `invalidation`, `dissent_summary` |
| Lifecycle | `status` (enum), `approved_at`, `executed_at`, `expired_at` |
| Execution | `alpaca_order_id`, `fill_price`, `fill_qty` |
| Traces (JSONB) | `debate_transcript`, `signal_snapshot`, `risk_verdict`, `policy_verdict`, `catalyst_stress_test`, `agent_trace` |

Indexes: `user_id`, `personality_id`, `status`, `ticker`, `created_at desc`. **RLS:** owner-only.

### `audit_events` — immutable trail
`proposal_id` (FK), `user_id`, `event_type`, `actor`, `reason`, `payload` JSONB, `created_at`.
**RLS:** read own.

### `activity_events` — live "what the AI is thinking" stream
`personality_id` (FK), `user_id`, `event_type`, `message`, `payload` JSONB, `created_at`. **RLS:** read own.

### `pilot_memory` — layered semantic memory (pgvector)
ENUM `memory_layer`: `hot|warm|cold`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `user_id`, `personality_id` | UUID FK | |
| `layer` | memory_layer | default `warm` |
| `category`, `ticker`, `content` | TEXT | |
| `importance` | FLOAT [0,1] | |
| `embedding` | `vector(1536)` | HNSW cosine index |
| `metadata` | JSONB | |
| `expires_at`, `created_at` | TIMESTAMPTZ | |

Indexes: `(user_id, personality_id)`, `layer`, `ticker`, `category`, partial `expires_at`,
`created_at desc`, **HNSW** `embedding vector_cosine_ops`. **RLS:** owner-only.

### `journal_entries`, `drift_flags`, `portfolio_snapshots`, `workflow_checkpoints`
| Table | Key columns | RLS |
|-------|-------------|-----|
| `journal_entries` | `personality_id`, `entry_date` (UNIQUE), `summary`, `trades_reviewed`, `lessons` JSONB, `mood` | readable if personality public/seed/owned |
| `drift_flags` | `personality_id`, `flag_type`, `severity`, `message`, `resolved` | owner via personality |
| `portfolio_snapshots` | `user_id`, `personality_id`, `snapshot_date` (UNIQUE triple), `equity`, `cash`, `buying_power`, `unrealized_pl`, `realized_pl`, `positions` JSONB | owner-only |
| `workflow_checkpoints` | `thread_id`, `step`, `state` JSONB, `metadata` | **service-role only** (LangGraph state) |

---

## 3. Supabase Postgres — vnext Domain (`vnext_pgvector_schema.sql`)

Extensions: `pgcrypto`, `vector`. **No RLS** — isolation is `owner_user_id TEXT` filtered in the
app layer. This is the thesis / strategy-terminal / paper-trading domain.

### Thesis engine
| Table | Key columns |
|-------|-------------|
| `theses` | `owner_user_id`, `ticker`, `time_horizon`, `status` (active/retired), `claim`, `why_now`, `invalidation_conditions` JSONB, `legacy_saved_thesis_id` (UNIQUE, migration link), `portfolio_id` |
| `thesis_revisions` | `thesis_id` (FK), `version` (UNIQUE per thesis), `change_summary`, `claim`, `why_now`, `time_horizon`, `status`, `invalidation_conditions`, `snapshot` JSONB |
| `evidence_blocks` | `thesis_id` (FK), `revision_id`, `source`, `summary`, `payload` JSONB, `confidence` NUMERIC, `freshness`, `links`, `observed_at` |
| `memos` | `thesis_id` (FK), `revision_id`, `summary`, `body`, `generated_by` (user/ai), `metadata` |

### Strategy terminal & execution
| Table | Key columns |
|-------|-------------|
| `terminal_sessions` | `owner_user_id`, `session_key` (UNIQUE), `objective`, `mode` (paper), `risk_profile`, `capital_base`, `status`, `request_payload`/`response_payload` JSONB |
| `strategy_proposals` | `owner_user_id`, `session_id` (FK), `strategy_type`, `ticker`/`tickers[]`, `title`, `thesis`, `entry`/`target`/`stop`, `confidence`, `invalidation`, `evidence`/`competing_view`/`market_context`/`model_trace`/`usage` JSONB, `is_paper`, `approved_by`, `execution_status` (pending_approval→approved/rejected/paper_open/paper_closed/blocked). **CHECK:** live trades require `approved_by` |
| `execution_approvals` | `strategy_id` (FK), `approved_by`, `decision`, `notes` |
| `paper_orders` | `strategy_id` (FK), `symbol`, `side`, `quantity`, `order_type`, `limit_price`/`stop_price`, `broker_status`, `execution_status`, `alpaca_order_id`/`alpaca_status` |
| `paper_positions` | `strategy_id`, `symbol`, `quantity`, `avg_price`, `mark_price`, `unrealized_pnl`, `execution_status` |

### Thesis-linked paper trading
| Table | Key columns |
|-------|-------------|
| `paper_trades` | `owner_user_id`, `thesis_id` (FK), `thesis_revision_id`, `ticker`, `side` (buy/sell), `size`, `entry_price`, `exit_price`, `status` (open/closed/blocked), `policy_check_snapshot` JSONB, `pnl`, `notes`, `alpaca_order_id`/`alpaca_status` |
| `policy_rules` | `owner_user_id`, `rule_type`, `enabled`, `params` JSONB; UNIQUE `(owner_user_id, rule_type)` |

### Research, briefs & retrieval
| Table | Key columns |
|-------|-------------|
| `research_runs` | `owner_user_id`, `scope`, `ticker`, `prompt`, `run_type`, `status`, `steps`/`output`/`citations` JSONB, `model_cost_usd` |
| `research_documents` | `ticker`, `source_type`, `source_url`, `title`, `chunk_text`, `metadata`, `embedding vector(1536)` — RAG corpus |
| `daily_briefs` | `brief_date`, `owner_user_id`, `macro_regime`, `top_signals`, `watchlist_updates`, `citations` JSONB; UNIQUE `(brief_date, owner_user_id)` |
| `signal_events` | `signal_type`, `asset_scope`, `severity`, `title`, `summary`, `tickers[]`, `evidence` JSONB, `freshness` |
| `ticker_workspaces` | `ticker` PK, JSONB blobs: `snapshot`, `thesis`, `filings`, `transcripts`, `insider`, `macro_context`, `technicals`, `open_questions` |
| `watchlist_items` | `owner_user_id`, `watchlist_id`, `ticker`, `priority`, `tags`/`catalyst_dates`/`alert_rules` JSONB, `thesis_id` (FK → saved_theses) |
| `saved_theses` | `owner_user_id`, `ticker`, `thesis_text`, `stance`, `confidence` [0-100], `catalysts`/`risks` JSONB |
| `competitor_profiles` | `slug` PK, `audience`, `strengths`/`weaknesses`/`pricing_notes`/`proof_points` JSONB |
| `model_usage_events` | `session_id`, `owner_user_id`, `provider`, `model_id`, `request_purpose`, token counts, `estimated_cost_usd`, `raw_usage` JSONB |

### Agent & backtest tracing (`migrations/2026051500000{2,3}`)
| Table | Purpose |
|-------|---------|
| `agent_runs`, `agent_run_steps` | ReAct/multi-agent run tracing (run → ordered steps) |
| `backtest_runs` | Persisted backtest results (equity curve, metrics, config) |

---

## 4. Relationship Overview

```
auth.users ──1:1── profiles
     │
     ├──< personalities ──< trade_proposals ──< audit_events
     │         │                  └──────────── (alpaca_order_id → broker)
     │         ├──< activity_events
     │         ├──< journal_entries
     │         ├──< drift_flags
     │         └──< pilot_memory (pgvector)
     ├──< portfolio_snapshots
     └──< user_consent

owner_user_id (TEXT) ─┬─< theses ──< thesis_revisions ──< evidence_blocks
                      │       │            └──< memos
                      │       └──< paper_trades ──(alpaca)
                      ├─< terminal_sessions ──< strategy_proposals ──< execution_approvals
                      │                                │
                      │                                ├──< paper_orders ──(alpaca)
                      │                                └──< paper_positions
                      ├─< policy_rules
                      ├─< research_runs / daily_briefs / signal_events
                      └─< watchlist_items ──(FK)── saved_theses
```

Two distinct "proposal" concepts coexist:
- **`trade_proposals`** (copilot/pilot) — single-ticker order from a personality, full debate trace.
- **`strategy_proposals`** (strategy terminal) — multi-ticker strategy from a terminal session.

Three distinct paper-trading models coexist: `trade_proposals` (copilot), `paper_trades`
(thesis-linked), and `paper_orders`/`paper_positions` (strategy-linked).

---

## 5. Functions, Triggers & Jobs (Supabase)

| Object | Purpose |
|--------|---------|
| `handle_new_user()` + `on_auth_user_created` | Auto-create `profiles` row on signup. **Hardened** (`migrations/20260523000001`): `SET search_path = public`, qualified `public.profiles`, `ON CONFLICT DO NOTHING`, `EXCEPTION WHEN OTHERS` guard so it can never block signup again (see architecture §10.6) |
| `retrieve_memory(...)` | Semantic memory retrieval: score = `importance × exp(-decay·age/halflife) × cosine_sim`; half-life by layer (hot 1d / warm 7d / cold 90d) |
| `cleanup_expired_memory()` | Deletes expired `pilot_memory` (pg_cron hourly) |
| `promote_warm_to_cold()` | Promotes high-importance warm memories to cold before expiry (pg_cron daily 3am) |
| `moddatetime` triggers | Auto-update `updated_at` on `profiles`, `personalities`, `trade_proposals` |

---

## 6. Schema Risks & Consolidation Notes

1. **Legacy Mongo↔Supabase duplication** — `pilot_*` (Mongo) vs copilot tables (PG); `saved_theses`,
   `signal_events`, `daily_briefs` exist in both. Supabase should be the system of record.
2. **Two ownership models** — `user_id UUID` (RLS-enforced) vs `owner_user_id TEXT` (app-filtered,
   no RLS). The vnext tables are not RLS-protected; isolation depends entirely on correct
   `owner_user_id` filtering in every query.
3. **No FK from vnext `owner_user_id` to `auth.users`** — orphaning and type drift are possible.
4. **`legacy_saved_thesis_id`** on `theses` is the bridge from the Mongo-era saved theses; a full
   migration would backfill and drop the duplicate stores.

> Migration target & sequencing live in [`trd-marketflux.md`](./trd-marketflux.md) → "Data Consolidation".
