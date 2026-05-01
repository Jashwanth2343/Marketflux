"""Alpaca integration configuration.

Centralised, environment-aware config that supports paper trading and
live trading modes with feature flags, rate limiting, and validation.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AlpacaEnvironment(str, Enum):
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class AlpacaConfig:
    api_key: str
    api_secret: str
    environment: AlpacaEnvironment = AlpacaEnvironment.PAPER

    # Feature flags
    sync_thesis_trades: bool = True
    enable_webhooks: bool = True
    enable_fractional_shares: bool = True
    enable_bracket_orders: bool = True
    enable_short_selling: bool = False

    # Rate limiting (requests per minute)
    rate_limit_rpm: int = 200

    # Retry configuration
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0

    # Default order settings
    default_time_in_force: str = "day"
    max_order_qty: float = 10000
    max_notional_per_order: float = 1_000_000

    # Webhook secret for verifying Alpaca event payloads
    webhook_secret: Optional[str] = None

    @property
    def base_url(self) -> str:
        if self.environment == AlpacaEnvironment.LIVE:
            return "https://api.alpaca.markets"
        return "https://paper-api.alpaca.markets"

    @property
    def is_paper(self) -> bool:
        return self.environment == AlpacaEnvironment.PAPER

    @property
    def is_live(self) -> bool:
        return self.environment == AlpacaEnvironment.LIVE


_config: Optional[AlpacaConfig] = None


def get_alpaca_config() -> Optional[AlpacaConfig]:
    """Load Alpaca config from environment variables. Returns None if unconfigured."""
    global _config
    if _config is not None:
        return _config

    api_key = os.getenv("APCA_API_KEY_ID", "").strip()
    api_secret = os.getenv("APCA_API_SECRET_KEY", "").strip()

    if not api_key or not api_secret:
        return None

    env_str = os.getenv("ALPACA_ENVIRONMENT", "paper").strip().lower()
    environment = AlpacaEnvironment.LIVE if env_str == "live" else AlpacaEnvironment.PAPER

    _config = AlpacaConfig(
        api_key=api_key,
        api_secret=api_secret,
        environment=environment,
        sync_thesis_trades=os.getenv("ALPACA_SYNC_THESIS_TRADES", "true").lower() == "true",
        enable_webhooks=os.getenv("ALPACA_ENABLE_WEBHOOKS", "true").lower() == "true",
        enable_fractional_shares=os.getenv("ALPACA_ENABLE_FRACTIONAL", "true").lower() == "true",
        enable_bracket_orders=os.getenv("ALPACA_ENABLE_BRACKET_ORDERS", "true").lower() == "true",
        enable_short_selling=os.getenv("ALPACA_ENABLE_SHORT_SELLING", "false").lower() == "true",
        rate_limit_rpm=int(os.getenv("ALPACA_RATE_LIMIT_RPM", "200")),
        max_retries=int(os.getenv("ALPACA_MAX_RETRIES", "3")),
        retry_backoff_seconds=float(os.getenv("ALPACA_RETRY_BACKOFF_SECONDS", "1.0")),
        default_time_in_force=os.getenv("ALPACA_DEFAULT_TIF", "day"),
        max_order_qty=float(os.getenv("ALPACA_MAX_ORDER_QTY", "10000")),
        max_notional_per_order=float(os.getenv("ALPACA_MAX_NOTIONAL", "1000000")),
        webhook_secret=os.getenv("ALPACA_WEBHOOK_SECRET") or None,
    )
    return _config


def reset_config() -> None:
    """Reset cached config (useful for testing)."""
    global _config
    _config = None


def is_alpaca_configured() -> bool:
    """Check if Alpaca credentials are present in the environment."""
    return get_alpaca_config() is not None
