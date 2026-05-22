"""Microsoft Entra (Azure AD) SSO authentication and user management.

Login flow:
  1. Frontend acquires an Entra access token via MSAL (client-side).
  2. Frontend posts the raw Bearer token to POST /api/auth/login.
  3. Backend verifies signature (JWKS), audience, issuer, tenant, scope,
     and the authorized-party (azp) claim against the configured frontend
     client IDs.
  4. On success, the backend upserts a local User row and issues an HttpOnly
     Flask session cookie. The Entra token is not stored.

Account deactivation is local-only: completed sessions are deleted and the
local user row is marked with users.blocked_at. Microsoft Entra is left
unchanged so the user can reactivate the local account by logging in.

Required env vars: AZURE_TENANT_ID, AZURE_API_CLIENT_ID, AZURE_FRONTEND_CLIENT_ID
(or AZURE_FRONTEND_CLIENT_IDS for multiple), ALLOWED_EMAIL_DOMAINS.
Optional: SUPER_ADMIN_EMAILS (comma-separated) bootstraps SuperAdmin accounts on
first login without needing a DB migration.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from flask import Blueprint, jsonify, request, session

from extensions import limiter
from logic.auth import get_current_user, require_auth, require_roles
from logic.database.init.init_db import db

logger = logging.getLogger(__name__)

DEFAULT_REQUIRED_SCOPE = "access_as_user"

auth_bp = Blueprint("auth", __name__)


class AuthenticationError(Exception):
    """Raised when the incoming Entra bearer token cannot be trusted."""


@dataclass(frozen=True)
class VerifiedRequestContext:
    sso_id: str
    email: str
    tenant_id: str
    claims: dict[str, Any]


def _split_env_list(raw_value: str | None) -> list[str]:
    """Parse comma-separated env settings into a clean list of values."""
    if not raw_value:
        return []

    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _normalize_string(value: Any) -> str | None:
    """Return a trimmed string or None so claim/env handling stays consistent."""
    if not isinstance(value, str):
        return None

    normalized = value.strip()
    return normalized or None


def _get_required_env(name: str) -> str:
    value = _normalize_string(os.getenv(name))
    if value is None:
        raise RuntimeError(f"{name} environment variable must be set.")
    return value


def _get_tenant_id() -> str:
    """Return the Entra tenant that this backend is willing to trust."""
    return _get_required_env("AZURE_TENANT_ID")


def _get_frontend_client_ids() -> set[str]:
    """Return the approved frontend app ids that may request tokens for this API."""
    configured_ids = _split_env_list(os.getenv("AZURE_FRONTEND_CLIENT_IDS"))
    if not configured_ids:
        configured_ids = [_get_required_env("AZURE_FRONTEND_CLIENT_ID")]
    return {client_id for client_id in configured_ids if client_id}


def _get_expected_audiences() -> set[str]:
    """Return the accepted audience values for access tokens targeting this backend API."""
    configured_audiences = _split_env_list(os.getenv("AZURE_API_AUDIENCES"))
    if configured_audiences:
        return set(configured_audiences)

    backend_client_id = _get_required_env("AZURE_API_CLIENT_ID")
    return {
        backend_client_id,
        f"api://{backend_client_id}",
    }


def _get_allowed_domains() -> set[str]:
    """Return the email domains that are allowed to use the application."""
    configured_domains = _split_env_list(_get_required_env("ALLOWED_EMAIL_DOMAINS"))
    return {domain.lower() for domain in configured_domains}


def _get_super_admin_emails() -> set[str]:
    """Return email addresses that should be bootstrapped as SuperAdmin."""
    return {
        email.lower()
        for email in _split_env_list(os.getenv("SUPER_ADMIN_EMAILS"))
    }


def _is_super_admin_email(email: str) -> bool:
    return email.strip().lower() in _get_super_admin_emails()


def _get_required_scope() -> str:
    """Return the API scope that must be present on the incoming access token."""
    return os.getenv("AZURE_API_REQUIRED_SCOPE", DEFAULT_REQUIRED_SCOPE)


def _extract_bearer_token(authorization_header: str | None) -> str:
    """Read the raw bearer token from the Authorization header."""
    if not authorization_header:
        raise AuthenticationError("Missing Authorization header.")

    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError("Authorization header must use Bearer token auth.")

    return token.strip()


_JWK_CLIENT_CACHE: dict[str, Any] = {}


def _get_jwk_client() -> Any:
    """Return a PyJWKClient with built-in TTL so Microsoft key rotation is honoured.

    A long-lived `lru_cache` would freeze the JWKS in memory until the worker
    restarts; instead, we keep one PyJWKClient per tenant and let it refresh
    its key set every hour.
    """
    from jwt import PyJWKClient

    tenant_id = _get_tenant_id()
    cached = _JWK_CLIENT_CACHE.get(tenant_id)
    if cached is not None:
        return cached

    jwks_uri = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    try:
        client = PyJWKClient(jwks_uri, lifespan=3600)
    except TypeError:
        client = PyJWKClient(jwks_uri)
    _JWK_CLIENT_CACHE[tenant_id] = client
    return client


def _decode_and_validate_claims(access_token: str) -> dict[str, Any]:
    """Verify the token signature and security-critical Entra claims."""
    from jwt import InvalidTokenError, decode

    tenant_id = _get_tenant_id()
    allowed_issuers = {
        f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        f"https://sts.windows.net/{tenant_id}/",
    }

    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(access_token)
        claims = decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=list(_get_expected_audiences()),
            options={
                "require": ["aud", "exp", "iss", "oid", "tid"],
            },
        )
    except InvalidTokenError as exc:
        raise AuthenticationError("Microsoft access token verification failed.") from exc

    issuer = _normalize_string(claims.get("iss"))
    if issuer not in allowed_issuers:
        raise AuthenticationError("Microsoft access token issuer is not allowed.")

    token_tenant_id = _normalize_string(claims.get("tid"))
    if token_tenant_id != tenant_id:
        raise AuthenticationError("Microsoft access token tenant does not match this app.")

    required_scope = _get_required_scope()
    token_scopes = set((_normalize_string(claims.get("scp")) or "").split())
    if required_scope and required_scope not in token_scopes:
        raise AuthenticationError("Microsoft access token is missing the required API scope.")

    frontend_client_ids = _get_frontend_client_ids()
    authorized_party = _normalize_string(claims.get("azp")) or _normalize_string(claims.get("appid"))
    if frontend_client_ids and authorized_party not in frontend_client_ids:
        raise AuthenticationError("Microsoft access token was not issued to an approved frontend client.")

    return claims


def _extract_email(claims: dict[str, Any]) -> str:
    """Pick the best available email-like claim from a verified token."""
    email = (
        _normalize_string(claims.get("email"))
        or _normalize_string(claims.get("preferred_username"))
        or _normalize_string(claims.get("upn"))
        or _normalize_string(claims.get("unique_name"))
    )
    if not email:
        raise AuthenticationError("Microsoft access token is missing a usable email claim.")

    return email


def _validate_email_domain(email: str) -> None:
    """Reject verified users whose email domain is outside the allowed list."""
    _, _, domain = email.rpartition("@")
    if not domain:
        raise AuthenticationError("Microsoft access token email claim is invalid.")

    if _is_super_admin_email(email):
        return

    if domain.lower() not in _get_allowed_domains():
        raise AuthenticationError("This account is not allowed to use the application.")


def resolve_verified_request_context(authorization_header: str | None) -> VerifiedRequestContext:
    """Turn an Authorization header into the verified user identity the backend may trust."""
    access_token = _extract_bearer_token(authorization_header)
    claims = _decode_and_validate_claims(access_token)

    sso_id = _normalize_string(claims.get("oid"))
    if not sso_id:
        raise AuthenticationError("Microsoft access token is missing the oid claim.")

    email = _extract_email(claims)
    _validate_email_domain(email)

    return VerifiedRequestContext(
        sso_id=sso_id,
        email=email,
        tenant_id=_get_tenant_id(),
        claims=claims,
    )


def get_verified_request_context() -> VerifiedRequestContext:
    """Resolve the authenticated Entra user for the current Flask request."""
    return resolve_verified_request_context(request.headers.get("Authorization"))



@auth_bp.get("/login")
def login_info():
    return jsonify({"message": "Login endpoint"})


@auth_bp.post("/api/auth/login")
@limiter.limit("20 per minute")
def login():
    """Verify the Entra token, then translate the verified identity into a local Flask session."""
    try:
        verified_user = get_verified_request_context()
    except AuthenticationError as exc:
        return jsonify({"error": str(exc)}), 401

    from logic.database.init.class_db import USER_ROLE_SUPER_ADMIN
    from logic.database.operations.sql_setters import (
        activate_user_by_id,
        create_or_get_user_by_sso,
    )

    user, created = create_or_get_user_by_sso(
        db.session,
        sso_id=verified_user.sso_id,
        email=verified_user.email,
    )
    if getattr(user, "blocked_at", None) is not None:
        activated = activate_user_by_id(db.session, user.id)
        if not activated:
            db.session.rollback()
            return jsonify({"error": "User not found."}), 404
        user.blocked_at = None

    if (
        _is_super_admin_email(verified_user.email)
        and user.role != USER_ROLE_SUPER_ADMIN
    ):
        user.role = USER_ROLE_SUPER_ADMIN

    db.session.commit()

    existing_user_id = session.get("user_id")
    if existing_user_id != user.id:
        session.clear()

    session["user_id"] = user.id
    session["role"] = user.role
    session.permanent = True

    return jsonify(
        {
            "user_id": user.id,
            "created": created,
            "sso_id": verified_user.sso_id,
            "email": verified_user.email,
            "role": user.role,
        }
    )


@auth_bp.get("/api/auth/me")
@require_auth
def current_user():
    """Return the authenticated user's current database role."""
    from logic.database.init.class_db import USER_ROLE_ADMIN, USER_ROLE_SUPER_ADMIN

    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required"}), 401

    role = user.get("role")
    return jsonify(
        {
            "user_id": user.get("id"),
            "email": user.get("email"),
            "role": role,
            "can_access_control_panel": role in (USER_ROLE_ADMIN, USER_ROLE_SUPER_ADMIN),
            "can_manage_users": role == USER_ROLE_SUPER_ADMIN,
        }
    )


