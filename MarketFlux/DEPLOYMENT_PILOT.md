# Marketflux Pilot — Deployment & Operations

This guide deploys the AI Portfolio Manager subsystem ("Pilot") on top of the
existing Marketflux backend + frontend. Pilot is paper-trading only. There is
no live-trading switch in this release. Do not add one.

## 0. What ships in this drop

**Backend** (Python / FastAPI):
- `backend/vnext/pilot/strategy_dsl.py` — JSON DSL + deterministic compiler.
- `backend/vnext/pilot/personality.py` — Atlas / Sage / Vega + Mongo CRUD.
- `backend/vnext/pilot/trade_proposals.py` — proposal lifecycle + audit log.
- `backend/vnext/pilot/pilot_engine.py` — orchestrator wiring signal_engine,
  risk_engine, strategy_swarm, policy_engine, mirofish_bridge, nemoclaw_bridge,
  alpaca_client.
- `backend/vnext/pilot_router.py` — 20 endpoints under `/api/pilot`.
- `backend/tests/test_pilot_smoke.py` — 12 unit tests, all passing on a
  no-network / no-Mongo env.

**Frontend** (React 19 / shadcn / Tailwind):
- `frontend/src/pages/Pilot.js` — 3-column page (personalities · live activity · approval queue).
- `frontend/src/components/pilot/*` — debate transcript, glass-box trade, kill switch, onboarding.

**Mongo collections** (created on first use):
- `pilot_personalities`, `pilot_trade_proposals`, `pilot_audit_events`,
  `pilot_activity_events`, `pilot_user_consent`.

## 1. Environment variables

Add the following to your existing `.env` (backend) and Vercel/Render config.
Pilot-specific keys are at the bottom; the rest are existing Marketflux ones it
inherits.

```bash
# --- existing Marketflux backend ---
MONGO_URL=mongodb+srv://...
DB_NAME=marketflux
JWT_SECRET=<32+ chars; generate via: python3 -c "import secrets;print(secrets.token_hex(32))">
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000

# --- existing Alpaca Broker API (paper / sandbox) ---
ALPACA_BROKER_API_KEY=...
ALPACA_BROKER_API_SECRET=...

# --- existing LLM routing (already wired into strategy_swarm) ---
# Either of these turns on the swarm. NIM is preferred for cost at scale.
NVIDIA_NIM_API_KEY=nvapi-...
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_NIM_REASONING_MODEL=nvidia/llama-3.3-nemotron-super-49b-v1
NVIDIA_NIM_FAST_MODEL=nvidia/llama-3.1-nemotron-70b-instruct
# Fallback:
OPENROUTER_API_KEY=sk-or-...

# --- optional sandboxed-agent bridge (no-op if unset) ---
NEMOCLAW_BASE_URL=          # https://your-modal-app.modal.run, vLLM endpoint, etc.
NEMOCLAW_BEARER_TOKEN=

# --- optional MiroFish catalyst stress test (no-op if unset) ---
MIROFISH_BASE_URL=
MIROFISH_BEARER_TOKEN=

# --- Pilot has no dedicated env vars beyond the above. ---
```

The pilot subsystem will run even with most of these unset:
- If `ALPACA_BROKER_API_*` is missing, proposals stop at the approval stage
  and never submit an order (a "no Alpaca account" error surfaces to the user).
- If both NIM and OpenRouter are missing, `strategy_swarm.run_swarm()` returns
  empty agent output, the verdict parser yields `PASS`, and no proposals are
  created. The system fails-closed cleanly.
- If `NEMOCLAW_BASE_URL` is unset, the bridge step is silently skipped.
- If `MIROFISH_BASE_URL` is unset, the catalyst stress test is silently skipped.

## 2. Local dev

```bash
# Backend
cd backend
pip install -r requirements.txt
# (If running smoke tests in isolation, numpy and pandas are enough.)
python -m uvicorn server:app --reload --port 8001

# Frontend
cd frontend
yarn install
REACT_APP_BACKEND_URL=http://localhost:8001 yarn start

# Smoke test (no network, no Mongo)
cd backend
python tests/test_pilot_smoke.py
```

