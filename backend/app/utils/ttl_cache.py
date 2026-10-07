"""TTL cache."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    def __init__(self, ttl_seconds: float, max_entries: int = 512):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, allow_stale: bool = False) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
        if entry is None:
            return None
        fetched_at, value = entry
        if allow_stale or (time.monotonic() - fetched_at) < self.ttl_seconds:
            return value
        return None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def is_fresh(self, key: str) -> bool:
        return self.get(key) is not None

    def set(self, key: str, value: Any) -> None:
        now = time.monotonic()
        with self._lock:
            self._store[key] = (now, value)
            if len(self._store) > self.max_entries:
                self._evict(now)

    def _evict(self, now: float) -> None:
        for key in [k for k, (ts, _v) in self._store.items() if now - ts >= self.ttl_seconds]:
            del self._store[key]
        overflow = len(self._store) - self.max_entries
        if overflow > 0:
            for key, _ in sorted(self._store.items(), key=lambda kv: kv[1][0])[:overflow]:
                del self._store[key]

    def get_or_set(self, key: str, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value)
        return value
