# MarketFlux Copilot — Feature & UI Development Specification

**Project:** MarketFlux — AI-Powered Quantitative Trading Platform
**Document Type:** Agent Development Brief
**Version:** 1.0
**Date:** May 2026
**Scope:** Copilot feature completion + platform-wide UI upgrades

---

## Overview

MarketFlux is an AI-powered quantitative trading and financial analysis platform. The core Copilot feature allows users to interact with an AI agent that monitors the market, analyzes portfolios, and executes paper trades via the Alpaca broker API. The backend is built with FastAPI, the frontend with React, and the agent layer uses LangChain/LangGraph with Claude (Anthropic) as the LLM.

The platform currently has the following working:
- Alpaca paper trading account integration (live equity, cash, open positions)
- TradingView ticker tape widget (real-time market prices)
- Copilot chat UI with suggested prompt templates
- Navigation shell: Dashboard, Intelligence, Copilot, Backtest, Portfolio, Leaderboard

This document defines all **remaining features to build** and **UI improvements to make** across the platform.

---

## Part 1: Critical Features (Blockers for Beta)

These must be completed before the product can be shared with early users.

---

### 1.1 Agent Step Visibility (Chain-of-Thought Panel)

**What:** Every Copilot response must show the agent's reasoning steps alongside its final answer.

**Why:** Traders will not trust an AI that gives recommendations without showing its work. This is the #1 trust-building feature.

**Behavior:**
- When a user sends a prompt, the agent streams its steps in real time in a collapsible panel beneath each message bubble.
- Steps include: data fetched, analysis performed, tools called, trade parameters evaluated, final decision rationale.
- Each step has an icon (🔍 Research, 📊 Analysis, ⚙️ Execution, ✅ Complete, ⚠️ Warning).
- The panel is collapsed by default but expands on click.

**Implementation notes:**
- Use LangGraph's `StreamEvent` API to stream step updates to the frontend via FastAPI WebSocket or SSE (Server-Sent Events).
- Each event should carry: `step_type`, `step_label`, `data_summary`, `timestamp`.
- Frontend: React component `<AgentStepTrace />` that renders a vertical timeline of steps.

**Acceptance criteria:**
- [ ] Agent steps are streamed and visible per message in the UI
- [ ] Steps collapse/expand cleanly
- [ ] No step is missing from the trace (all tool calls are logged)

---

### 1.2 Trade Confirmation Modal (Approve / Reject)

**What:** Before any trade is executed — even on the paper account — the user must see a confirmation modal and explicitly approve or reject it.

**Why:** Builds user control, prevents accidental trades, and mirrors real brokerage UX (TD Ameritrade, Alpaca web).

**Behavior:**
- Agent proposes a trade: "I want to BUY 10 shares of NVDA at market price (~$XXX.XX). Estimated cost: $X,XXX."
- A modal appears with: Ticker, Action (BUY/SELL), Quantity, Order Type, Estimated Price, Estimated Total, Agent Rationale (2-sentence summary).
- Two buttons: **Approve Trade** (green) and **Reject** (ghost/outline).
- On approve: order is submitted to Alpaca via the backend. On reject: agent is notified and logs the rejection.
- After execution: show order confirmation with order ID, filled price, timestamp.

**Implementation notes:**
- Backend: `POST /api/trades/propose` returns trade proposal object. `POST /api/trades/execute` actually submits to Alpaca only after frontend approval.
- Frontend: `<TradeConfirmModal />` React component, triggered by a `trade_proposal` event in the WebSocket/SSE stream.
- Alpaca API: Use `alpaca.submit_order()` with `paper=True`. Handle errors: `insufficient_funds`, `market_closed`, `invalid_symbol`.

**Acceptance criteria:**
- [ ] No trade executes without user confirmation
- [ ] Modal shows all relevant order details
- [ ] Errors are shown inline in the modal (not silent failures)
- [ ] Order confirmation screen shows after successful execution

