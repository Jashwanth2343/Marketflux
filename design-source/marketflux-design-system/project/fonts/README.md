# Fonts

This system uses three Google Fonts, all loaded via the Google Fonts CDN. No `.ttf` files ship with this folder.

| Role | Family | Weights used | Source |
| :--- | :--- | :--- | :--- |
| Display & headings | **Space Grotesk** | 400, 500, 600, 700 | [fonts.google.com/specimen/Space+Grotesk](https://fonts.google.com/specimen/Space+Grotesk) |
| Body & UI | **Inter** | 300, 400, 500, 600, 700 | [fonts.google.com/specimen/Inter](https://fonts.google.com/specimen/Inter) |
| Mono & data | **JetBrains Mono** | 400, 500, 600, 700 | [fonts.google.com/specimen/JetBrains+Mono](https://fonts.google.com/specimen/JetBrains+Mono) |

All three are imported at the top of [`colors_and_type.css`](../colors_and_type.css) via a single `@import url(...)` from Google Fonts. To use them in a standalone page without that stylesheet, paste:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
```

## Substitution note (please review)

The **original MarketFlux frontend** uses a mix of `Inter`, `Outfit`, `Roboto`, and `Space Mono` (see `MarketFlux/frontend/src/index.css` in the source repo). The display feel was inconsistent across pages — some headers in Outfit, others in Inter, the wordmark in Space Mono.

This system **collapses display into one family — Space Grotesk** — for a single unified geometric voice that pairs cleanly with JetBrains Mono. Space Mono was *also* considered (since it appears in `design_guidelines.json` for headings) but its glyph proportions read as too playful for a trading terminal at large display sizes; JetBrains Mono carries the "terminal" identity instead.

**If you want to restore the source product's typography exactly**, replace the Google Fonts import in `colors_and_type.css` with:

```css
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
```

…and update `--font-display` to `'Outfit'` and add a `--font-mono-display` token pointing at `'Space Mono'`. Flag the substitution to the brand owner before locking down.
