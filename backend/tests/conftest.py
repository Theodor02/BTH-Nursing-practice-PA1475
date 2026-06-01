import importlib
import types
from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Pre-import with real SQLAlchemy db so class_db is cached before FakeDB is patched in.
# Without this, running a single test file that doesn't trigger test_database_schema.py
# collection would cause 'FakeDB has no attribute Table' errors.
import logic.database.init.class_db  # noqa: E402

_MODULES_TO_RELOAD = [
    "app",
    "routes",
    "routes.question_routes",
    "routes.session_routes",
    "routes.auth_routes",
    "routes.cat_routes",
    "routes.admin_routes",
    "routes.stats_routes",
    "logic.auth",
    "logic.cat_request_cache",
    "logic.grader",
    "logic.pending_attempts",
]


@pytest.fixture
def app_module(monkeypatch):
    """Import app.py with fake DB/getter modules for unit-level tests."""

    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_DEBUG_ALL", "true")
    monkeypatch.setenv("APP_ENV", "test")

    fake_init_db = types.ModuleType("logic.database.init.init_db")

    class FakeSession:
        def __init__(self):
            self.should_fail = False
            self.appended_question_results = []
            self.updated_scores = []
            self.created_sessions = []

        def execute(self, *_args, **_kwargs):
            if self.should_fail:
                raise RuntimeError("database unavailable")
            _self = self

            class _FakeResult:
                def scalar(self_r):
                    return None

                def scalars(self_r):
                    return self_r

                def unique(self_r):
                    return self_r

                def all(self_r):
                    return []

            return _FakeResult()

        def get(self, model, id, **kwargs):
            if self.should_fail:
                raise RuntimeError("database unavailable")
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

        def flush(self):
            return None

    class FakeDB:
        def __init__(self):
            self.session = FakeSession()

    fake_db = FakeDB()

    def init_database(_app):
        return fake_db

    fake_init_db.db = fake_db
    fake_init_db.init_database = init_database

    fake_getters = types.ModuleType(
        "logic.database.operations.sql_getters"
    )
    fake_getters.retrieve_active_question_templates_by_course_and_category = (  # noqa: E501
        lambda session, course_id, category_id, limit: []
    )
    fake_getters.retrieve_active_template_count_by_course_and_category = (
        lambda session, course_id, category_id: 0
    )
    fake_getters.retrieve_cat_request_payload = (
        lambda session: ({}, {})
    )
    fake_getters.retrieve_category_by_name_and_course_id = (
        lambda session, category_name, course_id: None
    )
    fake_getters.retrieve_course_by_code = (
        lambda session, course_code: None
    )
    fake_getters.retrieve_users_by_sso_id = (
        lambda session, sso_id: []
    )
    fake_getters.retrieve_users = lambda session, limit=None, offset=0: []
    fake_getters.count_users_by_role = lambda session: {}
    fake_getters.retrieve_user_by_id = (
        lambda session, user_id: {
            "id": user_id,
            "email": "admin@example.com",
            "role": "SuperAdmin",
            "blocked_at": None,
        }
    )
    fake_getters.retrieve_session_by_id = (
        lambda session, session_id: None
    )
    fake_getters.retrieve_sessions_by_user_id = (
        lambda session, user_id: []
    )
    fake_getters.retrieve_session_by_user_id_and_session_id = (
        lambda session, user_id, session_id: None
    )

    fake_setters = types.ModuleType(
        "logic.database.operations.sql_setters"
    )

    def append_session_question_result(
        session, session_id, updated_snapshot
    ):
        session.appended_question_results.append(
            (session_id, updated_snapshot)
        )
        return updated_snapshot

    def update_session_score(session, session_id, score):
        session.updated_scores.append((session_id, score))
        return score

    fake_setters.append_session_question_result = (
        append_session_question_result
    )
    fake_setters.update_session_score = update_session_score
    fake_setters.create_or_get_user_by_sso = (
        lambda session, sso_id, email: (
            types.SimpleNamespace(id=1, role="Student", blocked_at=None), True
        )
    )
    fake_setters.block_user_by_id = lambda session, user_id: True
    fake_setters.activate_user_by_id = lambda session, user_id: True

    def create_session(
        session, user_id, course_id, category_id, questions, score
    ):
        session.created_sessions.append(
            {
                "user_id": user_id,
                "course_id": course_id,
                "category_id": category_id,
                "questions": questions,
                "score": score,
            }
        )
        created_id = len(session.created_sessions)
        return types.SimpleNamespace(id=created_id)

    fake_setters.create_session = create_session

    fake_setters.attach_category_to_course = lambda session, **kw: True
    fake_setters.detach_category_from_course = lambda session, **kw: True
    fake_setters.create_course = lambda session, **kw: types.SimpleNamespace(id=1)
    fake_setters.update_course = lambda session, **kw: None
    fake_setters.set_course_active = lambda session, **kw: None
    fake_setters.create_category = lambda session, **kw: types.SimpleNamespace(id=1)
    fake_setters.update_category = lambda session, **kw: None
    fake_setters.set_category_active = lambda session, **kw: None
    fake_setters.create_question_template = lambda session, **kw: types.SimpleNamespace(id="stub")
    fake_setters.update_question_template = lambda session, **kw: None
    fake_setters.set_question_template_active = lambda session, **kw: None
    fake_setters.replace_template_categories = lambda session, **kw: None
    fake_setters.replace_template_courses = lambda session, **kw: None
    fake_setters.create_unit = lambda session, **kw: types.SimpleNamespace(id=1)
    fake_setters.update_unit = lambda session, **kw: None
    fake_setters.set_unit_active = lambda session, **kw: None
    fake_setters.create_unit_alias = lambda session, **kw: types.SimpleNamespace(id=1)
    fake_setters.update_unit_alias = lambda session, **kw: None
    fake_setters.delete_unit_alias = lambda session, **kw: True
    fake_setters.write_history_entry = lambda session, *args, **kw: None
    fake_setters.set_user_admin_by_email = lambda session, email, is_admin: None

    fake_stats = types.ModuleType("logic.database.operations.sql_stats")
    fake_stats.get_admin_overview_stats = lambda session, f, t: {}
    fake_stats.get_admin_course_stats = lambda session, f, t: []
    fake_stats.get_admin_category_stats = lambda session, f, t, **kw: []
    fake_stats.get_admin_question_stats = lambda session, f, t, **kw: []
    fake_stats.get_user_overview_stats = lambda session, uid, from_dt=None, to_dt=None: {}
    fake_stats.get_user_mastery_stats = lambda session, uid, from_dt=None, to_dt=None: []
    fake_stats.get_user_activity_stats = lambda session, uid, **kw: []

    monkeypatch.setitem(
        sys.modules, "logic.database.operations.sql_stats", fake_stats
    )
    monkeypatch.setitem(
        sys.modules, "logic.database.init.init_db", fake_init_db
    )
    monkeypatch.setitem(
        sys.modules,
        "logic.database.operations.sql_getters",
        fake_getters,
    )
    monkeypatch.setitem(
        sys.modules,
        "logic.database.operations.sql_setters",
        fake_setters,
    )

    for mod in _MODULES_TO_RELOAD:
        sys.modules.pop(mod, None)

    app_mod = importlib.import_module("app")
    app_mod.fake_db = fake_db
    return app_mod


@pytest.fixture
def client(app_module, monkeypatch):
    """Create a test client with mocked Azure auth for testing."""
    from routes.auth_routes import VerifiedRequestContext
    
    # Mock resolve_verified_request_context to bypass Azure auth in tests
    def mock_resolve_verified_request_context(auth_header):
        if not auth_header:
            from routes.auth_routes import AuthenticationError
            raise AuthenticationError("Missing Authorization header.")
        return VerifiedRequestContext(
            sso_id="oid-123",
            email="student@example.com",
            tenant_id="00000000-0000-0000-0000-000000000000",
            claims={"oid": "oid-123", "email": "student@example.com"},
        )
    
    import routes.auth_routes as auth_routes
    monkeypatch.setattr(
        auth_routes,
        "resolve_verified_request_context",
        mock_resolve_verified_request_context,
    )
    
    return app_module.app.test_client()
