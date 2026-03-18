# Market Flux - Product Requirements Document

## Original Problem Statement
Build a real-time financial news and sentiment analysis platform called "Market Flux" that aggregates news, performs AI-driven sentiment analysis, provides stock screening via natural language, AI chatbot, portfolio rebalancing, and rich stock detail pages.

## Tech Stack
- **Frontend:** React, Tailwind CSS, Shadcn/UI, Recharts
- **Backend:** FastAPI, Pydantic
- **Database:** MongoDB (via Motor async driver)
- **Data Source:** yfinance library (including yf.Search API)
- **AI/LLM:** Google Gemini API (via Emergent LLM Key)
- **Auth:** JWT + Emergent-managed Google OAuth

## Core Features

### Completed
- [x] Dashboard with market indices, top gainers/losers, news headlines (2-col grid), market mood
- [x] News Feed with filtering, 3-column responsive grid layout with thumbnails
- [x] Sentiment Analysis on news articles (bullish/bearish/neutral via Gemini)
- [x] Stock Detail Pages with charts, stats, fundamentals, news grid with thumbnails, AI insight box
- [x] AI Chatbot - persistent, context-aware, grounded in real data
- [x] **AI Screener** - NLQ → structured filter JSON → backend filtering → results table + filter chips + AI summary
- [x] **Global Search Bar** - Yahoo Finance-style, company name search via yf.Search API, shows symbol/name/type/exchange, Ctrl+K shortcut
- [x] **News Thumbnails + Grid Layout** - Responsive grid on Dashboard (2-col), News Feed (3-col), Stock Detail (3-col) with thumbnail images from yfinance
- [x] Portfolio endpoint scaffolding (save/load/rebalance)
- [x] JWT Auth + Google OAuth integration
- [x] Retrofuturism dark-mode design theme

### P1 - Upcoming
- [ ] Portfolio Rebalancing UI - full feature with holdings input, AI-driven analysis, rebalancing suggestions
- [ ] Finalize Authentication - rate-limiting for guests, user management UI
- [ ] Saved News Streams - save/manage custom news filter configurations

### P2 - Future
- [ ] Alerts System - notifications for significant sentiment shifts
- [ ] Advanced Data Pipeline - replace yfinance-only with dedicated news API
- [ ] Vector DB for semantic search

## Architecture
```
/app/
├── backend/
│   ├── .env (MONGO_URL, DB_NAME, EMERGENT_LLM_KEY)
│   ├── server.py (FastAPI routes, auth, middleware)
│   ├── ai_service.py (Gemini LLM: chat, screener filters, summaries, sentiment)
│   ├── market_data.py (yfinance data, filtering, search, news with thumbnails)
│   └── news_scraper.py (RSS feed parsing with thumbnail extraction)
├── frontend/
│   ├── src/
│   │   ├── App.js (router, layout with persistent search header)
│   │   ├── components/SearchBar.js - Yahoo Finance-style search
│   │   ├── components/NewsCard.js - Reusable news card with thumbnails
│   │   ├── components/Sidebar.js, AIChatbot.js
│   │   ├── pages/Dashboard.js, NewsFeed.js, StockDetail.js, AIScreener.js, Portfolio.js, Auth.js
│   │   └── contexts/AuthContext.js
```

## Key API Endpoints
- `GET /api/search-stocks?q=` - Global search via yfinance Search API (company name, ticker, exchange, type)
- `POST /api/ai/screen` - AI Screener (NLQ → filter JSON → filtered results + summary)
- `GET /api/market/overview` - Dashboard market indices
- `GET /api/market/movers` - Top gainers/losers
- `GET /api/market/stock/{ticker}/rich` - Comprehensive stock data
- `GET /api/market/chart/{ticker}` - Chart time-series
- `GET /api/news/ticker/{ticker}` - Stock news with thumbnails
- `GET /api/news/feed` - News feed with filters
- `POST /api/ai/chat` - AI Chatbot
- `POST /api/auth/register`, `/login`, `/google-session`, `/logout`
