"""Vectorized technical indicators used by the backtester DSL.

Each function takes the OHLCV DataFrame plus parameters and returns a Series
aligned to the frame's index. Indicators are computed once per backtest and
stored on the symbol's frame as additional columns named by the user
(e.g. ``rsi14``, ``sma200``).
"""
from __future__ import annotations

from typing import Callable, Dict

import numpy as np
import pandas as pd


def sma(df: pd.DataFrame, period: int = 20, source: str = "close") -> pd.Series:
    return df[source].rolling(window=int(period), min_periods=int(period)).mean()


def ema(df: pd.DataFrame, period: int = 20, source: str = "close") -> pd.Series:
    return df[source].ewm(span=int(period), adjust=False, min_periods=int(period)).mean()


def rsi(df: pd.DataFrame, period: int = 14, source: str = "close") -> pd.Series:
    delta = df[source].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(window=int(period), min_periods=int(period)).mean()
    avg_loss = loss.rolling(window=int(period), min_periods=int(period)).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.fillna(50.0)
    return out


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, source: str = "close") -> pd.Series:
    fast_e = df[source].ewm(span=int(fast), adjust=False).mean()
    slow_e = df[source].ewm(span=int(slow), adjust=False).mean()
    return fast_e - slow_e


def macd_signal(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, source: str = "close"
) -> pd.Series:
    line = macd(df, fast=fast, slow=slow, source=source)
    return line.ewm(span=int(signal), adjust=False).mean()


def bollinger_upper(df: pd.DataFrame, period: int = 20, num_std: float = 2.0, source: str = "close") -> pd.Series:
    mid = sma(df, period=period, source=source)
    std = df[source].rolling(window=int(period), min_periods=int(period)).std(ddof=0)
    return mid + float(num_std) * std


def bollinger_lower(df: pd.DataFrame, period: int = 20, num_std: float = 2.0, source: str = "close") -> pd.Series:
    mid = sma(df, period=period, source=source)
    std = df[source].rolling(window=int(period), min_periods=int(period)).std(ddof=0)
    return mid - float(num_std) * std


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=int(period), min_periods=int(period)).mean()


def returns(df: pd.DataFrame, period: int = 1, source: str = "close") -> pd.Series:
    return df[source].pct_change(int(period))


def rolling_high(df: pd.DataFrame, period: int = 20, source: str = "close") -> pd.Series:
    return df[source].rolling(window=int(period), min_periods=int(period)).max()


def rolling_low(df: pd.DataFrame, period: int = 20, source: str = "close") -> pd.Series:
    return df[source].rolling(window=int(period), min_periods=int(period)).min()


def volume_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    return df["volume"].rolling(window=int(period), min_periods=int(period)).mean()


INDICATOR_REGISTRY: Dict[str, Callable[..., pd.Series]] = {
    "sma": sma,
    "ema": ema,
    "rsi": rsi,
    "macd": macd,
    "macd_signal": macd_signal,
    "bollinger_upper": bollinger_upper,
    "bollinger_lower": bollinger_lower,
    "atr": atr,
    "returns": returns,
    "rolling_high": rolling_high,
    "rolling_low": rolling_low,
    "volume_sma": volume_sma,
}


def attach_indicators(df: pd.DataFrame, indicator_specs: Dict[str, Dict]) -> pd.DataFrame:
    """Compute each named indicator and attach it as a column.

    indicator_specs is ``{name: {"type": "rsi", "period": 14, ...}}``.
    Unknown indicator types raise ValueError so misconfigured strategies fail fast.
    """
    out = df.copy()
    for name, spec in (indicator_specs or {}).items():
        if not isinstance(spec, dict) or "type" not in spec:
            raise ValueError(f"indicator '{name}' missing 'type'")
        kind = spec["type"]
        fn = INDICATOR_REGISTRY.get(kind)
        if fn is None:
            raise ValueError(f"unknown indicator type '{kind}' for '{name}'")
        params = {k: v for k, v in spec.items() if k != "type"}
        out[name] = fn(out, **params)
    return out
