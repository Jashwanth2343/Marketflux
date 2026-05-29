# MarketFlux

MarketFlux is an AI-native investment research platform with market dashboards, thesis workflows, Strategy Studio, and a conversational paper-trading Copilot.

## Architecture

```text
React CRA frontend (:3000)
        |
        | HTTP / SSE / Supabase session
        v
FastAPI backend (:8000)
        |
        +-- Supabase Auth + Postgres + pgvector
        +-- Alpaca paper trading
        +-- Gemini / OpenRouter / NVIDIA model providers
        +-- Market data, RSS, yfinance
```

Supabase is the primary auth and durable data layer. Some Mongo-backed compatibility paths remain in the backend while older features are migrated, but Mongo is not the default local development database.

## Local Setup

```bash
cd backend
./venv/bin/python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
BROWSER=none HOST=127.0.0.1 PORT=3000 REACT_APP_BACKEND_URL=http://localhost:8000 npx craco start --config craco.config.dev.js
```

Open `http://localhost:3000`.

## Environment Variables

Backend:

- `ALLOWED_ORIGINS`: usually `http://localhost:3000`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_DB_URL` or `MARKETFLUX_VNEXT_DATABASE_URL` or `FUNDOS_DATABASE_URL`
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY` or `NVIDIA_NIM_API_KEY`
- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`

Frontend:

- `REACT_APP_BACKEND_URL=http://localhost:8000`
- `REACT_APP_SUPABASE_URL`
- `REACT_APP_SUPABASE_ANON_KEY`

## vNext Quant Research OS

- `backend/vnext/` contains quant research engines and `/api/vnext/*` routes (theses, policies, paper-trades) consumed by the main `frontend/` app.
- `backend/sql/vnext_pgvector_schema.sql` contains Supabase/Postgres schema.
- `docker-compose.vnext.yml` is for optional local Postgres/Redis infrastructure.
