---
target: Dashboard page
total_score: 22
p0_count: 0
p1_count: 3
timestamp: 2026-06-12T21-01-43Z
slug: marketflux-frontend-src-pages-dashboard-js
---
# Critique: Dashboard (MarketFlux/frontend/src/pages/Dashboard.js)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Skeletons, market-open badge, live pulse; silent console.error on fetch failure |
| 2 | Match System / Real World | 3 | Raw "Data as of (UTC): <iso>" leaks machine format |
| 3 | User Control and Freedom | 3 | Collapse toggle + tabs work |
| 4 | Consistency and Standards | 1 | Token system bypassed ~30 times; 3 reds, 4 greens for same semantics; hand-rolled CTA |
| 5 | Error Prevention | 3 | Read-only surface |
| 6 | Recognition Rather Than Recall | 2 | Market detail hidden behind unpersisted toggle |
| 7 | Flexibility and Efficiency | 1 | No keyboard shortcuts; click-per-session to see movers/heatmap |
| 8 | Aesthetic and Minimalist Design | 2 | Fear & Greed shown 3x in one viewport |
| 9 | Error Recovery | 2 | Empty news state copy lies ("Fetching headlines..." after failure) |
| 10 | Help and Documentation | 2 | Capability descriptions only |
| **Total** | | **22/40** | **Acceptable** |

## Anti-Patterns Verdict
LLM: banned eyebrow (AI-POWERED TRADING PLATFORM 10px tracked uppercase) + banned identical card grid (4 capability cards); hero-metric-lite stats strip. Register inversion: marketing page behavior on a daily product surface. Detector: clean (exit 0) — markup-level detector cannot catch register-level JSX issues. Browser overlays skipped: no dev server; backend-dependent surface renders skeletons.

## Priority Issues
- [P1] Register inversion — marketing dominates daily-use surface; market detail collapsed by default, toggle unpersisted. Fix: logged-in = data-first; hero one line; capabilities logged-out/one-time. Command: distill
- [P1] Neutral sentiment renders as Bearish (binary ternary in MARKET MOMENTUM tile) — data-correctness bug. Fix: 3-state logic. Command: polish
- [P1] Token system bypassed: ~30 hex values, 3 reds/4 greens, inline-styled CTA Link instead of Button. Fix: gain/loss tokens, primary token, Button asChild. Command: polish
- [P2] Legibility: text-[#666] 9px labels fail AA on ink card; 8px tag. Fix: muted-foreground + 10px floor. Command: typeset
- [P2] F&G triplication + timestamp format inconsistency (UTC iso vs local time). Fix: drop duplicate tile, one relative-time format. Command: clarify

## Persona Red Flags
- Alex/Operator: hero re-read every morning; unpersisted toggle costs a click per session; no keyboard paths.
- Sam: 9px #666 fails AA; gauge SVG lacks role/aria-label; tabs lack aria-selected.
- Jordan (logged-out): well served — best-designed state of the page.

## Minor Observations
- Gauge hardcodes its own 5-color ramp separate from chart tokens.
- pulse-live dot implies real-time on a fetch-once feed.
- Inline scrollbar colors per tab; one-off mt-4 spacing on earnings calendar.

## Questions to Consider
- Open with the operator's state (portfolio delta, pending approvals, last pilot run) instead of generic market data?
- Does the capabilities grid belong once a user has used 2+ features?
- Why is the conviction ledger absent from the entry surface?
