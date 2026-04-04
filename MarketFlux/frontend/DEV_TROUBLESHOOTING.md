# Dev Troubleshooting

## Local ports (MarketFlux)

| Service | Default port | Notes |
|--------|--------------|--------|
| CRA frontend (`yarn start`) | **3000** | Set `REACT_APP_BACKEND_URL` (e.g. `http://localhost:8001`) so API calls hit the backend. |
| FastAPI backend (`uvicorn server:app --port 8001`) | **8001** | CORS uses `ALLOWED_ORIGINS`; default includes `http://localhost:3000`. |
| Next.js quant-app (`npm run dev`) | **3000** | Conflicts with CRA if both run at once; use `PORT=3001 npm run dev`. Uses `MARKETFLUX_API_URL` (default `http://localhost:8001`). |
| Redis (optional cache) | **6379** | `REDIS_HOST` / `REDIS_PORT` in backend `.env`. |
| Postgres (docker-compose.vnext) | **5432** | Only when you run `docker compose -f docker-compose.vnext.yml up`. |

## Frontend changes not showing

1. **Hard refresh** – `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows) to bypass cache
2. **Restart dev server** – Stop (`Ctrl+C`) and run `yarn start` again (cached bundles can persist)
3. **Clear browser cache** – DevTools → Application → Clear storage
4. **Confirm dev mode** – You should see hot-reload messages in the terminal when editing `src/` files

## Slow initial load

- **AIChatbot** is lazy-loaded; it only loads when the chat panel is opened
- **External scripts** (emergent, PostHog) load with `defer` so they don’t block rendering
- First load may still be slow due to large bundles (Recharts, Radix UI, etc.)

