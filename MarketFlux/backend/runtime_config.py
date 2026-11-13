"""Process-wide deployment flags.

Production is the default. Anonymous fallbacks, localhost CORS, and the Python
scratchpad turn on only when the process is explicitly in development, or when
the operator sets the matching flag. Render does not set NODE_ENV, so an unset
environment must not look like local development.
"""
from __future__ import annotations

import os

_DEV_VALUES = {"development", "dev", "local", "test"}
_PROD_VALUES = {"production", "prod"}
_LOCALHOST_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def deployment_env() -> str:
    """Return the explicit environment name, or an empty string when unset."""
    for key in ("MARKETFLUX_ENV", "APP_ENV"):
        raw = os.getenv(key, "").strip().lower()
        if raw:
            return raw
    return os.getenv("NODE_ENV", "").strip().lower()


def is_development() -> bool:
    """True only for an explicit development/test environment.

    Unset and unknown values are treated as production so a public host that
    forgot NODE_ENV does not inherit local-only shortcuts.
    """
    env = deployment_env()
    if env in _DEV_VALUES:
        return True
    if env in _PROD_VALUES:
        return False
    return False


def demo_mode() -> bool:
    """Public portfolio demo: paper trades, confirm-before-execute, no standing agents."""
    return env_flag("DEMO_MODE", False)


def code_sandbox_enabled() -> bool:
    """The Copilot Python tool is off unless a private host opts in.

    DEMO_MODE forces it off. The tool is not a security boundary: pandas and
    numpy can reach the filesystem, so it must not run on a public server.
    """
    if demo_mode():
        return False
    return env_flag("ENABLE_CODE_SANDBOX", False)


def require_env(name: str, why: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required. {why} See MarketFlux/backend/.env.example.")
    return value


def require_mongo_url() -> str:
    return require_env(
        "MONGO_URL",
        "MongoDB is still required for copilot history, news, auth rate limits, and other "
        "collections. Supabase is the primary auth and Postgres store; it does not replace Mongo yet.",
    )


def require_db_name() -> str:
    return require_env(
        "DB_NAME",
        "DB_NAME is the MongoDB database that holds the collections MarketFlux still stores in Mongo.",
    )


def allowed_origins() -> list[str]:
    """Browser origins allowed to call the API with credentials.

    Localhost is added only in development. Production must list the real
    frontend origin in ALLOWED_ORIGINS.
    """
    raw = os.getenv("ALLOWED_ORIGINS", "").strip()
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    if origins:
        if is_development():
            for origin in _LOCALHOST_ORIGINS:
                if origin not in origins:
                    origins.append(origin)
        return origins
    if is_development():
        return list(_LOCALHOST_ORIGINS)
    raise RuntimeError(
        "ALLOWED_ORIGINS is required outside development. "
        "Set it to the public frontend origin, for example "
        "https://your-app.vercel.app. Localhost is not added automatically in production."
    )


def localhost_origin_regex() -> str | None:
    if is_development():
        return r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    return None


def copilot_daily_turn_cap() -> int:
    raw = os.getenv("COPILOT_DAILY_TURNS")
    if raw is None or not raw.strip():
        return 20 if demo_mode() else 50
    return int(raw)
