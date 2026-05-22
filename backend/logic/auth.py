"""Session-based authentication and role-based authorization helpers.

Auth flow: the frontend obtains a Microsoft Entra access token (MSAL), posts it
to POST /api/auth/login, and receives an HttpOnly session cookie. All subsequent
API calls carry that cookie — the Entra token is never stored server-side.

The per-request g.current_user cache avoids extra DB round-trips when both a
decorator (@require_auth) and the view handler call get_current_user() in the
same request. The cache is invalidated automatically at request teardown because
Flask clears g between requests.
"""
import logging
import os
from functools import wraps
from typing import Any

from flask import g, jsonify, session


logger = logging.getLogger(__name__)


def get_current_user_id() -> int | None:
    """Return the authenticated user's integer id from the Flask session, or None."""
    user_id = session.get("user_id")
    return user_id if isinstance(user_id, int) and user_id > 0 else None


def _get_role(user: Any) -> str | None:
    """Extract the role string from a user dict or ORM object, or None if absent."""
    if isinstance(user, dict):
        role = user.get("role")
    else:
        role = getattr(user, "role", None)

    return role if isinstance(role, str) and role else None


def _is_blocked(user: Any) -> bool:
    if isinstance(user, dict):
        return user.get("blocked_at") is not None
    return getattr(user, "blocked_at", None) is not None


def get_current_user() -> Any | None:
    """Return the authenticated user record, cached per request in flask.g.

    Without the per-request cache, every decorator (`require_auth`,
    `require_roles`) and any handler that touches `get_current_user()` causes
    a fresh DB round-trip — multiple per request.
    """
    if "current_user" in g:
        return g.current_user

    user_id = get_current_user_id()
    if user_id is None:
        g.current_user = None
        return None

    from logic.database.init.init_db import db
    from logic.database.operations.sql_getters import retrieve_user_by_id

    user = retrieve_user_by_id(db.session, user_id)
    if user is None:
        session.clear()
        g.current_user = None
        return None
    if _is_blocked(user):
        session.clear()
        g.current_user = None
        return None

    role = _get_role(user)
    if role is not None:
        session["role"] = role

    g.current_user = user
    return user


def get_current_user_role() -> str | None:
    """Return the role string for the authenticated user, or None if not logged in."""
    user = get_current_user()
    if user is None:
        return None

    return _get_role(user)


def require_auth(view_func):
    """Decorator: return 401 if no valid session exists or the user was deactivated."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if get_current_user_id() is None:
            return jsonify({"error": "Authentication required"}), 401
        # Validate the user still exists and is active so blocked accounts cannot
        # ride a stale session through student-level endpoints.
        if get_current_user() is None:
            return jsonify({"error": "Authentication required"}), 401
        return view_func(*args, **kwargs)

    return wrapped


def require_roles(*allowed_roles: str):
    """Decorator factory: allow only users whose role is in ``allowed_roles``.

    Returns 401 when no session exists, 403 when the session user's role is
    not in the allowed set. When ``ADMIN_DEBUG_ALL=true`` all role checks are
    bypassed (local dev only — blocked at startup in non-local envs).

    Args:
        *allowed_roles: Role strings that may access the decorated view.
    """
    allowed_role_set = set(allowed_roles)

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if os.environ.get("ADMIN_DEBUG_ALL", "").lower() == "true":
                return view_func(*args, **kwargs)

            if get_current_user_id() is None:
                return jsonify({"error": "Authentication required"}), 401

            role = get_current_user_role()
            if role is None:
                return jsonify({"error": "Authentication required"}), 401

            if role not in allowed_role_set:
                return jsonify({"error": "Insufficient role"}), 403

            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def require_admin(view_func):
    """Decorator: allow Admin and SuperAdmin roles; shorthand for ``require_roles``."""
    from logic.database.init.class_db import USER_ROLE_ADMIN, USER_ROLE_SUPER_ADMIN

    return require_roles(USER_ROLE_ADMIN, USER_ROLE_SUPER_ADMIN)(view_func)


def invalidate_sessions_for_user(user_id: int) -> int:
    """Drop all Redis-backed Flask sessions belonging to ``user_id``.

    Account deactivation happens out-of-band: a logged-in user might have an
    active session on another worker that survives the local block until
    its TTL expires. Scanning Redis for sessions that reference this user
    and deleting them forces immediate logout everywhere.

    Returns the number of session keys removed. Best-effort — a missing or
    misconfigured Redis just logs and returns 0.
    """
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return 0

    try:
        import pickle

        import redis as redis_lib

        client = redis_lib.from_url(redis_url)
        prefix = "session:"
        deleted = 0
        for key in client.scan_iter(match=f"{prefix}*"):
            try:
                raw = client.get(key)
                if raw is None:
                    continue
                data = pickle.loads(raw)
            except Exception:  # noqa: BLE001 — corrupt or foreign keys are skipped
                continue
            if not isinstance(data, dict):
                continue
            if data.get("user_id") == user_id:
                client.delete(key)
                deleted += 1
        return deleted
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to invalidate Redis sessions for user_id=%s", user_id
        )
        return 0
