# MarketFlux vNext Implementation Notes

This repo now contains a parallel vNext foundation for the public AI-native quant research product.

## Backend additions

- `backend/vnext/router.py`
- `backend/vnext/engines.py`
- `backend/vnext/repository.py`
- `backend/vnext/schemas.py`
- `backend/sql/vnext_pgvector_schema.sql`

New FastAPI routes are mounted at:

- `/api/vnext/briefing/today`
- `/api/vnext/signals/feed`
- `/api/vnext/research/ticker/{ticker}`
- `/api/vnext/watchlists/board`
- `/api/vnext/portfolio/diagnostics`
- `/api/vnext/compare`
- `/api/vnext/methodology`
- `/api/vnext/theses`

The runtime still uses the existing Mongo-backed app as a compatibility layer, but the repo now also contains a Postgres + pgvector schema for the planned strategic data model.

## NemoClaw integration seam

- `backend/vnext/nemoclaw_bridge.py` is a thin future bridge client.
- Expected environment variables:
  - `NEMOCLAW_BASE_URL`
  - `NEMOCLAW_BEARER_TOKEN`

This keeps the research architecture ready for a sandboxed external agent service without making the first vNext slice depend on it.

## Frontend additions

- The vNext research/thesis surfaces are served by the main CRA app in `frontend/`
  (Intelligence → Theses, Portfolio & Risk, etc.) via the `/api/vnext/*` routes.
- A standalone `Next.js` `quant-app/` shell previously hosted a public
  marketing/research site against the same backend; it has since been retired and
  removed in favor of consolidating everything into the main `frontend/` app.

## Local infrastructure

- `docker-compose.vnext.yml` adds:
  - Postgres with pgvector
  - Redis

This is the intended vNext local foundation for the quant research architecture.

## Practical next step

If you already have a running NemoClaw/NIM instance, the cleanest follow-up is to add a bridge service behind the new research endpoints instead of wiring it directly into the legacy chat surface.
