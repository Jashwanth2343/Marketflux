# MarketFlux Design System

**AI‑Native Trading Terminal & Research Brain for Public Markets**

MarketFlux is an investment‑research and real‑time market intelligence platform. It sits at the intersection of a Bloomberg‑style trading terminal and an LLM‑powered research agent — built for both professional analysts and informed retail traders.

This design system is an **evolved, refined version** of the existing MarketFlux UI. It keeps the spiritual core — cyberpunk‑trader, retrofuturist, high‑density, dark — and pushes it forward into something more deliberate, more typographically considered, and more legible at trading‑desk densities. Think *"Bloomberg Terminal × Linear × Vercel"*, not *"Matrix screensaver"*.

---

## Product surfaces

MarketFlux ships a single product — a web app — but it spans many surfaces. The major routes (lifted directly from the codebase):

| Route | Surface | Purpose |
| :--- | :--- | :--- |
| `/` | **Dashboard** | Bento overview — indices ticker, movers, market heatmap, Fear & Greed gauge, news. |
| `/news` | **News Feed** | Sentiment‑scored news aggregation from financial RSS feeds. |
| `/screener` | **AI Screener** | Natural‑language stock screener (chat → filtered equities). |
| `/stock/:ticker` | **Stock Detail** | Deep‑dive on a single ticker — chart, fundamentals, technicals, news, AI summary. |
| `/research` | **Research Center** | LLM research dossiers and saved investigations. |
| `/macro` | **Macro Dashboard** | Economic indicators, yield curve, global cross‑asset. |
| `/risk` | **Risk Console** | Portfolio risk, factor exposures, scenario stress. |
| `/portfolio` | **Portfolio** | Holdings, P&L, watchlists. |
| `/theses` | **Theses** | Long‑form research workspace, trade lab. |
| `/fund-os` | **Fund OS** | Strategy terminal — AI agents executing research workflows. |
| `+ floating` | **AI Chatbot** | Side‑docked LLM research assistant available everywhere. |

The AI Chatbot is the soul of the product: a side‑docked panel powered by Gemini 2.5 Flash that you can summon from any surface, ask in plain English, and get back streamed answers grounded in live market data.

---

## Sources

This design system was distilled from a single canonical source. The reader is encouraged to explore it directly.

