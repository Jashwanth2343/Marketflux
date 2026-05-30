# MarketFlux UI Kit — Web

A clickable, mainly-cosmetic recreation of the MarketFlux web app. The kit is **not production code** — it cuts corners on data, auth, and routing — but it covers the visual surfaces a designer needs to compose new screens in the brand.

## Files

| File | Purpose |
| :--- | :--- |
| `index.html` | Entry point. Hosts the app, loads React + Babel + Lucide via CDN. |
| `data.js` | Static demo data — indices, gainers/losers, heatmap, news, AI insights, candles. |
| `components.jsx` | Atoms & molecules — `Card`, `Button`, `Badge`, `Delta`, `Pct`, `Sparkline`, `Kicker`, `Icon`, `LiveDot`. |
| `nav.jsx` | `TopNav`, `TickerTape`, `AIChatPanel`. |
| `screens.jsx` | Screen components — `Dashboard`, `StockDetail`, `AIScreener` + the supporting cards (`Heatmap`, `FearGreedGauge`, `MoversCard`, `IndexStrip`, `NewsItem`, `CandleChart`). |

## Try the flow

1. The kit boots on the **Dashboard**.
2. Click any ticker in the **Top Movers** or **Market Heatmap** → opens the **Stock Detail** screen for that ticker, with a candle chart, fundamentals, and AI thesis card.
3. Switch tabs in **Top Movers** between Gainers and Losers.
4. Switch sectors in **Market Heatmap** (Technology, Financials, Healthcare).
5. Click **Screener** in the top nav → natural-language **AI Screener** with chips you can dismiss.
6. Click **Ask AI** in the top-right → docks the **AI Chat Panel** on the right with a fake threaded conversation.
7. Click any nav item that isn't wired (News, Research, Macro, Risk, Portfolio) → a polite "not wired" placeholder. Visual coverage > full coverage in the kit.

## Component coverage

- `TopNav` + `TickerTape` — sticky top nav with logo, route tabs, command-bar search, AI toggle. Ticker tape scrolls automatically.
- `IndexStrip` — top-of-dashboard quote strip with corner brackets.
- `Card` / `CardHeader` / `CardBody` — atomic surface with optional `hero` corner-bracket decoration.
- `MoversCard` — tabbed Gainers/Losers with hoverable rows.
- `Heatmap` — sector-tabbed, cap-weighted tile grid using the TradingView color stops.
- `FearGreedGauge` + `FearGreedCard` — speedometer + supporting metric tiles.
- `NewsItem` — sentiment-tagged news row with ticker chips.
- `CandleChart` — bull/bear candles, MA overlay, volume row.
- `StockDetail` — period picker, KPI cards, AI thesis with confidence.
- `AIScreener` — NL query input + result table.
- `AIChatPanel` — right-docked agent chat with violet identity.

## What's intentionally absent

- No real API / network — `data.js` is static.
- No authentication, no routing library — `route` is local state.
- Empty / loading / error states are not surfaced (the kit always has data).
- Mobile breakpoints — built for ≥1280px viewports.

For anything beyond visual replication, refer to the source repo: [Jashwanth2343/Marketflux](https://github.com/Jashwanth2343/Marketflux) — `MarketFlux/frontend/src/` contains the real implementations.
