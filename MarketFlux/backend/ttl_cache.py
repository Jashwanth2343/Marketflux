"""In-process TTL cache.

Replaces diskcache. DiskCache pickles values onto the local disk, and every
published release through 5.6.3 is flagged for unsafe pickle deserialization
(GHSA-w8v5-vhqr-4h9v). Render's filesystem is ephemeral, so a process-local
cache is the same practical lifetime without writing pickles.
"""
from __future__ import annotations

import time
import threading
from typing import Any, Optional


class TTLCache:
    def __init__(self, directory: Optional[str] = None):
        del directory
        self._items: dict[str, tuple[Optional[float], Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, default: Any = None) -> Any:
        now = time.time()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return default
            expires, value = item
            if expires is not None and expires <= now:
                self._items.pop(key, None)
                return default
            return value

    def set(self, key: str, value: Any, expire: Optional[int] = None) -> None:
        expires = time.time() + expire if expire else None
        with self._lock:
            self._items[key] = (expires, value)
