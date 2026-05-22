"""
Integration tests for the admin entity CRUD chain.

Tests the full lifecycle: create → read (categories_nested + cat_request) →
edit → read → archive → read → unarchive → read, for questions, categories,
courses, and units.

Requires a running PostgreSQL instance. Set POSTGRES_* env vars to point at
the test database (defaults match the docker-compose dev stack).

Run with:
    cd backend && pytest tests/test_admin_entity_integration.py -v
"""
import os
import uuid

import pytest
from flask import Flask

from logic.database.init.init_db import db


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_client():
    """
    Flask test client wired to a real database.
    Admin auth bypassed via ADMIN_DEBUG_ALL=true.
    Cat-request auth bypassed by injecting user_id into the cookie session.
    """
    os.environ["ADMIN_DEBUG_ALL"] = "true"
    os.environ["FLASK_SECRET_KEY"] = "integration-test-secret"

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "qtrain")
    password = os.getenv("POSTGRES_PASSWORD", "qtrain")
    dbname = os.getenv("POSTGRES_DB", "qtrain")

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "integration-test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Import blueprints inside the fixture so module-level cache (_cache) is
    # shared with the route handlers that will run inside this app.
    from routes.admin_routes import admin_bp
    from routes.cat_routes import cat_bp, invalidate_cat_request_cache

    app.register_blueprint(admin_bp)
    app.register_blueprint(cat_bp)

    client = app.test_client()

    # Inject a user_id so require_auth passes for /cat_request.
    # (The value 1 is arbitrary — require_auth only checks it is a positive int.)
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    # Ensure the cache is empty at the start of the test session.
    with app.app_context():
        invalidate_cat_request_cache()

    yield client

    # Cleanup env vars set for this fixture.
    os.environ.pop("ADMIN_DEBUG_ALL", None)
    os.environ.pop("FLASK_SECRET_KEY", None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mutate(client, operations):
    resp = client.post("/admin/mutate", json=operations)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert "results" in data
    for r in data["results"]:
        assert r["status"] == "success", r
    return data["results"]


def _categories_nested(client):
    resp = client.get("/admin/categories_nested")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


def _cat_request(client):
    resp = client.get("/cat_request")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


def _find_category(nested, category_id):
    return next((c for c in nested if c["id"] == category_id), None)


def _find_question(nested, category_id, question_id):
    cat = _find_category(nested, category_id)
    if cat is None:
        return None
    return next((q for q in cat["questions"] if q["id"] == question_id), None)


def _cat_request_count(payload, course_code, category_name):
    courses = payload.get("courses", {})
    max_q = payload.get("max_questions", {})
    if course_code not in courses:
        return None
    cats = [c for c in courses[course_code].get("categories", []) if c == category_name]
    if not cats:
        return None
    return max_q.get(course_code, {}).get(category_name)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAdminEntityCRUD:
    """Full CRUD lifecycle for course → category → question chain."""

    # Unique suffix prevents conflicts with existing DB data.
    _suffix = uuid.uuid4().hex[:8]
    _course_code = f"INT_{_suffix}"
    _category_name = f"Int Category {_suffix}"
    _question_template = f"Integration question {_suffix}: what is {{v}}+1?"

    _course_id = None
    _category_id = None
    _question_id = None

    def test_01_create_course(self, admin_client):
        results = _mutate(admin_client, [
            {
                "type": 0,
                "action": 0,
                "body": {"course_code": self._course_code, "name": f"Integration Course {self._suffix}"},
            }
        ])
        TestAdminEntityCRUD._course_id = results[0]["id"]
        assert isinstance(self._course_id, int)

    def test_02_create_category_linked_to_course(self, admin_client):
        results = _mutate(admin_client, [
            {
                "type": 1,
                "action": 0,
                "body": {
                    "name": self._category_name,
                    "course_ids": [self._course_id],
                },
            }
        ])
        TestAdminEntityCRUD._category_id = results[0]["id"]
        assert isinstance(self._category_id, int)

    def test_03_categories_nested_shows_new_category(self, admin_client):
        nested = _categories_nested(admin_client)
        cat = _find_category(nested, self._category_id)
        assert cat is not None, "New category not found in categories_nested"
        assert cat["active"] is True
        assert cat["name"] == self._category_name
        assert any(c["id"] == self._course_id for c in cat["courses"])

    def test_04_create_question_with_course_and_category(self, admin_client):
        results = _mutate(admin_client, [
            {
                "type": 2,
                "action": 0,
                "body": {
                    "template": self._question_template,
                    "variables": {"v": {"min": 1, "max": 10, "decimals": 0}},
                    "formula": "v + 1",
                    "unit": "ml",
                    "tolerance": 0.01,
                    "category_ids": [self._category_id],
                    "course_ids": [self._course_id],
                },
            }
        ])
        TestAdminEntityCRUD._question_id = results[0]["id"]
        assert self._question_id is not None

    def test_05_categories_nested_shows_new_question(self, admin_client):
        nested = _categories_nested(admin_client)
        q = _find_question(nested, self._category_id, self._question_id)
        assert q is not None, "New question not found in categories_nested"
        assert q["active"] is True

    def test_06_cat_request_counts_new_question(self, admin_client):
        payload = _cat_request(admin_client)
        count = _cat_request_count(payload, self._course_code, self._category_name)
        assert count is not None, (
            f"Course '{self._course_code}' / category '{self._category_name}' "
            f"not found in cat_request — question may lack course association or cache not invalidated"
        )
        assert count >= 1, f"Expected at least 1 question, got {count}"

    def test_07_edit_question_template_text(self, admin_client):
        new_template = f"EDITED: {self._question_template}"
        _mutate(admin_client, [
            {
                "type": 2,
                "action": 2,
                "body": {"id": self._question_id, "template": new_template},
            }
        ])

    def test_08_categories_nested_reflects_edit(self, admin_client):
        nested = _categories_nested(admin_client)
        q = _find_question(nested, self._category_id, self._question_id)
        assert q is not None
        assert q["active"] is True
        # excerpt is first 50 chars of template + "..." (if long)
        assert "EDITED" in q["excerpt"]

    def test_09_archive_question(self, admin_client):
        _mutate(admin_client, [
            {
                "type": 2,
                "action": 1,
                "body": {"id": self._question_id, "archive": True},
            }
        ])

    def test_10_categories_nested_shows_question_inactive_after_archive(self, admin_client):
        nested = _categories_nested(admin_client)
        q = _find_question(nested, self._category_id, self._question_id)
        assert q is not None, "Archived question should still appear in categories_nested"
        assert q["active"] is False, (
            f"Expected active=False after archive, got active={q['active']}"
        )

    def test_11_cat_request_excludes_archived_question(self, admin_client):
        payload = _cat_request(admin_client)
        count = _cat_request_count(payload, self._course_code, self._category_name)
        # Count may be 0 or the entry may be absent — both are acceptable.
        assert count is None or count == 0, (
            f"Archived question still counted in cat_request: count={count}"
        )

    def test_12_unarchive_question(self, admin_client):
        _mutate(admin_client, [
            {
                "type": 2,
                "action": 1,
                "body": {"id": self._question_id, "archive": False},
            }
        ])

    def test_13_categories_nested_shows_question_active_after_unarchive(self, admin_client):
        nested = _categories_nested(admin_client)
        q = _find_question(nested, self._category_id, self._question_id)
        assert q is not None
        assert q["active"] is True

    def test_14_cat_request_recounts_after_unarchive(self, admin_client):
        payload = _cat_request(admin_client)
        count = _cat_request_count(payload, self._course_code, self._category_name)
        assert count is not None and count >= 1

    def test_15_edit_question_again_after_unarchive(self, admin_client):
        _mutate(admin_client, [
            {
                "type": 2,
                "action": 2,
                "body": {
                    "id": self._question_id,
                    "template": f"TWICE EDITED: {self._question_template}",
                    "tolerance": 0.05,
                },
            }
        ])
        nested = _categories_nested(admin_client)
        q = _find_question(nested, self._category_id, self._question_id)
        assert q is not None
        assert q["active"] is True
        assert "TWICE EDITED" in q["excerpt"]

    def test_16_archive_category(self, admin_client):
        _mutate(admin_client, [
            {
                "type": 1,
                "action": 1,
                "body": {"id": self._category_id, "archive": True},
            }
        ])

    def test_17_categories_nested_shows_category_inactive(self, admin_client):
        nested = _categories_nested(admin_client)
        cat = _find_category(nested, self._category_id)
        assert cat is not None
        assert cat["active"] is False, (
            f"Expected category active=False after archive, got {cat['active']}"
        )

    def test_18_unarchive_category(self, admin_client):
        _mutate(admin_client, [
            {
                "type": 1,
                "action": 1,
                "body": {"id": self._category_id, "archive": False},
            }
        ])
        nested = _categories_nested(admin_client)
        cat = _find_category(nested, self._category_id)
        assert cat is not None
        assert cat["active"] is True

    def test_19_archive_course(self, admin_client):
        _mutate(admin_client, [
            {
                "type": 0,
                "action": 1,
                "body": {"id": self._course_id, "archive": True},
            }
        ])

    def test_20_unarchive_course(self, admin_client):
        _mutate(admin_client, [
            {
                "type": 0,
                "action": 1,
                "body": {"id": self._course_id, "archive": False},
            }
        ])


class TestUnitCRUD:
    """Full CRUD lifecycle for units and their aliases."""

    _suffix = uuid.uuid4().hex[:8]
    _unit_name = f"int_unit_{_suffix}"
    _unit_id = None
    _alias_id = None

    def test_01_create_unit(self, admin_client):
        results = _mutate(admin_client, [
            {"type": 3, "action": 0, "body": {"name": self._unit_name}}
        ])
        TestUnitCRUD._unit_id = results[0]["id"]
        assert isinstance(self._unit_id, int)

    def test_02_add_alias(self, admin_client):
        results = _mutate(admin_client, [
            {"type": 4, "action": 0, "body": {"unit_id": self._unit_id, "alias": f"alias_{self._suffix}"}}
        ])
        TestUnitCRUD._alias_id = results[0]["id"]
        assert isinstance(self._alias_id, int)

    def test_03_edit_unit_name(self, admin_client):
        _mutate(admin_client, [
            {"type": 3, "action": 2, "body": {"id": self._unit_id, "name": f"edited_{self._unit_name}"}}
        ])

    def test_04_edit_alias(self, admin_client):
        _mutate(admin_client, [
            {"type": 4, "action": 2, "body": {"id": self._alias_id, "alias": f"edited_alias_{self._suffix}"}}
        ])

    def test_05_archive_unit(self, admin_client):
        _mutate(admin_client, [
            {"type": 3, "action": 1, "body": {"id": self._unit_id, "archive": True}}
        ])

    def test_06_unarchive_unit(self, admin_client):
        _mutate(admin_client, [
            {"type": 3, "action": 1, "body": {"id": self._unit_id, "archive": False}}
        ])

    def test_07_delete_alias(self, admin_client):
        _mutate(admin_client, [
            {"type": 4, "action": 1, "body": {"id": self._alias_id}}
        ])
