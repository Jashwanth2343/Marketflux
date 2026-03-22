from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx


class NemoclawBridgeClient:
    """Thin integration seam for a future sandboxed agent bridge."""

    def __init__(self, base_url: Optional[str] = None, bearer_token: Optional[str] = None):
        self.base_url = (base_url or os.getenv("NEMOCLAW_BASE_URL") or "").rstrip("/")
        self.bearer_token = bearer_token or os.getenv("NEMOCLAW_BEARER_TOKEN") or ""

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    async def analyze(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.configured:
            return {
                "configured": False,
                "status": "bridge_unavailable",
                "message": "NemoClaw bridge is not configured yet.",
            }

        headers = {"Content-Type": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/analyze", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            data["configured"] = True
            return data

