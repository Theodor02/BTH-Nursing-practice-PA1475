"""Distributed TTL cache for the category-request payload.

Backed by the shared Redis-or-NullCache helper so an admin mutation that calls
``invalidate()`` clears the entry for every worker, not just the one that
handled the request.
"""
from config import _CAT_REQUEST_TTL
from logic.cache import get_cache
from logic.database.operations.sql_getters import (
    retrieve_cat_request_payload,
)

_CAT_REQUEST_CACHE_KEY = "cat_request_payload"


class CatRequestCache:
    """Wrapper kept for the existing module-level ``_cache`` singleton call sites."""

    def __init__(self, ttl: int = _CAT_REQUEST_TTL):
        """Args:
            ttl: Cache lifetime in seconds (default from ``_CAT_REQUEST_TTL``).
        """
        self._ttl = ttl

    def get(self, db_session):
        """Return (payload_courses, payload_max_questions), reading from cache or DB.

        On a cache miss the payload is rebuilt from the database and stored in
        Redis so subsequent requests from any worker hit the cache.

        Args:
            db_session: Active SQLAlchemy session used on a cache miss.

        Returns:
            Tuple of (courses dict, max_questions dict) as produced by
            ``retrieve_cat_request_payload``.
        """
        cache = get_cache()
        cached = cache.get_json(_CAT_REQUEST_CACHE_KEY)
        if isinstance(cached, list) and len(cached) == 2:
            payload_courses, payload_max_questions = cached
            return payload_courses, payload_max_questions

        payload_courses, payload_max_questions = retrieve_cat_request_payload(
            db_session
        )
        cache.set_json(
            _CAT_REQUEST_CACHE_KEY,
            [payload_courses, payload_max_questions],
            ttl_seconds=self._ttl,
        )
        return payload_courses, payload_max_questions

    def invalidate(self):
        """Drop the cached payload so all workers fetch fresh data on the next request."""
        get_cache().delete(_CAT_REQUEST_CACHE_KEY)
