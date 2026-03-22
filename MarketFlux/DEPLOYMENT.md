# MarketFlux Deployment Guide

Deploy MarketFlux (React frontend + FastAPI backend) to production.

## Prerequisites

- **MongoDB Atlas** – [Create a free cluster](https://www.mongodb.com/atlas)
- **Google Gemini API key** – [Get one here](https://makersuite.google.com/app/apikey)
- **JWT secret** – Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"`

---

## Option 1: Docker Compose (Self-Hosted / VPS)

Best for: DigitalOcean, AWS EC2, Linode, or any VPS.

### 1. Prepare environment

```bash
cd MarketFlux

# Backend secrets (required)
cp backend/.env.example backend/.env
# Edit backend/.env: set MONGO_URL, DB_NAME, GEMINI_API_KEY, JWT_SECRET

# For docker-compose build
cp .env.example .env
# Edit .env: set REACT_APP_BACKEND_URL to your backend URL
# For same-host: http://YOUR_SERVER_IP:8001 or https://api.yourdomain.com
```

### 2. Deploy

```bash
docker compose up -d
```

- Frontend: http://localhost:3000  
- Backend API: http://localhost:8001  

### 3. Update CORS

In `backend/.env`, set:

```
ALLOWED_ORIGINS=https://yourdomain.com,http://yourdomain.com
```

---

## Option 2: Render

Best for: Simple deploy with free tiers.

### Backend (Web Service)

1. [Render Dashboard](https://dashboard.render.com) → **New** → **Web Service**
2. Connect your repo, set **Root Directory**: `MarketFlux`
3. **Build**:
   - Build Command: `pip install -r backend/requirements.txt`
   - Start Command: `uvicorn server:app --host 0.0.0.0 --port $PORT` (run from `backend/`)
   - Or use a Dockerfile: set **Dockerfile Path** to `MarketFlux/backend/Dockerfile`

4. **Environment** (Required):
   - `MONGO_URL`
   - `DB_NAME`
   - `GEMINI_API_KEY`
   - `JWT_SECRET`
   - `ALLOWED_ORIGINS` = `https://your-frontend.onrender.com`

5. Deploy. Note the backend URL (e.g. `https://marketflux-api.onrender.com`).

### Frontend (Static Site)

1. **New** → **Static Site**
2. Root Directory: `MarketFlux/frontend`
3. Build Command: `yarn install && yarn build` (or `npm ci && npm run build`)
4. Publish Directory: `build`
5. **Environment**:
   - `REACT_APP_BACKEND_URL` = your backend URL (e.g. `https://marketflux-api.onrender.com`)

---

## Option 3: Railway

Best for: Full-stack with minimal config.

1. [Railway](https://railway.app) → **New Project** → **Deploy from GitHub**
2. Add two services from the same repo:
   - **Backend**: Root `MarketFlux/backend`, use `Dockerfile`, expose port 8001
   - **Frontend**: Root `MarketFlux/frontend`, build with Dockerfile (or `yarn build`), expose 80

3. Set env vars for backend (same as Render).
4. Set `REACT_APP_BACKEND_URL` for frontend = Railway backend URL.
5. Railway will assign public URLs to both services.

---

## Option 4: Vercel (Frontend) + Render/Railway (Backend)

Best for: Using Vercel for the frontend.

### Backend

Deploy to Render or Railway as in Option 2 or 3.

### Frontend (Vercel)

1. [Vercel](https://vercel.com) → **Import** your repo
2. Root Directory: `MarketFlux/frontend`
3. Framework Preset: Create React App
4. **Environment Variable**: `REACT_APP_BACKEND_URL` = your backend URL
5. Deploy

---

## Environment Reference

| Variable | Where | Required | Description |
|----------|-------|----------|-------------|
| `MONGO_URL` | Backend | Yes | MongoDB connection string |
| `DB_NAME` | Backend | Yes | Database name (e.g. `MarketFlux`) |
| `GEMINI_API_KEY` | Backend | Yes | Google Gemini API key |
| `JWT_SECRET` | Backend | Yes | 64-char hex (from `secrets.token_hex(32)`) |
| `ALLOWED_ORIGINS` | Backend | Yes | Comma-separated frontend origins |
| `REACT_APP_BACKEND_URL` | Frontend (build) | Yes | Backend API URL, no trailing slash |
| `REDIS_HOST` | Backend | No | Redis host (optional caching) |

---

## Quick Local Test (Docker)

```bash
cd MarketFlux
cp backend/.env.example backend/.env
# Fill in MONGO_URL, DB_NAME, GEMINI_API_KEY, JWT_SECRET in backend/.env
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
docker compose up --build
```

Open http://localhost:3000
