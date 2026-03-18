---
name: MarketFlux Project Guidelines
description: Design, architecture, and constraints for the MarketFlux project
---

# MarketFlux Project Architecture and Guidelines

## Architecture Overview
- **Frontend** (Port 3000): React, Tailwind CSS, Shadcn/UI, Recharts.
- **Backend** (Port 8001): FastAPI, Python 3.10+, motor (async MongoDB).
- **Core Integrations**: MongoDB Atlas, Gemini 2.5 Flash, yfinance, RSS feeds.

## Design Philosophy (Retrofuturism/Cyberpunk Trader)
- **Theme**: "High-Visibility Terminal for the Modern Age".
- **Visuals**:
  - High density (Bento Grid layout).
  - Sharp edges only (no rounded corners > 2px).
  - Force dark mode (`#050505` background, `#00FF41` neon green primary, `#00F3FF` cyan secondary).
  - No smooth gradients or deep shadows; rely on 1px solid borders and glow effects (`shadow-[0_0_10px_rgba(0,255,65,0.3)]`).
- **Typography**: `Space Mono` for headings/data, `Inter` for body copy.

## Development Constraints
- Use `data-testid` on all interactive elements.
- Use `framer-motion` for mechanical/glitch-style UI interactions.
- Avoid blocking calls in the backend; strictly use async HTTP clients (`httpx`) and DB drivers (`motor`).
- Data density > white space. Maximize visible data without sacrificing readability.