Pilot endpoints will appear under `http://localhost:8001/api/pilot/*`.
Visit `http://localhost:3000/pilot` for the UI.

## 3. Deployment — Render (backend) + Vercel (frontend) + Mongo Atlas

### 3.1 Mongo Atlas
- Create a project + free-tier M0 cluster.
- Add IP `0.0.0.0/0` to network access (or restrict to Render's egress IPs).
- Create a DB user; the connection string is your `MONGO_URL`.
- Pilot creates its 5 collections lazily on first write. Indexes recommended:

  ```js
  db.pilot_personalities.createIndex({ user_id: 1 });
  db.pilot_personalities.createIndex({ id: 1 }, { unique: true });
  db.pilot_trade_proposals.createIndex({ user_id: 1, status: 1, created_at: -1 });
  db.pilot_trade_proposals.createIndex({ id: 1 }, { unique: true });
  db.pilot_audit_events.createIndex({ proposal_id: 1, timestamp: 1 });
  db.pilot_activity_events.createIndex({ personality_id: 1, timestamp: -1 });
  db.pilot_user_consent.createIndex({ user_id: 1 }, { unique: true });
  ```

### 3.2 Render (backend)
- New Web Service from this repo, root directory `backend/`.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Plan: Starter ($7/mo) for V1. Bump to Standard if /propose latency hurts.
- Env vars: paste from section 1 above.
- Health check path: `/` (returns 200).

### 3.3 Vercel (frontend)
- Import the repo, root directory `frontend/`.
- Framework preset: Create React App.
- Env vars: `REACT_APP_BACKEND_URL=https://your-render-app.onrender.com`.
- Build command: `yarn build`. Output: `build/`.

### 3.4 Cron — expire-overdue sweep
Render Cron Job, every 5 minutes:
```bash
curl -X POST -H "Cookie: $RENDER_PILOT_SESSION" https://your-backend.onrender.com/api/pilot/sweep
```
Or call from your own auth context. The sweep is idempotent.

## 4. Open-LLM path: NemoClaw, OpenClaw, and Nemotron

The user asked: can we use NemoClaw / OpenClaw, and is cloud compute viable?
Short answer: **yes, and the wiring already exists.** Long answer:

### 4.1 NemoClaw bridge — already in the repo
`backend/vnext/nemoclaw_bridge.py` is a `httpx`-based HTTP client. Set
`NEMOCLAW_BASE_URL` and it POSTs `{base_url}/analyze` with a bearer token.
The Pilot orchestrator calls it (when configured) as one extra adversarial
signal alongside the existing swarm. **You do not need to modify any code
to flip it on — only env vars.**

To self-host the NemoClaw endpoint with an open-weight model:

| Option | Best for | Cost (rough) | Latency |
|---|---|---|---|
| **NVIDIA NIM cloud** (managed) | quickest path; no GPU ops | $0.20–1.20 per Mtok depending on model | 1–4 s |
| **Modal Labs** with vLLM + Nemotron-70B | bursty traffic, autoscale to zero | ~$0.45/h while idle-warm; A100 80GB ~$3.30/h on demand | 2–6 s cold, <1 s warm |
| **RunPod** Serverless GPU + vLLM | cheaper sustained workloads | A100 from $1.89/h spot, $2.99/h on-demand | 1–3 s warm |
| **Lambda Labs Cloud** | longest-running paper accounts | A10 from $0.75/h | 2–5 s |
| **Self-hosted on your own box** | dev only | hardware + power | depends |

For Marketflux V1 (you + ~20 beta users, ~5 proposals/day each), the math:
- Each proposal runs the 5-agent swarm = 5 LLM calls @ ~600 input + 200 output
  tokens. With NIM Nemotron-Super-49B (~$0.40/Mtok blended), one proposal is
  ~$0.001. 100 proposals/day across 20 users is ~$3/mo. Effectively free.
- If you want to host Nemotron-70B yourself on Modal:
  - Image: `vllm/vllm-openai:latest` with the model weight downloaded once.
  - Endpoint: OpenAI-compatible. Set `NEMOCLAW_BASE_URL=https://<your-modal-app>.modal.run/v1`.
  - Set the model id on `NVIDIA_NIM_REASONING_MODEL` since the swarm reads
    that via `StrategyLLMRouter` — or add a fork/branch in
    `vnext/model_router.py` for a `vllm_openai` provider.

### 4.2 OpenClaw — proposed extension (NOT yet built)
Your codebase has one reference: `terminal_status: "pending_openclaw"` in
`vnext/fundos_service.py`. There is no bridge module yet.

Recommended action (out of scope for this drop): add
`backend/vnext/openclaw_bridge.py`, a near-identical sibling of
`nemoclaw_bridge.py`, pointing at a **fully open-weight, fully self-hostable**
endpoint (e.g., an Ollama or LM Studio instance running Llama-3.3-70B). This
gives users a "completely off-cloud" tier while keeping NemoClaw as the
managed/hosted option.

The Pilot orchestrator calls bridges via lazy import: adding a second one is a
~30-line change to `pilot_engine._decide_for_candidate()`.

### 4.3 Hot recommendation
For paper-trading V1, start on **NVIDIA NIM** (managed). It's already wired
through `StrategyLLMRouter`, costs are negligible, and you avoid the GPU
ops tax until you have paying users. Migrate the bull/bear agents to a
self-hosted Nemotron-70B on Modal *after* the leaderboard goes public —
that's when API costs become a margin issue.

## 5. Operational notes

### Safety guarantees (hardcoded)
- **No live trading.** `vnext.policy_engine.no_live_trading` is True by default,
  enforced at every personality. Removing it requires editing both the policy
  defaults AND every personality's `risk_policy.no_live_trading=False`. This is
  intentional friction.
- **Kill switch acts <1s.** `POST /api/pilot/personalities/{id}/kill` pauses the
  personality, expires all pending proposals, and cancels any Alpaca orders.
- **Approval timeout = end of NY trading day** (not 30 seconds; deliberate).
- **Immutable audit log.** Every status transition is appended to
  `pilot_audit_events` with timestamp, actor, payload. Do not GC this collection.
- **Consent gate.** Every state-changing Pilot endpoint requires the user to
  have POSTed `/api/pilot/consent` with all three booleans true.

### Cost ceiling
- Set Gemini / NIM rate limits per user at your provider's dashboard.
- The activity feed is unbounded; add a daily Mongo TTL index if it grows fast:
  ```js
  db.pilot_activity_events.createIndex({ timestamp: 1 }, { expireAfterSeconds: 2592000 });
  ```

### Observability
- `pilot_audit_events` is the canonical record. Every approval-to-execution path
  produces a `created → status:approved → status:executed` triple.
- `pilot_activity_events` is the "what is the AI thinking right now" feed —
  good for the live UI but also useful when debugging "why didn't it trade today?"

## 6. The launch checklist (you on your own paper account)

- [ ] Render backend deployed, env vars set, `/api/pilot/status` returns 200.
- [ ] Vercel frontend deployed, `/pilot` page loads.
- [ ] Mongo indexes created (section 3.1).
- [ ] Alpaca Broker API sandbox keys provisioned + tested via `/api/alpaca/status`.
- [ ] You log in, accept consent at `/pilot`.
- [ ] You see three seed personalities (Atlas, Sage, Vega).
- [ ] You click "Propose Trades" on Atlas — within 60s you see at least one
      proposal card on the right column with a debate transcript.
- [ ] You approve one proposal. Within 10s the proposal flips to EXECUTED and
      Alpaca shows a fill in `/api/alpaca/orders`.
- [ ] You hit the kill switch on Atlas — the personality pauses, any pending
      proposals flip to EXPIRED, audit events are logged.
- [ ] You run `python tests/test_pilot_smoke.py` — 12/12 pass.

Once you've done all of those at least once, you can hand the URL to your
first beta users.
