"""General-purpose TTL cache for backend data."""
import time


class TTLCache:
    """Dict-based cache with per-key time-to-live expiry."""

    def __init__(self, default_ttl_s: float = 60):
        self._default_ttl = default_ttl_s
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        """Return cached value if not expired, else None."""
        if key not in self._store:
            return None
        expiry, value = self._store[key]
        if time.monotonic() > expiry:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: object, ttl_s: float | None = None) -> None:
        """Store a value with optional custom TTL."""
        ttl = ttl_s if ttl_s is not None else self._default_ttl
        self._store[key] = (time.monotonic() + ttl, value)

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()
