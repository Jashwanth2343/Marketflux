# PRD — Autonomous Trading Copilot Agent

## Summary
A conversational, autonomous paper-trading agent that researches markets **and**
executes trades on the shared Alpaca paper account, streaming every step
(thinking → tool call → result → trade) so the user can watch what it does. This
is the new primary "Copilot Agent" tab; the older proposal/personality flow moved
to the "Auto-Pilot" tab. Supersedes nothing in [prd-copilot-trading.md](prd-copilot-trading.md)
— it adds a conversational/agentic layer on top of the same Alpaca client.

## Problem
The previous "copilot" was a passive proposal-card system that (a) required
configuring "personalities" first, (b) silently no-op'd on approval after the
Trading-API migration, and (c) gave no real conversational control. Alpaca itself
was dead because `alpaca-py` was missing from the installed venv. The Strategy
Studio produced text that connected to nothing.

## Scope (delivered)
- Conversational ReAct agent (Gemini function calling) with 23 tools.
- Real paper-trade execution: buy/sell/close/cancel via Alpaca Trading API.
- Sandboxed Python compute tool for quant math (numpy/pandas/scipy).
- Live transparency stream: thinking, tool_call, tool_result, trade, token, done.
- Chat UI with activity timeline + trade cards + live account/positions sidebar.
- Strategy Studio → "Execute with Copilot" handoff (sessionStorage).
- Fixed proposal approve→execute (gate on broker config, not per-user account id).

## API contracts
- `POST /api/copilot/chat/stream` — body `{message, session_id?}`; SSE events:
  - `thinking {step,message}`, `tool_call {name,label,args,is_trade}`,
    `tool_result {name,ok,summary}`, `trade {action,symbol,side,qty,status,price}`,
    `token {content}`, `done {error?}`. Auth optional (shared paper account).
- `GET /api/copilot/account` — `{item}` (no auth, read-only paper account).
- `GET /api/copilot/positions` — `{items,total}` (no auth).
- `GET /api/copilot/trades?limit` — agent's executed-trade log.
- `GET /api/copilot/status` — health + `alpaca_configured`.

## Backend structure
- `backend/copilot_trading_tools.py` — 8 trading tools wrapping `vnext/alpaca_client`
  (account, positions, orders, market clock, portfolio history, place_order,
  close_position, cancel_all_open_orders). Paper-only; per-order notional cap
  `COPILOT_MAX_ORDER_NOTIONAL` (default 60000).
- `backend/copilot_agent.py` — system prompt, tool registry (8 trading + 14 research
  tools from `agent_tools` + 1 code tool), live-context injection, manual
  function-calling loop, SSE emission, trade logging to `db.copilot_trade_log`.
- `backend/copilot_code_tool.py` — `run_python`: AST allowlist (blocks
  file/network/system imports, dunder escapes, dangerous builtins) + isolated
  `python -I` subprocess with clean env (no secrets), temp cwd, CPU rlimit, 12s
  wall timeout, capped output. numpy/pandas pre-imported.
- `backend/copilot_router.py` — endpoints above; mounted in `server.py`.

## Frontend structure
- `frontend/src/components/copilot/CopilotAgent.js` — chat + activity timeline +
  trade cards + account sidebar + suggested prompts; consumes the SSE stream.
- `AccountSummary.js` — gained `source="copilot"` (no-auth) + `refreshSignal` +
  aggregate P&L derived from positions.
- `pages/Copilot.js` — tabs: Copilot Agent / Strategy Studio / Auto-Pilot / Paper Portfolio.
- `StrategyTerminal.js` — action bar (Execute with Copilot / Backtest / Copy).

## Acceptance criteria (all verified in browser)
- [x] Alpaca connected; live paper account reachable ($100k).
- [x] Agent researches a ticker and shows tool calls in the timeline.
- [x] Agent places a real paper order (verified: bought 2 MSFT, landed on Alpaca).
- [x] Agent respects conditional intent (declined a conditional buy when neutral).
- [x] Trade card + toast render; account sidebar refreshes after a trade.
- [x] Studio strategy hands off to the Copilot composer.
- [x] run_python computes (verified Sharpe + Kelly sizing); code renders in timeline; sandbox blocks os/open/dunder escapes.
- [x] No console errors; all four tabs render.

## Run notes
- Frontend dev server **must** use `craco.config.dev.js` (visual-edits babel plugin
  stack-overflows otherwise). Backend: `backend/venv` must have `alpaca-py` installed.

## Future ideas (not built)
- Bracket orders (stop-loss / take-profit) as a single tool.
- Confirm-before-execute toggle for higher-stakes actions.
- Scheduled autonomous runs ("check my book every morning").
- Persisted multi-session chat history UI; per-strategy P&L attribution.
