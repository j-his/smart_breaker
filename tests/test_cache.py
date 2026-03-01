"""Tests for the TTL cache."""
import time
import pytest
from unittest.mock import patch

from backend.cache import TTLCache


class TestTTLCache:
    """TTLCache unit tests."""

    def test_ttl_cache_set_get(self):
        """Store and retrieve a value within TTL."""
        cache = TTLCache(default_ttl_s=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_ttl_cache_expired(self):
        """Value should be None after TTL expires."""
        cache = TTLCache(default_ttl_s=60)
        cache.set("key1", "value1", ttl_s=0.01)
        time.sleep(0.02)
        assert cache.get("key1") is None

    def test_ttl_cache_invalidate(self):
        """Explicit invalidation removes the key."""
        cache = TTLCache(default_ttl_s=60)
        cache.set("key1", "value1")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_ttl_cache_clear(self):
        """Clear removes all entries."""
        cache = TTLCache(default_ttl_s=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