---

### 1.3 Streaming Response with Step Indicators

**What:** Replace the current static "send message → wait → full response appears" flow with live streaming output.

**Why:** A trading copilot feels laggy and untrustworthy if users stare at a blank screen for 5–10 seconds. Streaming makes it feel responsive and alive.

**Behavior:**
- As soon as the user submits a prompt, a status bar appears below the input: "🔍 Researching market data…" → "📊 Analyzing your portfolio…" → "⚙️ Sizing the trade…" → "✅ Done"
- The text response streams token-by-token (typewriter effect).
- Step labels transition automatically as the agent progresses through LangGraph nodes.

**Implementation notes:**
- Backend: Use FastAPI `StreamingResponse` or WebSocket to push token chunks + step events.
- Frontend: React streaming renderer using `ReadableStream` or WebSocket `onmessage`.
- Step labels map to LangGraph node names: configure a `STEP_LABEL_MAP` dict in the backend.

**Acceptance criteria:**
- [ ] Response streams visibly, token by token
- [ ] Step indicator transitions in real time
- [ ] No loading spinner that shows nothing — always something moving

---

### 1.4 Graceful Error Handling

**What:** The agent must handle and display all failure modes gracefully.

**Failure scenarios to handle:**

| Scenario | User-Facing Message |
|---|---|
| Market is closed | "Markets are closed right now. This trade will execute at the next market open if you approve." |
| Invalid ticker symbol | "I couldn't find a ticker for '[X]'. Did you mean one of these? [suggestions]" |
| Alpaca API timeout | "The broker API is taking too long to respond. Retry?" |
| LLM API error | "The AI service is temporarily unavailable. Your message has been saved — try again in a moment." |
| Insufficient paper funds | "Your paper account doesn't have enough cash for this trade. Current available: $X,XXX." |
| Position not found | "You don't currently hold any [X] shares. Want me to open a new position instead?" |

**Implementation notes:**
- Wrap all Alpaca calls in try/except blocks, return structured error objects: `{ "error_type": "...", "message": "...", "recoverable": true/false }`.
- Frontend: error messages render inline in the chat thread, styled with `--color-warning` or `--color-error` tokens, never as raw error codes.
- Add a "Retry" button on recoverable errors.

**Acceptance criteria:**
- [ ] All 6 error scenarios above are handled and tested
- [ ] No raw stack traces or API error codes shown to the user
- [ ] Recoverable errors have a Retry action

---

## Part 2: Important Features (Pre-Launch Polish)

---

### 2.1 Conversational Memory Across Sessions

**What:** The Copilot should remember what the user has discussed in previous sessions.

**Why:** Without memory, every conversation starts from zero. A copilot that remembers "last week you bought AAPL because of earnings" is dramatically more useful.

**Behavior:**
- Agent has access to a summarized memory of the last N conversations (configurable, default: last 10 sessions).
- Memory includes: trades executed, strategies discussed, user-stated preferences ("I prefer swing trades over day trades"), watchlist stocks mentioned.
- Memory is surfaced when relevant: "Based on your previous sessions, you've been building a position in semiconductors. Want me to factor that in?"

**Implementation notes:**
- Use LangGraph's `MemorySaver` or a MongoDB collection `copilot_memory` per user.
- On each session start, fetch the last N session summaries and inject into the system prompt context window.
- On session end, use the LLM to auto-summarize the conversation into 3–5 bullet points and store.
- Schema: `{ user_id, session_id, timestamp, summary: string[], trades_executed: [], tickers_mentioned: [] }`

**Acceptance criteria:**
- [ ] Agent references relevant prior context naturally
- [ ] Memory does not bloat the context window (summaries only, not raw transcripts)
- [ ] User can view and clear their memory from a settings panel

---

### 2.2 Position Detail Enrichment

**What:** The portfolio sidebar in the Copilot should show richer position data.

**Current state:** Shows ticker, shares, price, unrealized P&L.

