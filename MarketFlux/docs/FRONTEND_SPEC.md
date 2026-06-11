# MarketFlux — Complete Frontend / UX Spec

> Source of truth for design (Claude design or any UI rebuild). Derived from the live React app
> (`MarketFlux/frontend/src`) and `design_guidelines.json`. Every page, tab, and sub-feature below
> maps to a real route/component in the codebase.

---

## 0. Design Language (global)

**Theme:** Retrofuturism / Cyberpunk Trader — "high-visibility terminal for the modern age."
Emotional tone: intense, precise, nostalgic, electric. Data density over whitespace.

- **Colors:** background `#050505`, card `#0A0A0A`, primary neon green `#00FF41`, secondary cyan
  `#00F3FF`, accent amber `#FFB000`, destructive red `#FF3333`, border `#1E293B`. Green/cyan are for
  **data values only**; body text stays `#EDEDED`/white.
- **Typography:** headings/mono = Space Mono; body = Inter; data/numbers = JetBrains Mono. Headings
  are `uppercase tracking-tighter`. Numbers are tabular/`font-data`.
- **Shape:** sharp edges — no radius larger than ~2px. 1px solid borders everywhere; depth comes from
  borders, not shadows. Cards get optional "corner bracket" accents.
- **Motion:** mechanical / glitchy, not fluid. Framer Motion staggered fades (`y:10 → 0`, linear ease,
  ~0.2s). Hover states **invert** (black text on green) or add a glow `shadow-[0_0_10px_rgba(0,255,65,0.3)]`.
- **Atmosphere:** fixed scanline overlay (`ScanlineOverlay`), subtle SVG grid background, pulse-dot for
  "live" states.
- **Layout:** Bento Grid Mode B (high density), `grid-cols-1 md:grid-cols-4 gap-4`. Containers fill
  height. Default theme is **dark**; a light theme exists via `ThemeContext` (sun/moon toggle).
- **Charts:** Recharts, neon green/cyan lines, subtle/hidden gridlines, dark tooltips.
- **Notifications:** `sonner` toasts, top-right.

---

## 1. Global Shell (every page)

**Top navigation (`TopNav`)** — sticky, blurred, two rows:
1. **TradingView ticker tape** (top strip, 46px): S&P 500, Nasdaq 100, EUR/USD, BTC, ETH.
2. **Main bar:**
   - Logo "MARKET FLUX" + animated Activity glyph (green glow on hover).
   - **Market-status pill**: live green pulse when US market open (9:30–16:00 ET, Mon–Fri), grey "Closed" otherwise.
   - **Primary nav (6):** Dashboard · Intelligence · Copilot · Backtest · Portfolio · Leaderboard.
   - **Global SearchBar** (ticker/company autocomplete → routes to `/stock/:ticker`).
   - **Theme toggle** (dark/light).
   - **Auth zone:** signed-out → "Login" + "Sign In with Google"; signed-in → avatar + name + Logout.
   - **Mobile:** hamburger → full-screen dropdown with search, 2-col nav grid, auth.

**Floating "Flux AI" terminal (`AIChatbot`)** — global, docks to the right on desktop (resizable,
default 380px), floating bubble on mobile. Available on every page.
- Conversational markets/stocks/macro assistant (streamed SSE responses, rich markdown).
- Chat history list (new chat, history drawer), file/screenshot attach (paperclip).
- "Aggregated Data Sources" + "Analysis Pipeline" disclosure panel.
- Free vs. logged-in gating ("Login for unlimited AI access").
- Opened/closed globally via `marketflux:open-terminal` events from other pages.

---

## 2. Dashboard — `/`

The command center / market overview landing page.

- **Hero header:** headline + market-mood strip — Market Open/Closed, Fear/Greed index (0–100,
  color-coded), VIX.
- **Quick-action launchers (4 cards):** AI Trading Copilot, Strategy Backtester, Market Intelligence,
  Portfolio & Risk → deep-link into those sections.
- **Market Movers panel:** tabbed **Gainers / Losers** (green/red themed), scrollable dense list with
  ticker, price, % change; row click → Stock Detail.
- **Major indices** tiles (S&P, Nasdaq, VIX, etc.).
- **Market Heatmap** (`MarketHeatmap`) — red/green sector/stock blocks.
- **Earnings calendar widget** (`EarningsCalendarWidget`) — upcoming earnings.
- **Latest news preview** (`NewsCard` list) with "View all →" to `/intelligence?tab=news`.

