# MarketFlux Quant App

This is the new `Next.js` product shell for the MarketFlux vNext quant research experience.

## What it includes

- Public site pages:
  - `/`
  - `/product`
  - `/pricing`
  - `/compare`
  - `/features/[slug]`
  - `/vs/[slug]`
  - `/alternatives/bloomberg-terminal`
- Product app pages:
  - `/briefing`
  - `/signals`
  - `/research/[ticker]`
  - `/research/compare`
  - `/watchlists`
  - `/portfolio`
  - `/settings`
  - `/methodology`

## Backend integration

The app expects a FastAPI backend exposing the new `vnext` endpoints:

- `/api/vnext/briefing/today`
- `/api/vnext/signals/feed`
- `/api/vnext/research/ticker/{ticker}`
- `/api/vnext/watchlists/board`
- `/api/vnext/portfolio/diagnostics`
- `/api/vnext/compare`

Set:

```bash
MARKETFLUX_API_URL=http://localhost:8001
```

If the backend is unavailable, the UI falls back to static preview data so the shell still renders.

