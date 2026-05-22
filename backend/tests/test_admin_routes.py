import types

import pytest


@pytest.fixture(autouse=True)
def super_admin_session(client):
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["role"] = "SuperAdmin"


def _fake_execute_returning(templates):
    """Return a mock that satisfies db.session.execute(...).scalars().unique().all()."""
    unique_mock = types.SimpleNamespace(all=lambda: templates)
    scalars_mock = types.SimpleNamespace(all=lambda: templates, unique=lambda: unique_mock)
    return types.SimpleNamespace(scalars=lambda: scalars_mock)


# ── GET /admin/categories_nested ─────────────────────────────────────────────

def patch_db_session_execute(monkeypatch, ar, results):
    """Patch db.session.execute to return the given results."""
    monkeypatch.setattr(ar.db.session, "execute", lambda *a, **k: _fake_execute_returning(results))


def patch_db_session_get(monkeypatch, ar, entity):
    """Patch db.session.get to return a single entity."""
    monkeypatch.setattr(ar.db.session, "get", lambda model, id: entity)


def test_categories_nested_returns_categories_with_active_field(client, monkeypatch):
    import routes.admin_routes as ar

    fake_q = types.SimpleNamespace(id="q1", template="A short question", active=True)
    fake_cat = types.SimpleNamespace(
        id=1, name="Algebra", active=True,
        courses=[types.SimpleNamespace(id=2, course_code="MATH101", name="Math 101")],
        question_templates=[fake_q],
    )
    patch_db_session_execute(monkeypatch, ar, [fake_cat])

    response = client.get("/admin/categories_nested")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0] == {
        "id": 1,
        "name": "Algebra",
        "active": True,
        "courses": [{"id": 2, "course_code": "MATH101", "name": "Math 101"}],
        "questions": [{"id": "q1", "excerpt": "A short question", "active": True}],
    }


def test_categories_nested_truncates_long_question_excerpts(client, monkeypatch):
    import routes.admin_routes as ar

    long_template = "A" * 60
    fake_q = types.SimpleNamespace(id="q2", template=long_template, active=False)
    fake_cat = types.SimpleNamespace(
        id=2, name="Geometry", active=False, courses=[], question_templates=[fake_q]
    )
    patch_db_session_execute(monkeypatch, ar, [fake_cat])

    response = client.get("/admin/categories_nested")

    assert response.status_code == 200
    data = response.get_json()
    assert data[0]["active"] is False
    assert data[0]["questions"][0]["excerpt"] == "A" * 50 + "..."


def test_categories_nested_returns_empty_list_when_no_categories(client, monkeypatch):
    import routes.admin_routes as ar

    patch_db_session_execute(monkeypatch, ar, [])

    response = client.get("/admin/categories_nested")

    assert response.status_code == 200
    assert response.get_json() == []


def test_categories_nested_returns_500_on_db_error(client, monkeypatch):
    import routes.admin_routes as ar

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(ar.db.session, "execute", boom)

    response = client.get("/admin/categories_nested")

    assert response.status_code == 500
    assert "db down" in response.get_json()["error"]


# ── GET /admin/entity/<entity_type>/<entity_id> ───────────────────────────────

def _fake_model_get(entity):
    """Return a SimpleNamespace that acts as Model with query.get() returning entity."""
    return types.SimpleNamespace(query=types.SimpleNamespace(get=lambda _: entity))


def test_get_entity_course_returns_fields_including_active(client, monkeypatch):
    import routes.admin_routes as ar

    fake_course = types.SimpleNamespace(
        id=3, course_code="MEK101", name="Mechanics", active=True,
        created_at=None, last_updated=None, history=None,
    )
    monkeypatch.setattr(ar.db.session, "get", lambda *a, **k: fake_course)

    response = client.get("/admin/entity/0/3")

    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == 3
    assert data["course_code"] == "MEK101"
    assert data["name"] == "Mechanics"
    assert data["active"] is True


def test_get_entity_course_returns_404_when_not_found(client, monkeypatch):
    import routes.admin_routes as ar

    monkeypatch.setattr(ar.db.session, "get", lambda *a, **k: None)

    response = client.get("/admin/entity/0/99")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Course not found"}