**Add:**
- Entry date and days held
- % of total portfolio
- Sector / Industry tag (e.g., "Technology – Semiconductors")
- 7-day mini price sparkline chart
- Analyst consensus rating (Buy / Hold / Sell) from Alpha Vantage or similar

**Implementation notes:**
- Backend: Enrich position data from `GET /v2/positions` (Alpaca) with yFinance `Ticker.info` for sector, market cap, analyst ratings.
- Frontend: Redesign the position card component. Use a tiny SVG sparkline (D3 or Recharts `<Sparkline />`).

**Acceptance criteria:**
- [ ] All enriched fields populated for current positions
- [ ] Sparkline renders cleanly at small size
- [ ] Loads within 2 seconds of page render (cache enrichment data, TTL: 15 minutes)

---

### 2.3 Auto-Pilot Tab (Scheduled Agent Runs)

**What:** Users define a standing instruction ("Every Monday at market open, screen for high-momentum S&P 500 stocks and buy the top pick with 2% of portfolio") and the agent runs it automatically on a schedule.

**Behavior:**
- User creates an "Auto-Pilot Strategy" via a form: name, natural language instruction, schedule (cron-style or plain language: "every Monday at 9:30am ET"), account allocation limit.
- Strategies appear in a list with status (Active / Paused / Draft), last run time, next run time, last action taken.
- Each run generates an activity log entry visible in the Copilot chat history.
- User can pause, edit, or delete any strategy.

**Implementation notes:**
- Backend: Store strategies in MongoDB `autopilot_strategies` collection.
- Scheduling: Use APScheduler (or Celery Beat) to run strategies on their defined schedule.
- Agent execution: Reuse the Copilot LangGraph agent but invoked programmatically (no user input required).
- On completion, push a WebSocket notification to the frontend.

**Schema:**

```json
{
  "strategy_id": "uuid",
  "user_id": "...",
  "name": "Monday Momentum Scanner",
  "instruction": "Screen S&P 500 for top momentum...",
  "schedule": "0 9 * * 1",
  "allocation_pct": 2.0,
  "status": "active",
  "last_run": "2026-05-19T09:30:00Z",
  "next_run": "2026-05-26T09:30:00Z",
  "activity_log": []
}
```

**Acceptance criteria:**
- [ ] Strategies run on schedule without manual trigger
- [ ] Activity log is populated after each run
- [ ] Strategies can be paused and resumed
- [ ] Max concurrent strategies: 5 (enforce in backend)

---

### 2.4 Backtest Tab — Strategy Backtesting Engine

**What:** Users input a strategy in natural language or structured parameters, and the system runs a historical backtest.