---

## 3. Intelligence — `/intelligence` (tabbed hub)

Five tabs (URL `?tab=`): **Research · News · Screener · Macro · Theses**. Legacy routes
`/news`, `/screener`, `/research`, `/macro`, `/theses` redirect here.

### 3a. Research (`ResearchCenter`) — default tab
- **AI idea generation:** theme input ("AI infrastructure, clean energy, biotech…") → ranked idea cards.
- **Macro context** summary block.
- **Document generator:** Morning Briefing · Research Memo · Quant Signals · Thematic report types.
- **Per-ticker deep research:** enter ticker (e.g. NVDA) → generated analyst write-up.
- **Cross-links** to Macro Dashboard, Risk Console, AI Screener, News Feed.

### 3b. News (`NewsFeed`)
- **Live headline feed** (dense list, typewriter effect on new items).
- **Sentiment filter:** All · ▲ Bullish · ▼ Bearish · ◆ Neutral.
- **Category filter:** All · General · Tech · Finance · World.
- **Search** headlines/tickers/topics. Cards link to source + related tickers.

### 3c. Screener (`AIScreener`)
- **Natural-language screen:** "Large-cap tech with low P/E and strong earnings growth" → results table.
- **AI Analysis** summary of the result set.
- **Results table:** Ticker · Company · Sector · Price · Change · Market Cap · Volume · Yield.
- Empty state: "No stocks matched." Rows → Stock Detail.

### 3d. Macro (`MacroDashboard`)
- **US Treasury yield curve** chart.
- **VIX regime** gauge.
- **Cross-asset board:** S&P 500, DXY (Dollar), Gold, WTI Oil, VIX, Bitcoin.
- **Sector momentum** table (Sector · Momentum).
- **Macro Intelligence Summary** (AI narrative).
- **Fear/Greed** dial (Extreme Fear ↔ Extreme Greed).

### 3e. Theses (`Theses`) — living investment theses
List/gallery of theses → links into the thesis sub-app below.

#### Thesis sub-app
- **New thesis** — `/intelligence/thesis/new` (`ThesisNew`): create a "living thesis" with title,
  body, and horizon (Short / Medium / Long term). Login required.
- **Thesis Workspace** — `/intelligence/thesis/:id` (`ThesisWorkspace`), tabs:
  - **Overview** — thesis statement, horizon, conviction.
  - **Evidence** — auto-refreshed supporting evidence with confidence scoring.
  - **Memos** — analyst memos/notes.
  - **Revisions** — immutable snapshot history; "saving a revision updates the canonical thesis,
    writes a snapshot, and queues an evidence refresh."
- **Thesis Trade Lab** — `/intelligence/thesis/:id/trade-lab` (`ThesisTradeLab`): convert a thesis into
  **simulated** paper trades under a policy engine.
  - **Policy rules:** no live trading (hard default), max position %, max gross exposure %, max
    single-name concentration %, block during earnings window (days before/after), max open trades,
    minimum evidence confidence %.
  - **Trades table:** Trade · Status · Entry · P&L · Action.

---

## 4. Copilot — `/copilot` (tabbed)

Conversational + autonomous **paper-trading** workspace. Four tabs (`?tab=`):
**Agent · Studio · Auto-Pilot · Portfolio**. Trust badges reinforce "simulated only."

### 4a. Agent (`CopilotAgent`) — default
- Conversational trading assistant ("Copilot Agent").
- **Copilot Memory** (`CopilotMemory`) — persistent context/preferences the agent remembers.

### 4b. Studio (`StrategyTerminal` / Strategy Studio)
- Build a strategy and **hand it off** to the agent / backtester.
- Deep-linkable per strategy (`?tab=studio&strategy=:id`); legacy `/fund-os/*` routes redirect here.

### 4c. Auto-Pilot (`StandingAgents` + `ProposalCard`)
- **Standing agents** that monitor and generate trade **proposals**.
- **Proposal cards:** glass-box rationale, accept/reject, drift badge, **kill switch**.
- **Adversarial debate** (`AdversarialDebate`) — bull vs. bear argument before acting.
- **Glass-box trade** (`GlassBoxTrade`) — full transparency on why a trade was proposed.

### 4d. Portfolio (`AccountSummary`)
- **Paper account:** cash, buying power, equity.
- Positions snapshot (mirrors the Alpaca paper account).

---

## 5. Backtest — `/backtest` (`Backtest`)

Full visual strategy backtester (the heaviest page).

