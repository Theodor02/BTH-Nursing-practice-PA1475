"""
Tests for GET /admin/stats/* and GET /stats/* endpoints.

Admin endpoints use ADMIN_DEBUG_ALL=true (set by the app_module fixture),
so admin checks are bypassed and no DB is needed for auth.

User endpoints require an active session, obtained by calling POST /login
with the mocked Entra token (mock is installed by the client fixture).

Pattern for mocking sql_stats functions:
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_overview_stats", lambda s, f, t: {...})
"""

# ─── Stub payloads ────────────────────────────────────────────────────────────

_OVERVIEW_STUB = {
    "total_sessions": 10,
    "total_questions_answered": 50,
    "total_correct": 35,
    "overall_accuracy_pct": 70.0,
    "active_courses": 2,
    "active_categories": 4,
}

_COURSE_STUB = [
    {
        "course_id": 1,
        "course_code": "OM125G",
        "course_name": "Omvårdnad",
        "session_count": 5,
        "questions_answered": 25,
        "correct_count": 18,
        "accuracy_pct": 72.0,
        "avg_score": 72.0,
    }
]

_CATEGORY_STUB = [
    {
        "category_id": 1,
        "category_name": "Dosberäkning",
        "session_count": 3,
        "questions_answered": 12,
        "correct_count": 8,
        "accuracy_pct": 66.7,
        "avg_score": 66.7,
        "linked_courses": [
            {"course_id": 1, "course_code": "OM125G", "course_name": "Omvårdnad"}
        ],
    }
]

_QUESTION_STUB = [
    {
        "template_id": "Mek_1_1",
        "template_text": "A patient needs 250 mg paracetamol...",
        "unit": "ml",
        "attempt_count": 100,
        "correct_count": 55,
        "accuracy_pct": 55.0,
        "difficulty": "medium",
        "categories": [{"category_id": 1, "name": "Dosberäkning"}],
        "courses": [{"course_id": 1, "course_code": "OM125G", "name": "Omvårdnad"}],
    }
]

_USER_OVERVIEW_STUB = {
    "total_sessions": 5,
    "total_questions": 25,
    "overall_accuracy_pct": 80.0,
    "current_streak": 3,
    "longest_streak": 7,
    "best_category": {"category_id": 1, "name": "Algebra", "accuracy_pct": 95.0},
    "worst_category": {"category_id": 2, "name": "Calculus", "accuracy_pct": 55.0},
    "estimated_practice_minutes": 30,
}

_MASTERY_STUB = [
    {
        "course_id": 1,
        "course_code": "OM125G",
        "course_name": "Omvårdnad",
        "session_count": 5,
        "mastery_pct": 74.0,
        "categories": [
            {
                "category_id": 1,
                "category_name": "Dosberäkning",
                "session_count": 5,
                "mastery_pct": 74.0,
                "last_practiced": "2024-04-25T10:30:00",
            }
        ],
    }
]


def _login(client):
    """Establish an authenticated session in the test client."""
    resp = client.post("/api/auth/login", headers={"Authorization": "Bearer faketoken"})
    assert resp.status_code == 200, f"Login failed: {resp.get_json()}"


# ═══════════════════════════════════════════════════════════════
# GET /admin/stats/overview
# ═══════════════════════════════════════════════════════════════