**Behavior:**
- Input panel: Strategy description (NL or structured), ticker(s), date range, starting capital.
- The LLM converts the NL strategy into backtestable rules (entry signal, exit signal, position size).
- Backend runs the backtest using historical OHLCV data (yFinance).
- Output panel: Equity curve chart, key metrics table (Total Return, Sharpe Ratio, Max Drawdown, Win Rate, # Trades), trade log.

**Implementation notes:**
- Use `yfinance.download()` for historical data.
- Build a simple event-driven backtesting loop in Python (or integrate `backtesting.py` library).
- LLM parses NL strategy into a structured `BacktestConfig` object (entry conditions, exit conditions, stop loss, take profit).
- Frontend: Recharts `<LineChart />` for equity curve. Metrics in a summary card grid.

**Key metrics to display:**

| Metric | Definition |
|---|---|
| Total Return | (End equity − Start equity) / Start equity |
| Annualized Return | Geometric annualized from total return |
| Sharpe Ratio | (Mean daily return − risk-free rate) / StdDev of daily returns |
| Max Drawdown | Largest peak-to-trough decline |
| Win Rate | % of trades that were profitable |
| Avg Trade Duration | Mean holding period in days |

**Acceptance criteria:**
- [ ] NL strategy is correctly parsed into backtestable rules
- [ ] Backtest runs in < 30 seconds for 1-year range
- [ ] All 6 metrics computed and displayed
- [ ] Equity curve chart renders correctly

---

## Part 3: UI Upgrades

---

### 3.1 Copilot Chat Interface

**Current issues:**
- No streaming / typewriter effect (messages appear all at once)
- No visible step trace per message
- Suggested prompts disappear after first message (should persist as a collapsible panel)
- Portfolio sidebar lacks depth (see Section 2.2)

**Required changes:**
- Implement token streaming (typewriter effect) for all AI responses
- Add collapsible `<AgentStepTrace />` panel per AI message bubble
- Add a "Suggested Prompts" toggle button that opens a flyout of pre-written prompts, always accessible
- AI message bubbles: add a copy-to-clipboard icon, a thumbs-up/thumbs-down feedback button
- Human message bubbles: show timestamp and edit icon (allow editing and re-sending)
- Empty state: when chat history is empty, show a centered animated welcome card with 4 suggested prompts in a 2×2 grid

---

### 3.2 Navigation & Layout

**Current issues:**
- Active page indicator in nav could be stronger
- No user profile / account info visible anywhere
- Mobile responsiveness not verified

**Required changes:**
- Nav active state: add a left-border accent (3px, `--color-primary`) and slightly bolder font weight on the active item
- Add a user avatar + dropdown in the top-right header: shows account name, paper/live toggle, logout
- Add a **Paper Trading** badge (yellow pill) prominently in the header so users always know they are in paper mode
- Ensure all pages collapse correctly at 375px width (test each tab)

---

### 3.3 Portfolio Page

**Required additions:**
- Holdings table with columns: Ticker, Company Name, Sector, Shares, Avg Cost, Current Price, Market Value, Unrealized P&L ($), Unrealized P&L (%), 7-Day Sparkline
- Portfolio allocation pie chart (by sector)
- Performance chart: portfolio equity curve over time vs. S&P 500 benchmark
- Realized P&L history table (closed positions)

---

### 3.4 Dashboard Page

**Required additions:**
- Market Overview section: S&P 500, Nasdaq, BTC mini-cards with 1D change, 5D sparkline
- Watchlist widget: user-curated list of tickers with real-time price + % change
- Top Movers section: top 5 gainers and top 5 losers today (from a curated universe)
- News feed: latest headlines for watchlist stocks (from Alpha Vantage News or similar)
- Quick-action buttons: "Ask Copilot", "Run Backtest", "View Portfolio"

---

### 3.5 Global Design System Consistency

Apply these fixes across all pages:

| Issue | Fix |
|---|---|
| Inconsistent card padding | Standardize all cards to `padding: var(--space-6)` |
| Mixed border styles | Use only `1px solid oklch(from var(--color-text) l c h / 0.10)` for all card borders |
| No skeleton loaders on data-fetching views | Add shimmer skeleton for all async data (positions, charts, news) |
| No empty states on unfilled sections | Add illustrated empty states with a CTA for every data panel |
| No toast/notification system | Implement a global toast system for: trade executed, agent completed, error occurred |
| Dark mode inconsistency | Audit all pages in dark mode, ensure every surface token is applied (no hardcoded colors) |

---

## Part 4: Technical Debt & Infrastructure

---

### 4.1 WebSocket / SSE Infrastructure

The current backend likely uses REST polling or full response returns. Migrate Copilot to a persistent connection model:

- FastAPI: implement `GET /api/copilot/stream` as an SSE endpoint (Server-Sent Events)
- Event types: `token`, `step`, `trade_proposal`, `trade_confirmation`, `error`, `done`
- Frontend: use the `EventSource` API to consume the SSE stream
- Fallback: if SSE fails, fall back to chunked HTTP with 3-second polling

---

### 4.2 Caching Layer

Prevent redundant API calls and reduce latency:

- Cache Alpaca account/position data: TTL 30 seconds (positions change slowly)
- Cache yFinance historical data: TTL 15 minutes
- Cache enrichment data (sector, analyst ratings): TTL 1 hour
- Use a simple in-memory dict cache in FastAPI (or Redis if multi-process deployment)

---

### 4.3 Environment & Config

- All API keys must be in `.env` (never hardcoded): `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ANTHROPIC_API_KEY`, `ALPHA_VANTAGE_KEY`
- Add a `config.py` that reads from `.env` using `pydantic-settings`
- Add `PAPER_TRADING=true` flag that gates live order execution

---

## Part 5: Feature Priority Matrix

| Feature | Priority | Effort | Impact |
|---|---|---|---|
| Agent Step Visibility | P0 – Critical | Medium | Very High |
| Trade Confirmation Modal | P0 – Critical | Low | Very High |
| Streaming Responses | P0 – Critical | Medium | High |
| Error Handling | P0 – Critical | Low | High |
| Conversational Memory | P1 – Important | High | High |
| Position Enrichment | P1 – Important | Low | Medium |
| Auto-Pilot Strategies | P1 – Important | High | Very High |
| Backtest Engine | P1 – Important | High | Very High |
| Copilot UI Polish | P1 – Important | Medium | High |
| Dashboard Widgets | P2 – Nice to Have | Medium | Medium |
| Portfolio Analytics | P2 – Nice to Have | Medium | Medium |
| Design System Cleanup | P1 – Important | Low | High |
| WebSocket/SSE Migration | P1 – Important | Medium | High |
| Caching Layer | P2 – Nice to Have | Low | Medium |

---

## Implementation status (as built in MarketFlux)

> Annotations reflect what already exists in this repo, which diverges from the brief's assumed stack (the agent uses **Gemini function-calling over SSE**, not LangGraph/Claude/WebSocket — the streaming + step-visibility intent is met regardless).

- **1.1 Agent Step Visibility** — DONE. SSE `thinking`/`tool_call`/`tool_result`/`trade` events render in a per-message activity timeline (`CopilotAgent.js`).
- **1.3 Streaming Responses** — DONE. Token streaming + live step labels via `/api/copilot/chat/stream`.
- **1.2 Trade Confirmation Modal** — DONE. Autonomous/Confirm toggle in the header. In Confirm mode (default) the agent stages trades; an Approve/Reject card executes them via `POST /api/copilot/trades/{id}/approve`. Core security gate against accidental/injected trades.
- **1.4 Error Handling** — PARTIAL. Tool failures surface as inline `⚠` summaries; the structured per-scenario copy table is not yet implemented.
- **2.1 Conversational Memory** — DONE: Mem0 over Supabase pgvector (Gemini embeddings + extraction). Auto-extracts durable facts per turn, semantic recall injected into context, sidebar panel to view/clear. Verified: agent honors remembered constraints (declined a short that violated "never short" + "under 10%").
- **2.3 Auto-Pilot (scheduled agents)** — DONE. "Standing agents": saved NL instructions the copilot runs autonomously on an interval. In-process asyncio scheduler (60s tick) started on app startup; per-user cap + min interval; every run logs its summary + trades. Managed in the Auto-Pilot tab (create / run-now / pause / delete). This is the Public.com-style always-on layer.
- **2.4 Backtest Engine** — Existing `backtest/` engine + Backtest tab; NL→rules parsing not wired to the Studio.
- **Compute** — BONUS (not in brief): sandboxed `run_python` tool for sizing/risk math.
- **Multi-model picker** — BONUS: the agent runs on Gemini (native function-calling)
  or any OpenAI-compatible provider (OpenRouter → GPT-4o / Claude / Qwen / DeepSeek;
  NVIDIA NIM → Nemotron) via a shared tool-calling loop. Header dropdown gated by
  which provider keys are present (`GET /api/copilot/models`). Lets the user trade
  off cost/quality per their plan to add cheaper provider keys later.
