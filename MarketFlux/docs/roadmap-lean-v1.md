# Roadmap: Lean v1 → Sellable Product

> Working plan for taking MarketFlux from feature-complete prototype to a product a stranger
> would pay for. Supersedes the root `TODOS.md` and `HANDOVER.md` (deleted 2026-06-12; the
> still-valid items from both are folded in below). Feature PRDs live alongside this file.

## North star

One traceable loop, executed excellently: **ask the copilot → get a proposal with evidence,
debate, and risk/policy verdicts → approve → paper-execute → conviction ledger records the
receipt**. Every workstream below either strengthens that loop or removes weight around it.

## Phase 1 — Cut weight (in progress)

- [x] Remove dead frontend components (3 pilot components, 28 unused shadcn/ui files, toast stack)
- [x] Prune ~28 unused npm packages; standardize on npm (yarn.lock removed)
- [x] Delete stale docs (`TODOS.md`, `HANDOVER.md`, `guidelines/Guidelines.md`, `memory/PRD.md`),
      old eval/test artifacts, accumulated dev logs, `quant-app` leftover
- [ ] Consolidate venvs: `MarketFlux/backend/venv` is canonical (README); delete root `.venv`/`venv`
      and `backend/.venv` (~3.9 GB)
- [ ] Rotate the Gemini API key sitting in the root `.env`, then delete that file (backend/.env is
      the real one)
- [ ] Delete stale local branches (~13) and remote `copilot/*`, `codex/*`, `claude/*` branches
- [ ] Finish Mongo → Supabase migration and delete the legacy Mongo fallback paths

## Phase 2 — Trust the data (commercial blocker #1)

- [ ] Replace yfinance with a licensed provider for anything user-facing
      (candidates: Polygon.io starter, Finnhub, Alpaca Market Data — already integrated for trading)
- [ ] Surface data provenance + delay disclosures in the UI (per PRD non-goal N4)
- [ ] Carry-over from HANDOVER: yfinance ToS likely prohibits commercial use — legal check before
      any paid user

## Phase 3 — Prove the AI (commercial blocker #2)

- [ ] Standing eval harness for the copilot (golden-query set, scored on correctness/latency;
      replaces the deleted one-off `eval_report.json`)
- [ ] Copilot test suite: trade staging idempotency, standing-agent run isolation, auth fallback,
      memory inject (carried over from TODOS P2)
- [ ] Public pilot track record: run 1–2 pilots for a quarter, publish ledger receipts — this is
      the marketing engine

## Phase 4 — UI trust pass

- [ ] Designed empty states + first-run onboarding that teaches the core loop in <3 minutes
- [ ] Visible SSE error/retry states ("Connection lost — retrying", retry-last-message button)
- [ ] Move the model picker out of the user-facing header into developer settings
- [ ] Dial down costume (scanline overlay, neon glow) — keep terminal density and sharp edges
- [ ] IA: four top-level destinations (Dashboard, Research, Copilot, Ledger); leaderboard behind
      a flag until track records exist

## Phase 5 — Platform health

- [ ] Migrate CRA/craco → Vite (react-scripts is unmaintained; removes `ajv` pin and
      `--legacy-peer-deps`)
- [ ] CI that actually runs integration tests (carried over from HANDOVER: they silently skip
      when `REACT_APP_BACKEND_URL` is unset)
- [ ] Carry-over engineering debt from HANDOVER: TOCTOU guard on broker sub-account creation,
      broker-mode isolation for cancel-all/liquidate-all/get-order, `datetime.utcnow()` migration

## Performance note ("make agents trade superfast")

The agent loop is LLM- and IO-bound: a proposal takes seconds because of Gemini inference and
market-data fetches, not Python. A faster language (Rust/Go/C++) would optimize the ~1% that is
already fast. What actually moves latency, in order of leverage:

1. **Parallel tool calls** in the agent loop (research tools fan out concurrently)
2. **Caching**: Redis/in-proc for market data and EDGAR fetches (partially built — extend TTLs by
   data type)
3. **uvloop + httptools** for uvicorn and **orjson** responses — cheap drop-ins, ~10–30% on the
   HTTP layer
4. **Streaming-first UX**: perceived speed; first token < 1s matters more than total time
5. Model tiering: Flash for tool-call steps, stronger model only for final synthesis

HFT-style execution speed is explicitly out of scope: the product is approval-gated paper
trading (PRD G2/N1) — a human in the loop means seconds are fine; *traceability, not latency,
is the moat*.
