# Changelog

A record of the major design directions tried during this design system's evolution, so future readers can understand why we landed where we did.

## v1.0 — Final (Fey / Coinbase / Robinhood / Bloomberg)
**Direction:** Editorial finance, warm-dark canvas, single brand green.

- **Palette** — green `#22C55E` / cream `#F0EAD9` / warm-black `#0C0B09` / red `#EF4444` / gold `#F5C147`. No violet, no cyan, no neon.
- **Type** — DM Sans (display + body), DM Serif Display (editorial moments), JetBrains Mono (data only).
- **Radius** — soft 4/8/12px, not the sharp 0/2px of earlier iterations.
- **Motion** — calm ease-out 140–220ms, not the mechanical "snap" originally specced.
- **Chrome** — no scanlines, no corner brackets, no glow effects. Borders define depth.
- **New surfaces** — Liquid glass utilities (`.mf-glass*`), agentic Agents page, marketing landing with 3D mockup, 5-step onboarding flow.
- **Responsive** — viewport meta, fluid `clamp()` typography, breakpoints at 1400/1100/980/640/380, 44px touch targets, `prefers-reduced-motion` honoured.

## v0.4 — Anthropic detour (abandoned)
**Direction:** Warm dark, ember orange, editorial typography.

Tried after user feedback "no violet, no blue, more Anthropic-like". Got close to the right warmth but the ember orange felt off-brand for a finance product. **Replaced by v1.0 when user pointed to Fey / Coinbase / Robinhood / Bloomberg references.**

## v0.3 — Investment-firm slate (abandoned)
**Direction:** Cool slate canvas, TradingView greens & reds, Bloomberg amber, agent violet for AI.

Designed after user said "the existing green looks so bad — use the green or color palettes that most top investment firms use". Used TradingView's `#089981 / #F23645`. **Read as too cool/clinical; user wanted warmer and dropped the violet entirely. Replaced by v1.0.**

## v0.2 — Cyberpunk refinement (abandoned)
**Direction:** Refined version of the original design_guidelines.json. Dark canvas + neon green + scanlines + corner brackets.

Used `#00FF88` neon green, agent violet `#A78BFA`, cyber cyan, sharp 2px corners, mechanical snap motion. **Read as "Matrix screensaver" to the user; replaced by v0.3.**

## v0.1 — Source product
**Direction:** Reverse-engineered from [Jashwanth2343/Marketflux](https://github.com/Jashwanth2343/Marketflux).

Used the existing `design_guidelines.json` (cyberpunk trader, `#00FF41`, Space Mono headings) as the starting point. **The basis everything iterates from.**

---

## What flipped between iterations

| Concern | v0.1 (source) | v0.2 | v0.3 | v1.0 (final) |
| :--- | :--- | :--- | :--- | :--- |
| Canvas | `#050505` | `#070809` | `#0A0E14` slate | `#0C0B09` warm |
| Bull green | `#00FF41` neon | `#00FF88` neon | `#089981` teal | `#22C55E` mint |
| AI surface | (none) | violet `#A78BFA` | violet `#8B5CF6` | brand green |
| Radius | sharp 0–2px | sharp 2px | sharp 2px | soft 4–12px |
| Motion | mechanical | mechanical 0ms | mechanical | calm ease-out |
| Scanlines | yes | yes | optional | removed |
| Corner brackets | yes | yes | yes | removed |
| Display type | Space Mono | Space Grotesk | Space Grotesk | DM Sans |
| Body type | Inter | Inter | Inter | DM Sans |
| Wordmark | UPPERCASE mono | UPPERCASE mono | UPPERCASE mono | "Market**Flux**" sentence-case |

If you ever want to restore an earlier direction, every iteration above used the same file structure — only the CSS tokens and a handful of preview cards changed. The hardest pieces to recreate are the landing page (added in v1.0), onboarding flow (v1.0), and the Agents surface (v1.0).