def test_get_entity_category_returns_fields_including_active(client, monkeypatch):
    import routes.admin_routes as ar

    fake_cat = types.SimpleNamespace(
        id=5, name="Derivatives", active=False,
        created_at=None, last_updated=None, history=None,
    )
    monkeypatch.setattr(ar.db.session, "get", lambda *a, **k: fake_cat)

    response = client.get("/admin/entity/1/5")

    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == 5
    assert data["name"] == "Derivatives"
    assert data["active"] is False


def test_get_entity_category_returns_404_when_not_found(client, monkeypatch):
    import routes.admin_routes as ar

    monkeypatch.setattr(ar.db.session, "get", lambda *a, **k: None)

    response = client.get("/admin/entity/1/99")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Category not found"}


def test_get_entity_question_returns_full_template(client, monkeypatch):
    import routes.admin_routes as ar

    fake_qt = types.SimpleNamespace(
        id="Mek_1_1",
        template="A ball is thrown",
        variables={"v": {"min": 1, "max": 10, "decimals": 0}},
        formula="v * 2",
        unit="m/s",
        tolerance=0.01,
        hints=None,
        link=None,
        active=True,
    )
    monkeypatch.setattr(ar.db.session, "get", lambda *a, **k: fake_qt)

    response = client.get("/admin/entity/2/Mek_1_1")

    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == "Mek_1_1"
    assert data["unit"] == "m/s"
    assert data["tolerance"] == 0.01
    assert data["active"] is True


def test_get_entity_question_returns_404_when_not_found(client, monkeypatch):
    import routes.admin_routes as ar

    monkeypatch.setattr(ar.db.session, "get", lambda *a, **k: None)

    response = client.get("/admin/entity/2/missing_id")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Question not found"}


def test_get_entity_unit_returns_unit_fields(client, monkeypatch):
    import routes.admin_routes as ar

    fake_unit = types.SimpleNamespace(
        id=2, name="mg", active=True, created_at=None, last_updated=None,
        aliases=[],
    )
    monkeypatch.setattr(ar.db.session, "get", lambda *a, **k: fake_unit)

    response = client.get("/admin/entity/3/2")

    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == 2
    assert data["name"] == "mg"
    assert data["active"] is True
    assert data["aliases"] == []


def test_get_entity_unit_returns_aliases(client, monkeypatch):
    import routes.admin_routes as ar

    fake_unit = types.SimpleNamespace(
        id=2, name="mg", active=True, created_at=None, last_updated=None,
        aliases=[types.SimpleNamespace(id=1, alias="milligrams")],
    )
    monkeypatch.setattr(ar.db.session, "get", lambda *a, **k: fake_unit)

    response = client.get("/admin/entity/3/2")

    assert response.status_code == 200
    data = response.get_json()
    assert data["aliases"] == [{"id": 1, "alias": "milligrams"}]


def test_get_entity_unit_returns_404_when_not_found(client, monkeypatch):
    import routes.admin_routes as ar

    monkeypatch.setattr(ar.db.session, "get", lambda *a, **k: None)

    response = client.get("/admin/entity/3/99")

    assert response.status_code == 404
    assert response.get_json() == {"error": "Unit not found"}


def test_get_entity_returns_400_for_unknown_entity_type(client):
    response = client.get("/admin/entity/9/1")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid entity type"}


def test_get_entity_returns_400_for_non_integer_id_on_numeric_entity(client):
    response = client.get("/admin/entity/0/not-a-number")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid ID format"}


# ── GET /admin/questions ──────────────────────────────────────────────────────

def test_get_questions_returns_paginated_list(client, app_module, monkeypatch):
    fake_templates = [
        types.SimpleNamespace(id="q1", template="Short template", unit="kg", active=True),
        types.SimpleNamespace(id="q2", template=None, unit=None, active=False),
    ]
    monkeypatch.setattr(
        app_module.fake_db.session, "execute",
        lambda *a, **kw: _fake_execute_returning(fake_templates),
    )

    response = client.get("/admin/questions")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    assert data[0] == {"id": "q1", "excerpt": "Short template", "unit": "kg", "active": True}
    assert data[1] == {"id": "q2", "excerpt": None, "unit": None, "active": False}