@auth_bp.delete("/api/auth/me")
@limiter.limit("30 per minute")
@require_auth
def deactivate_current_account():
    """Deactivate the signed-in user's local account.

    Completed sessions are deleted and the local user row is deactivated. Entra
    is left unchanged so the user can reactivate the local account by logging in.
    """
    from logic.database.init.class_db import USER_ROLE_SUPER_ADMIN

    user = get_current_user()
    if user is None:
        return jsonify({"error": "Authentication required"}), 401

    if user.get("role") == USER_ROLE_SUPER_ADMIN:
        return jsonify({"error": "SuperAdmin accounts cannot deactivate themselves."}), 403

    user_id = user.get("id")
    if not isinstance(user_id, int) or user_id <= 0:
        return jsonify({"error": "Current user id is invalid."}), 400

    from logic.database.operations.sql_setters import block_user_by_id

    try:
        blocked = block_user_by_id(db.session, user_id)
        if not blocked:
            db.session.rollback()
            return jsonify({"error": "User not found."}), 404

        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to deactivate local user account."}), 500

    session.clear()
    return jsonify({"ok": True, "status": "deactivated"})


_MAX_ADMIN_USERS_PAGE = 200
_DEFAULT_ADMIN_USERS_PAGE = 50


@auth_bp.get("/api/admin/user-counts")
@require_roles("Admin", "SuperAdmin")
def admin_user_counts():
    """Return control panel user counts grouped by role.

    Uses a single ``COUNT(*) GROUP BY role`` so the entire users table no
    longer has to be loaded into memory just to tally rows.
    """
    from logic.database.init.class_db import (
        USER_ROLE_ADMIN,
        USER_ROLE_STUDENT,
        USER_ROLE_SUPER_ADMIN,
    )
    from logic.database.operations.sql_getters import count_users_by_role

    by_role = count_users_by_role(db.session)
    counts = {
        "students": int(by_role.get(USER_ROLE_STUDENT, 0)),
        "admins": int(by_role.get(USER_ROLE_ADMIN, 0)),
        "super_admins": int(by_role.get(USER_ROLE_SUPER_ADMIN, 0)),
    }
    counts["total_users"] = (
        counts["students"] + counts["admins"] + counts["super_admins"]
    )
    return jsonify(counts)


