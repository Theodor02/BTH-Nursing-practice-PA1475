"""Flask application entry point.

Initialises CORS (whitelist driven by CORS_ORIGINS env var), server-side cookie
sessions (Redis in production, filesystem fallback in dev), rate limiting, the
database, and all route blueprints.

The CSRF origin check on state-mutation methods is a lightweight second line of
defence: Flask-Session cookies are HttpOnly so JavaScript cannot read them, but a
browser will still attach them on cross-site form submissions. Checking the Origin
header against the same CORS allowlist blocks that vector without needing a
separate CSRF token.
"""
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, g, jsonify, request  # noqa: E402
from flask_cors import CORS  # noqa: E402
from flask_session import Session  # noqa: E402
from sqlalchemy import text  # noqa: E402

from config import configure_app  # noqa: E402
from extensions import limiter  # noqa: E402
from logic.cache import get_cache  # noqa: E402
from logic.database.init.init_db import db, init_database  # noqa: E402
from logic.logging_config import configure_logging  # noqa: E402
from routes.admin_routes import admin_bp  # noqa: E402
from routes.auth_routes import auth_bp  # noqa: E402
from routes.cat_routes import cat_bp  # noqa: E402
from routes.question_routes import question_bp  # noqa: E402
from routes.session_routes import session_bp  # noqa: E402
from routes.stats_routes import stats_bp  # noqa: E402

configure_logging()

app = Flask(__name__)

_cors_origins = [
    o.strip() for o in os.getenv(
        'CORS_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080,http://localhost:5000,http://127.0.0.1:5000'
    ).split(',')
]

CORS(app, resources={r"/*": {"origins": _cors_origins}}, supports_credentials=True)

configure_app(app)
Session(app)
limiter.init_app(app)
init_database(app)

app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(cat_bp)
app.register_blueprint(question_bp)
app.register_blueprint(session_bp)
app.register_blueprint(stats_bp)


@app.before_request
def _attach_request_id():
    """Bind a per-request correlation id so log lines can be traced.

    Honours an inbound ``X-Request-Id`` header (so an upstream proxy can
    propagate its own trace id) and otherwise generates a fresh UUID.
    """
    incoming = request.headers.get("X-Request-Id")
    g.request_id = incoming if incoming else uuid.uuid4().hex


@app.after_request
def _emit_request_id(response):
    request_id = getattr(g, "request_id", None)
    if request_id:
        response.headers.setdefault("X-Request-Id", request_id)
    return response


@app.get("/ping")
def _ping():
    """Trivial liveness probe — does not touch DB or Redis."""
    return jsonify({"pong": True})


@app.get("/health")
def _health():
    """Readiness probe: confirms DB and Redis are reachable.

    Returns 503 with a per-dependency status when anything is unhealthy.
    """
    db_ok = False
    redis_ok = False
    try:
        result = db.session.execute(text("SELECT 1")).scalar()
        db_ok = result == 1
    except Exception:  # noqa: BLE001
        db_ok = False

    try:
        redis_ok = bool(get_cache().ping())
    except Exception:  # noqa: BLE001
        redis_ok = False

    payload = {"status": "ok" if (db_ok and redis_ok) else "degraded", "db": db_ok, "redis": redis_ok}
    return jsonify(payload), (200 if (db_ok and redis_ok) else 503)


@app.before_request
def _check_csrf_origin():
    """Reject state-mutation requests whose Origin is not in the CORS whitelist.

    Only applies to POST/PUT/PATCH/DELETE — safe methods are exempt.
    Browsers always send Origin on cross-origin requests; absent Origin is
    allowed to support server-to-server callers that have no origin.
    """
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return
    origin = request.headers.get('Origin')
    if origin is not None and origin not in _cors_origins:
        return jsonify({'error': 'CSRF check failed: origin not allowed'}), 403


@app.errorhandler(404)
def _not_found(_e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(405)
def _method_not_allowed(_e):
    return jsonify({'error': 'Method not allowed'}), 405


@app.errorhandler(500)
def _internal_error(_e):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
