"""app/utils/ttl_cache.py — jednoduchy generický in-memory TTL cache.

Nahradza niekolko rucne pisanych "dict + fetched_at" vzorov v
app/services/market_data.py jednym opakovane pouzitelnym mechanizmom.
Nie je thread-safe v prisnom zmysle (viacero vlakien moze v ojedinelom
pripade obidve zapisat rovnaky kluc naraz), co je pre read-heavy cache
externych trhovych dat akceptovatelne riziko."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str, allow_stale: bool = False) -> Optional[Any]:
        """Vrati cachovanu hodnotu, ak este nevyprsala TTL. S allow_stale=True
        vrati aj expirovanu hodnotu (pouzitelne ako fallback pri sietovej chybe)."""
        entry = self._store.get(key)
        if entry is None:
            return None
        fetched_at, value = entry
        if allow_stale or (time.monotonic() - fetched_at) < self.ttl_seconds:
            return value
        return None

    def is_fresh(self, key: str) -> bool:
        return self.get(key) is not None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)

    def get_or_set(self, key: str, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value)
        return value
