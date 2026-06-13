# PRD: Trading Copilot

> **Status — updated 2026-06-13 (post-PR #30):** ✅ **SHIPPED, then superseded/extended.** The
> `/copilot` cockpit is live; the original proposal/personality flow moved to the **Auto-Pilot** tab,
> and the conversational agent ([`prd-copilot-agent.md`](prd-copilot-agent.md) → 35 tools in
> [`prd-copilot-godtier.md`](prd-copilot-godtier.md)) is now the primary surface. The "paper trading
> broken (Postgres dependency)" blocker is **resolved** — PR #30 migrated the copilot trust path to
> Supabase Postgres (`copilot_store.py`, `sql/copilot_core_schema.sql`). Acceptance criteria below
> shipped.

## Problem Statement
The AI Pilot, Strategy Terminal, and paper trading features exist but are scattered across separate pages. Paper trading is broken (Postgres dependency). Users want a single "cockpit" where an AI copilot can propose and execute trades with human approval.

## Scope

### In Scope
- Copilot page with 4 sub-tabs: Trading Copilot, Strategy Studio, Proposals, Paper Portfolio
- Trading Copilot: AI chat with structured trade proposals + approve/reject
- Strategy Studio: Existing StrategyTerminal embedded
- Proposals: Pilot proposal cards + FundOS strategy queue
- Paper Portfolio: Alpaca account summary + positions
- All trade execution happens backend-side (frontend only sends approval)

### Out of Scope
- Autonomous execution without approval
- Real money trading
- LangGraph migration (Phase E separate)
- Portfolio rebalancing automation

## Copilot Execution Model

```
1. AI analyzes market + account context
2. AI generates structured trade proposal
3. Frontend renders proposal with Approve/Reject buttons
4. User clicks Approve → POST /api/pilot/proposals/:id/approve
5. Backend: re-check policy → re-check account → submit Alpaca order
6. Backend: persist audit trail → return result
7. If AI not confident → asks clarifying questions instead
```

## Component Structure

```
Copilot.js (shell)
  ├── Tabs
  │   ├── Trading Copilot → <TradingCopilotPanel />
  │   ├── Strategy Studio → <StrategyTerminal embedded />
  │   ├── Proposals → <ProposalCard /> list (from pilot)
  │   └── Paper Portfolio → <AccountSummary /> + positions table
  └── components/copilot/
      ├── TradingCopilotPanel.js (~350 lines)
      └── AccountSummary.js (~80 lines)
```

## API Contracts

### Trading Copilot Chat
- Uses existing `POST /api/ai/chat/stream` (SSE)
- System prompt enriched with: current positions, account equity, pending proposals
- AI response format includes structured `trade_proposal` blocks

### Proposal Approval (reuses pilot_router)
- `POST /api/pilot/proposals/:id/approve` → re-checks policy, executes server-side
- `POST /api/pilot/proposals/:id/reject` → marks rejected
- `GET /api/pilot/proposals` → list pending proposals

### Account Data (reuses alpaca_router)
- `GET /api/alpaca/account` → equity, buying power, P/L
- `GET /api/alpaca/positions` → current positions
- `GET /api/alpaca/orders` → recent orders

## Files to Create/Modify

| File | Action |
|------|--------|
| `pages/Copilot.js` | Create (~160 lines) |
| `components/copilot/TradingCopilotPanel.js` | Create (~350 lines) |
| `components/copilot/AccountSummary.js` | Create (~80 lines) |
| `components/StrategyTerminal.js` | Modify (add embedded prop) |

## Acceptance Criteria
- [x] `/copilot` loads with Trading Copilot tab active
- [x] Strategy Studio tab renders the swarm terminal
- [x] AI chat streams responses via SSE
- [x] Trade proposals render with approve/reject buttons
- [x] Approval triggers backend execution (not frontend)
- [x] Paper Portfolio shows Alpaca account data
- [x] Account refreshes every 15 seconds