- **GitHub:** [Jashwanth2343/Marketflux](https://github.com/Jashwanth2343/Marketflux) — full React + FastAPI implementation. The frontend lives at `MarketFlux/frontend/src/` and the canonical design tokens are written down in `MarketFlux/design_guidelines.json`.

No Figma, no slide deck, no separate brand kit was provided. Everything here is reverse‑engineered from the codebase and the live product screenshots, then **deliberately refined** to be more design‑system‑shaped than the source.

> If you are building new MarketFlux surfaces, **the codebase is your most authoritative source for the existing UI**. This system is for *new* designs that should feel like they belong.

---

## CONTENT FUNDAMENTALS

MarketFlux copy reads like a **trading desk**, not a B2B SaaS app. It is terse, scan‑first, and biased toward acronyms and uppercase labels. The voice is **expert‑to‑expert**: it never explains what RSI is, it just shows the value.

**Tone:** Confident, technical, slightly retrofuturist. The terminal is the metaphor — you are addressing a quant, not a beginner. Headlines feel like a Reuters wire.

**Casing.** Section labels, navigation, button text, badges, table headers, and metric kickers are all **`UPPERCASE`** with wide tracking (`letter-spacing: 0.08em`–`0.22em`). Body prose and headlines stay in sentence case. Numbers are always digits, never spelled out.

**Person.** Almost no I/you. The interface speaks to itself in a third‑person/imperative voice — "Top Movers", "Live Watchlist", "Run screener". The AI Chatbot is the *only* place that addresses the user directly ("What do I research, Assistant?"), and even there the AI replies in clipped, structured analysis form.

**Emoji.** **No emoji** in product chrome, ever. The original README uses 📈 🌟 🚀 for repo decoration; that does not carry into the UI. The only "icons in text" are stroke‑weight Lucide glyphs.

**Density.** Copy is short. A news headline is two lines max with `line-clamp-2`. A metric is `LABEL` + value + delta. A chart caption is six words.

**Numeric formatting.**
- Prices: `$1,248.50` — comma thousands, two decimals, leading `$`.
- Percent: `+1.84%` / `−1.84%` — explicit sign, two decimals. Note the **proper minus** (U+2212), not a hyphen, when typographically possible.
- Big numbers: `$1.2B`, `$24.5M`, `12.4K` — single letter suffix, one decimal.
- Tickers: bare uppercase, no `$` prefix in chrome (`AAPL`, not `$AAPL`).
- Timestamps: `2m ago`, `4h ago`, `3d ago` for relative; `14:32 UTC` for absolute.
- All numeric text uses **`font-variant-numeric: tabular-nums`** so columns align without hand‑tuning.

**Sentiment vocabulary.** Three buckets and three buckets only: `BULLISH` (green), `BEARISH` (red), `NEUTRAL` (amber). News cards, AI summaries, and screener filters all use this vocabulary.

**Example copy specimens**

> `MARKET OPEN` · `EXTREME GREED · 82/100` · `VIX 29.49 +24%` · `Top Mover: NVDA +4.2%`
>
> *AI INSIGHT — AAPL: Q3 earnings, technical signals, and supply‑chain data indicate a bullish outlook with 84% confidence. Current price target: $210 (12‑month).*
>
> Button labels: `RUN SCREEN` · `ADD TO WATCHLIST` · `EXPORT CSV` · `OPEN TERMINAL`

---

## VISUAL FOUNDATIONS

The visual language is **deliberately mechanical**. The brand calls itself *retrofuturism / cyberpunk trader* — but the refined version pulls the dial back from "Matrix" toward "considered terminal". Glow is rationed. Color is reserved for data. Whitespace is rare but not absent.

### Color

A **slate dark canvas + investment‑firm accent** system. The palette is deliberately aligned with the tools professional traders already use — TradingView greens & reds, Bloomberg‑warm amber, slate neutrals — so MarketFlux feels native to the trading desk rather than to a Matrix screensaver.

Every accent has been spot‑checked for **WCAG AA contrast (≥4.5:1 on the canvas)** at body size. Color is never the *only* signal of meaning — bull/bear always pair with ▲▼ glyphs or explicit `+/−` signs.

- **Surfaces** are cool slate dark, never pure black. Background `#0A0E14`, raised surface `#131720`, hover `#1A1F2C`, pressed `#232A3A`. The slight blue undertone is intentional — it reads as "trading desk" and is markedly easier on the eye over a 12‑hour session than warm‑black.
- **Foreground** is a cool off‑white `#E4E7EB`, secondary `#9CA3AF` (slate‑400), tertiary `#6B7280`, quaternary `#374151`. Pure `#FFFFFF` is reserved for use *on* coloured fills (bull green button) — never on the canvas.
- **Borders** are a single hairline, `1px solid #1F2937` (slate‑800). The system **uses borders for depth, not shadows.** A card is defined by its frame, not its float.
- **Bull green** `#089981` — the **exact** TradingView bull. Used for gains, BULLISH sentiment, primary CTA, the wordmark. A brighter variant `#00C26A` exists for data emphasis (delta text, live indicators). No neon — neon greens fatigue the eye, create after‑images, and read as amateur.
- **Bear red** `#F23645` — TradingView's exact bear. Clean primary red, no orange shift, distinguishable from amber even for the ~5% of users with red‑green colour‑vision deficiency (pair it with ▼).
- **Alert amber** `#FF9F0A` — a Bloomberg‑warm orange for NEUTRAL sentiment, warnings, earnings‑week callouts, and high‑attention metadata.
- **Secondary cyan** `#06B6D4` — secondary data ink. Volume, secondary chart lines, info messages.
- **Agent violet** `#8B5CF6` — AI agent surfaces only. Reasoning traces, citations, AI insight callouts, the chat panel border. Keeps AI distinct from bull/bear semantics.
- **Usage rule.** Never apply accent colors to large surfaces. They are *data inks*. A whole card painted bull‑green is a bug. A single number painted bull‑green is a feature. The 60/30/10 rule applies: 60% canvas+surface, 30% neutral ink, 10% colored data.

### Type

- **Display & headings:** `DM Sans` — modern geometric sans, slightly warmer than Inter, the workhorse of Fey / Linear / many premium fintech surfaces. 500–700 weight, tight tracking.
- **Body & UI:** `DM Sans` 400/500. Body sits at 15px/24px with line‑height 1.55–1.6 — more breathing room than the previous Inter‑at‑14px. Reads as editorial finance, not cyberpunk terminal.
- **Editorial moments:** `DM Serif Display` — used sparingly for hero KPIs, big stock prices on marketing surfaces, share cards.
- **Mono & data:** `JetBrains Mono` — all numbers, tickers, code, terminal output. Tabular numerals always on.
- **Wordmark:** "Market**Flux**" in DM Sans 600 with the *Flux* half painted in `--bull-strong`. No uppercase, no tracking. Reads as a brand, not a server name.
- **Scale:**
  - Display XL: 44–56 / 1.04, DM Sans 700, tracking −0.025em (hero KPIs)
  - Display L: 32–40 / 1.1, DM Sans 600, tracking −0.02em (page titles)
  - H1: 24/30, DM Sans 600 (section headers)
  - H2: 20/26, DM Sans 600
  - H3: 17/24, DM Sans 600
  - Body: 15/24, DM Sans 400
  - Body small: 13/20, DM Sans 400
  - Caption: 12/18, DM Sans 500 (no uppercase)
  - Micro: 11/16, JetBrains Mono 500, uppercase, tracking 0.10em (reserved — kickers and audit labels only)
  - Data L: 32/34, JetBrains Mono 500, tabular‑nums (big price)
  - Data M: 17/22, JetBrains Mono 500, tabular‑nums (table values)
  - Data S: 13/18, JetBrains Mono 500, tabular‑nums (deltas, percentages)

### Spacing

The system runs on a **4px base**. Tokens: `space-1` 4, `space-2` 8, `space-3` 12, `space-4` 16, `space-5` 20, `space-6` 24, `space-8` 32, `space-10` 40, `space-12` 48, `space-16` 64. Card padding is `space-4`/`space-5`. Section padding is `space-6`/`space-8`. The dashboard bento gap is `space-4`. Touch targets are 36px minimum.

### Radius

Corners are **soft, not sharp**. The original cyberpunk "no rounded corners > 2px" rule is dropped in favour of Fey/Coinbase‑style rounding — it reads as editorial finance, not Matrix terminal. Tokens: `radius-0` 0px (rare), `radius-1` 4px (badges, chips), `radius-2` 8px (cards, panels, buttons — the default), `radius-3` 12px (hero cards, modals), `radius-full` 9999px (pills, dots).

### Shadows & depth

Shadows are **almost never used.** Depth comes from borders. The acceptable shadow tokens are:
- `shadow-glow` — `0 0 12px rgba(8, 153, 129, 0.36)` — bull-green glow for the active CTA / focused chart line.
- `shadow-glow-cyan` / `shadow-glow-amber` / `shadow-glow-agent` — matching glows in the other semantic colors, used at the same intensity.
- `shadow-elev` — `0 1px 0 rgba(255,255,255,0.04) inset, 0 16px 48px rgba(0,0,0,0.46)` — for modals and the AI chat panel only.

No `0 1px 3px rgba(0,0,0,0.1)` Material‑style drop shadows. They look out of place on the slate canvas.

### Backgrounds & motifs

- **No scanlines.** The previous CRT scanline overlay was stripped — the new direction is editorial calm, not retrofuturism.
- **Subtle dot grid** — optional, available via `.mf-grid-bg` for empty states and marketing hero canvases.
- **No corner brackets.** The previous "technical card" decoration was dropped — cards now define themselves with a single 1px border and `radius-2` (8px) rounding.
- **No textures, no grain, no patterns.** Restraint is the brand.
- **Imagery** — news thumbnails render at 100% saturation. Marketing imagery leans cool/considered (after‑hours trading desks, abstract data) but never warm/lifestyle.

### Borders

`1px solid var(--border)` — one weight, one style. Use opacity to soften (`border-border/40`), never to thicken. The exceptions:
- `2px` left border on a quoted AI insight block.
- `1px` dashed for "pending" or "draft" states (rare).

### Animation & motion

Motion is **calm, not mechanical**. The cyberpunk "snap, no transitions" of the original is replaced with measured 140–220ms `ease-out` transitions — closer to Coinbase / Fey than to a Bloomberg terminal.

- Default transition: 140ms `cubic-bezier(0.22, 1, 0.36, 1)` (ease‑out).
- **Allowed motion:** opacity fades for new data (220ms), flash highlight on price tick (`flash-up` / `flash-down` — 900ms ease‑out from 36% green/red to transparent), ticker scroll (60s linear infinite), live pulse (2.4s ease‑in‑out infinite, 1.0 → 0.6 opacity).
- **Forbidden:** spring physics, bounce, glitch effects, scanlines, scale‑on‑load entrances.
- Page transitions: 220ms ease-out fade. No stagger choreography — dashboards should appear, not perform.

### Hover, focus, active states

- **Hover:** `1px` border shifts from `--border` to `--bull-border` (36% opacity bull green). Text color shifts to `--bull-strong`. Background gets a faint `--bull-bg` (10% bull green) wash. No size change, no shadow.
- **Active CTA on hover:** the *invert pattern* — white text on bull‑green fill (`#089981` bg, `#FFFFFF` ink — 4.6:1 contrast). Sharp, instant.
- **Focus:** `2px` solid outline in `--bull` with `1px` offset — *always* visible, never glow‑only. Glow alone fails WCAG focus‑visible requirements.
- **Press:** 95% scale on the button only — never on the surrounding card.
- **Loading:** mono pulse on the affected text (`animate-pulse`). No skeleton screens shaped like content; just a faint bar.

### Transparency & blur

Used in three places, nowhere else:
- The AI Chatbot panel (`backdrop-blur-md`, `bg-card/80`).
- The sticky top nav (`backdrop-blur-md`, `bg-card/80`).
- Mobile drawer overlays.

Cards do **not** use blur. The bento grid stays opaque so the chart pixels are sharp.

### Cards

The atomic surface. A card has:
- `background: var(--card)` (`#0F1216`)
- `border: 1px solid var(--border)` (`#1E2530`)
- `border-radius: 2px` (`radius-1`)
- `padding: 16px` body, `12px 16px` header
- No drop shadow
- A header with a uppercase mono kicker + optional right‑aligned meta
- An optional `corner-brackets` decoration for hero cards

### Layout rules

- **Bento Grid Mode B** (high density) — 4‑column desktop grid, 2‑column tablet, 1‑column mobile, gap `16px`. Cards span 1/2/3/4 columns.
- **Fixed elements:** top nav (sticky), AI chat side panel (fixed right), scanline overlay (fixed full viewport, pointer‑events‑none).
- **Page padding:** `24px` desktop, `16px` mobile.
- **Max width:** none. The terminal fills the viewport.

### Color vibe of imagery

The Unsplash/Pexels hero images referenced in the original design_guidelines.json are **deep blue / cyan / black** — abstract market data, glowing chart screens, trader silhouettes. The vibe is **cool, electric, after‑hours**. Avoid: warm tones, daylight scenes, lifestyle imagery, people smiling.

---

## ICONOGRAPHY

MarketFlux uses **Lucide React** as its single icon system. Stroke style, ~1.5–2px weight, sharp endpoints. The same Lucide set is available from `lucide.dev` and via CDN as `https://unpkg.com/lucide@latest`. No custom SVGs except the wordmark.

**Usage rules:**
- Default size: `16px` inline with text, `20px` for primary actions, `24px` for hero/empty‑state.
- Default color: `currentColor` (inherits). Tinted to `--primary` for active state.
- **Always paired with text** in nav and buttons. Icon‑only is allowed only in `36×36` square slots (theme toggle, mobile menu toggle, close X).
- **No filled icons.** Lucide's outlined style only.
- **No emoji** in product chrome.
- **No flag emojis or country emojis** — use a tiny abbreviation badge (`US`, `EU`, `JP`) instead.

**Canonical icon vocabulary** (lifted from the codebase nav and key components):

- `Activity` — Live, real‑time, vital signs (used in the wordmark lockup)
- `LayoutDashboard` — Dashboard
- `Newspaper` — News Feed
- `Search` — Screener, search input
- `Brain` — Research, AI
- `Globe` — Macro
- `Shield` — Risk
- `Briefcase` — Portfolio
- `BookOpenText` — Theses
- `TerminalSquare` — Fund OS / strategy terminal
- `TrendingUp` / `TrendingDown` — Movers, sentiment, deltas
- `Sun` / `Moon` — Theme toggle
- `LogIn` / `LogOut` / `User` — Auth
- `BarChart2` / `Map` — Chart and heatmap
- `ExternalLink` — Outbound links
- `MessageSquare` / `Send` — Chat
- `Sparkles` — AI insight badge (use sparingly)

**Loaded via CDN** in this design system:
```html
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
<i data-lucide="activity"></i>
<script>lucide.createIcons();</script>
```

The wordmark "MARKETFLUX" pairs the `Activity` glyph (a heartbeat trace) in `--primary` green with the uppercase JetBrains Mono wordmark. See `assets/logo-lockup.svg`.

---

## Index — files in this system

- **`README.md`** — this file. Brand, content, visual, and iconography fundamentals.
- **`SKILL.md`** — Agent‑Skills‑compatible entry point for using this system inside Claude Code.
- **`colors_and_type.css`** — single drop-in stylesheet with every CSS custom property: colors, type, spacing, radius, shadows, motion, layout tokens. Use `var(--bull)`, `var(--fg-primary)`, `var(--data-l)`, etc.
- **`fonts/README.md`** — Google Fonts swap notice. The original product uses Inter + JetBrains Mono + Space Mono. This system substitutes **Space Grotesk** for display. All loaded via Google Fonts CDN — no `.ttf` shipped.
- **`assets/`** — `hero.png` (original product render, reference only), `logo-mark.svg` (the signet), `logo-lockup.svg` (mark + wordmark).
- **`preview/`** — 28+ small specimen cards rendered in the Design System tab. One concept per card.
- **`ui_kits/web/`** — the clickable React UI kit. See `ui_kits/web/README.md` for the file map. Loads `index.html` to demo Dashboard → Stock Detail → AI Screener with a docked AI chat panel.

### UI kits

- **`ui_kits/web/`** — Web app UI kit. `index.html` + `data.js` + `components.jsx` + `nav.jsx` + `screens.jsx`. Components: `TopNav`, `TickerTape`, `Card`, `Button`, `Badge`, `Delta`, `Pct`, `Sparkline`, `Kicker`, `IndexStrip`, `MoversCard`, `Heatmap`, `FearGreedGauge`, `FearGreedCard`, `NewsItem`, `CandleChart`, `StockDetail`, `AIScreener`, `AIChatPanel`, `Dashboard`.

### Substitutions & flags

- **No real `.ttf` files shipped.** All fonts pulled from Google Fonts CDN. If you need offline assets, ask the user.
- **`lucide-react` is used in the source codebase** but for static HTML previews this system loads Lucide via UMD CDN. Same icons.
- **Space Grotesk** was tried for display and rejected. The final system uses **DM Sans** (display + body) and **DM Serif Display** (editorial moments) — closer to Fey's design language. The original product's `Outfit` is also a reasonable swap. **Flag if you want Space Grotesk or Outfit restored.**
- **Cyberpunk chrome was stripped.** The original system specified scanlines, corner brackets, glow effects, and "motion should feel glitchy". This system removes those entirely — the new aesthetic is editorial-finance (Fey / Coinbase / Robinhood / Bloomberg) rather than retrofuturism. The CSS still ships `mf-pulse`, `mf-flash-up`, `mf-flash-down` for live data feedback, but corner brackets, scanline overlays, and neon glow are gone. **Flag this if you want the cyberpunk direction restored.**
- **Bull / bear / amber accents were retuned** through several iterations. The current palette is `#22C55E / #EF4444 / #F5C147` (Robinhood-leaning bright green, classic warm red, Bloomberg-lineage gold). Earlier iterations (neon `#00FF41`, TradingView teal `#089981`) were rejected as too amateur or too clinical. **Flag if you want a different reference set.**
- **No accent violet, cyan, or AI‑purple.** The previous spec added an "agent violet" `#A78BFA` for AI surfaces. This was removed entirely — FluxAI surfaces now use the brand green, keeping the palette to three accents only. **Flag if you want AI to have its own colour.**
- **Space Grotesk** was tried for display and rejected. The final system uses **DM Sans** (display + body) and **DM Serif Display** (editorial moments) — closer to Fey's design language. The original product's `Outfit` is also a reasonable swap. **Flag if you want Space Grotesk or Outfit restored.**

---

## Quick start

```html
<link rel="stylesheet" href="colors_and_type.css" />
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>

<body class="scanlines">
  <header class="mf-nav">
    <span class="mf-wordmark"><i data-lucide="activity"></i> MARKETFLUX</span>
  </header>
  <main class="mf-bento">
    <section class="mf-card">
      <div class="mf-kicker">S&amp;P 500</div>
      <div class="mf-data-l">5,892.40</div>
      <div class="mf-delta mf-bull">+38.21 (+0.65%)</div>
    </section>
  </main>
</body>
```
