"""Process-shared cache facade backed by Redis.

The backend runs under multi-worker Gunicorn. Module-level dicts in any one
worker are invisible to the other workers, so admin mutations that
``invalidate_*`` an in-process cache only reach the worker that handled the
request — every other worker keeps serving stale data until its TTL fires.

This helper centralises the Redis access pattern for caches and exposes a
``_NullCache`` fallback for environments without Redis (unit tests, fully
local dev). Always go through ``get_cache()``; never reach for a module
global.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class _NullCache:
    """Process-local TTL cache used when Redis is unavailable.

    Single-worker only — explicitly does not propagate across processes.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[float | None, str]] = {}
        self._lock = threading.Lock()

    def _expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and time.monotonic() > expires_at

    def get_json(self, key: str) -> Any:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, raw = entry
            if self._expired(expires_at):
                self._store.pop(key, None)
                return None
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                return None

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        with self._lock:
            payload = json.dumps(value, default=str)
            expires_at = time.monotonic() + ttl_seconds if ttl_seconds else None
            self._store[key] = (expires_at, payload)

    def delete(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._store.pop(k, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for k in [k for k in self._store if k.startswith(prefix)]:
                self._store.pop(k, None)

    def ping(self) -> bool:
        return True


class _RedisCache:
    """Redis-backed cache implementation.

    All operations degrade gracefully on transient Redis errors — a failed
    GET returns None (cache miss) and a failed SET is silently skipped rather
    than raising, so application code never crashes due to cache unavailability.
    """

    def __init__(self, client) -> None:
        self._client = client

    def get_json(self, key: str) -> Any:
        try:
            raw = self._client.get(key)
        except Exception:  # noqa: BLE001 — degrade gracefully on transient Redis errors
            logger.exception("Redis GET failed for key=%s", key)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Failed to deserialise cached value at key=%s", key)
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        try:
            payload = json.dumps(value, default=str)
        except (TypeError, ValueError):
            logger.exception("Failed to serialise value for key=%s", key)
            return
        try:
            if ttl_seconds:
                self._client.set(key, payload, ex=int(ttl_seconds))
            else:
                self._client.set(key, payload)
        except Exception:  # noqa: BLE001
            logger.exception("Redis SET failed for key=%s", key)

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            self._client.delete(*keys)
        except Exception:  # noqa: BLE001
            logger.exception("Redis DEL failed for keys=%s", keys)

    def delete_prefix(self, prefix: str) -> None:
        try:
            for key in self._client.scan_iter(match=f"{prefix}*"):
                self._client.delete(key)
        except Exception:  # noqa: BLE001
            logger.exception("Redis prefix delete failed for prefix=%s", prefix)

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:  # noqa: BLE001
            return False


_cache_instance = None
_cache_lock = threading.Lock()


def get_cache():
    """Return the process-shared cache. Idempotent and lazily-initialised."""
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    with _cache_lock:
        if _cache_instance is not None:
            return _cache_instance

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            _cache_instance = _NullCache()
            return _cache_instance

        try:
            import redis as redis_lib

            client = redis_lib.from_url(redis_url, decode_responses=True)
            client.ping()
            _cache_instance = _RedisCache(client)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Redis cache init failed (REDIS_URL=%s); falling back to in-process cache",
                redis_url,
            )
            _cache_instance = _NullCache()

    return _cache_instance


def reset_cache_for_tests() -> None:
    """Drop the singleton so tests can rebind the cache implementation."""
    global _cache_instance
    with _cache_lock:
        _cache_instance = None
