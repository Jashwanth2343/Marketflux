# PRD: Supabase Data Foundation

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
- [ ] `GET /api/health/db` returns all green when Supabase DSN is set
- [ ] Thesis creation succeeds (INSERT INTO theses works)
- [ ] Paper trade creation succeeds
- [ ] Strategy terminal writes to strategy_proposals
- [ ] Dev bootstrap applies schema when flag is set
- [ ] Pilot router is mounted and `/api/pilot/status` responds
