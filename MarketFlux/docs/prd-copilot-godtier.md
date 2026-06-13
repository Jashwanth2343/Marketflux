# PRD — Copilot: God-Tier Agentic Intelligence Trader

Status: **in progress** · Supersedes nothing; extends [prd-copilot-agent.md](prd-copilot-agent.md).

## Vision
Turn the Trading Copilot from a competent research-and-execute chatbot into an
**AI-native portfolio manager** that an institution would actually pay to run a
book: it forms conviction from systematic signals, sizes to risk, validates
systematic ideas on history, clears every order through a real compliance gate,
and shows its full reasoning. The differentiator is the *closed loop* — quant
intelligence → risk → backtest → compliance → execution → memory — driven
conversationally and transparently. Most "AI trading" products are a thin LLM
wrapper over a chart. This is an agent wired into a fund's actual machinery.

## What shipped in this iteration

### 1. The agent can now reach the fund's deep engines (the core ask)
Previously the copilot's 23 tools were research + trading + a Python sandbox.
The product's most valuable engines — the quant signal library, the portfolio
risk engine, and the backtester — were invisible to it. Now wired in via
[`copilot_intelligence_tools.py`](../backend/copilot_intelligence_tools.py):

| Tool | Engine | What the agent can now do |
|------|--------|---------------------------|
| `get_quant_signals` | `signal_engine` | Score one ticker on 20+ signals → a composite conviction (-100..+100) |
| `scan_signals` | `signal_engine` | Rank a basket by conviction, pick the best idea |
| `analyze_portfolio_risk` | `risk_engine` | Beta, 95% VaR, stress tests, concentration on the **live** book |
| `analyze_stock_risk` | `risk_engine` | Beta/vol/VaR + Kelly-style sizing for one name |
| `run_strategy_backtest` | `backtest/` | Backtest a DSL strategy on history before trading it |
| `deep_research` | `multi_agent` | Convene a 5-analyst team in parallel → committee-grade memo |
| `review_and_learn` | `copilot_learning` | Review own outcomes, distil lessons into long-term memory |
| `compliance_precheck` | `compliance_engine` | Pre-flight an order against all controls without placing it |
| `debate_thesis` | `copilot_debate` | Adversarial Bull vs Bear debate → Research-Manager verdict (audit-logged) |
| `get_market_regime` | `market_regime` | Classify the tape (risk-on…risk-off) + suggested gross exposure |
| `simulate_trade` | `copilot_intelligence_tools` | What-if: projected book + compliance, nothing placed |
| `get_earnings_intel` | `earnings_intel` | Earnings catalyst: date, beat rate, surprise probability |

The agent is now **35 tools** and runs a richer operating doctrine
(ground → score → size to risk → validate → clear compliance → execute → learn).

### 1b. Self-learning, multi-agent, long-running (the autonomy upgrade)
- **Self-improvement loop** ([`copilot_learning.py`](../backend/copilot_learning.py)):
  memory previously learned only from what the *user said*. `review_and_learn` now
  closes the harder loop — it reviews the agent's *own* track record (account,
  positions, performance, executed trades), grades what worked vs hurt, and writes
  durable, generalizable **lessons** back into long-term memory via
  `copilot_memory.add_fact`. Those lessons are recalled on future turns, so behaviour
  compounds. Persisted to `copilot_reviews` for history/UI.
- **Multi-agent delegation**: `deep_research` lets the copilot *spawn a team* — the
  5 specialist analysts + Director in [`multi_agent.py`](../backend/multi_agent.py),
  in parallel — for high-stakes calls. The agent decides when one pass isn't enough.
- **Long-running**: both are callable by the existing standing-agent scheduler
  ([`copilot_standing.py`](../backend/copilot_standing.py)) — e.g. a standing agent
  "review my book and learn every morning" runs unattended and improves the system
  over time. Context-aware tools (`review_and_learn`) get `(db, user_id)` injected by
  the runtime and run on a longer timeout (`_HEAVY_TIMEOUT`).

