"""StrategySpec: a typed JSON DSL + a deterministic Python compiler.

The contract is non-negotiable:

  * The LLM emits ONLY a StrategySpec JSON. It never writes executable code.
  * This module turns a StrategySpec into a deterministic backtest. The same
    spec always produces the same numbers — replay-safe.
  * The compiler is lookahead-safe: signals computed at bar t can only be used
    to enter at bar t+1's open.
  * The compiler warns when the universe likely contains survivorship bias.

The DSL is intentionally tight. Adding an operator means adding a unit test.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

DEFAULT_SPEC_SCHEMA_VERSION = "1"

# ---------------------------------------------------------------------------
# Supported signal vocabulary. Each maps to a (window, computation) pair.
# Adding a new signal requires:
#   1) Implementing it in _compute_signal_column
#   2) Adding a unit test
#   3) Documenting expected range
# ---------------------------------------------------------------------------
SUPPORTED_SIGNALS = {
    "rsi_14",            # 0..100
    "sma_cross_50_200",  # -1, 0, +1 (golden cross / death cross)
    "mom_20d_pct",       # percent return over last 20 sessions
    "mom_120d_pct",      # percent return over last 120 sessions
    "drawdown_pct",      # current drawdown from 252d high, negative pct
    "close",             # raw close (rarely useful as a signal alone)
}

SUPPORTED_OPS = {">", ">=", "<", "<=", "==", "!="}

SUPPORTED_SIZING = {"equal_weight"}

SUPPORTED_EXIT_TYPES = {"signal", "stop_loss", "take_profit", "max_hold_days"}


@dataclass(frozen=True)
class StrategySpec:
    """Frozen, hashable strategy spec. Mutations are not allowed."""
    name: str
    universe: Tuple[str, ...]
    entry: Tuple[Dict[str, Any], ...]
    exit: Tuple[Dict[str, Any], ...]
    sizing: Dict[str, Any]
    schema_version: str = DEFAULT_SPEC_SCHEMA_VERSION
    rebalance_cadence: str = "daily"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "StrategySpec":
        validate_spec_dict(data)
        return StrategySpec(
            name=str(data["name"]).strip(),
            universe=tuple(sorted({t.upper() for t in data["universe"]})),
            entry=tuple({**c} for c in data["entry"]),
            exit=tuple({**c} for c in data["exit"]),
            sizing=dict(data["sizing"]),
            schema_version=str(data.get("schema_version", DEFAULT_SPEC_SCHEMA_VERSION)),
            rebalance_cadence=str(data.get("rebalance", {}).get("cadence", "daily")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "universe": list(self.universe),
            "entry": [dict(c) for c in self.entry],
            "exit": [dict(c) for c in self.exit],
            "sizing": dict(self.sizing),
            "rebalance": {"cadence": self.rebalance_cadence},
        }

    @property
    def spec_hash(self) -> str:
        """Stable hash for replay/audit. Same spec → same hash."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def validate_spec_dict(data: Dict[str, Any]) -> None:
    """Raises ValueError if spec is malformed. Be picky here."""
    if not isinstance(data, dict):
        raise ValueError("spec must be a dict")
    for required in ("name", "universe", "entry", "exit", "sizing"):
        if required not in data:
            raise ValueError(f"spec missing required field: {required}")
    if not isinstance(data["name"], str) or not data["name"].strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(data["universe"], list) or not data["universe"]:
        raise ValueError("universe must be a non-empty list of tickers")
    for ticker in data["universe"]:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError("universe entries must be non-empty strings")
        if len(ticker) > 10:
            raise ValueError(f"ticker too long: {ticker!r}")

    if not isinstance(data["entry"], list) or not data["entry"]:
        raise ValueError("entry must be a non-empty list of conditions")
    for cond in data["entry"]:
        _validate_signal_condition(cond, context="entry")

    if not isinstance(data["exit"], list) or not data["exit"]:
        raise ValueError("exit must be a non-empty list of conditions")
    for cond in data["exit"]:
        _validate_exit_condition(cond)

    sizing = data["sizing"]
    if not isinstance(sizing, dict):
        raise ValueError("sizing must be a dict")
    if sizing.get("type") not in SUPPORTED_SIZING:
        raise ValueError(
            f"sizing.type must be one of {sorted(SUPPORTED_SIZING)}; got {sizing.get('type')!r}"
        )
    max_positions = sizing.get("max_positions", 8)
    if not isinstance(max_positions, int) or max_positions < 1 or max_positions > 50:
        raise ValueError("sizing.max_positions must be int in [1,50]")
    max_pct = sizing.get("max_position_pct", 12)
    if not isinstance(max_pct, (int, float)) or max_pct <= 0 or max_pct > 100:
        raise ValueError("sizing.max_position_pct must be number in (0,100]")