@auth_bp.get("/api/admin/users")
@require_roles("SuperAdmin")
def admin_users():
    """Return user emails grouped for the control panel admin view.

    Paginated. Defaults to 50 per page; ``?limit`` is hard-capped at 200.
    """
    from logic.database.init.class_db import USER_ROLE_ADMIN, USER_ROLE_STUDENT
    from logic.database.operations.sql_getters import retrieve_users

    try:
        limit = min(
            int(request.args.get("limit", _DEFAULT_ADMIN_USERS_PAGE)),
            _MAX_ADMIN_USERS_PAGE,
        )
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        return jsonify({"error": "limit and offset must be integers"}), 400

    users = retrieve_users(db.session, limit=limit, offset=offset)
    grouped_users = {
        "students": [],
        "admins": [],
        "limit": limit,
        "offset": offset,
    }

    for user in users:
        is_deactivated = user.get("blocked_at") is not None
        role = user.get("role")
        if role not in (USER_ROLE_STUDENT, USER_ROLE_ADMIN):
            continue

        user_payload = {
            "id": user.get("id"),
            "email": user.get("email"),
            "role": role,
            "is_deactivated": is_deactivated,
        }

        if role == USER_ROLE_STUDENT:
            grouped_users["students"].append(user_payload)
        else:
            grouped_users["admins"].append(user_payload)

    for key in ("students", "admins"):
        grouped_users[key].sort(
            key=lambda user: (
                bool(user.get("is_deactivated")),
                (user.get("email") or "").lower(),
            )
        )

    return jsonify(grouped_users)


