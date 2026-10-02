# Handover — `god-tier-hardening` branch

**For:** the next coding agent picking up MarketFlux.
**Branch:** `god-tier-hardening` (off `main` at `fc2d041`).
**Status:** all changes are committed on this branch. Backend tests: 112 passed, 29 skipped (integration tests need `REACT_APP_BACKEND_URL`). Frontend: `CI=true npx craco build --config craco.config.dev.js` exits 0; jest 2/2 pass.
**Not yet done:** branch is NOT pushed (no GitHub auth in this environment) — see "To open the PR" below.

House rules live in the repo-root `AGENTS.md` — read it first. The short version: backend on :8000 via `MarketFlux/backend/venv`, frontend on :3000 via `craco.config.dev.js`, never invent secrets.

---

## 1. What this branch changed

### Backend safety hardening (`MarketFlux/backend/`)
| Change | File(s) | Notes |
|---|---|---|
| Actionable `MONGO_URL`/`DB_NAME` startup error | `server.py` | Was a bare `KeyError` at import; now a `RuntimeError` telling the operator exactly what to set. Behavior unchanged otherwise: backend still will not boot without Mongo. |
| Global trading kill switch | `trading_halt.py` (new), `server.py`, `copilot_trading_tools.py`, `vnext/alpaca_router.py` | `is_trading_halted()` is checked on **every** order path: copilot `place_order` tool, staged-trade approvals, pilot proposal execution, Alpaca REST order endpoints. Engage via `TRADING_HALTED=1` env or `POST /api/admin/trading-halt` (header `X-Admin-Token`; gated by `ADMIN_TOKEN`, disabled in prod when unset). Status: `GET /api/admin/trading-halt`. Does NOT cancel already-open orders — use cancel/liquidate endpoints for that. |
| Compliance chokepoint (fail-closed) | `copilot_trading_tools.py` | Order validation now denies by default on unexpected errors instead of failing open. |
| Per-minute copilot chat rate limit | `copilot_router.py` | `COPILOT_CHAT_PER_MINUTE` (default 20), sliding window, Redis-backed when `REDIS_URL` is set, in-memory otherwise. Returns 429 + `Retry-After`. The existing daily-turn budget (`COPILOT_DAILY_TURNS`) is unchanged. |
| Broker-mode isolation | `vnext/alpaca_router.py`, `vnext/alpaca_client.py` | Broker sub-account creation is now atomic (`find_one_and_update` claim, 120s stale-claim steal) — the old find→create→upsert had a TOCTOU race that could mint duplicate Alpaca sub-accounts. Cancel-all/liquidate paths were audited to stay scoped to the caller's account. |
| Hardening tests | `tests/test_hardening.py` (new) | Kill switch (halt blocks, release passes through, env-var variants, status shape), compliance fail-closed, rate limiter. |
| Market overview resilience | `server.py` | 12s hard timeout on the yfinance fetch; serves 1h-stale fallback with `X-Cache: STALE` instead of hanging. |
| `/api/health/db` speed | `server.py` | Pings now run concurrently with 2s timeouts (was ~5.5s sequential). |
| docker-compose | `docker-compose.yml` | Mongo documented as required primary data layer; `REDIS_URL` wired. |

