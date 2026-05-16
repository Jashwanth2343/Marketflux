# PRD: Backtest Lab

## Problem Statement
A complete backtesting engine exists on the backend (DSL parser, bar-by-bar simulator, walk-forward analysis, metrics) but has zero frontend. Users cannot access backtesting capabilities.

## Scope

### In Scope
- Strategy form with visual DSL builder
- Raw JSON editor toggle for power users
- Equity curve visualization
- Performance metrics display
- Trade log table
- Walk-forward analysis UI
- Load example strategy button

### Out of Scope
- Saving backtest results to database (future migration)
- Strategy optimization / parameter sweeps
- Converting backtest results to trade proposals (Phase F)
- Real-time streaming (backtest is synchronous)

## API Contracts (all exist, already mounted)

### GET /api/backtest/example
Response: Example strategy DSL JSON

### POST /api/backtest/validate
Request: `{ strategy: {...DSL} }`
Response: `{ valid: true }` or `{ valid: false, errors: [...] }`

### POST /api/backtest/run
Request:
```json
{
  "strategy": { "universe": ["AAPL"], "indicators": [...], "entry_rules": [...], "exit_rules": [...], "position_sizing": {...}, "stop_loss_pct": 0.05 },
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "capital": 100000,
  "cost_model": { "commission_per_trade": 1.0, "slippage_bps": 5 }
}
```
Response:
```json
{
  "equity_curve": [{ "date": "...", "equity": 100000 }, ...],
  "trades": [{ "ticker": "AAPL", "entry_date": "...", "exit_date": "...", "pnl": 500, "return_pct": 5.0 }, ...],
  "metrics": { "cagr": 0.15, "sharpe": 1.2, "sortino": 1.5, "max_drawdown": -0.08, "win_rate": 0.6, "total_return": 0.15 }
}
```

### POST /api/backtest/walk-forward
Request: Same as /run + `{ train_months: 6, test_months: 2 }`
Response: `{ windows: [{ train_metrics: {...}, test_metrics: {...} }, ...] }`

## Component Structure

```
Backtest.js (~500 lines)
  ├── Left Panel (40%): Strategy Editor
  │   ├── Universe: multi-ticker input chips
  │   ├── Indicators: add/remove blocks (type select + period)
  │   ├── Entry Rules: condition builder (indicator op threshold)
  │   ├── Exit Rules: same pattern
  │   ├── Position Sizing: fixed_pct / equal_weight + pct
  │   ├── Stop Loss / Take Profit inputs
  │   ├── Date Range picker
  │   ├── Capital Base input
  │   ├── Cost Model fields
  │   ├── [Load Example] [Raw JSON toggle]
  │   └── [Run Backtest] [Walk Forward] buttons
  └── Right Panel (60%): Results
      ├── Equity Curve (Recharts AreaChart)
      ├── Metrics Grid (4-column stat cards)
      ├── Trade Log (sortable Table)
      └── Walk-Forward Windows (train/test pairs)
```

## Files to Create

| File | Lines |
|------|-------|
| `pages/Backtest.js` | ~500 |
| `lib/backtestApi.js` | ~30 |

## DSL Comparators (from backend dsl.py)
- `lt`, `gt`, `lte`, `gte`
- `crosses_above`, `crosses_below`

## Available Indicators (from backend indicators.py)
- `sma`, `ema`, `rsi`, `atr`, `bbands_upper`, `bbands_lower`, `macd`, `macd_signal`

## Acceptance Criteria
- [ ] `/backtest` renders the split-pane layout
- [ ] "Load Example" populates the form with a valid strategy
- [ ] "Run Backtest" sends strategy to backend and renders results
- [ ] Equity curve renders as an area chart
- [ ] Metrics grid shows CAGR, Sharpe, Sortino, Max DD
- [ ] Trade log table is sortable
- [ ] "Walk Forward" renders train/test window pairs
- [ ] Validation errors shown inline