@auth_bp.patch("/api/admin/users/<int:user_id>/role")
@require_roles("SuperAdmin")
def update_admin_user_role(user_id: int):
    """Promote students to admins or demote admins back to students."""
    from logic.database.init.class_db import (
        USER_ROLE_ADMIN,
        USER_ROLE_STUDENT,
        USER_ROLE_SUPER_ADMIN,
    )
    from logic.database.operations.sql_getters import retrieve_user_by_id
    from logic.database.operations.sql_setters import update_user_role

    payload = request.get_json(silent=True) or {}
    role = payload.get("role")
    if role not in (USER_ROLE_STUDENT, USER_ROLE_ADMIN):
        return jsonify({"error": "Invalid role"}), 400

    existing_user = retrieve_user_by_id(db.session, user_id)
    if existing_user is None:
        return jsonify({"error": "User not found"}), 404
    if existing_user.get("blocked_at") is not None:
        return jsonify({"error": "User account is deactivated"}), 400

    if existing_user.get("role") == USER_ROLE_SUPER_ADMIN:
        return jsonify({"error": "SuperAdmin role cannot be changed here"}), 403

    try:
        updated_user = update_user_role(db.session, user_id, role)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "id": updated_user.id,
            "email": updated_user.email,
            "role": updated_user.role,
        }
    )


@auth_bp.delete("/api/admin/users/<int:user_id>")
@require_roles("SuperAdmin")
def deactivate_admin_user(user_id: int):
    """Deactivate another user's local account.

    Completed sessions are deleted and the local user row is deactivated. Entra
    is left unchanged so the user can reactivate the local account by logging in.
    """
    from logic.database.init.class_db import USER_ROLE_SUPER_ADMIN
    from logic.database.operations.sql_getters import retrieve_user_by_id
    from logic.database.operations.sql_setters import block_user_by_id

    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Authentication required"}), 401

    current_user_id = current_user.get("id")
    if current_user_id == user_id:
        return jsonify({"error": "SuperAdmin accounts cannot deactivate themselves."}), 403

    target_user = retrieve_user_by_id(db.session, user_id)
    if target_user is None:
        return jsonify({"error": "User not found"}), 404

    if target_user.get("role") == USER_ROLE_SUPER_ADMIN:
        return jsonify({"error": "SuperAdmin accounts cannot be deactivated here"}), 403

    try:
        blocked = block_user_by_id(db.session, user_id)
        if not blocked:
            db.session.rollback()
            return jsonify({"error": "User not found"}), 404

        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to deactivate user account user_id=%s", user_id)
        return jsonify({"error": "Failed to deactivate user account."}), 500

    # Force-logout any active sessions belonging to the deactivated user across all workers.
    from logic.auth import invalidate_sessions_for_user

    invalidate_sessions_for_user(user_id)

    return jsonify({"ok": True, "status": "deactivated"})


@auth_bp.patch("/api/admin/users/<int:user_id>/activate")
@require_roles("SuperAdmin")
def activate_admin_user(user_id: int):
    """Reactivate a locally deactivated user."""
    from logic.database.init.class_db import USER_ROLE_SUPER_ADMIN
    from logic.database.operations.sql_getters import retrieve_user_by_id
    from logic.database.operations.sql_setters import activate_user_by_id

    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Authentication required"}), 401

    current_user_id = current_user.get("id")
    if current_user_id == user_id:
        return jsonify({"error": "SuperAdmin accounts cannot activate themselves here."}), 403

    target_user = retrieve_user_by_id(db.session, user_id)
    if target_user is None:
        return jsonify({"error": "User not found"}), 404

    if target_user.get("role") == USER_ROLE_SUPER_ADMIN:
        return jsonify({"error": "SuperAdmin accounts cannot be activated here"}), 403

    if target_user.get("blocked_at") is None:
        return jsonify({"error": "User account is already active"}), 400

    try:
        activated = activate_user_by_id(db.session, user_id)
        if not activated:
            db.session.rollback()
            return jsonify({"error": "User not found"}), 404

        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to activate user account."}), 500

    return jsonify(
        {
            "ok": True,
            "status": "activated",
            "user": {
                "id": target_user.get("id"),
                "email": target_user.get("email"),
                "role": target_user.get("role"),
                "is_deactivated": False,
            },
        }
    )


@auth_bp.post("/api/auth/logout")
@limiter.limit("60 per minute")
def logout():
    """Clear the local Flask session while leaving Microsoft session cleanup to the frontend."""
    session.clear()
    return jsonify({"ok": True})