### Frontend (`MarketFlux/frontend/src/`)
| Change | File(s) | Notes |
|---|---|---|
| Floating Flux AI chatbot fixed | `App.js`, `components/AIChatbot.js` | Root cause: a TopNav rewrite deleted the button dispatching `marketflux:open-terminal`, and the drawer's own open button lived inside the lazy chunk (stale chunk = dead button). Fix: a global floating action button in `App.js` **outside** the lazy chunk + a `ChatErrorBoundary` with reload fallback. Removed the duplicated internal open button. |
| All 7 pilot components mounted | `components/pilot/PilotAutopilot.js` (new), `pages/Copilot.js` | Personalities, pending proposals, `GlassBoxTrade` dialog, consent gate — all reachable in the Copilot Auto-Pilot tab. `AdversarialDebate.js` was deliberately NOT deleted: `GlassBoxTrade` uses its debate tab. |
| Order ticket | `components/copilot/OrderTicket.js` (new), `pages/Copilot.js` | Symbol/side/qty/type/TIF with 2-step review→confirm, paper-only. Wired into the Portfolio tab. |
| Pending-approval hydration | `components/copilot/CopilotAgent.js` | Hydrates against `GET /api/copilot/trades/pending`; degrades gracefully if the backend route is absent. |
| Backtest disclaimer + real Python export | `pages/Backtest.js` | Disclaimer banner added. The Python export is now a genuine DSL→backtrader compiler (verified with `ast.parse` on 5 strategies); also fixed pre-existing broken docstring escaping and `datetime(2024, 01, 01)` leading-zero bugs. |
| Clear consent labels | `pages/Copilot.js` | Toggles now read "Confirm before trade" / "Execute automatically". |
| Route-level code splitting | `App.js` | Main bundle **422.95 kB → 169.5 kB gzipped (~60% smaller)**; 9 → 39 chunks. Measured with the dev CRACO config. |

### Docs / config
- `backend/.env.example`: `MONGO_URL`/`DB_NAME` now documented as required (they already were at runtime); new section for `TRADING_HALTED`, `ADMIN_TOKEN`, `COPILOT_CHAT_PER_MINUTE`, `REDIS_URL`.

---

## 2. Known tensions / open questions (do not "fix" unilaterally)

1. **Mongo required vs. AGENTS.md "legacy" framing.** Repo-root `AGENTS.md` says Supabase is primary and Mongo is legacy/optional. Reality on this branch: `server.py` hard-requires `MONGO_URL` at import (it did before this branch too — the old code was `os.environ['MONGO_URL']`), and `docker-compose.yml` treats Mongo as the required primary data layer. If the product direction is Supabase-first, someone needs to make Mongo genuinely optional with graceful degradation; until then, docs match the code.
2. **Kill switch does not cancel open orders.** Deliberate scope cut — halting stops new submissions only. If a "panic button" should also flatten positions, that is new work with real risk; discuss with Jashwanth first.
3. **Paper-only enforcement is by convention + UI copy**, not by a single runtime guard asserting `paper=true` on the Alpaca client. There is no live-money code path today, but a defense-in-depth assertion in `alpaca_client.py` would be cheap insurance before any real user touches this.
4. **`GET /api/copilot/trades/pending`** — the frontend hydrates against this contract; confirm the backend route exists and matches (it degrades gracefully if absent, but verify).

## 3. Suggested next work (ordered)

1. Push branch + open PR (blocked on GitHub auth — see below).
2. Reconcile the Mongo/Supabase story (item 1 above).
3. Add the paper-mode runtime assertion (item 3 above).
4. E2E smoke: boot backend + frontend, log in, run copilot chat → staged trade → approve → verify paper order on Alpaca paper dashboard; then engage kill switch and confirm 403s.
5. Re-measure frontend bundle after any new feature lands (baseline: 169.5 kB gzipped main).

## 4. To open the PR

```bash
cd ~/workspace/marketflux
gh auth login            # interactive — needs Jashwanth
git push -u origin god-tier-hardening
gh pr create --base main --head god-tier-hardening \
  --title "God-tier hardening: trading kill switch, compliance chokepoint, rate limiting, broker isolation + frontend fixes" \
  --body-file /tmp/pr_body.md
```

Suggested PR body is in `/tmp/pr_body.md` (generated alongside this handover; recreate from section 1 if missing).

## 5. Verify commands

```bash
# Backend unit tests (from MarketFlux/backend, using ./venv)
./venv/bin/python -m pytest -q
# Frontend tests + production-style build (from MarketFlux/frontend)
CI=true npx craco test --watchAll=false --passWithNoTests
CI=true npx craco build --config craco.config.dev.js
```