def _validate_signal_condition(cond: Dict[str, Any], context: str) -> None:
    if not isinstance(cond, dict):
        raise ValueError(f"{context} condition must be a dict")
    signal = cond.get("signal")
    if signal not in SUPPORTED_SIGNALS:
        raise ValueError(
            f"{context}.signal must be one of {sorted(SUPPORTED_SIGNALS)}; got {signal!r}"
        )
    op = cond.get("op")
    if op not in SUPPORTED_OPS:
        raise ValueError(f"{context}.op must be one of {sorted(SUPPORTED_OPS)}; got {op!r}")
    value = cond.get("value")
    if not isinstance(value, (int, float)) or math.isnan(value) or math.isinf(value):
        raise ValueError(f"{context}.value must be a finite number")


def _validate_exit_condition(cond: Dict[str, Any]) -> None:
    if not isinstance(cond, dict):
        raise ValueError("exit condition must be a dict")
    etype = cond.get("type", "signal")
    if etype not in SUPPORTED_EXIT_TYPES:
        raise ValueError(
            f"exit.type must be one of {sorted(SUPPORTED_EXIT_TYPES)}; got {etype!r}"
        )
    if etype == "signal":
        _validate_signal_condition(cond, context="exit")
        return
    if etype in {"stop_loss", "take_profit"}:
        pct = cond.get("pct")
        if not isinstance(pct, (int, float)) or pct <= 0 or pct >= 1:
            raise ValueError(f"exit.{etype}.pct must be a number in (0,1)")
        return
    if etype == "max_hold_days":
        days = cond.get("value")
        if not isinstance(days, int) or days <= 0 or days > 365:
            raise ValueError("exit.max_hold_days.value must be int in (0,365]")


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------
@dataclass
class SpecCompileResult:
    spec_hash: str
    universe: List[str]
    trades: List[Dict[str, Any]]
    equity_curve: List[Dict[str, Any]]
    stats: Dict[str, float]
    warnings: List[str] = field(default_factory=list)


