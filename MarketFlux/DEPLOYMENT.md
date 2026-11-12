# Deploy MarketFlux

Public demo shape: React on Vercel, FastAPI on Render (free web service, `MarketFlux/backend/Dockerfile`), Supabase for auth and Postgres, MongoDB Atlas M0 for the collections that still use Mongo. Redis is optional.

The API process is production-safe when `MARKETFLUX_ENV` is unset: copilot routes require a logged-in user, localhost is not added to CORS, and `run_python` stays off. `render.yaml` sets `MARKETFLUX_ENV=production` and `DEMO_MODE=true` explicitly.

## Render (backend)

`render.yaml` at the repo root defines one Docker web service:

- Dockerfile: `MarketFlux/backend/Dockerfile` (Python 3.12)
- Health check: `GET /api/health`
- Bind: `0.0.0.0:$PORT` (Render sets `PORT`)

In the Render dashboard, set the secrets marked `sync: false`. `DEMO_MODE`, `ENABLE_CODE_SANDBOX=false`, `DB_NAME`, and the copilot limits are already in the blueprint.

Required:

| Variable | Why |
| --- | --- |
| `MONGO_URL` | Copilot history, news, and other Mongo collections. The process exits with a clear error if this is missing. |
| `DB_NAME` | Mongo database name. The blueprint defaults it to `marketflux`. |
| `JWT_SECRET` | 32+ characters. Required if Supabase auth is not configured. |
| `ALLOWED_ORIGINS` | The Vercel origin, for example `https://your-app.vercel.app`. No localhost default in production. |
| `SUPABASE_URL` | Same project as the frontend. |
| `SUPABASE_ANON_KEY` | Verifies user JWTs. |
| `SUPABASE_SERVICE_KEY` | Server writes. Never ship this to the browser. |
| `GEMINI_API_KEY` | Copilot, digests, screener. |

Needed for trading and memory:

| Variable | Why |
| --- | --- |
| `SUPABASE_DB_URL` | Postgres connection for pgvector memory and vNext tables. |
| `APCA_API_KEY_ID` | Alpaca **paper** key. The client is constructed with `paper=True`. |
| `APCA_API_SECRET_KEY` | Paired paper secret. |
| `REDIS_URL` | Optional. Use `rediss://` for TLS. `REDIS_HOST` / `REDIS_PORT` are only a fallback when `REDIS_URL` is unset. |

Optional: `OPENROUTER_API_KEY`, `NVIDIA_NIM_API_KEY`, `FINNHUB_KEY`, `FRED_API_KEY`, `ALPHA_VANTAGE_KEY`, `TAVILY_API_KEY`, `LEDGER_GRADE_TOKEN`, `COPILOT_DAILY_TURNS`, `COPILOT_RATE_LIMIT`.

Do not set `ENABLE_CODE_SANDBOX=true` on this service. Demo mode forces the Python tool off even if you do.

## Vercel (frontend)

Root `vercel.json` installs and builds `MarketFlux/frontend` and rewrites every path to `index.html`. Security headers match `MarketFlux/frontend/nginx.conf`, with Google Fonts and TradingView allowed so the ticker tape and charts still load.

Set these before the first production build. `yarn build` fails if `REACT_APP_BACKEND_URL` is empty. `frontend/.env.production` sets `GENERATE_SOURCEMAP=false`.

| Variable | Why |
| --- | --- |
| `REACT_APP_BACKEND_URL` | Render URL, no trailing slash. Example: `https://marketflux-api.onrender.com` |
| `REACT_APP_SUPABASE_URL` | Same project as the backend. |
| `REACT_APP_SUPABASE_ANON_KEY` | Public anon key. RLS is what keeps table data private. |
| `REACT_APP_DEMO_MODE` | `true` shows the paper-trading banner immediately. The API `demo_mode` flag also turns the banner on. |

If you would rather set the Vercel root directory to `MarketFlux/frontend`, the same env vars apply and the output directory is `build`. The repo-root `vercel.json` is the path that works without changing the project root.

## Supabase

Apply every file in `supabase/migrations/` in filename order (SQL editor or `supabase db push`). That creates the vNext tables, pilot tables, ledger tables, and row level security.

The anon key can authenticate users. It cannot read another user's rows, and it cannot read service-only tables (checkpoints, filings corpus, daily closes). The API uses the service role for those writes.

Google sign-in is `supabase.auth.signInWithOAuth({ provider: 'google' })`. Enable the Google provider in the Supabase dashboard if you want that button. There is no Emergent login proxy.

## MongoDB Atlas

Create an M0 cluster, allow the Render egress IPs (or `0.0.0.0/0` for a demo, knowing what that means), and set `MONGO_URL` to the SRV string. `DB_NAME` must match the database you want the API to use.

## Local Docker

`MarketFlux/docker-compose.yml` builds the API and the nginx frontend. Put the variables from `backend/.env.example` in `backend/.env`. Compose defaults `MARKETFLUX_ENV` to `development` so localhost CORS works. It does not start Mongo; point `MONGO_URL` at Atlas or a Mongo you run yourself.

## Health

- `GET /api/health` returns 200 when the process is up. Render uses this path. It does not ping Mongo.
- `GET /api/health/db` reports Mongo, Postgres, and Redis connectivity for debugging.