def test_admin_overview_returns_200_with_all_keys(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_overview_stats", lambda s, f, t: _OVERVIEW_STUB)

    resp = client.get("/api/admin/stats/overview")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_sessions"] == 10
    assert data["overall_accuracy_pct"] == 70.0
    assert data["active_courses"] == 2
    assert "period" in data
    assert "from" in data["period"]
    assert "to" in data["period"]


def test_admin_overview_default_dates_are_forwarded(client, monkeypatch):
    import routes.stats_routes as sr
    captured = {}

    def capture(s, f, t):
        captured["from_dt"] = f
        captured["to_dt"] = t
        return _OVERVIEW_STUB

    monkeypatch.setattr(sr, "get_admin_overview_stats", capture)
    client.get("/api/admin/stats/overview")

    assert "from_dt" in captured
    assert "to_dt" in captured


def test_admin_overview_explicit_date_range_forwarded(client, monkeypatch):
    import routes.stats_routes as sr
    captured = {}

    def capture(s, f, t):
        captured["from_dt"] = f
        captured["to_dt"] = t
        return _OVERVIEW_STUB

    monkeypatch.setattr(sr, "get_admin_overview_stats", capture)
    client.get("/api/admin/stats/overview?from_date=2024-01-01&to_date=2024-03-31")

    assert captured["from_dt"].year == 2024 and captured["from_dt"].month == 1
    assert captured["to_dt"].year == 2024 and captured["to_dt"].month == 3
    assert captured["to_dt"].hour == 23


def test_admin_overview_bad_from_date_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_overview_stats", lambda s, f, t: _OVERVIEW_STUB)

    resp = client.get("/api/admin/stats/overview?from_date=not-a-date")

    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_admin_overview_bad_to_date_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_overview_stats", lambda s, f, t: _OVERVIEW_STUB)

    resp = client.get("/api/admin/stats/overview?to_date=2024-99-01")

    assert resp.status_code == 400


def test_admin_overview_requires_auth_when_debug_off(app_module, monkeypatch):
    monkeypatch.setenv("ADMIN_DEBUG_ALL", "false")
    with app_module.app.test_client() as c:
        resp = c.get("/api/admin/stats/overview")
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
# GET /admin/stats/courses
# ═══════════════════════════════════════════════════════════════

def test_admin_courses_returns_200_with_courses_key(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_course_stats", lambda s, f, t: _COURSE_STUB)

    resp = client.get("/api/admin/stats/courses")

    assert resp.status_code == 200
    data = resp.get_json()
    assert "courses" in data
    assert data["courses"][0]["course_code"] == "OM125G"
    assert data["courses"][0]["accuracy_pct"] == 72.0


def test_admin_courses_empty_list_returned(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_course_stats", lambda s, f, t: [])

    resp = client.get("/api/admin/stats/courses")

    assert resp.status_code == 200
    assert resp.get_json()["courses"] == []


def test_admin_courses_bad_date_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_course_stats", lambda s, f, t: [])

    resp = client.get("/api/admin/stats/courses?to_date=2024-99-99")

    assert resp.status_code == 400


def test_admin_courses_period_in_response(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_course_stats", lambda s, f, t: [])

    resp = client.get("/api/admin/stats/courses?from_date=2024-01-01&to_date=2024-06-30")

    data = resp.get_json()
    assert data["period"]["from"] == "2024-01-01"
    assert data["period"]["to"] == "2024-06-30"


# ═══════════════════════════════════════════════════════════════
# GET /admin/stats/categories
# ═══════════════════════════════════════════════════════════════

def test_admin_categories_returns_200_with_linked_courses(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_category_stats", lambda s, f, t, **kw: _CATEGORY_STUB)

    resp = client.get("/api/admin/stats/categories")

    assert resp.status_code == 200
    data = resp.get_json()
    assert "categories" in data
    cat = data["categories"][0]
    assert cat["category_name"] == "Dosberäkning"
    assert cat["linked_courses"][0]["course_code"] == "OM125G"


def test_admin_categories_course_id_forwarded(client, monkeypatch):
    import routes.stats_routes as sr
    captured = {}

    def capture(s, f, t, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_admin_category_stats", capture)
    client.get("/api/admin/stats/categories?course_id=3")

    assert captured.get("course_id") == 3


def test_admin_categories_no_course_id_sends_none(client, monkeypatch):
    import routes.stats_routes as sr
    captured = {}

    def capture(s, f, t, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_admin_category_stats", capture)
    client.get("/api/admin/stats/categories")

    assert captured.get("course_id") is None


def test_admin_categories_invalid_course_id_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_category_stats", lambda s, f, t, **kw: [])

    resp = client.get("/api/admin/stats/categories?course_id=abc")

    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_admin_categories_negative_course_id_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_category_stats", lambda s, f, t, **kw: [])

    resp = client.get("/api/admin/stats/categories?course_id=-1")

    assert resp.status_code == 400


def test_admin_categories_bad_date_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_category_stats", lambda s, f, t, **kw: [])

    resp = client.get("/api/admin/stats/categories?from_date=bad")

    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════
# GET /admin/stats/questions
# ═══════════════════════════════════════════════════════════════

def test_admin_questions_returns_200_with_difficulty_field(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_question_stats", lambda s, f, t, **kw: _QUESTION_STUB)

    resp = client.get("/api/admin/stats/questions")

    assert resp.status_code == 200
    data = resp.get_json()
    assert "questions" in data
    q = data["questions"][0]
    assert q["difficulty"] == "medium"
    assert q["template_id"] == "Mek_1_1"
    assert "categories" in q
    assert "courses" in q


def test_admin_questions_sort_by_attempts_forwarded(client, monkeypatch):
    import routes.stats_routes as sr
    captured = {}

    def capture(s, f, t, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_admin_question_stats", capture)
    client.get("/api/admin/stats/questions?sort_by=attempts")

    assert captured.get("sort_by") == "attempts"


def test_admin_questions_default_sort_is_accuracy(client, monkeypatch):
    import routes.stats_routes as sr
    captured = {}

    def capture(s, f, t, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_admin_question_stats", capture)
    client.get("/api/admin/stats/questions")

    assert captured.get("sort_by") == "accuracy"


def test_admin_questions_invalid_sort_by_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_question_stats", lambda s, f, t, **kw: [])

    resp = client.get("/api/admin/stats/questions?sort_by=invalid")

    assert resp.status_code == 400
    assert "sort_by" in resp.get_json()["error"]


def test_admin_questions_limit_forwarded(client, monkeypatch):
    import routes.stats_routes as sr
    captured = {}

    def capture(s, f, t, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_admin_question_stats", capture)
    client.get("/api/admin/stats/questions?limit=25")

    assert captured.get("limit") == 25


def test_admin_questions_limit_too_large_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_question_stats", lambda s, f, t, **kw: [])

    resp = client.get("/api/admin/stats/questions?limit=201")

    assert resp.status_code == 400
    assert "limit" in resp.get_json()["error"]


def test_admin_questions_limit_zero_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_question_stats", lambda s, f, t, **kw: [])

    resp = client.get("/api/admin/stats/questions?limit=0")

    assert resp.status_code == 400


def test_admin_questions_course_and_category_filter_forwarded(client, monkeypatch):
    import routes.stats_routes as sr
    captured = {}

    def capture(s, f, t, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_admin_question_stats", capture)
    client.get("/api/admin/stats/questions?course_id=2&category_id=5")

    assert captured.get("course_id") == 2
    assert captured.get("category_id") == 5


def test_admin_questions_invalid_category_id_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_question_stats", lambda s, f, t, **kw: [])

    resp = client.get("/api/admin/stats/questions?category_id=abc")

    assert resp.status_code == 400


def test_admin_questions_bad_date_returns_400(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_question_stats", lambda s, f, t, **kw: [])

    resp = client.get("/api/admin/stats/questions?from_date=2024-13-01")

    assert resp.status_code == 400


def test_admin_questions_empty_result(client, monkeypatch):
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_admin_question_stats", lambda s, f, t, **kw: [])

    resp = client.get("/api/admin/stats/questions")

    assert resp.status_code == 200
    assert resp.get_json()["questions"] == []


# ═══════════════════════════════════════════════════════════════
# GET /stats/overview
# ═══════════════════════════════════════════════════════════════

def test_user_overview_returns_200_with_all_keys(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_user_overview_stats", lambda s, uid, from_dt=None, to_dt=None: _USER_OVERVIEW_STUB)

    resp = client.get("/api/stats/overview")

    assert resp.status_code == 200
    data = resp.get_json()
    assert "user_id" in data
    assert data["total_sessions"] == 5
    assert data["current_streak"] == 3
    assert data["best_category"]["name"] == "Algebra"


def test_user_overview_user_id_in_response(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_user_overview_stats", lambda s, uid, from_dt=None, to_dt=None: _USER_OVERVIEW_STUB)

    resp = client.get("/api/stats/overview")

    data = resp.get_json()
    assert isinstance(data["user_id"], int)


def test_user_overview_returns_401_when_not_logged_in(app_module):
    with app_module.app.test_client() as c:
        resp = c.get("/api/stats/overview")
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
# GET /stats/mastery
# ═══════════════════════════════════════════════════════════════

def test_user_mastery_returns_200_with_courses_key(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_user_mastery_stats", lambda s, uid, from_dt=None, to_dt=None: _MASTERY_STUB)

    resp = client.get("/api/stats/mastery")

    assert resp.status_code == 200
    data = resp.get_json()
    assert "courses" in data
    assert data["courses"][0]["course_code"] == "OM125G"
    assert len(data["courses"][0]["categories"]) == 1


def test_user_mastery_empty_courses(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    monkeypatch.setattr(sr, "get_user_mastery_stats", lambda s, uid, from_dt=None, to_dt=None: [])

    resp = client.get("/api/stats/mastery")

    assert resp.status_code == 200
    assert resp.get_json()["courses"] == []


def test_user_mastery_returns_401_when_not_logged_in(app_module):
    with app_module.app.test_client() as c:
        resp = c.get("/api/stats/mastery")
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
# GET /stats/activity
# ═══════════════════════════════════════════════════════════════

def test_user_activity_returns_200_with_days_key(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    fake_days = [{"date": f"2024-01-{i+1:02d}", "session_count": 0} for i in range(98)]
    monkeypatch.setattr(sr, "get_user_activity_stats", lambda s, uid, **kw: fake_days)

    resp = client.get("/api/stats/activity")

    assert resp.status_code == 200
    data = resp.get_json()
    assert "days" in data
    assert data["weeks"] == 14


def test_user_activity_default_weeks_is_14(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    captured = {}

    def capture(s, uid, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_user_activity_stats", capture)
    client.get("/api/stats/activity")

    assert captured.get("weeks") == 14


def test_user_activity_custom_weeks_forwarded(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    captured = {}

    def capture(s, uid, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_user_activity_stats", capture)
    client.get("/api/stats/activity?weeks=4")

    assert captured.get("weeks") == 4


def test_user_activity_weeks_zero_clamped_to_1(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    captured = {}

    def capture(s, uid, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_user_activity_stats", capture)
    resp = client.get("/api/stats/activity?weeks=0")

    assert resp.status_code == 200
    assert captured.get("weeks") == 1


def test_user_activity_weeks_over_52_clamped(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    captured = {}

    def capture(s, uid, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_user_activity_stats", capture)
    resp = client.get("/api/stats/activity?weeks=100")

    assert resp.status_code == 200
    assert captured.get("weeks") == 52


def test_user_activity_invalid_weeks_defaults_to_14(client, monkeypatch):
    _login(client)
    import routes.stats_routes as sr
    captured = {}

    def capture(s, uid, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr(sr, "get_user_activity_stats", capture)
    client.get("/api/stats/activity?weeks=notanumber")

    assert captured.get("weeks") == 14


def test_user_activity_returns_401_when_not_logged_in(app_module):
    with app_module.app.test_client() as c:
        resp = c.get("/api/stats/activity")
    assert resp.status_code == 401
