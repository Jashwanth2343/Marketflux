"""Supabase client for MarketFlux — the durable brain.

Provides:
  - Connection singleton (supabase-py)
  - Auth helpers (verify JWT from Supabase Auth)
  - Memory operations (pgvector semantic retrieval)
  - CRUD helpers for pilot tables

Env vars:
  SUPABASE_URL          — project URL (e.g. https://xxx.supabase.co)
  SUPABASE_SERVICE_KEY  — service_role key (backend only, bypasses RLS)
  SUPABASE_ANON_KEY     — publishable anon key (for frontend / RLS-gated calls)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_client = None
_service_client = None


def get_supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "")


def is_supabase_configured() -> bool:
    return bool(get_supabase_url() and os.getenv("SUPABASE_SERVICE_KEY"))


def get_client():
    """Get the Supabase client using the anon key (respects RLS)."""
    global _client
    if _client is not None:
        return _client

    url = get_supabase_url()
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return None

    from supabase import create_client
    _client = create_client(url, key)
    return _client


def get_service_client():
    """Get the Supabase client using service_role key (bypasses RLS).

    Use only in backend server code, never expose to frontend.
    """
    global _service_client
    if _service_client is not None:
        return _service_client

    url = get_supabase_url()
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return None

    from supabase import create_client
    _service_client = create_client(url, key)
    return _service_client


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

async def verify_supabase_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a Supabase Auth JWT and return user info.

    Returns dict with user_id, email, etc. or None if invalid.
    """
    client = get_service_client()
    if not client:
        return None

    try:
        user_response = client.auth.get_user(token)
        if user_response and user_response.user:
            u = user_response.user
            return {
                "user_id": str(u.id),
                "email": u.email,
                "name": (u.user_metadata or {}).get("full_name", ""),
                "provider": "supabase",
            }
    except Exception as exc:
        logger.debug(f"Supabase token verification failed: {exc}")
    return None


# ---------------------------------------------------------------------------
# Memory operations (pgvector)
# ---------------------------------------------------------------------------

async def store_memory(
    *,
    user_id: str,
    personality_id: str,
    layer: str,
    category: str,
    content: str,
    ticker: Optional[str] = None,
    importance: float = 0.5,
    embedding: Optional[List[float]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    expires_at: Optional[str] = None,
) -> Optional[str]:
    """Insert a memory entry into pilot_memory with optional embedding."""
    client = get_service_client()
    if not client:
        return None

    data = {
        "user_id": user_id,
        "personality_id": personality_id,
        "layer": layer,
        "category": category,
        "content": content,
        "ticker": ticker,
        "importance": importance,
        "metadata": metadata or {},
        "expires_at": expires_at,
    }
    if embedding:
        data["embedding"] = embedding

    try:
        result = client.table("pilot_memory").insert(data).execute()
        if result.data:
            return result.data[0]["id"]
    except Exception as exc:
        logger.error(f"store_memory failed: {exc}")
    return None


async def retrieve_memory_semantic(
    *,
    user_id: str,
    personality_id: str,
    query_embedding: Optional[List[float]] = None,
    ticker: Optional[str] = None,
    categories: Optional[List[str]] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Retrieve memories using the pgvector-powered retrieve_memory() function."""
    client = get_service_client()
    if not client:
        return []

    try:
        result = client.rpc("retrieve_memory", {
            "p_user_id": user_id,
            "p_personality_id": personality_id,
            "p_query_embedding": query_embedding,
            "p_ticker": ticker,
            "p_categories": categories,
            "p_limit": limit,
        }).execute()
        return result.data or []
    except Exception as exc:
        logger.error(f"retrieve_memory_semantic failed: {exc}")
        return []


async def retrieve_memory_simple(
    *,
    user_id: str,
    personality_id: str,
    ticker: Optional[str] = None,
    categories: Optional[List[str]] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Fallback retrieval without embeddings — ordered by recency * importance."""
    client = get_service_client()
    if not client:
        return []

    try:
        query = (
            client.table("pilot_memory")
            .select("*")
            .eq("user_id", user_id)
            .eq("personality_id", personality_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if ticker:
            query = query.or_(f"ticker.eq.{ticker},ticker.is.null")
        if categories:
            query = query.in_("category", categories)

        result = query.execute()
        return result.data or []
    except Exception as exc:
        logger.error(f"retrieve_memory_simple failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Embedding generation (uses existing LLM infra)
# ---------------------------------------------------------------------------

async def generate_embedding(text: str) -> Optional[List[float]]:
    """Generate a 1536-dim embedding for memory content.

    Uses OpenAI-compatible API (OpenRouter or NVIDIA NIM).
    Falls back to None if unavailable — memory still works without embeddings.
    """
    import httpx

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY")
    if not api_key:
        return None

    base_url = os.getenv("NVIDIA_NIM_BASE_URL", "https://openrouter.ai/api/v1")

    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(
                f"{base_url}/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "text-embedding-3-small",
                    "input": text[:8000],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
    except Exception as exc:
        logger.debug(f"Embedding generation failed (non-critical): {exc}")
        return None


# ---------------------------------------------------------------------------
# Profile + Consent helpers
# ---------------------------------------------------------------------------

async def get_or_create_profile(user_id: str, email: str = "", name: str = "") -> Dict[str, Any]:
    """Ensure a profile exists for the user."""
    client = get_service_client()
    if not client:
        return {"user_id": user_id}

    try:
        result = client.table("profiles").select("*").eq("id", user_id).single().execute()
        if result.data:
            return result.data
    except Exception:
        pass

    try:
        data = {"id": user_id, "email": email, "display_name": name or email.split("@")[0]}
        result = client.table("profiles").upsert(data).execute()
        return result.data[0] if result.data else {"user_id": user_id}
    except Exception as exc:
        logger.error(f"get_or_create_profile failed: {exc}")
        return {"user_id": user_id}


async def get_user_alpaca_account_id(user_id: str) -> Optional[str]:
    """Get the stored alpaca_account_id for broker mode."""
    client = get_service_client()
    if not client:
        return None
    try:
        result = client.table("profiles").select("alpaca_account_id").eq("id", user_id).single().execute()
        return (result.data or {}).get("alpaca_account_id")
    except Exception:
        return None


async def set_user_alpaca_account_id(user_id: str, account_id: str) -> None:
    """Store the alpaca_account_id after broker sub-account creation."""
    client = get_service_client()
    if not client:
        return
    try:
        client.table("profiles").update({"alpaca_account_id": account_id}).eq("id", user_id).execute()
    except Exception as exc:
        logger.error(f"set_user_alpaca_account_id failed: {exc}")
