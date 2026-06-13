# PRD: Supabase Data Foundation

> **Status — updated 2026-06-13 (post-PR #30):** ✅ **FOUNDATION SHIPPED**, and scope has since grown.
> The DSN resolution chain, `GET /api/health/db`, asyncpg pool, and pilot router are live. Two items
> originally **out of scope are now in flight:** (1) **Supabase Auth was adopted** — the backend accepts
> Supabase JWTs (master PRD FR1), not MongoDB auth; (2) the **Mongo→Postgres migration began** — PR #30
> moved the copilot trust path onto Supabase Postgres (`copilot_store.py`, `sql/copilot_core_schema.sql`,
> with an integration suite). **Row Level Security is still pending** (tracked as a roadmap risk; isolation
> currently relies on app-layer `owner_user_id` filtering). Acceptance below verified in dev.

## Problem Statement
Thesis creation, paper trading, and Fund OS features all fail because Postgres tables don't exist. The backend has asyncpg support but no Supabase project structure, no migration workflow, and no health checks.

## Scope

### In Scope
- Add `SUPABASE_DB_URL` to DSN resolution chain
- Create `supabase/` migration directory with core schema
- Add agent_runs and backtest_runs tables
- Add `GET /api/health/db` endpoint
- Dev-only auto-schema bootstrap with explicit opt-in
- Mount pilot router in server.py

### Out of Scope
- Supabase Auth (keep existing MongoDB auth)
- Supabase Realtime subscriptions
- Row Level Security policies (future)
- Migrating MongoDB collections to Postgres

## API Contracts

### GET /api/health/db
Response:
```json
{
  "postgres": { "connected": true, "tables_ok": true, "vector_ext": true },
  "mongo": { "connected": true },
  "redis": { "connected": true }
}
```

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `supabase/config.toml` | Create | Supabase project config |
| `supabase/migrations/20260515000001_vnext_core.sql` | Create | Core schema (copy of vnext_pgvector_schema.sql) |
| `supabase/migrations/20260515000002_agent_runs.sql` | Create | Agent run tracing tables |
| `supabase/migrations/20260515000003_backtest_runs.sql` | Create | Backtest result persistence |
| `backend/vnext/fundos_pg_client.py` | Modify | Add SUPABASE_DB_URL to DSN resolution |
| `backend/server.py` | Modify | Health endpoint, dev bootstrap, mount pilot router |

## Supabase Connection

- Project: https://etanlxohfiwhdwkbqyzq.supabase.co
- DSN resolution: `SUPABASE_DB_URL` > `MARKETFLUX_VNEXT_DATABASE_URL` > `FUNDOS_DATABASE_URL`
- Pool: asyncpg, min_size=1, max_size=5

## Acceptance Criteria
- [x] `GET /api/health/db` returns all green when Supabase DSN is set
- [x] Thesis creation succeeds (INSERT INTO theses works)
- [x] Paper trade creation succeeds
- [x] Strategy terminal writes to strategy_proposals
- [x] Dev bootstrap applies schema when flag is set
- [x] Pilot router is mounted and `/api/pilot/status` responds
