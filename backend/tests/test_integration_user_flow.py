import os
import uuid

import pytest
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_session import Session

from config import configure_app
from extensions import limiter
from logic.database.init.init_db import init_database


@pytest.fixture
def integration_client(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", os.getenv("FLASK_SECRET_KEY", "integration-secret"))

    app = Flask(__name__)
    app.config["TESTING"] = True

    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    CORS(app, origins=cors_origins)

    configure_app(app)
    Session(app)
    limiter.init_app(app)
    init_database(app)

    # The app_module unit-test fixture reimports routes/* while a fake db is
    # active, so those modules capture db=fake_db.  Monkeypatch restores
    # init_db but leaves the contaminated reimports in sys.modules.  Clear them
    # here so the imports below pick up the real db.
    import sys
    _stale = [
        m for m in list(sys.modules)
        if m.startswith("routes.") or m in (
            "logic.auth", "logic.cat_request_cache",
            "logic.pending_attempts", "logic.grader",
        )
    ]
    for _m in _stale:
        sys.modules.pop(_m, None)

    import routes.auth_routes as auth_routes_mod
    from routes.cat_routes import cat_bp
    from routes.question_routes import question_bp
    from routes.session_routes import session_bp

    def mock_resolve_verified_request_context(auth_header):
        if not auth_header:
            raise auth_routes_mod.AuthenticationError("Missing Authorization header.")
        test_id = uuid.uuid4().hex[:8]
        return auth_routes_mod.VerifiedRequestContext(
            sso_id=f"integration-{uuid.uuid4()}",
            email=f"integration-{test_id}@example.com",
            tenant_id="00000000-0000-0000-0000-000000000000",
            claims={"oid": f"integration-{uuid.uuid4()}", "email": f"integration-{test_id}@example.com"},
        )

    monkeypatch.setattr(
        auth_routes_mod,
        "resolve_verified_request_context",
        mock_resolve_verified_request_context,
    )

    app.register_blueprint(auth_routes_mod.auth_bp)
    app.register_blueprint(cat_bp)
    app.register_blueprint(question_bp)
    app.register_blueprint(session_bp)

    @app.before_request
    def _check_csrf_origin():
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return
        origin = request.headers.get("Origin")
        if origin is not None and origin not in cors_origins:
            return jsonify({"error": "CSRF check failed: origin not allowed"}), 403

    return app.test_client()


def test_user_can_run_answer_and_retrieve_question_history(integration_client):
    login_response = integration_client.post(
        "/login",
        headers={"Authorization": "Bearer mock-token-for-integration-test"}
    )
    assert login_response.status_code == 200
    user_id = login_response.get_json()["user_id"]
    assert isinstance(user_id, int) and user_id > 0

    cat_response = integration_client.get("/cat_request")
    assert cat_response.status_code == 200
    cat_payload = cat_response.get_json()
    courses = cat_payload["courses"]
    max_questions = cat_payload["max_questions"]

    selected_course = None
    selected_category = None
    for course_code, course_info in courses.items():
        for category_name in course_info["categories"]:
            max_count = max_questions.get(course_code, {}).get(category_name, 0)
            if isinstance(max_count, int) and max_count > 0:
                selected_course = course_code
                selected_category = category_name
                break
        if selected_course:
            break

    assert selected_course is not None
    assert selected_category is not None

    question_post_response = integration_client.post(
        "/question_post",
        json={
            "questions_request": {
                "course": {
                    selected_course: {
                        selected_category: 1,
                    }
                }
            }
        },
    )
    assert question_post_response.status_code == 200
    question_payload = question_post_response.get_json()
    attempt_id = question_payload["attempt_id"]
    generated_questions = question_payload["questions"]

    question_items = generated_questions[selected_course][selected_category]
    assert len(question_items) == 1
    question_item = question_items[0]

    submit_response = integration_client.post(
        "/question_submit",
        json={
            "attempt_id": attempt_id,
            "answers": {
                question_item["id"]: question_item["correct_answer"],
            },
        },
    )
    assert submit_response.status_code == 200
    submit_payload = submit_response.get_json()
    session_id = submit_payload["session_id"]
    assert isinstance(session_id, int)
    assert submit_payload["scored_count"] >= 1

    history_response = integration_client.get("/session_request")
    assert history_response.status_code == 200
    history_payload = history_response.get_json()
    assert history_payload["user_id"] == user_id
    user_sessions = history_payload["sessions"]
    assert any(session["id"] == session_id for session in user_sessions)

    session_response = integration_client.post(
        "/session_post",
        json={"session_id": session_id},
    )
    assert session_response.status_code == 200
    session_payload = session_response.get_json()
    assert session_payload["user_id"] == user_id
    assert session_payload["session"]["id"] == session_id
    assert session_payload["session"]["questions"]["attempt_id"] == attempt_id
