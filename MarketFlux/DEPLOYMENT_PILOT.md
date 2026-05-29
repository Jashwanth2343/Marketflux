# Copilot / Pilot Operations

This document covers the current paper-trading Copilot/Pilot operations layer. It is Supabase-first and paper-trading only.

## Current Surfaces

- Conversational Copilot: `frontend/src/components/copilot/CopilotAgent.js`
- Copilot page shell: `frontend/src/pages/Copilot.js`
- Standing agents: `frontend/src/components/copilot/StandingAgents.js`
- Backend Copilot routes: `backend/copilot_router.py`, `backend/copilot_agent.py`, `backend/copilot_trades.py`
- vNext Pilot routes: `backend/vnext/pilot_router.py`
- Memory/checkpoints: Supabase Postgres / pgvector, with Redis for hot state where configured

Some older `vnext/pilot/*` modules still accept Mongo-style `db` parameters for compatibility while the migration finishes. Do not document Mongo as required for normal local startup.

## Required Environment

```env
ALLOWED_ORIGINS=http://localhost:3000

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_DB_URL=postgresql://...

GEMINI_API_KEY=your-gemini-key
OPENROUTER_API_KEY=your-openrouter-key
NVIDIA_NIM_API_KEY=your-nvidia-key

APCA_API_KEY_ID=your-alpaca-paper-key
APCA_API_SECRET_KEY=your-alpaca-paper-secret
ALPACA_PAPER_API_URL=https://paper-api.alpaca.markets/v2
```

## Local Dev

```bash
cd MarketFlux/backend
./venv/bin/python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd MarketFlux/frontend
BROWSER=none HOST=127.0.0.1 PORT=3000 REACT_APP_BACKEND_URL=http://localhost:8000 npx craco start --config craco.config.dev.js
```

Open `http://localhost:3000/copilot`.

## Safety Invariants

- Paper trading only.
- Broker keys stay server-side.
- The Copilot UI must show staged trade approvals when confirmation mode is on.
- Server-side trade endpoints must re-check account state and policy before submission.
- If model provider keys or Alpaca keys are missing, the UI should degrade gracefully rather than blanking the app.