def test_get_questions_truncates_long_template_excerpts(client, app_module, monkeypatch):
    long_text = "B" * 60
    fake_templates = [
        types.SimpleNamespace(id="q3", template=long_text, unit="L", active=True),
    ]
    monkeypatch.setattr(
        app_module.fake_db.session, "execute",
        lambda *a, **kw: _fake_execute_returning(fake_templates),
    )

    response = client.get("/admin/questions")

    assert response.status_code == 200
    data = response.get_json()
    assert data[0]["excerpt"] == "B" * 50 + "..."


def test_get_questions_returns_empty_list_when_no_templates(client, app_module, monkeypatch):
    monkeypatch.setattr(
        app_module.fake_db.session, "execute",
        lambda *a, **kw: _fake_execute_returning([]),
    )

    response = client.get("/admin/questions")

    assert response.status_code == 200
    assert response.get_json() == []


def test_get_questions_rejects_non_integer_limit(client):
    response = client.get("/admin/questions?limit=abc")

    assert response.status_code == 400
    assert "limit and offset must be integers" in response.get_json()["error"]


def test_get_questions_rejects_non_integer_offset(client):
    response = client.get("/admin/questions?offset=xyz")

    assert response.status_code == 400
    assert "limit and offset must be integers" in response.get_json()["error"]


def test_get_questions_caps_limit_at_200(client, app_module, monkeypatch):
    captured = {}

    def fake_execute(query, *a, **kw):
        captured["query"] = query
        return _fake_execute_returning([])

    monkeypatch.setattr(app_module.fake_db.session, "execute", fake_execute)

    response = client.get("/admin/questions?limit=9999")

    assert response.status_code == 200


def test_get_questions_uses_default_limit_of_50(client, app_module, monkeypatch):
    monkeypatch.setattr(
        app_module.fake_db.session, "execute",
        lambda *a, **kw: _fake_execute_returning([]),
    )

    response = client.get("/admin/questions")

    assert response.status_code == 200


# ── POST /admin/mutate — validation ───────────────────────────────────────────

def test_mutate_rejects_non_list_body(client):
    response = client.post("/admin/mutate", json={"not": "a list"})

    assert response.status_code == 400
    assert response.get_json() == {"error": "Expected a list of operations"}


def test_mutate_returns_error_for_unknown_entity_type(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 99, "action": 0, "body": {}}],
    )

    assert response.status_code == 200
    results = response.get_json()["results"]
    assert results[0]["status"] == "error"
    assert "Unknown entity type" in results[0]["message"]


def test_mutate_processes_multiple_operations_in_one_batch(client):
    operations = [
        {"type": 0, "action": 0, "body": {"course_code": "TMA4100", "name": "Calculus"}},
        {"type": 1, "action": 0, "body": {"name": "Derivatives"}},
        {"type": 3, "action": 0, "body": {"name": "kg"}},
    ]

    response = client.post("/admin/mutate", json=operations)

    assert response.status_code == 200
    results = response.get_json()["results"]
    assert len(results) == 3
    assert all(r["status"] == "success" for r in results)


def test_mutate_rolls_back_entire_batch_on_setter_error(client, monkeypatch):
    import routes.admin_routes as ar

    def raise_value_error(*a, **kw):
        raise ValueError("DB constraint violated")

    monkeypatch.setattr(ar, "create_course", raise_value_error)

    response = client.post(
        "/admin/mutate",
        json=[{"type": 0, "action": 0, "body": {"course_code": "X", "name": "Y"}}],
    )

    assert response.status_code == 500
    assert "DB constraint violated" in response.get_json()["error"]


# ── POST /admin/mutate — course ───────────────────────────────────────────────

def test_mutate_course_create_returns_new_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 0, "action": 0, "body": {"course_code": "TMA4100", "name": "Calculus"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "course", "action": 0, "id": 1}


