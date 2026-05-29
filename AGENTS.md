# AGENTS.md

## Current Local Architecture

- **Backend**: FastAPI at `http://localhost:8000` (`MarketFlux/backend/`)
- **Frontend**: React CRA + CRACO at `http://localhost:3000` (`MarketFlux/frontend/`)
- **Primary data/auth**: Supabase Auth + Supabase Postgres / pgvector
- **Legacy compatibility**: some backend modules still accept a Mongo `db` object or read Mongo mirrors/fallbacks, but Mongo is not the primary local setup.

## Starting Services

```bash
# Backend
cd MarketFlux/backend
./venv/bin/python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd MarketFlux/frontend
BROWSER=none HOST=127.0.0.1 PORT=3000 REACT_APP_BACKEND_URL=http://localhost:8000 npx craco start --config craco.config.dev.js
```

Open the app at `http://localhost:3000`.

## Known Gotchas

1. **Use backend port 8000**: The frontend `.env` and `src/lib/api.js` default to `http://localhost:8000`. Do not start the backend on another port unless you also intentionally change the frontend env.

2. **Use `MarketFlux/backend/venv`, not `.venv`**: The `venv` environment has the current backend dependencies such as `asyncpg`. The `.venv` directory is stale/incomplete and can fail during startup.

3. **Use `craco.config.dev.js` for frontend dev**: The default CRACO config can trip the visual-edits Babel plugin in dev mode. The dev config bypasses it.

4. **Supabase is the primary auth/data layer**: Frontend auth uses `REACT_APP_SUPABASE_URL` and `REACT_APP_SUPABASE_ANON_KEY`. Backend vNext/FundOS data uses the DSN chain `SUPABASE_DB_URL` > `MARKETFLUX_VNEXT_DATABASE_URL` > `FUNDOS_DATABASE_URL`.

5. **Legacy Mongo code still exists**: Do not reintroduce Mongo-first setup instructions. If Mongo fallback code is touched, keep it optional and non-blocking unless the feature explicitly still depends on it.

6. **HuggingFace models**: `sentence-transformers` may download/load models on first backend startup. The server should degrade gracefully if embeddings are unavailable.

7. **NaN in market data**: `yfinance` can return NaN values that crash JSON serialization. Use the existing `sanitize_for_json` helper when adding market-data responses.

## Required Secrets for Full Feature Set

| Secret | Features it unlocks |
|--------|-------------------|
| `REACT_APP_SUPABASE_URL` | Frontend Supabase auth |
| `REACT_APP_SUPABASE_ANON_KEY` | Frontend Supabase auth |
| `SUPABASE_URL` | Backend Supabase service client |
| `SUPABASE_SERVICE_KEY` | Backend Supabase auth verification / service writes |
| `SUPABASE_DB_URL` or `FUNDOS_DATABASE_URL` | Supabase Postgres / pgvector data |
| `GEMINI_API_KEY` | AI Chat, Stock Digests, AI Screener, Copilot scoring, Autoresearch |
| `APCA_API_KEY_ID` | Paper trading execution and account management |
| `APCA_API_SECRET_KEY` | Paired with Alpaca paper key |
| `OPENROUTER_API_KEY` or `NVIDIA_NIM_API_KEY` | Strategy Studio / Strategy Terminal |

Without AI/broker keys, non-AI market pages can still render with degraded functionality.

## Running Tests

```bash
# Frontend
cd MarketFlux/frontend
CI=true npx craco test --watchAll=false --passWithNoTests

# Backend unit tests
cd MarketFlux/backend
./venv/bin/python -m pytest tests/test_pilot_smoke.py tests/test_thesis_router_unittest.py tests/test_thesis_backfill_unittest.py tests/test_policy_engine_unittest.py -v

# Frontend production-style compile with the dev CRACO config
cd MarketFlux/frontend
CI=true npx craco build --config craco.config.dev.js
```

## Frontend Environment Variable

Set `REACT_APP_BACKEND_URL=http://localhost:8000` when starting the frontend locally.