### 2. Institutional pre-trade compliance ([`compliance_engine.py`](../backend/compliance_engine.py))
A **pure, deterministic** pre-trade gate every order passes through before it is
staged or sent — independent of the model's intent (defends against
prompt-injection too). Controls: per-order notional cap, Reg-T buying power,
single-name concentration ceiling (soft warn + hard block), short-sale/over-sell
flag, FINRA pattern-day-trader equity floor, penny-stock liquidity, and
wash-sale awareness, plus disclosures. Returns `PASS / WARN / BLOCK`. A `BLOCK`
in the agent loop means the order is **never** staged or executed. Covered by
[`tests/test_compliance_engine.py`](../backend/tests/test_compliance_engine.py)
(10/10 passing).

### 3. Transparency UI for the new capabilities
[`CopilotAgent.js`](../frontend/src/components/copilot/CopilotAgent.js) renders
two new SSE event types in the activity timeline:
- `compliance` → a PASS/WARN/BLOCK gate card with per-rule checks.
- `insight` → rich cards for quant scorecards (composite meter + factor
  sub-scores), conviction-ranked scans, portfolio risk X-rays, single-name risk
  profiles with sizing, backtest result tiles, **research-team memos** (specialist
  chips), and **self-review cards** (letter grade + lessons committed to memory).

### 1c. Adversarial debate, regime radar, what-if & catalysts (round 3)
Informed by a scan of the open-source field — **TradingAgents** (Tauric Research):
analysts → Bull/Bear debate → research manager → risk committee → *audit-logged
structured decision*; **virattt/ai-hedge-fund** (51k★): investor-persona agents;
and the **"Profit Mirage"** paper warning about LLM information leakage (our prompts
already forbid training-data prices — the right guard).

- **Bull vs Bear debate** ([`copilot_debate.py`](../backend/copilot_debate.py)) — two
  opposing analysts argue the same evidence, a Research Manager issues a typed verdict
  (Bullish/Neutral/Bearish + conviction + action + what would change it). Reuses
  `multi_agent._assemble_data`; every debate is persisted to `copilot_debates` for audit.
  The cheapest antidote to LLM overconfidence.
- **Market Regime Radar** ([`market_regime.py`](../backend/market_regime.py)) — SPY trend
  + VIX band + sector breadth → a regime label and a suggested gross-exposure band, so the
  agent scales conviction to the tape. Pure `classify_regime` is unit-tested.
- **What-if simulator** (`simulate_trade`) — projects the book *after* a hypothetical order
  (weight, cash, buying power, concentration) and runs the compliance gate, placing nothing.
- **Catalyst awareness** (`get_earnings_intel`) — reuses the existing `earnings_intel` engine
  so the agent won't size into an imminent earnings print.
- **Slash commands** in the composer (`/debate`, `/regime`, `/whatif`, `/score`, `/research`,
  `/earnings`, `/risk`, `/backtest`, `/review`) for power-user speed.

### 4. Production hardening, perf & evals (round 4 — PR #30, 2026-06-13)
- **Trust path → Supabase Postgres** ([`copilot_store.py`](../backend/copilot_store.py),
  [`sql/copilot_core_schema.sql`](../backend/sql/copilot_core_schema.sql)) — staged trades / approval
  state moved off Mongo onto Postgres, with a real integration suite
  ([`tests/test_copilot_store_pg.py`](../backend/tests/test_copilot_store_pg.py), skips cleanly when no
  PG is reachable). This is the system-of-record consolidation the master-PRD risk table called for.
- **Standing eval harness** ([`evals/run_evals.py`](../backend/evals/run_evals.py),
  [`evals/golden.json`](../backend/evals/golden.json)) — a golden-query suite with graded checks,
  replacing the deleted one-off `eval_report.json`. Kicks off roadmap "Prove the AI" (Phase 3).
