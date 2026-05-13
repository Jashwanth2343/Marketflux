"""Strategy DSL: a small JSON-friendly rule language for entry/exit logic.

Example strategy::

    {
      "name": "RSI mean reversion w/ trend filter",
      "universe": ["AAPL", "MSFT"],
      "indicators": {
        "rsi14":  {"type": "rsi", "period": 14},
        "sma200": {"type": "sma", "period": 200}
      },
      "entry":  {"all": [{"lt": ["rsi14", 30]}, {"gt": ["close", "sma200"]}]},
      "exit":   {"any": [{"gt": ["rsi14", 65]}, {"hold_days_gte": 20}]},
      "position_sizing": {"type": "fixed_pct", "pct": 0.10},
      "max_positions": 5,
      "stop_loss_pct": 0.08,
      "take_profit_pct": 0.20
    }

Comparators take a 2-element list ``[lhs, rhs]``. Each operand is either a
number or the name of an OHLCV column / user-defined indicator. Boolean
combinators are ``all`` (AND), ``any`` (OR), ``not`` (NOT). Two trade-state
predicates are also allowed in exit conditions:

* ``{"hold_days_gte": N}`` – true when the open position has been held >= N bars
* ``{"profit_pct_gte": x}`` – true when unrealized return >= x (e.g. 0.10 for 10%)
* ``{"loss_pct_gte": x}``   – true when unrealized loss >= x (positive number)

Cross-bar predicates (``crosses_above`` / ``crosses_below``) compare the current
bar to the previous bar. They evaluate to False on the first bar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pandas as pd


COMPARATORS = {"lt", "lte", "gt", "gte", "eq", "neq", "crosses_above", "crosses_below"}
COMBINATORS = {"all", "any", "not"}
TRADE_PREDICATES = {"hold_days_gte", "profit_pct_gte", "loss_pct_gte"}


# ---------------------------------------------------------------------------
# Strategy container
# ---------------------------------------------------------------------------

@dataclass
class Strategy:
    name: str
    universe: List[str]
    indicators: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    entry: Dict[str, Any] = field(default_factory=dict)
    exit: Dict[str, Any] = field(default_factory=dict)
    position_sizing: Dict[str, Any] = field(default_factory=lambda: {"type": "fixed_pct", "pct": 0.1})
    max_positions: int = 10
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Strategy":
        validate_strategy(data)
        return cls(
            name=str(data.get("name", "unnamed")),
            universe=[str(s).upper() for s in data["universe"]],
            indicators=dict(data.get("indicators") or {}),
            entry=dict(data.get("entry") or {}),
            exit=dict(data.get("exit") or {}),
            position_sizing=dict(data.get("position_sizing") or {"type": "fixed_pct", "pct": 0.1}),
            max_positions=int(data.get("max_positions", 10)),
            stop_loss_pct=_opt_float(data.get("stop_loss_pct")),
            take_profit_pct=_opt_float(data.get("take_profit_pct")),
        )


def _opt_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    return float(v)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_strategy(data: Mapping[str, Any]) -> None:
    """Raise ValueError if the strategy dict is malformed.

    Validates structure only; we don't try to validate that operand names
    correspond to real columns until the engine runs (some come from indicators
    that are defined in the same dict).
    """
    if not isinstance(data, Mapping):
        raise ValueError("strategy must be a dict")
    if "universe" not in data or not isinstance(data["universe"], list) or not data["universe"]:
        raise ValueError("strategy.universe must be a non-empty list")
    if "entry" not in data or not isinstance(data["entry"], dict):
        raise ValueError("strategy.entry must be a dict expression")
    if "exit" not in data or not isinstance(data["exit"], dict):
        raise ValueError("strategy.exit must be a dict expression")
    _validate_expr(data["entry"], in_exit=False, path="entry")
    _validate_expr(data["exit"], in_exit=True, path="exit")
    sizing = data.get("position_sizing") or {"type": "fixed_pct", "pct": 0.1}
    if not isinstance(sizing, Mapping) or "type" not in sizing:
        raise ValueError("position_sizing must be a dict with a 'type'")
    if sizing["type"] not in {"fixed_pct", "fixed_dollar", "equal_weight"}:
        raise ValueError(f"unknown position_sizing.type {sizing['type']!r}")


def _validate_expr(expr: Mapping[str, Any], in_exit: bool, path: str) -> None:
    if not isinstance(expr, Mapping) or len(expr) != 1:
        raise ValueError(f"{path}: each node must be a dict with exactly one key")
    op, val = next(iter(expr.items()))
    if op in COMBINATORS:
        if op == "not":
            if not isinstance(val, Mapping):
                raise ValueError(f"{path}.not: value must be a dict expression")
            _validate_expr(val, in_exit, f"{path}.not")
            return
        if not isinstance(val, list) or not val:
            raise ValueError(f"{path}.{op}: value must be a non-empty list")
        for i, sub in enumerate(val):
            _validate_expr(sub, in_exit, f"{path}.{op}[{i}]")
        return
    if op in COMPARATORS:
        if not isinstance(val, list) or len(val) != 2:
            raise ValueError(f"{path}.{op}: value must be a 2-element list")
        return
    if op in TRADE_PREDICATES:
        if not in_exit:
            raise ValueError(f"{path}.{op}: trade-state predicates only allowed in exit conditions")
        if not isinstance(val, (int, float)):
            raise ValueError(f"{path}.{op}: value must be numeric")
        return
    raise ValueError(f"{path}: unknown operator {op!r}")


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _resolve(operand: Any, row: Mapping[str, Any], prev_row: Optional[Mapping[str, Any]] = None) -> Tuple[float, Optional[float]]:
    """Return (current_value, previous_value) for an operand.

    Numeric literals return ``(literal, literal)``. Column names look up in row /
    prev_row. Missing / NaN values are returned as NaN so comparators short-circuit
    to False.
    """
    if isinstance(operand, (int, float)) and not isinstance(operand, bool):
        f = float(operand)
        return f, f
    if not isinstance(operand, str):
        raise ValueError(f"operand must be string or number, got {operand!r}")
    cur = _safe_lookup(row, operand)
    prev = _safe_lookup(prev_row, operand) if prev_row is not None else None
    return cur, prev


def _safe_lookup(row: Optional[Mapping[str, Any]], name: str) -> float:
    if row is None:
        return float("nan")
    if name not in row:
        raise KeyError(f"unknown column / indicator: {name}")
    val = row[name]
    try:
        return float(val)
    except (TypeError, ValueError):
        return float("nan")


def _is_nan(x: float) -> bool:
    return x != x  # NaN-safe; faster than math.isnan in hot path


@dataclass
class TradeState:
    """Snapshot the engine passes into exit-condition evaluation."""

    hold_days: int = 0
    unrealized_return: float = 0.0  # decimal, e.g. 0.05 for +5%


def evaluate(
    expr: Mapping[str, Any],
    row: Mapping[str, Any],
    prev_row: Optional[Mapping[str, Any]] = None,
    trade: Optional[TradeState] = None,
) -> bool:
    """Evaluate a DSL expression against the current bar."""
    op, val = next(iter(expr.items()))

    if op == "all":
        return all(evaluate(sub, row, prev_row, trade) for sub in val)
    if op == "any":
        return any(evaluate(sub, row, prev_row, trade) for sub in val)
    if op == "not":
        return not evaluate(val, row, prev_row, trade)

    if op in TRADE_PREDICATES:
        if trade is None:
            return False
        if op == "hold_days_gte":
            return trade.hold_days >= float(val)
        if op == "profit_pct_gte":
            return trade.unrealized_return >= float(val)
        if op == "loss_pct_gte":
            return trade.unrealized_return <= -float(val)

    lhs, lhs_prev = _resolve(val[0], row, prev_row)
    rhs, rhs_prev = _resolve(val[1], row, prev_row)

    if op == "lt":
        return (not _is_nan(lhs)) and (not _is_nan(rhs)) and lhs < rhs
    if op == "lte":
        return (not _is_nan(lhs)) and (not _is_nan(rhs)) and lhs <= rhs
    if op == "gt":
        return (not _is_nan(lhs)) and (not _is_nan(rhs)) and lhs > rhs
    if op == "gte":
        return (not _is_nan(lhs)) and (not _is_nan(rhs)) and lhs >= rhs
    if op == "eq":
        return (not _is_nan(lhs)) and (not _is_nan(rhs)) and lhs == rhs
    if op == "neq":
        return (not _is_nan(lhs)) and (not _is_nan(rhs)) and lhs != rhs
    if op == "crosses_above":
        if any(_is_nan(x) for x in (lhs, rhs, lhs_prev or float("nan"), rhs_prev or float("nan"))):
            return False
        return lhs_prev <= rhs_prev and lhs > rhs  # type: ignore[operator]
    if op == "crosses_below":
        if any(_is_nan(x) for x in (lhs, rhs, lhs_prev or float("nan"), rhs_prev or float("nan"))):
            return False
        return lhs_prev >= rhs_prev and lhs < rhs  # type: ignore[operator]

    raise ValueError(f"unknown operator {op!r} during evaluation")


def evaluate_series(expr: Mapping[str, Any], df: pd.DataFrame) -> pd.Series:
    """Evaluate a DSL expression across an entire frame for diagnostics.

    Trade-state predicates are not allowed (they require a live position).
    """
    out = []
    prev = None
    for _, row in df.iterrows():
        out.append(evaluate(expr, row, prev))
        prev = row
    return pd.Series(out, index=df.index, dtype=bool)
