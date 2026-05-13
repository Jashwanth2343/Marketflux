"""OHLCV data loader for the backtester.

Wraps yfinance with a small disk cache so repeated backtests over the same
window are deterministic and cheap. All data is returned as a pandas DataFrame
with a tz-naive DatetimeIndex and lowercase columns: open, high, low, close,
volume.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]

_DISK_CACHE = None


def _get_disk_cache():
    global _DISK_CACHE
    if _DISK_CACHE is not None:
        return _DISK_CACHE
    try:
        import diskcache  # type: ignore

        cache_dir = os.environ.get(
            "BACKTEST_CACHE_DIR",
            os.path.join(os.path.dirname(__file__), ".cache"),
        )
        _DISK_CACHE = diskcache.Cache(cache_dir)
    except Exception as exc:  # pragma: no cover - cache is best-effort
        logger.info("backtest.data: disk cache unavailable (%s)", exc)
        _DISK_CACHE = None
    return _DISK_CACHE


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    keep = [c for c in OHLCV_COLUMNS if c in df.columns]
    df = df[keep].astype(float, errors="ignore")
    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def _yf_download(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
    import yfinance as yf  # local import; heavy

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)
    return _normalize_frame(df)


def load_ohlcv(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame:
    """Return OHLCV bars for `symbol` between `start` and `end` (inclusive).

    Dates are ISO strings (YYYY-MM-DD). The frame's index is tz-naive.
    Empty frames are returned for missing data; callers must check.
    """
    symbol = symbol.upper().strip()
    cache_key = f"ohlcv::{symbol}::{start}::{end}::{interval}"
    cache = _get_disk_cache() if use_cache else None
    if cache is not None:
        cached = cache.get(cache_key)
        if isinstance(cached, pd.DataFrame):
            return cached

    df = _yf_download(symbol, start, end, interval)

    if cache is not None and not df.empty:
        try:
            cache.set(cache_key, df, expire=24 * 3600)
        except Exception:  # pragma: no cover
            pass
    return df


def load_universe(
    symbols: Iterable[str],
    start: str,
    end: str,
    interval: str = "1d",
    use_cache: bool = True,
) -> Dict[str, pd.DataFrame]:
    """Load OHLCV for many symbols. Symbols with no data are skipped silently."""
    out: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = load_ohlcv(sym, start, end, interval=interval, use_cache=use_cache)
        if df is not None and not df.empty:
            out[sym.upper()] = df
        else:
            logger.info("backtest.data: no bars for %s in %s..%s", sym, start, end)
    return out


@dataclass
class SyntheticPriceConfig:
    """Used by tests to build deterministic OHLCV frames."""

    start: str
    periods: int
    drift: float = 0.0
    seed: Optional[int] = 0

    def build(self, symbol: str) -> pd.DataFrame:
        import numpy as np

        rng = np.random.default_rng(self.seed)
        idx = pd.bdate_range(start=self.start, periods=self.periods)
        steps = rng.normal(loc=self.drift, scale=0.01, size=self.periods)
        closes = 100.0 * (1.0 + pd.Series(steps, index=idx)).cumprod()
        opens = closes.shift(1).fillna(closes.iloc[0])
        highs = pd.concat([opens, closes], axis=1).max(axis=1) * 1.005
        lows = pd.concat([opens, closes], axis=1).min(axis=1) * 0.995
        vols = pd.Series(rng.integers(1_000_000, 5_000_000, size=self.periods), index=idx)
        return pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols}
        )