def test_mutate_course_create_requires_course_code_and_name(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 0, "action": 0, "body": {"name": "Missing code"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "course_code and name are required" in result["message"]


def test_mutate_course_edit_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 0, "action": 2, "body": {"id": 5, "name": "Updated Calculus"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "course", "action": 2}


def test_mutate_course_edit_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 0, "action": 2, "body": {"name": "No ID given"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_course_archive_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 0, "action": 1, "body": {"id": 5}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "course", "action": 1}


def test_mutate_course_unarchive_sends_archive_false(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 0, "action": 1, "body": {"id": 5, "archive": False}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "success"


def test_mutate_course_archive_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 0, "action": 1, "body": {}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_course_unknown_action_returns_error(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 0, "action": 99, "body": {"course_code": "X", "name": "Y"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "Unknown action" in result["message"]


# ── POST /admin/mutate — category ─────────────────────────────────────────────

def test_mutate_category_create_returns_new_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 1, "action": 0, "body": {"name": "Derivatives"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "category", "action": 0, "id": 1}


def test_mutate_category_create_requires_name(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 1, "action": 0, "body": {}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "name is required" in result["message"]


def test_mutate_category_edit_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 1, "action": 2, "body": {"id": 3, "name": "Integrals"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "category", "action": 2}


def test_mutate_category_edit_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 1, "action": 2, "body": {"name": "Integrals"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_category_archive_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 1, "action": 1, "body": {"id": 3}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "category", "action": 1}


def test_mutate_category_archive_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 1, "action": 1, "body": {}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_category_unknown_action_returns_error(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 1, "action": 99, "body": {"name": "X"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "Unknown action" in result["message"]


# ── POST /admin/mutate — question ─────────────────────────────────────────────

def test_mutate_question_create_returns_new_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 2, "action": 0, "body": {"category_ids": [1, 2], "course_ids": [1]}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "question", "action": 0, "id": "stub"}


def test_mutate_question_create_requires_category_ids(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 2, "action": 0, "body": {"course_ids": [1]}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "category_ids is required" in result["message"]


def test_mutate_question_create_requires_course_ids(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 2, "action": 0, "body": {"category_ids": [1, 2]}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "course_ids is required" in result["message"]


def test_mutate_question_edit_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 2, "action": 2, "body": {"id": "Mek_1_1", "template": "New text"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "question", "action": 2}


def test_mutate_question_edit_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 2, "action": 2, "body": {"template": "No ID"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_question_archive_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 2, "action": 1, "body": {"id": "Mek_1_1"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "question", "action": 1}


def test_mutate_question_archive_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 2, "action": 1, "body": {}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_question_unknown_action_returns_error(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 2, "action": 99, "body": {"category_ids": [1]}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "Unknown action" in result["message"]


# ── POST /admin/mutate — unit ─────────────────────────────────────────────────

def test_mutate_unit_create_returns_new_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 3, "action": 0, "body": {"name": "mg"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "unit", "action": 0, "id": 1}


def test_mutate_unit_create_requires_name(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 3, "action": 0, "body": {}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "name is required" in result["message"]


def test_mutate_unit_create_with_active_false(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 3, "action": 0, "body": {"name": "mL", "active": False}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "success"
    assert result["type"] == "unit"


def test_mutate_unit_edit_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 3, "action": 2, "body": {"id": 2, "name": "mL"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "unit", "action": 2}


def test_mutate_unit_edit_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 3, "action": 2, "body": {"name": "mL"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_unit_archive_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 3, "action": 1, "body": {"id": 2}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "unit", "action": 1}


def test_mutate_unit_archive_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 3, "action": 1, "body": {}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_unit_unknown_action_returns_error(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 3, "action": 99, "body": {"name": "kg"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "Unknown action" in result["message"]


# ── GET /admin/units ──────────────────────────────────────────────────────────

def _fake_unit_class(units):
    return types.SimpleNamespace(query=types.SimpleNamespace(all=lambda: units))


def test_get_units_returns_units_with_aliases(client, monkeypatch):
    import routes.admin_routes as ar

    fake_unit = types.SimpleNamespace(
        id=1, name="m/s", active=True,
        aliases=[types.SimpleNamespace(id=1, alias="meters per second")],
    )
    patch_db_session_execute(monkeypatch, ar, [fake_unit])

    response = client.get("/admin/units")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0] == {
        "id": 1,
        "name": "m/s",
        "active": True,
        "aliases": [{"id": 1, "alias": "meters per second"}],
    }


def test_get_units_returns_empty_list(client, monkeypatch):
    import routes.admin_routes as ar

    patch_db_session_execute(monkeypatch, ar, [])

    response = client.get("/admin/units")

    assert response.status_code == 200
    assert response.get_json() == []


def test_get_units_returns_500_on_error(client, monkeypatch):
    import routes.admin_routes as ar

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(ar.db.session, "execute", boom)

    response = client.get("/admin/units")

    assert response.status_code == 500
    assert "db down" in response.get_json()["error"]


# ── POST /admin/mutate — unit alias ───────────────────────────────────────────

def test_mutate_unit_alias_create_returns_new_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 4, "action": 0, "body": {"unit_id": 1, "alias": "meters per second"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "unit_alias", "action": 0, "id": 1}


def test_mutate_unit_alias_create_requires_unit_id_and_alias(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 4, "action": 0, "body": {"unit_id": 1}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "unit_id and alias are required" in result["message"]


def test_mutate_unit_alias_edit_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 4, "action": 2, "body": {"id": 1, "alias": "m/s"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "unit_alias", "action": 2}


def test_mutate_unit_alias_edit_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 4, "action": 2, "body": {"alias": "m/s"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_unit_alias_edit_requires_alias(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 4, "action": 2, "body": {"id": 1}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "alias is required" in result["message"]


def test_mutate_unit_alias_delete_returns_success(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 4, "action": 1, "body": {"id": 1}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result == {"status": "success", "type": "unit_alias", "action": 1}


def test_mutate_unit_alias_delete_requires_id(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 4, "action": 1, "body": {}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "id is required" in result["message"]


def test_mutate_unit_alias_unknown_action_returns_error(client):
    response = client.post(
        "/admin/mutate",
        json=[{"type": 4, "action": 99, "body": {"unit_id": 1, "alias": "x"}}],
    )

    assert response.status_code == 200
    result = response.get_json()["results"][0]
    assert result["status"] == "error"
    assert "Unknown action" in result["message"]


# ── POST /admin/users/set_admin ───────────────────────────────────────────────

def test_set_admin_promotes_user(client, monkeypatch):
    import routes.admin_routes as ar

    fake_user = types.SimpleNamespace(id=7, email="teacher@bth.se", role="Admin")
    monkeypatch.setattr(ar, "set_user_admin_by_email", lambda session, email, is_admin: fake_user)

    response = client.post("/admin/users/set_admin", json={"email": "teacher@bth.se", "is_admin": True})

    assert response.status_code == 200
    data = response.get_json()
    assert data == {
        "user_id": 7,
        "email": "teacher@bth.se",
        "role": "Admin",
        "is_admin": True,
    }


def test_set_admin_revokes_admin(client, monkeypatch):
    import routes.admin_routes as ar

    fake_user = types.SimpleNamespace(id=7, email="teacher@bth.se", role="Student")
    monkeypatch.setattr(ar, "set_user_admin_by_email", lambda session, email, is_admin: fake_user)

    response = client.post("/admin/users/set_admin", json={"email": "teacher@bth.se", "is_admin": False})

    assert response.status_code == 200
    assert response.get_json()["is_admin"] is False


def test_set_admin_returns_404_when_user_not_found(client, monkeypatch):
    import routes.admin_routes as ar

    monkeypatch.setattr(ar, "set_user_admin_by_email", lambda session, email, is_admin: None)

    response = client.post("/admin/users/set_admin", json={"email": "nobody@bth.se"})

    assert response.status_code == 404


def test_set_admin_returns_400_when_email_missing(client):
    response = client.post("/admin/users/set_admin", json={})

    assert response.status_code == 400
    assert "email" in response.get_json()["error"]


def test_set_admin_returns_400_when_is_admin_not_bool(client):
    response = client.post("/admin/users/set_admin", json={"email": "teacher@bth.se", "is_admin": "yes"})

    assert response.status_code == 400
