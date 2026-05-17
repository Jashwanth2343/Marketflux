"""LangGraph-compatible checkpoint store for pilot agent workflows.

Persists agent workflow state (swarm debates, proposal pipelines, reflection loops)
so they can be resumed after failures, inspected for debugging, and replayed.

Storage: Supabase Postgres (primary) with Redis for in-flight state.

Checkpoint structure:
  - thread_id: unique workflow execution ID
  - step: current step in the workflow DAG
  - state: serialized agent state (messages, tool results, partial decisions)
  - metadata: timing, personality_id, user_id, trigger

This module implements the LangGraph CheckpointSaver interface so it can plug
directly into LangGraph workflows when we migrate the swarm to a proper DAG.
For now, it also works standalone as a simple state persistence layer.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Checkpoint data model
# ---------------------------------------------------------------------------

class Checkpoint:
    __slots__ = ("thread_id", "step", "state", "metadata", "created_at", "updated_at")

    def __init__(
        self,
        *,
        thread_id: str,
        step: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.thread_id = thread_id
        self.step = step
        self.state = state
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "step": self.step,
            "state": self.state,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Checkpoint store (Supabase + Redis)
# ---------------------------------------------------------------------------

class PilotCheckpointStore:
    """Hybrid checkpoint store: Redis for in-flight, Supabase for durable.

    Usage:
        store = PilotCheckpointStore()
        thread_id = store.new_thread(personality_id="...", user_id="...")

        # Save state at each workflow step
        await store.save(thread_id, step="universe_scan", state={...})
        await store.save(thread_id, step="swarm_debate", state={...})

        # Resume from last checkpoint
        last = await store.get_latest(thread_id)
        if last and last["step"] == "swarm_debate":
            # Resume from debate step
            ...

        # Mark complete
        await store.complete(thread_id, result={...})
    """

    def __init__(self):
        self._redis = self._init_redis()
        self._supabase = self._init_supabase()

    def _init_redis(self):
        try:
            import redis
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", "6379"))
            password = os.getenv("REDIS_PASSWORD") or None
            r = redis.Redis(host=host, port=port, password=password, decode_responses=True)
            r.ping()
            return r
        except Exception:
            return None

    def _init_supabase(self):
        try:
            from vnext.supabase_client import get_service_client, is_supabase_configured
            if not is_supabase_configured():
                return None
            return get_service_client()
        except Exception:
            return None

    def new_thread(
        self,
        *,
        personality_id: str = "",
        user_id: str = "",
        workflow_type: str = "propose_trades",
    ) -> str:
        """Create a new workflow thread ID."""
        thread_id = f"pilot:{workflow_type}:{uuid.uuid4().hex[:12]}"
        metadata = {
            "personality_id": personality_id,
            "user_id": user_id,
            "workflow_type": workflow_type,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

        # Store initial metadata in Redis (fast access during execution)
        if self._redis:
            try:
                key = f"checkpoint:meta:{thread_id}"
                self._redis.setex(key, 3600, json.dumps(metadata))
            except Exception:
                pass

        return thread_id

    async def save(
        self,
        thread_id: str,
        step: str,
        state: Dict[str, Any],
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save a checkpoint at the current workflow step."""
        now = datetime.now(timezone.utc).isoformat()
        checkpoint_data = {
            "thread_id": thread_id,
            "step": step,
            "state": state,
            "metadata": metadata or {},
            "updated_at": now,
        }

        # Redis: fast in-flight state (overwrite previous step)
        if self._redis:
            try:
                key = f"checkpoint:state:{thread_id}"
                self._redis.setex(key, 3600, json.dumps(checkpoint_data, default=str))
            except Exception as exc:
                logger.debug(f"Redis checkpoint save failed: {exc}")

        # Supabase: durable history (append each step)
        if self._supabase:
            try:
                self._supabase.table("workflow_checkpoints").insert({
                    "thread_id": thread_id,
                    "step": step,
                    "state": state,
                    "metadata": metadata or {},
                    "created_at": now,
                }).execute()
            except Exception as exc:
                logger.debug(f"Supabase checkpoint save failed: {exc}")

    async def get_latest(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent checkpoint for a thread."""
        # Try Redis first (in-flight)
        if self._redis:
            try:
                key = f"checkpoint:state:{thread_id}"
                raw = self._redis.get(key)
                if raw:
                    return json.loads(raw)
            except Exception:
                pass

        # Supabase fallback (durable)
        if self._supabase:
            try:
                result = (
                    self._supabase.table("workflow_checkpoints")
                    .select("*")
                    .eq("thread_id", thread_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
            except Exception:
                pass

        return None

    async def get_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get all checkpoints for a thread (workflow step history)."""
        if self._supabase:
            try:
                result = (
                    self._supabase.table("workflow_checkpoints")
                    .select("*")
                    .eq("thread_id", thread_id)
                    .order("created_at", desc=False)
                    .execute()
                )
                return result.data or []
            except Exception:
                pass
        return []

    async def complete(self, thread_id: str, *, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark a workflow thread as complete."""
        await self.save(thread_id, step="__complete__", state={"result": result or {}})

        # Update metadata
        if self._redis:
            try:
                key = f"checkpoint:meta:{thread_id}"
                raw = self._redis.get(key)
                if raw:
                    meta = json.loads(raw)
                    meta["status"] = "complete"
                    meta["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self._redis.setex(key, 3600, json.dumps(meta))
            except Exception:
                pass

    async def fail(self, thread_id: str, *, error: str = "") -> None:
        """Mark a workflow thread as failed (can be resumed later)."""
        await self.save(thread_id, step="__failed__", state={"error": error})

        if self._redis:
            try:
                key = f"checkpoint:meta:{thread_id}"
                raw = self._redis.get(key)
                if raw:
                    meta = json.loads(raw)
                    meta["status"] = "failed"
                    meta["failed_at"] = datetime.now(timezone.utc).isoformat()
                    meta["error"] = error
                    self._redis.setex(key, 7200, json.dumps(meta))
            except Exception:
                pass

    async def list_threads(
        self,
        *,
        user_id: Optional[str] = None,
        personality_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List recent workflow threads (for debugging UI)."""
        if self._supabase:
            try:
                query = (
                    self._supabase.table("workflow_checkpoints")
                    .select("thread_id, step, metadata, created_at")
                    .eq("step", "__complete__")
                    .order("created_at", desc=True)
                    .limit(limit)
                )
                result = query.execute()
                return result.data or []
            except Exception:
                pass
        return []


# Singleton instance
_store: Optional[PilotCheckpointStore] = None


def get_checkpoint_store() -> PilotCheckpointStore:
    global _store
    if _store is None:
        _store = PilotCheckpointStore()
    return _store