def compile_spec(
    spec: StrategySpec,
    *,
    price_panel: Optional[pd.DataFrame] = None,
    initial_capital: float = 25_000.0,
    transaction_cost_bps: float = 5.0,
) -> SpecCompileResult:
    """Deterministically run the spec against the supplied price panel.

    `price_panel` is a DataFrame indexed by date with MultiIndex columns
    ('field', 'ticker'). Required field: 'close'. Optional: 'high', 'low',
    'open'. If omitted, callers must inject their own data — the compiler
    itself does NOT fetch market data (keeps it pure and testable).
    """
    if price_panel is None or price_panel.empty:
        return SpecCompileResult(
            spec_hash=spec.spec_hash,
            universe=list(spec.universe),
            trades=[],
            equity_curve=[],
            stats={"final_equity": initial_capital, "cagr": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0, "num_trades": 0},
            warnings=["no_price_data_supplied"],
        )

    closes = price_panel["close"]
    closes = closes.reindex(columns=list(spec.universe))
    closes = closes.dropna(how="all")

    if closes.empty:
        return SpecCompileResult(
            spec_hash=spec.spec_hash,
            universe=list(spec.universe),
            trades=[],
            equity_curve=[],
            stats={"final_equity": initial_capital, "cagr": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0, "num_trades": 0},
            warnings=["no_overlapping_universe_data"],
        )

    signals = _compute_all_signals(closes)
    entry_mask = _eval_conditions(signals, spec.entry, mode="and")
    exit_signal_mask = _eval_conditions(
        signals,
        [c for c in spec.exit if c.get("type", "signal") == "signal"],
        mode="or",
    )

    stop_loss = _first_numeric(spec.exit, "stop_loss", "pct")
    take_profit = _first_numeric(spec.exit, "take_profit", "pct")
    max_hold = _first_numeric(spec.exit, "max_hold_days", "value")

    sizing = spec.sizing
    max_positions = int(sizing.get("max_positions", 8))
    max_position_pct = float(sizing.get("max_position_pct", 12)) / 100.0

    trades, equity_curve = _simulate(
        closes=closes,
        entry_mask=entry_mask,
        exit_signal_mask=exit_signal_mask,
        stop_loss_pct=stop_loss,
        take_profit_pct=take_profit,
        max_hold_days=int(max_hold) if max_hold is not None else None,
        max_positions=max_positions,
        max_position_pct=max_position_pct,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
    )

    stats = _compute_stats(equity_curve, initial_capital)
    stats["num_trades"] = float(len(trades))

    warnings: List[str] = []
    if len(spec.universe) <= 50:
        warnings.append(
            "backtest_universe_uses_current_constituents: results may be biased by survivorship; "
            "treat as a sanity check, not as forward-performance proof."
        )

    return SpecCompileResult(
        spec_hash=spec.spec_hash,
        universe=list(spec.universe),
        trades=trades,
        equity_curve=equity_curve,
        stats=stats,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _compute_all_signals(closes: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    return {sig: _compute_signal_column(sig, closes) for sig in SUPPORTED_SIGNALS}


def _compute_signal_column(signal: str, closes: pd.DataFrame) -> pd.DataFrame:
    if signal == "close":
        return closes
    if signal == "rsi_14":
        delta = closes.diff()
        gains = delta.clip(lower=0).rolling(window=14, min_periods=14).mean()
        losses = (-delta.clip(upper=0)).rolling(window=14, min_periods=14).mean()
        rs = gains / losses.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)
    if signal == "sma_cross_50_200":
        sma50 = closes.rolling(window=50, min_periods=50).mean()
        sma200 = closes.rolling(window=200, min_periods=200).mean()
        cross = (sma50 > sma200).astype(int) - (sma50 < sma200).astype(int)
        return cross.fillna(0).astype(float)
    if signal == "mom_20d_pct":
        return (closes.pct_change(20) * 100.0).fillna(0.0)
    if signal == "mom_120d_pct":
        return (closes.pct_change(120) * 100.0).fillna(0.0)
    if signal == "drawdown_pct":
        rolling_max = closes.rolling(window=252, min_periods=20).max()
        dd = (closes / rolling_max - 1.0) * 100.0
        return dd.fillna(0.0)
    raise ValueError(f"signal not implemented: {signal!r}")


def _eval_conditions(
    signals: Dict[str, pd.DataFrame],
    conditions: List[Dict[str, Any]],
    mode: str = "and",
) -> pd.DataFrame:
    if not conditions:
        # No conditions → "and" returns all True (always enter), "or" returns all False
        sample = next(iter(signals.values()))
        if mode == "or":
            return pd.DataFrame(False, index=sample.index, columns=sample.columns)
        return pd.DataFrame(True, index=sample.index, columns=sample.columns)

    masks: List[pd.DataFrame] = []
    for cond in conditions:
        if cond.get("type", "signal") != "signal":
            continue
        col = signals[cond["signal"]]
        op = cond["op"]
        v = cond["value"]
        if op == ">":
            masks.append(col > v)
        elif op == ">=":
            masks.append(col >= v)
        elif op == "<":
            masks.append(col < v)
        elif op == "<=":
            masks.append(col <= v)
        elif op == "==":
            masks.append(col == v)
        elif op == "!=":
            masks.append(col != v)

    if not masks:
        sample = next(iter(signals.values()))
        return pd.DataFrame(False, index=sample.index, columns=sample.columns)

    combined = masks[0]
    for m in masks[1:]:
        combined = combined & m if mode == "and" else combined | m
    return combined.fillna(False)


def _first_numeric(
    conds: Tuple[Dict[str, Any], ...],
    type_name: str,
    key: str,
) -> Optional[float]:
    for c in conds:
        if c.get("type") == type_name and key in c:
            return float(c[key])
    return None


def _simulate(
    *,
    closes: pd.DataFrame,
    entry_mask: pd.DataFrame,
    exit_signal_mask: pd.DataFrame,
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float],
    max_hold_days: Optional[int],
    max_positions: int,
    max_position_pct: float,
    initial_capital: float,
    transaction_cost_bps: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Daily-bar simulator. Lookahead-safe: signals at t -> action at t+1 open.

    Approximation: uses close as both entry and exit price (no intraday data).
    Transaction cost charged per fill. Cash earns 0%. No margin, no shorts.
    """
    cost = transaction_cost_bps / 10_000.0
    cash = initial_capital
    positions: Dict[str, Dict[str, Any]] = {}
    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []

    # Shift signals by 1: act on close[t-1] info at bar t.
    entry_mask = entry_mask.shift(1).fillna(False)
    exit_signal_mask = exit_signal_mask.shift(1).fillna(False)

    dates = closes.index
    for t_idx, date in enumerate(dates):
        prices = closes.loc[date]

        # --- 1. Process exits first (so cash is freed before entries) ---
        to_close: List[str] = []
        for ticker, pos in positions.items():
            price = prices.get(ticker)
            if price is None or pd.isna(price):
                continue
            entry_price = pos["entry_price"]
            held_days = t_idx - pos["entry_idx"]

            exit_reason: Optional[str] = None
            if stop_loss_pct is not None and price <= entry_price * (1 - stop_loss_pct):
                exit_reason = "stop_loss"
            elif take_profit_pct is not None and price >= entry_price * (1 + take_profit_pct):
                exit_reason = "take_profit"
            elif max_hold_days is not None and held_days >= max_hold_days:
                exit_reason = "max_hold_days"
            elif bool(exit_signal_mask.at[date, ticker]) if ticker in exit_signal_mask.columns else False:
                exit_reason = "signal"

            if exit_reason:
                proceeds = pos["shares"] * price * (1 - cost)
                cash += proceeds
                trades.append({
                    "ticker": ticker,
                    "entry_date": pos["entry_date"].isoformat(),
                    "exit_date": date.isoformat(),
                    "entry_price": float(entry_price),
                    "exit_price": float(price),
                    "shares": float(pos["shares"]),
                    "pnl_usd": float(proceeds - pos["cost_basis"]),
                    "pnl_pct": float((price / entry_price - 1) * 100),
                    "exit_reason": exit_reason,
                    "held_days": held_days,
                })
                to_close.append(ticker)
        for ticker in to_close:
            positions.pop(ticker, None)

        # --- 2. Process entries ---
        open_slots = max_positions - len(positions)
        if open_slots > 0:
            # Tickers that triggered entry today and aren't already held
            row = entry_mask.loc[date] if date in entry_mask.index else None
            if row is not None:
                candidates = [t for t, v in row.items() if bool(v) and t not in positions]
                # Deterministic ordering: alphabetical
                candidates.sort()
                candidates = candidates[:open_slots]
                # Equity at this bar for position sizing
                equity = cash + sum(
                    p["shares"] * (prices.get(t, p["entry_price"]) or p["entry_price"])
                    for t, p in positions.items()
                )
                target_per_position = min(
                    equity * max_position_pct,
                    cash / max(1, len(candidates)),
                ) if candidates else 0.0
                for ticker in candidates:
                    price = prices.get(ticker)
                    if price is None or pd.isna(price) or price <= 0:
                        continue
                    shares = math.floor(target_per_position / price)
                    if shares <= 0:
                        continue
                    cost_basis = shares * price * (1 + cost)
                    if cost_basis > cash:
                        continue
                    cash -= cost_basis
                    positions[ticker] = {
                        "shares": shares,
                        "entry_price": float(price),
                        "entry_date": date,
                        "entry_idx": t_idx,
                        "cost_basis": cost_basis,
                    }

        # --- 3. Mark-to-market the equity curve ---
        mtm = cash + sum(
            p["shares"] * (prices.get(t, p["entry_price"]) or p["entry_price"])
            for t, p in positions.items()
        )
        equity_curve.append({"date": date.isoformat(), "equity": float(mtm)})

    return trades, equity_curve


def _compute_stats(equity_curve: List[Dict[str, Any]], initial_capital: float) -> Dict[str, float]:
    if not equity_curve:
        return {"final_equity": initial_capital, "cagr": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0}
    equities = pd.Series([e["equity"] for e in equity_curve])
    final = float(equities.iloc[-1])
    n_days = len(equities)
    years = max(n_days / 252.0, 1 / 252.0)
    cagr = (final / initial_capital) ** (1 / years) - 1 if final > 0 else -1.0

    rolling_max = equities.cummax()
    dd = (equities / rolling_max - 1.0) * 100.0
    max_dd = float(dd.min())

    returns = equities.pct_change().dropna()
    if len(returns) > 5 and returns.std() > 0:
        sharpe = float((returns.mean() / returns.std()) * math.sqrt(252))
    else:
        sharpe = 0.0

    return {
        "final_equity": final,
        "cagr": float(cagr),
        "max_dd_pct": max_dd,
        "sharpe": sharpe,
    }


# ---------------------------------------------------------------------------
# Replay helpers
# ---------------------------------------------------------------------------
def replay(spec_dict: Dict[str, Any], price_panel: pd.DataFrame, **kwargs: Any) -> SpecCompileResult:
    """Convenience: from a JSON spec dict + price panel, run compile_spec."""
    spec = StrategySpec.from_dict(spec_dict)
    return compile_spec(spec, price_panel=price_panel, **kwargs)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
