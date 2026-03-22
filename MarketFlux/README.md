# MarketFlux
AI-powered investment research platform with real-time stock data, natural language stock screener, AI chat assistant, news aggregation with sentiment analysis, and portfolio management.

[Live Demo](#)

## Architecture
```
┌─────────────────────────────────────┐
│     React Frontend (Port 3000)      │
│   Tailwind + Shadcn/UI + Recharts   │
└────────────────┬────────────────────┘
                 │ HTTP / SSE
┌────────────────▼────────────────────┐
│     FastAPI Backend (Port 8001)     │
│  server.py + ai_service.py +        │
│  market_data.py + news_scraper.py   │
└───┬──────────────────────┬──────────┘
    │                      │
┌───▼──────┐    ┌──────────▼──────────┐
│ MongoDB  │    │   External APIs     │
│ (Atlas)  │    │ • Gemini 2.5 Flash  │
│          │    │ • yfinance          │
└──────────┘    │ • RSS Feeds (7)     │
                └─────────────────────┘
```

## Tech Stack
| Layer | Technologies |
|-------|--------------|
| Frontend | React, Tailwind CSS, Shadcn/UI, Recharts |
| Backend | FastAPI, Python 3.10+, motor (asyncio MongoDB) |
| Database | MongoDB Atlas |
| AI | Google Gemini 2.5 Flash |

## Features
- AI Chat Assistant
- Natural Language Stock Screener
- Real-time News Feed
- Sentiment Analysis
- Portfolio Management
- Watchlists
- Market Overview Dashboard

## vNext Quant Research OS

This repo now also includes a parallel `vNext` foundation for the public AI-native quant research product:

- `backend/vnext/` for new research engines and `/api/vnext/*` routes
- `backend/sql/vnext_pgvector_schema.sql` for the planned Postgres + pgvector schema
- `docker-compose.vnext.yml` for local Postgres/Redis infrastructure
- `quant-app/` for the new `Next.js` product shell

See [VNEXT_IMPLEMENTATION.md](/Users/jashwanthkanderi/Downloads/Financegptwebdashboard-main/MarketFlux/VNEXT_IMPLEMENTATION.md) for the implementation overview.

## Local Setup
1. Clone the repository: `git clone https://github.com/Jashwanth2343/MarketFlux_v1.git`
2. Install Backend Dependencies: `cd backend && pip install -r requirements.txt`
3. Install Frontend Dependencies: `cd frontend && yarn install`
4. Configure `.env` files (see Environment Variables below).
5. Run Backend: `cd backend && uvicorn server:app --reload --port 8001`
6. Run Frontend: `cd frontend && yarn start` (runs on Port 3000)

## Environment Variables
Create a `.env` file in the `backend/` directory with the following keys:
- `MONGO_URL`: MongoDB connection string 
- `DB_NAME`: MongoDB database name
- `EMERGENT_LLM_KEY`: API key for Gemini 2.5 Flash
- `JWT_SECRET_KEY`: Strong randomly generated 32-character hex for session tokens
- `ALLOWED_ORIGINS`: Comma separated list of allowed CORS origins (e.g. `http://localhost:3000`)

## Known Limitations & Future Improvements
- yfinance is a scraper, not an official API — would replace with Polygon.io or Finnhub in production for reliability.
- In-memory caching replaced with diskcache — Redis/ElastiCache would be the production choice for multi-instance deployments.
- AI chat uses conversation history window — full RAG with ChromaDB vector database would improve context quality.
- No automated test coverage — would add pytest for backend and React Testing Library for frontend.
- Single server deployment — would containerize with Docker and deploy on AWS ECS or Cloud Run for scalability.

## What I Learned
Building MarketFlux taught me how to architect production-ready FastAPI applications with async MongoDB drivers, avoiding blocking calls with background executors. I gained deep experience integrating live LLM streams directly into a React frontend using Server-Sent Events (SSE). Working with real-time, unstructured financial data sources like RSS feeds and yfinance exposed me to the challenges of data deduplication, rate limiting, and defensive error handling. Finally, I learned how to identify architectural bottlenecks, such as replacing unbounded context windows with sliding token management and moving from entirely in-memory caching to persistent solutions.
