"""Bar-by-bar portfolio simulator.

Design principles
-----------------
* Signals are evaluated on bar ``t`` close. Fills happen at bar ``t+1`` open
  with slippage applied — this prevents lookahead bias. The final bar therefore
  cannot open a new position; open positions are force-closed at the last close.
* Exit logic is checked before entry logic each bar, so a stop-out frees capital
  for new entries the same day.
* Position sizing uses the current equity (cash + marked-to-market positions) so
  the strategy compounds.
* The simulator is symbol-independent for indicator computation but
  portfolio-aware for sizing and the ``max_positions`` cap.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

import pandas as pd

from .costs import CostModel, DEFAULT_COSTS
from .dsl import Strategy, TradeState, evaluate
from .indicators import attach_indicators


@dataclass
class Position:
    symbol: str
    shares: float
    entry_price: float       # post-slippage
    entry_date: pd.Timestamp
    entry_bar_index: int
    cost_basis: float        # shares * entry_price + commission paid


@dataclass
class Trade:
    symbol: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: float
    pnl: float           # net of all commissions and slippage
    return_pct: float    # net return on cost basis
    bars_held: int
    exit_reason: str

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "entry_date": self.entry_date.isoformat(),
            "exit_date": self.exit_date.isoformat(),
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "shares": self.shares,
            "pnl": self.pnl,
            "return_pct": self.return_pct,
            "bars_held": self.bars_held,
            "exit_reason": self.exit_reason,
        }


@dataclass
class BacktestResult:
    strategy_name: str
    start: pd.Timestamp
    end: pd.Timestamp
    initial_capital: float
    final_equity: float
    equity_curve: pd.Series
    trades: List[Trade] = field(default_factory=list)
    universe: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        from .metrics import compute_metrics, monthly_returns

        trade_dicts = [t.as_dict() for t in self.trades]
        metrics = compute_metrics(self.equity_curve, trade_dicts)
        return {
            "strategy_name": self.strategy_name,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "initial_capital": self.initial_capital,
            "final_equity": self.final_equity,
            "universe": self.universe,
            "metrics": metrics.as_dict(),
            "monthly_returns": monthly_returns(self.equity_curve),
            "equity_curve": [
                {"date": idx.isoformat(), "equity": float(val)}
                for idx, val in self.equity_curve.items()
            ],
            "trades": [t.as_dict() for t in self.trades],
        }


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------

def _compute_position_size(
    sizing: Mapping,
    equity: float,
    cash: float,
    fill_price: float,
    open_position_count: int,
    max_positions: int,
) -> float:
    """Return a number of shares (float; fractional shares allowed) for a new entry."""
    if fill_price <= 0:
        return 0.0
    sizing_type = sizing.get("type", "fixed_pct")
    target_dollars: float
    if sizing_type == "fixed_pct":
        pct = float(sizing.get("pct", 0.10))
        target_dollars = equity * pct
    elif sizing_type == "fixed_dollar":
        target_dollars = float(sizing.get("amount", 1000.0))
    elif sizing_type == "equal_weight":
        slots = max(1, max_positions - open_position_count)
        target_dollars = cash / slots
    else:
        target_dollars = equity * 0.10
    target_dollars = min(target_dollars, cash)
    if target_dollars <= 0:
        return 0.0
    shares = target_dollars / fill_price
    return shares


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def run_engine(
    strategy: Strategy,
    data: Dict[str, pd.DataFrame],
    initial_capital: float = 100_000.0,
    costs: Optional[CostModel] = None,
) -> BacktestResult:
    """Simulate `strategy` over the provided per-symbol OHLCV frames.

    All frames must already cover the desired date range. Frames missing from
    `data` are silently skipped. Indicators declared on the strategy are
    computed once per frame.
    """
    costs = costs or DEFAULT_COSTS

    # Compute indicators per symbol; align on union calendar.
    enriched: Dict[str, pd.DataFrame] = {}
    for sym in strategy.universe:
        df = data.get(sym.upper())
        if df is None or df.empty:
            continue
        enriched[sym.upper()] = attach_indicators(df, strategy.indicators)

    if not enriched:
        empty = pd.Series(dtype=float)
        return BacktestResult(
            strategy_name=strategy.name,
            start=pd.Timestamp("1970-01-01"),
            end=pd.Timestamp("1970-01-01"),
            initial_capital=initial_capital,
            final_equity=initial_capital,
            equity_curve=empty,
            universe=list(strategy.universe),
        )

    # Shared trading calendar = union of all frames' indices, sorted.
    union_index = pd.Index(sorted(set().union(*(df.index for df in enriched.values()))))

    # Pre-build per-symbol bar lookup as list of (timestamp, row_dict, prev_row_dict)
    # to keep the inner loop fast.
    per_symbol_bars: Dict[str, Dict[pd.Timestamp, dict]] = {}
    for sym, df in enriched.items():
        per_symbol_bars[sym] = {ts: row.to_dict() for ts, row in df.iterrows()}

    cash = float(initial_capital)
    positions: Dict[str, Position] = {}
    closed_trades: List[Trade] = []
    pending_orders: List[dict] = []  # filled at the next bar's open
    equity_records: List[tuple] = []

    bar_index_for: Dict[str, Dict[pd.Timestamp, int]] = {
        sym: {ts: i for i, ts in enumerate(df.index)} for sym, df in enriched.items()
    }

    for ts in union_index:
        # 1. Execute pending orders at today's open.
        if pending_orders:
            still_pending: List[dict] = []
            for order in pending_orders:
                sym = order["symbol"]
                bars = per_symbol_bars.get(sym, {})
                row = bars.get(ts)
                if row is None:
                    # symbol has no bar today; carry the order to the next bar
                    still_pending.append(order)
                    continue
                ref_open = float(row.get("open", float("nan")))
                if ref_open != ref_open or ref_open <= 0:  # NaN or non-positive
                    still_pending.append(order)
                    continue
                if order["side"] == "buy":
                    fill = costs.fill_price(ref_open, "buy")
                    shares = _compute_position_size(
                        strategy.position_sizing,
                        equity=_mark_to_market_equity(cash, positions, ts, per_symbol_bars),
                        cash=cash,
                        fill_price=fill,
                        open_position_count=len(positions),
                        max_positions=strategy.max_positions,
                    )
                    if shares <= 0 or len(positions) >= strategy.max_positions:
                        continue
                    notional = shares * fill
                    commission = costs.commission(shares, fill)
                    if notional + commission > cash:
                        # scale down to what we can afford
                        shares = max(0.0, (cash - commission) / fill)
                        if shares <= 0:
                            continue
                        notional = shares * fill
                        commission = costs.commission(shares, fill)
                    cash -= notional + commission
                    positions[sym] = Position(
                        symbol=sym,
                        shares=shares,
                        entry_price=fill,
                        entry_date=ts,
                        entry_bar_index=bar_index_for[sym].get(ts, 0),
                        cost_basis=notional + commission,
                    )
                elif order["side"] == "sell":
                    pos = positions.pop(sym, None)
                    if pos is None:
                        continue
                    fill = costs.fill_price(ref_open, "sell")
                    proceeds = pos.shares * fill
                    commission = costs.commission(pos.shares, fill)
                    cash += proceeds - commission
                    pnl = (proceeds - commission) - pos.cost_basis
                    return_pct = pnl / pos.cost_basis if pos.cost_basis > 0 else 0.0
                    bars_held = bar_index_for[sym].get(ts, pos.entry_bar_index) - pos.entry_bar_index
                    closed_trades.append(
                        Trade(
                            symbol=sym,
                            entry_date=pos.entry_date,
                            exit_date=ts,
                            entry_price=pos.entry_price,
                            exit_price=fill,
                            shares=pos.shares,
                            pnl=pnl,
                            return_pct=return_pct,
                            bars_held=bars_held,
                            exit_reason=order.get("reason", "signal"),
                        )
                    )
            pending_orders = still_pending

        # 2. Evaluate exits on currently open positions (using today's close).
        for sym in list(positions.keys()):
            bars = per_symbol_bars.get(sym, {})
            row = bars.get(ts)
            if row is None:
                continue
            df = enriched[sym]
            idx = bar_index_for[sym].get(ts)
            prev_row = df.iloc[idx - 1].to_dict() if idx and idx > 0 else None
            pos = positions[sym]
            close = float(row.get("close", float("nan")))
            if close != close:
                continue
            unrealized = (close / pos.entry_price - 1.0) if pos.entry_price > 0 else 0.0
            trade_state = TradeState(
                hold_days=idx - pos.entry_bar_index if idx is not None else 0,
                unrealized_return=unrealized,
            )

            exit_reason = None
            if strategy.stop_loss_pct is not None and unrealized <= -abs(strategy.stop_loss_pct):
                exit_reason = "stop_loss"
            elif strategy.take_profit_pct is not None and unrealized >= abs(strategy.take_profit_pct):
                exit_reason = "take_profit"
            elif evaluate(strategy.exit, row, prev_row, trade_state):
                exit_reason = "signal"

            if exit_reason is not None:
                pending_orders.append({"symbol": sym, "side": "sell", "reason": exit_reason})

        # 3. Evaluate entries (only if we have headroom).
        if len(positions) < strategy.max_positions:
            for sym in strategy.universe:
                sym = sym.upper()
                if sym in positions:
                    continue
                if any(o["symbol"] == sym and o["side"] == "buy" for o in pending_orders):
                    continue
                bars = per_symbol_bars.get(sym, {})
                row = bars.get(ts)
                if row is None:
                    continue
                df = enriched[sym]
                idx = bar_index_for[sym].get(ts)
                prev_row = df.iloc[idx - 1].to_dict() if idx and idx > 0 else None
                if evaluate(strategy.entry, row, prev_row):
                    pending_orders.append({"symbol": sym, "side": "buy"})
                    if len(positions) + sum(1 for o in pending_orders if o["side"] == "buy") >= strategy.max_positions:
                        break

        # 4. Mark-to-market and record equity.
        equity = _mark_to_market_equity(cash, positions, ts, per_symbol_bars)
        equity_records.append((ts, equity))

    # Force-close any remaining positions at last available close (no slippage on
    # the forced exit — we're past the strategy's control).
    if positions:
        last_ts = union_index[-1]
        for sym, pos in list(positions.items()):
            bars = per_symbol_bars.get(sym, {})
            row = bars.get(last_ts)
            close_price = float(row["close"]) if row and "close" in row else pos.entry_price
            commission = costs.commission(pos.shares, close_price)
            proceeds = pos.shares * close_price
            cash += proceeds - commission
            pnl = (proceeds - commission) - pos.cost_basis
            return_pct = pnl / pos.cost_basis if pos.cost_basis > 0 else 0.0
            bars_held = bar_index_for[sym].get(last_ts, pos.entry_bar_index) - pos.entry_bar_index
            closed_trades.append(
                Trade(
                    symbol=sym,
                    entry_date=pos.entry_date,
                    exit_date=last_ts,
                    entry_price=pos.entry_price,
                    exit_price=close_price,
                    shares=pos.shares,
                    pnl=pnl,
                    return_pct=return_pct,
                    bars_held=bars_held,
                    exit_reason="end_of_backtest",
                )
            )
            positions.pop(sym)
        equity_records[-1] = (last_ts, cash)

    equity_series = pd.Series({ts: val for ts, val in equity_records}, dtype=float).sort_index()

    return BacktestResult(
        strategy_name=strategy.name,
        start=union_index[0] if len(union_index) else pd.Timestamp("1970-01-01"),
        end=union_index[-1] if len(union_index) else pd.Timestamp("1970-01-01"),
        initial_capital=initial_capital,
        final_equity=float(equity_series.iloc[-1]) if not equity_series.empty else initial_capital,
        equity_curve=equity_series,
        trades=closed_trades,
        universe=list(enriched.keys()),
    )


def _mark_to_market_equity(
    cash: float,
    positions: Mapping[str, Position],
    ts: pd.Timestamp,
    per_symbol_bars: Mapping[str, Mapping[pd.Timestamp, dict]],
) -> float:
    total = cash
    for sym, pos in positions.items():
        bars = per_symbol_bars.get(sym, {})
        row = bars.get(ts)
        if row is None:
            total += pos.shares * pos.entry_price
        else:
            close = row.get("close")
            try:
                total += pos.shares * float(close)
            except (TypeError, ValueError):
                total += pos.shares * pos.entry_price
    return total
