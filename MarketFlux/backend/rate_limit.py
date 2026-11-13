"""Per-IP limits for the public demo.

Render terminates TLS and sets X-Forwarded-For. The direct peer address would
be the proxy, so every visitor would share one bucket. The left-most forwarded
address is the client IP Render records.
"""
from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip, headers_enabled=True)


def copilot_rate_limit() -> str:
    raw = os.getenv("COPILOT_RATE_LIMIT", "10/minute").strip()
    return raw or "10/minute"
