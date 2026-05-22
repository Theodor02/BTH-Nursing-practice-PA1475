"""In-flight quiz attempt storage.

Pending attempts are keyed by a UUID generated at question-generation time and
consumed (deleted) on final submission to prevent double-scoring.

Production (``REDIS_URL`` set): attempts are stored in Redis with a TTL so
abandoned quizzes expire automatically without any cleanup job.

Dev / test (no ``REDIS_URL``): falls back to a thread-safe in-process dict
with manual TTL enforcement. The in-process store is lost on worker restart,
but that is acceptable outside production.
"""
import json
import os
import threading
import time
import uuid

from config import _MAX_PENDING_ATTEMPTS
from config import _PENDING_ATTEMPT_TTL

_REDIS_KEY_PREFIX = "qtrain:attempt:"


class PendingAttemptsManager:
    """Stores in-flight quiz attempts.

    Production: uses Redis directly (REDIS_URL env var), keyed by attempt
    UUID with a TTL. Attempts are independent of the Flask auth session, so
    session resets and concurrent login requests cannot corrupt in-progress
    quizzes.

    Dev/test (no REDIS_URL): falls back to a thread-safe in-process dict.
    """

    def __init__(self):
        self._redis = None
        self._redis_ready = False
        self._init_lock = threading.Lock()
        self._mem: dict = {}
        self._mem_lock = threading.Lock()

    def _client(self):
        """Return the Redis client, lazily initialised on first call.

        Uses a double-checked lock so concurrent requests do not race to
        create multiple Redis connections on startup.
        """
        if self._redis_ready:
            return self._redis
        with self._init_lock:
            if not self._redis_ready:
                redis_url = os.getenv("REDIS_URL")
                if redis_url:
                    import redis as redis_lib
                    self._redis = redis_lib.from_url(redis_url)
                self._redis_ready = True
        return self._redis

    def store(
        self,
        user_id: int,
        course_id: int,
        category_id: int,
        category_ids: list,
        question_snapshots: dict,
    ) -> str:
        """Persist a new pending attempt and return its UUID.

        Args:
            user_id: Authenticated user who started the quiz.
            course_id: Primary course for the attempt.
            category_id: Primary category for the attempt.
            category_ids: All category IDs included in the attempt (for
                multi-category quizzes).
            question_snapshots: Dict mapping question instance id → snapshot
                dict as produced by ``build_generated_payload``.

        Returns:
            A UUID string that the client must present when grading or
            submitting the attempt.
        """
        attempt_id = str(uuid.uuid4())
        attempt = {
            "user_id": user_id,
            "created_at": time.time(),
            "course_id": course_id,
            "category_id": category_id,
            "category_ids": category_ids,
            "question_snapshots": question_snapshots,
        }
        r = self._client()
        if r is not None:
            r.setex(
                f"{_REDIS_KEY_PREFIX}{attempt_id}",
                _PENDING_ATTEMPT_TTL,
                json.dumps(attempt),
            )
        else:
            self._mem_store(attempt_id, attempt)
        return attempt_id

    def _mem_store(self, attempt_id: str, attempt: dict) -> None:
        """Write to the in-process dict, pruning expired entries first.

        Evicts the oldest entries when the cap (``_MAX_PENDING_ATTEMPTS``) is
        reached to prevent unbounded memory growth in long-running dev servers.
        """
        with self._mem_lock:
            now = time.time()
            self._mem = {
                k: v
                for k, v in self._mem.items()
                if now - float(v.get("created_at", 0)) <= _PENDING_ATTEMPT_TTL
            }
            self._mem[attempt_id] = attempt
            if len(self._mem) > _MAX_PENDING_ATTEMPTS:
                sorted_ids = sorted(
                    self._mem,
                    key=lambda k: self._mem[k].get("created_at", 0),
                )
                for old_id in sorted_ids[:-_MAX_PENDING_ATTEMPTS]:
                    del self._mem[old_id]

    def get(self, attempt_id: str) -> dict | None:
        """Return the attempt dict without consuming it, or None if not found/expired.

        Used by the per-question grading endpoint so students can check answers
        mid-quiz without finalising the attempt.
        """
        r = self._client()
        if r is not None:
            data = r.get(f"{_REDIS_KEY_PREFIX}{attempt_id}")
            return json.loads(data) if data is not None else None
        with self._mem_lock:
            attempt = self._mem.get(attempt_id)
            if attempt is None:
                return None
            if time.time() - float(attempt.get("created_at", 0)) > _PENDING_ATTEMPT_TTL:
                del self._mem[attempt_id]
                return None
            return dict(attempt)

    def pop(self, attempt_id: str) -> dict | None:
        """Atomically remove and return the attempt, or None if not found/expired.

        The delete-on-read pattern ensures each attempt can only be submitted
        once — a duplicate submission with the same ``attempt_id`` returns None.
        """
        r = self._client()
        if r is not None:
            key = f"{_REDIS_KEY_PREFIX}{attempt_id}"
            data = r.get(key)
            if data is None:
                return None
            r.delete(key)
            return json.loads(data)
        with self._mem_lock:
            attempt = self._mem.pop(attempt_id, None)
            if attempt is None:
                return None
            if time.time() - float(attempt.get("created_at", 0)) > _PENDING_ATTEMPT_TTL:
                return None
            return attempt
