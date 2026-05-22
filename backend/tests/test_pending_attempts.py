import time

from logic.pending_attempts import PendingAttemptsManager


def test_pending_attempts_store_and_pop_roundtrip():
    manager = PendingAttemptsManager()
    attempt_id = manager.store(
        user_id=1,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={"q1": {"id": "q1"}},
    )

    assert isinstance(attempt_id, str)

    attempt = manager.pop(attempt_id)
    assert attempt["user_id"] == 1
    assert attempt["category_ids"] == [42]
    assert manager.pop(attempt_id) is None


def test_pending_attempts_get_returns_none_for_unknown():
    manager = PendingAttemptsManager()
    assert manager.get("nonexistent-id") is None


def test_pending_attempts_get_returns_none_for_expired():
    manager = PendingAttemptsManager()
    attempt_id = manager.store(
        user_id=1,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={},
    )
    manager._mem[attempt_id]["created_at"] = time.time() - 7200

    assert manager.get(attempt_id) is None


def test_pending_attempts_pop_returns_none_for_expired():
    manager = PendingAttemptsManager()
    attempt_id = manager.store(
        user_id=1,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={},
    )
    manager._mem[attempt_id]["created_at"] = time.time() - 7200

    assert manager.pop(attempt_id) is None


def test_pending_attempts_caps_max_entries():
    manager = PendingAttemptsManager()
    for index in range(12):
        manager.store(
            user_id=1,
            course_id=7,
            category_id=42,
            category_ids=[42],
            question_snapshots={"q": {"id": f"q-{index}"}},
        )

    assert len(manager._mem) == 10
