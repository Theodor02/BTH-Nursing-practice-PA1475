"""Application configuration constants and startup validation.

Validation limits (max courses per request, max questions, etc.) are centralised
here so route modules can import them without depending on each other.

Redis is required for rate limiting and session storage in any non-local
environment. A missing REDIS_URL outside local/test envs raises at startup
rather than silently degrading to an insecure in-process state.

ADMIN_DEBUG_ALL=true bypasses every admin auth check — it is intentionally
blocked at startup if the env is not recognised as local/dev/test.
"""
import logging
import os
import redis

logger = logging.getLogger(__name__)

# ── Request-size limits ───────────────────────────────────────────────────────
# Prevent a single request from generating an unreasonably large quiz or
# burning excessive DB query time. Kept here so route handlers and tests share
# the same source of truth.
_MAX_COURSES_PER_REQUEST = 10
_MAX_CATEGORIES_PER_COURSE = 20
_MAX_QUESTIONS_PER_CATEGORY = 50
_MAX_QUESTIONS_TOTAL = 100       # hard cap across all courses in one request
_MAX_COURSE_CODE_LEN = 50
_MAX_CATEGORY_NAME_LEN = 150

# ── TTL / capacity constants ──────────────────────────────────────────────────
_CAT_REQUEST_TTL = 300       # seconds — category payload Redis cache lifetime
_PENDING_ATTEMPT_TTL = 3600  # seconds — in-flight attempt expires after 1 hour
_MAX_PENDING_ATTEMPTS = 10   # in-process fallback only; Redis has no such cap

# Env values treated as local/dev so REDIS_URL and strict admin checks are optional.
_LOCAL_APP_ENVS = {"development", "dev", "local", "test", "testing"}


def _resolve_rate_limit_storage_uri(app) -> str:
    """Return the Flask-Limiter storage URI for the current environment.

    Returns the ``REDIS_URL`` env var if set. Falls back to ``"memory://"``
    (single-process, non-shared) only when the app is in testing mode or a
    recognised local environment. Raises ``RuntimeError`` otherwise so a
    misconfigured production deploy fails fast at startup.
    """
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis_url

    app_env = os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or os.getenv("ENV") or "development"
    if app.testing or app_env.strip().lower() in _LOCAL_APP_ENVS:
        return "memory://"

    raise RuntimeError(
        "REDIS_URL must be set for rate limiting outside local/test environments"
    )


def _assert_admin_debug_all_safe() -> None:
    """Refuse to boot if the admin-bypass flag is set outside local environments."""
    if os.getenv("ADMIN_DEBUG_ALL", "").lower() != "true":
        return

    app_env = (
        os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or os.getenv("ENV") or "development"
    ).strip().lower()
    if app_env not in _LOCAL_APP_ENVS:
        raise RuntimeError(
            "ADMIN_DEBUG_ALL=true is forbidden outside local/test environments "
            f"(APP_ENV={app_env!r}). Refusing to start."
        )
    logger.warning("ADMIN_DEBUG_ALL is enabled — every admin auth check is bypassed")


def configure_app(app):
    """Apply all Flask configuration from environment variables.

    Sets the secret key, session backend (Redis or filesystem), rate-limit
    storage, and cookie security attributes. Calls the admin-bypass safety
    check so the app refuses to start if ``ADMIN_DEBUG_ALL=true`` outside a
    local environment.

    Args:
        app: The Flask application instance to configure.

    Raises:
        RuntimeError: If ``FLASK_SECRET_KEY`` is unset, if ``REDIS_URL`` is
            missing outside local envs, or if ``ADMIN_DEBUG_ALL=true`` in a
            non-local environment.
    """
    _assert_admin_debug_all_safe()

    secret = os.getenv("FLASK_SECRET_KEY")
    if not secret:
        raise RuntimeError("FLASK_SECRET_KEY environment variable must be set")
    app.config["SECRET_KEY"] = secret
    app.config["SESSION_PERMANENT"] = True
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        app.config["SESSION_TYPE"] = "redis"
        app.config["SESSION_REDIS"] = redis.from_url(redis_url)
    else:
        app.config["SESSION_TYPE"] = "filesystem"
    app.config["RATELIMIT_STORAGE_URI"] = _resolve_rate_limit_storage_uri(app)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = (
        os.getenv("SESSION_COOKIE_SECURE", "true").lower() != "false"
    )
    app.config["SESSION_COOKIE_SAMESITE"] = os.getenv(
        "SESSION_COOKIE_SAMESITE", "Lax"
    )
