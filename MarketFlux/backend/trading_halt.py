"""Global trading kill switch for MarketFlux.

Two ways to halt all trading (checked live on every order path — no restart
needed to engage):

1. Env var ``TRADING_HALTED=1`` (or true/yes/on).
2. Runtime toggle via ``POST /api/admin/trading-halt`` (shared-secret header).

When halted, every order-placement path — the copilot ``place_order`` tool,
staged-trade approvals, pilot proposal execution, and the Alpaca REST order
endpoints — rejects with 403 / "Trading halted by kill switch".

This is a safety control for a paper-trading system, not a compliance
guarantee: it sits in front of order submission, it does not cancel
already-open orders (use the Alpaca cancel/liquidate endpoints for that).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

HALT_ENV_VAR = "TRADING_HALTED"
HALT_MESSAGE = "Trading halted by kill switch."

_runtime_halted: bool = False


def _env_halted() -> bool:
    return os.environ.get(HALT_ENV_VAR, "").strip().lower() in ("1", "true", "yes", "on")


def is_trading_halted() -> bool:
    """True if trading is halted via env var or the runtime toggle."""
    return _env_halted() or _runtime_halted


def set_trading_halted(halted: bool) -> bool:
    """Set the runtime halt flag. Returns the new effective halted state."""
    global _runtime_halted
    _runtime_halted = bool(halted)
    logger.warning("Trading halt %s via runtime toggle", "ENGAGED" if halted else "released")
    return is_trading_halted()


def halt_status() -> dict:
    """Inspectable halt state (for the admin endpoint / status surfaces)."""
    return {
        "halted": is_trading_halted(),
        "runtime_halted": _runtime_halted,
        "env_halted": _env_halted(),
        "env_var": HALT_ENV_VAR,
    }
