# MarketFlux Deployment Guide

Deploy MarketFlux as a React frontend plus FastAPI backend.

## Current Runtime

- Frontend: React CRA build, served on `3000` locally
- Backend: FastAPI, `8000` locally
- Primary auth/data: Supabase Auth + Supabase Postgres / pgvector
- Optional services: Redis cache, Alpaca paper trading, model provider APIs
- Legacy compatibility: Mongo fallback/mirror code still exists in a few backend paths, but it is not the default deployment foundation.

## Required Backend Environment

```env
ALLOWED_ORIGINS=https://your-frontend.example.com,http://localhost:3000

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_DB_URL=postgresql://...

GEMINI_API_KEY=your-gemini-key

APCA_API_KEY_ID=your-alpaca-paper-key
APCA_API_SECRET_KEY=your-alpaca-paper-secret

# Optional model providers
OPENROUTER_API_KEY=your-openrouter-key
NVIDIA_NIM_API_KEY=your-nvidia-key

# Optional cache
REDIS_HOST=localhost
REDIS_PORT=6379
```

## Required Frontend Environment

```env
REACT_APP_BACKEND_URL=https://your-backend.example.com
REACT_APP_SUPABASE_URL=https://your-project.supabase.co
REACT_APP_SUPABASE_ANON_KEY=your-anon-key
```

For local frontend development, use:

```env
REACT_APP_BACKEND_URL=http://localhost:8000
```

## Docker Compose

```bash
cd MarketFlux
cp .env.example .env
cp backend/.env.example backend/.env
docker compose up --build
```

Local URLs:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`

## Render Backend

1. Create a Render Web Service.
2. Root directory: `MarketFlux/backend`.
3. Build command: `pip install -r requirements.txt`.
4. Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`.
5. Set the backend environment variables above.

## Vercel / Static Frontend

1. Root directory: `MarketFlux/frontend`.
2. Framework: Create React App.
3. Build command: `npm ci && npm run build` or `yarn install && yarn build`.
4. Output directory: `build`.
5. Set `REACT_APP_BACKEND_URL`, `REACT_APP_SUPABASE_URL`, and `REACT_APP_SUPABASE_ANON_KEY`.

## Local Smoke Checks

```bash
cd MarketFlux/backend
./venv/bin/python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd MarketFlux/frontend
BROWSER=none HOST=127.0.0.1 PORT=3000 REACT_APP_BACKEND_URL=http://localhost:8000 npx craco start --config craco.config.dev.js
```

Then open `http://localhost:3000`.
