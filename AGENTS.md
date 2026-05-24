# AGENTS.md

## Cursor Cloud specific instructions

### Architecture
- **Backend**: FastAPI (Python 3.12) at port 8001 (`MarketFlux/backend/`)
- **Frontend**: React CRA+CRACO (Node 20) at port 3000 (`MarketFlux/frontend/`)
- **Database**: MongoDB 7.0 (local or Atlas)

### Starting Services

```bash
# 1. MongoDB (must be running first)
mongod --dbpath /tmp/mongodb --port 27017 --fork --logpath /tmp/mongodb/mongod.log

# 2. Backend
cd MarketFlux/backend
export PATH="$HOME/.local/bin:$PATH"
uvicorn server:app --reload --port 8001

# 3. Frontend (use the dev config to bypass the visual-edits babel plugin bug)
cd MarketFlux/frontend
source /home/ubuntu/.nvm/nvm.sh && nvm use 20
BROWSER=none REACT_APP_BACKEND_URL=http://localhost:8001 npx craco start --config craco.config.dev.js
```

### Known Gotchas

1. **Visual-edits babel plugin crashes in dev mode**: The `plugins/visual-edits/babel-metadata-plugin.js` has a null-pointer bug (`importPath.parentPath.parentPath` can be null). Use `craco.config.dev.js` (which disables the plugin) instead of the default `craco.config.js` when starting the frontend dev server.

2. **MongoDB `pilot_personalities` index issue**: The `database.py` creates a `sparse: true` unique index on `public_slug`, but seed personalities store `public_slug: null` explicitly (field present with null value). Sparse indexes only skip documents where the field is *absent*. Fix: after first backend start, run:
   ```
   mongosh --eval "db.getSiblingDB('MarketFlux').pilot_personalities.dropIndex('public_slug_1'); db.getSiblingDB('MarketFlux').pilot_personalities.createIndex({public_slug:1},{unique:true,partialFilterExpression:{public_slug:{\$type:'string'}},name:'public_slug_1'})"
   ```

3. **Node version**: Frontend requires Node 20 (not 22). Use `nvm use 20`.

4. **Python PATH**: pip installs to `~/.local/bin` which isn't on PATH by default. Always `export PATH="$HOME/.local/bin:$PATH"` before running uvicorn.

5. **HuggingFace models**: sentence-transformers requires internet access to download on first run. The server gracefully degrades without it (agent embeddings disabled).

6. **NaN in market data**: yfinance occasionally returns NaN values that crash JSON serialization. The `sanitize_for_json` helper handles this, but if you see 500 errors with "Out of range float values", it's this issue.

### Required Secrets for Full Feature Set

| Secret | Features it unlocks |
|--------|-------------------|
| `GEMINI_API_KEY` | AI Chat, Stock Digests, AI Screener, Pilot signal scoring, Autoresearch |
| `APCA_API_KEY_ID` | Paper trading execution, account management, Paper Portfolio tab |
| `APCA_API_SECRET_KEY` | (paired with above) |
| `OPENROUTER_API_KEY` or `NVIDIA_NIM_API_KEY` | Strategy Studio / Strategy Terminal |

Without these keys, all non-AI features still work: market data, charts, news, watchlist, portfolio tracking, search.

### Running Tests

```bash
# Frontend (unit tests)
cd MarketFlux/frontend
CI=true npx craco test --watchAll=false --passWithNoTests

# Backend (unit tests only — integration tests need a running server + valid API keys)
cd MarketFlux/backend
python3 -m pytest tests/test_pilot_smoke.py tests/test_thesis_router_unittest.py tests/test_thesis_backfill_unittest.py tests/test_policy_engine_unittest.py -v

# Linting happens during webpack compilation via craco's eslint config
```

### Frontend environment variable

Set `REACT_APP_BACKEND_URL=http://localhost:8001` when starting the frontend to point API calls at the local backend.
