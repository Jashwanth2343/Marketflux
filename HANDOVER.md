# Handover — MarketFlux Code Review & Fix Session

**Date:** 2026-05-25
**Branch:** `fix/craco-babel-stack-env-port`
**Commit scope:** Merge conflict resolution + 9 bug fixes from 5-angle code review

---

## What was done

### 1. Merge conflicts resolved (8 files)

| File | Resolution |
|------|-----------|
| `backend/vnext/pilot_router.py` | Took origin/main (HEAD had 4-arg call to 3-param `_safe_execute`) |
| `frontend/src/pages/Backtest.js` | Took HEAD (kept Strategy Studio sessionStorage handoff) |
| `frontend/src/pages/Copilot.js` | Took origin/main (command center dashboard approach) |
| `backend/backtest/runner.py` | Already resolved, staged |
| `backend/requirements.txt` | Already resolved, staged |
| `backend/vnext/alpaca_client.py` | Already resolved, staged |
| `backend/vnext/alpaca_router.py` | Already resolved, staged |
| `backend/vnext/pilot/pilot_engine.py` | Already resolved, staged |

### 2. Bugs fixed (found via 5-angle parallel code review)

#### Critical — Security
| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `server.py:61` | Hardcoded JWT secret (`"supabase-auth-primary-no-legacy-jwt"`) when Supabase is primary auth — anyone who reads the source can forge tokens | Replaced with `secrets.token_hex(32)` — unique per process |

#### Critical — Trading Correctness
| # | File | Bug | Fix |
|---|------|-----|-----|
| 2 | `alpaca_router.py:152` | Limit orders in broker mode went to shared account (if/elif checked order_type before broker mode) | Restructured: broker mode checked first, order type nested within |
| 3 | `alpaca_router.py:261` | `broker_close_position` ignored `qty` param — partial closes became full liquidations | Updated function signature + call site to forward `qty` |
| 4 | `pilot_router.py:450` | `execution_dispatched` hardcoded `True` even when Alpaca not configured — UI showed fake dispatch | Gated on `is_alpaca_configured()` |

#### High — Runtime Crashes
| # | File | Bug | Fix |
|---|------|-----|-----|
| 5 | `alpaca_client.py` | `get_clock()` function deleted but `copilot_trading_tools.py:116` still calls it — AttributeError | Restored the function |
| 6 | `alpaca_client.py:43` | `_get_trading_client()` had no `try/except` around `TradingClient` import — server crash if alpaca-py not installed | Added ImportError guard matching `_get_broker_client()` pattern |

#### High — Data Correctness
| # | File | Bug | Fix |
|---|------|-----|-----|
| 7 | `alpaca_client.py:94-97` | `or` chains treated `0.0` as falsy — flat positions showed wrong P&L | Replaced with `_first_set()` helper using `is not None` checks |
| 8 | `metrics.py:129` | `dd == 0` float equality — near-zero drawdowns could produce infinite Calmar ratios | Changed to `abs(dd) < 1e-12` |

#### Medium — Performance
| # | File | Bug | Fix |
|---|------|-----|-----|
| 9 | `server.py:234` | `client.auth.get_user(token)` is synchronous — blocks FastAPI event loop on every auth check | Wrapped in `asyncio.to_thread()` |

### 3. Frontend

- Installed missing `@supabase/supabase-js` (was in package.json but not in node_modules; requires `--legacy-peer-deps` due to peer conflicts)
- Cleaned unused imports (`ListChecks`, `ChevronRight`) from Copilot.js
- Verified `npx craco build` passes

---

## Known issues NOT fixed (require design decisions)

| Issue | Location | Why not fixed |
|-------|----------|---------------|
| **TOCTOU race on broker sub-account creation** | `alpaca_router.py:79` | Needs atomic upsert pattern — architectural decision |
| **Broker mode isolation gaps** | `alpaca_router.py` | `GET /orders/{id}`, `DELETE /orders`, `POST /positions/liquidate` use shared client in broker mode — needs new broker-mode functions |
| **`datetime.utcnow()` deprecated** | `alpaca_client.py:440` | Low-risk; should migrate to `datetime.now(timezone.utc)` |
| **FinBERT removal** | `ai_service.py` | `analyze_sentiments_batch` was deleted — verify no live callers |
| **yfinance licensing** | all market data | yfinance ToS may not permit commercial use — need a commercial data provider |
| **Integration tests silently skip** | `test_p0_features.py:8` | Tests skip when `REACT_APP_BACKEND_URL` not set — CI may have zero coverage |

---

## How to verify

```bash
# Backend — all files compile
cd MarketFlux/backend
python3 -c "import py_compile, glob; [py_compile.compile(f, doraise=True) for f in glob.glob('**/*.py', recursive=True)]"

# Frontend — clean build
cd MarketFlux/frontend
npm install --legacy-peer-deps
CI=true REACT_APP_BACKEND_URL=http://localhost:8001 npx craco build

# No conflict markers
git diff --check
```

---

## Next steps (recommended priority)

1. **Fix broker mode isolation gaps** — cancel-all, liquidate-all, get-order need broker-mode branches
2. **Add TOCTOU guard** on sub-account creation (MongoDB findOneAndUpdate with upsert)
3. **Replace yfinance** with a commercial data provider before any paid users
4. **Set up CI** with `REACT_APP_BACKEND_URL` so integration tests actually run
5. **Migrate `datetime.utcnow()`** to `datetime.now(timezone.utc)` across the codebase
