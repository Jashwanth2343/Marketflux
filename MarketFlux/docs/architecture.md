# MarketFlux System Architecture

## Product Vision
An agentic trading cockpit where every AI idea becomes a traceable, backtestable, approval-gated trading workflow.

## Navigation (6 items)

| Route | Page | Purpose |
|-------|------|---------|
| `/` | Dashboard | Market overview, portfolio summary, key alerts |
| `/intelligence` | Intelligence Hub | News, Screener, Research, Macro, Theses (sub-tabs) |
| `/copilot` | Trading Copilot | AI copilot chat, Strategy Studio, Proposals, Paper Portfolio (sub-tabs) |
| `/backtest` | Backtest Lab | Strategy DSL editor, equity curves, walk-forward analysis |
| `/portfolio` | Portfolio & Risk | Holdings, Risk Analytics (sub-tabs) |
| `/leaderboard` | Leaderboard | Pilot personality rankings, public profiles |

## Service Architecture

```
Frontend (React, port 3000)
    |
    v
FastAPI Backend (port 8001)
    |
    +-- MongoDB (auth, users, pilot state, chat, news)
    +-- Supabase Postgres (theses, strategies, paper trades, agent runs, backtests)
    +-- Redis (market data cache, session cache)
    +-- LLM Router (Gemini, Nvidia NIM, OpenRouter)
    +-- Alpaca Trading API (paper trading execution)
    +-- LangGraph (agent workflow orchestration)
```

## Data Layer

| Store | Purpose | Key Collections/Tables |
|-------|---------|----------------------|
| MongoDB | Auth, user profiles, pilot personalities, activity events, chat history | users, pilot_personalities, pilot_trade_proposals, pilot_activity_events, chat_messages, news_articles |
| Supabase Postgres | Durable trading/research state | theses, thesis_revisions, evidence_blocks, paper_trades, strategy_proposals, terminal_sessions, agent_runs, backtest_runs |
| Redis | Cache layer | Market data (1h TTL), API response cache (5min TTL) |

## Agent Architecture

### Strategy Swarm (5 agents + synthesis)
```
User Prompt + Macro Regime Context
    |
    v  (parallel via LangGraph fan-out)
+-- Bull Case Agent
+-- Bear Case Agent
+-- Value Agent
+-- Momentum Agent
+-- Risk Officer
    |
    v  (synthesis via reasoning model)
Structured Verdict (VERDICT/CONVICTION/ENTRY/TARGET/STOP/SIZE/THESIS)
```

### Trade Lifecycle
```
Signal/Research → Thesis → Backtest → Agent Debate → Policy Check
    → Human Approval → Paper Execution → Monitoring → Journal
```

### Copilot Approval Flow
1. AI generates trade proposal (backend)
2. Frontend renders proposal with approve/reject buttons
3. User approves → backend re-checks policy + account state
4. Backend submits Alpaca order server-side
5. Audit trail persisted to Supabase

## API Prefixes

| Prefix | Router | Purpose |
|--------|--------|---------|
| `/api/` | api_router | Market data, news, sentiment, AI chat, portfolio, research, risk |
| `/api/vnext/` | vnext_router | Theses, evidence, memos, policies, paper trades |
| `/api/fundos/` | fundos_router | Fund OS terminal, strategy queue, paper portfolio |
| `/api/alpaca/` | alpaca_router | Alpaca paper trading bridge |
| `/api/pilot/` | pilot_router | AI personality management, proposals, journal, drift |
| `/api/backtest/` | backtest_router | Strategy backtesting engine |
| `/api/health/` | (inline) | DB health checks |

## Tech Stack

- **Frontend**: React (CRA + Craco), shadcn/ui (48 components), Tailwind CSS, Recharts, Framer Motion
- **Backend**: FastAPI, asyncpg, Motor (MongoDB), httpx
- **AI**: Google Gemini (primary), Nvidia NIM, OpenRouter, FinBERT sentiment, LangGraph
- **Database**: Supabase Postgres (pgvector), MongoDB Atlas, Redis
- **Broker**: Alpaca Trading API (paper mode)