- **Strategy builder:**
  - **Indicators:** SMA, EMA, RSI, MACD, MACD Signal, Bollinger Upper/Lower, ATR, Returns,
    Rolling High/Low, Volume SMA (each with its own params: period, source, fast/slow/signal, num_std…).
  - **Operators:** `>`, `>=`, `<`, `<=`, `==`, `!=`, Crosses Above, Crosses Below.
  - **Position sizing:** Fixed %, Fixed $, Equal Weight.
  - **Templates tab** vs. custom-rule tab.
- **Run config:** tickers/universe, date range, starting capital.
- **Results dashboard — metric cards** (each with tooltip + color thresholds): Total Return, CAGR,
  Sharpe, Sortino, Max Drawdown, Calmar, Win Rate, Profit Factor, Expectancy, Avg Duration, Best Trade,
  Worst Trade.
- **Equity curve** + drawdown charts, **trade log** table.

---

## 6. Portfolio — `/portfolio` (tabbed)

Two tabs (`?tab=`): **Holdings · Risk Analytics**. Legacy `/risk` → `?tab=risk`.

### 6a. Holdings (`Portfolio`)
- **Manual entry:** add positions (Ticker · Shares · Avg Price).
- **Upload Portfolio Screenshot** → AI-parsed positions.
- **Holdings table:** Ticker · Shares · Avg Price · Current · Value · Today's change.
- **Summary:** Total value, Total Gain/Loss, daily change. Login required.

### 6b. Risk Analytics (`RiskConsole`)
- **Per-ticker risk lookup:** Beta vs SPY, 95% Daily VaR, Max Drawdown (1Y), Annualized Volatility,
  Suggested Position size, Stop Loss.
- **Factor exposure:** Growth / Value / Quality.
- **Portfolio-level risk summary:** Portfolio Value, Portfolio Beta, 95% VaR (Daily), Max Drawdown.

---

## 7. Leaderboard — `/leaderboard` (`PilotLeaderboard`)

Public ranking of trading "pilots" (agents/users).
- **Timeframe filter:** 7d · 30d · 90d · 1y.
- **Podium** (top 3, large rank/return) + **full ranked table:** rank, pilot, return %, total P&L,
  trades, win metrics.
- Row → **Pilot public profile** `/leaderboard/p/:slug` (`PilotPublicProfile`): personality card,
  journal, track record. Sub-components: `PersonalityCard`, `JournalPanel`, `DriftBadge`.

---

## 8. Stock Detail — `/stock/:ticker` (`StockDetail`)

Deep dive for a single symbol.
- **Header:** ticker, price, change, volume (PRICE / CHANGE / VOLUME tiles).
- **Price chart** with range toggles: 1D · 5D · 1M · 6M · 1Y · 5Y.
- **AI Analyst Digest** (generated, with loading state).
- **Analyst price targets:** Low / Current / High.
- **Insider transactions** table (SEC Form 4: Name · Title · Shares · Value).
- **Institutional holders** table (Holder · Shares · Value).
- **Related news** feed (empty state when none).

---

## 9. Auth — `/auth` (`Auth`)

- Email login + **Google OAuth** (Supabase Auth).
- OAuth callback handled globally (`AuthCallback`, triggered on `session_id=` hash).
- Auth state via `AuthContext`; gates Portfolio, Theses, Copilot trading actions.

---

## 10. Route Map (quick reference)

| Route | Page | Notes |
|---|---|---|
| `/` | Dashboard | landing |
| `/intelligence?tab=research\|news\|screener\|macro\|theses` | Intelligence | 5 tabs |
| `/intelligence/thesis/new` | ThesisNew | auth |
| `/intelligence/thesis/:id` | ThesisWorkspace | Overview/Evidence/Memos/Revisions |
| `/intelligence/thesis/:id/trade-lab` | ThesisTradeLab | policy + paper trades |
| `/copilot?tab=copilot\|studio\|proposals\|portfolio` | Copilot | 4 tabs |
| `/backtest` | Backtest | builder + metrics |
| `/portfolio?tab=holdings\|risk` | PortfolioRisk | 2 tabs |
| `/leaderboard` · `/leaderboard/p/:slug` | Pilot leaderboard + profile | |
| `/stock/:ticker` | StockDetail | |
| `/auth` | Auth | |

Legacy redirects: `/news`, `/screener`, `/research`, `/macro`, `/theses*`, `/risk`, `/fund-os*`,
`/pilot*` all forward into the routes above.