- **Latency**: parallel **read-tool fan-out** in the agent loop + **uvloop/httptools/orjson** drop-ins
  (`copilot_agent.py`, `8a39280`) — the roadmap perf note's #1 and #3 levers; covered by
  [`tests/test_copilot_parallel.py`](../backend/tests/test_copilot_parallel.py).
- **Resilience**: approval queue **survives refresh** + collapsed model picker (`47ad627`); chat
  endpoints **fail open** when legacy Mongo is unreachable (`04c42b3`); fixed a render crash where
  `toggleMode` was nested in `toggleConfirm`, tripping the Copilot error boundary on open (`d2f56ee`).

## Architecture (closed loop)
```
        ┌─────────────── conversation (SSE: thinking/tool/insight/compliance/trade/token) ───────────────┐
        │                                                                                                 │
 user ──┤  copilot_agent.run_copilot_agent  ──►  ReAct loop (Gemini / OpenAI-compat)                      │
        │        │                                                                                        │
        │        ├─ research:   agent_tools (snapshots, fundamentals, news, SEC, macro, web)             │
        │        ├─ intelligence: signal_engine  (20+ signals → composite conviction)                     │
        │        ├─ risk:       risk_engine     (beta, VaR, stress, concentration, sizing)               │
        │        ├─ backtest:   backtest/runner (DSL strategy → Sharpe/return/drawdown)                  │
        │        ├─ compute:    copilot_code_tool (sandboxed Python)                                      │
        │        └─ execute:    copilot_trading_tools ──► [compliance_engine GATE] ──► Alpaca paper       │
        │                                                                                                 │
        └─ memory: copilot_memory (cross-session) · staging: copilot_trades (human-approve)               │
```

## Do we need Rust? — honest assessment
**Not yet. The bottleneck is latency and data I/O, not CPU.**

A trade turn is dominated by (1) LLM round-trips (hundreds of ms to seconds each,
×N tool steps) and (2) `yfinance`/broker network calls. The numeric work —
signal math, parametric VaR, a small-universe backtest — is milliseconds in
NumPy/pandas and is *not* on the critical path the user feels. Rewriting any of
it in Rust would shave time the user can't perceive while adding a second
toolchain, FFI/build complexity, and maintenance drag — a poor trade given
limited compute and a solo build.

**Where Rust *would* pay off later (revisit when these become real):**
- **Strategy-swarm / parameter sweeps** — backtesting thousands of
  parameterizations or a large universe (S&P 1500) in parallel. A vectorized
  Rust engine (e.g. `polars` + a custom bar simulator) could turn minutes into
  seconds. This is the first place to reach for Rust.
- **Real-time intraday risk** on a large multi-account book (rolling
  covariance / VaR on every tick) — CPU-bound and latency-sensitive.
- **A tick-level event-driven backtester** with microstructure modeling.

**Recommended path:** stay in Python now. Keep the backtest engine's interface
clean (it already is — `run_backtest(strategy, start, end, data=...)`) so a Rust
core can later slot in behind it via PyO3 without touching callers. Adopt Rust
only when a profiler shows a sweep/real-time workload is the actual constraint.

## Roadmap (next, highest-leverage first)
1. **Conviction loop** — persist each thesis (entry signal score + rationale),
   then auto-review on a schedule via standing agents; grade decisions over time.
2. **Bracket orders** — stop-loss + take-profit as one tool, sized from
   `analyze_stock_risk`'s stop recommendation.
3. **Backtest → live bridge** — let the agent promote a backtested DSL strategy
   into a standing autonomous agent (with compliance gating each fill).
4. **Attribution** — per-thesis and per-strategy P&L attribution in the UI.
5. **Compliance audit log** — persist every gate decision for a real audit trail.
6. **Rust sweep core** — only once strategy-swarm sweeps are the measured bottleneck.
