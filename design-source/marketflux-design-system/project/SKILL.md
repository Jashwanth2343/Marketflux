---
name: marketflux-design
description: Use this skill to generate well-branded interfaces and assets for MarketFlux — an AI-native trading terminal and equity-research product. Contains essential design guidelines, colors, type, fonts, assets, and a UI kit for prototyping new screens, slides, or marketing visuals in the MarketFlux brand.
user-invocable: true
---

# MarketFlux Design Skill

Read `README.md` in this skill first — it covers brand, content, visual, and iconography fundamentals end-to-end. Then explore the other available files:

- `colors_and_type.css` — drop-in CSS tokens for every color, type, spacing, radius, shadow, and motion variable
- `assets/logo-mark.svg` + `assets/logo-lockup.svg` — the brand mark (signet) and wordmark lockup
- `fonts/README.md` — font family list with Google Fonts CDN snippet
- `preview/*.html` — 28 specimen cards demonstrating individual tokens and components in isolation
- `ui_kits/web/` — clickable React UI kit. `components.jsx`, `nav.jsx`, `screens.jsx` are the source of truth for layout, density, and component shape. Read these to understand how cards, badges, charts, tables, and the AI chat panel are constructed.

## How to use

If you are creating a **visual artifact** (slide, mock, throwaway prototype, marketing site):

1. Copy `colors_and_type.css` and `assets/` into your target project.
2. Load the Google Fonts via the snippet in `fonts/README.md`.
3. Reach for the tokens (`var(--bull-strong)`, `var(--fg-primary)`, `var(--font-mono)`).
4. For component shape, lift from `ui_kits/web/components.jsx` and `screens.jsx`.
5. Add `<body class="scanlines">` if you want the subtle CRT overlay.
6. Output a static HTML file.

If you are working on **production code** for the actual MarketFlux app:

1. Map these tokens to the existing Tailwind config in `MarketFlux/frontend/tailwind.config.js`.
2. Use the React components in `MarketFlux/frontend/src/components/ui/` rather than the cosmetic kit components here.
3. Treat this design system as the source of truth for color values, spacing scale, and typographic hierarchy.

## The non-negotiables

- **Slate dark canvas**, never pure black. The colors_and_type.css defaults are correct.
- **No rounded corners > 4px.** Reach for `rounded-xl` and you are designing the wrong product.
- **No emoji** in chrome. Lucide icons only.
- **Tabular numerals** on every number, every time (`font-variant-numeric: tabular-nums`).
- **Accent colors are data ink, not surface paint.** A whole green card is a bug.
- **Bull/bear must pair with ▲▼** — never rely on color alone.
- **Motion is mechanical** — 0ms or 120–180ms linear, no spring physics.

If the user invokes this skill without specifics, ask them:
- *What surface are you designing — a dashboard view, a marketing page, a deck, a single component?*
- *Should this be production code or a throwaway prototype?*
- *Do you have specific tickers, news, or screens you want represented, or should I use the fake data baked into `ui_kits/web/data.js`?*

Then design like an expert MarketFlux designer would — outputting HTML artifacts or production code as appropriate.
