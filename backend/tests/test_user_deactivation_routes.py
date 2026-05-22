from datetime import datetime, timezone
import sys


def _set_session(client, user_id: int, role: str = "Student") -> None:
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = role


def test_deactivate_current_account_deactivates_local_user(client, monkeypatch):
    getters = sys.modules["logic.database.operations.sql_getters"]
    setters = sys.modules["logic.database.operations.sql_setters"]

    def fake_retrieve_user_by_id(_session, user_id):
        return {
            "id": user_id,
            "email": "student@example.com",
            "role": "Student",
            "blocked_at": None,
        }

    blocked_user_ids = []
    monkeypatch.setattr(getters, "retrieve_user_by_id", fake_retrieve_user_by_id)
    monkeypatch.setattr(
        setters,
        "block_user_by_id",
        lambda _session, user_id: blocked_user_ids.append(user_id) or True,
    )
    _set_session(client, 7)

    response = client.delete("/api/auth/me")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "status": "deactivated"}
    assert blocked_user_ids == [7]
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_admin_deactivate_user_deactivates_and_invalidates_sessions(client, monkeypatch):
    import logic.auth as auth_helpers

    getters = sys.modules["logic.database.operations.sql_getters"]
    setters = sys.modules["logic.database.operations.sql_setters"]

    def fake_retrieve_user_by_id(_session, user_id):
        if user_id == 1:
            return {
                "id": 1,
                "email": "root@example.com",
                "role": "SuperAdmin",
                "blocked_at": None,
            }
        return {
            "id": user_id,
            "email": "student@example.com",
            "role": "Student",
            "blocked_at": None,
        }

    blocked_user_ids = []
    invalidated_user_ids = []
    monkeypatch.setattr(getters, "retrieve_user_by_id", fake_retrieve_user_by_id)
    monkeypatch.setattr(
        setters,
        "block_user_by_id",
        lambda _session, user_id: blocked_user_ids.append(user_id) or True,
    )
    monkeypatch.setattr(
        auth_helpers,
        "invalidate_sessions_for_user",
        lambda user_id: invalidated_user_ids.append(user_id) or 1,
    )
    _set_session(client, 1, "SuperAdmin")

    response = client.delete("/api/admin/users/9")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "status": "deactivated"}
    assert blocked_user_ids == [9]
    assert invalidated_user_ids == [9]


def test_admin_can_reactivate_deactivated_user(client, monkeypatch):
    getters = sys.modules["logic.database.operations.sql_getters"]
    setters = sys.modules["logic.database.operations.sql_setters"]

    def fake_retrieve_user_by_id(_session, user_id):
        if user_id == 1:
            return {
                "id": 1,
                "email": "root@example.com",
                "role": "SuperAdmin",
                "blocked_at": None,
            }
        return {
            "id": user_id,
            "email": "student@example.com",
            "role": "Student",
            "blocked_at": datetime.now(timezone.utc),
        }

    activated_user_ids = []
    monkeypatch.setattr(getters, "retrieve_user_by_id", fake_retrieve_user_by_id)
    monkeypatch.setattr(
        setters,
        "activate_user_by_id",
        lambda _session, user_id: activated_user_ids.append(user_id) or True,
    )
    _set_session(client, 1, "SuperAdmin")

    response = client.patch("/api/admin/users/9/activate")

    assert response.status_code == 200
    assert response.get_json()["status"] == "activated"
    assert response.get_json()["user"]["is_deactivated"] is False
    assert activated_user_ids == [9]
