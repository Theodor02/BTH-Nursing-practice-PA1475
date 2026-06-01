import time


def test_ping_returns_pong(client):
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.get_json() == {"pong": True}


def _login(client):
    """Login by sending a mock bearer token in the Authorization header."""
    return client.post(
        "/api/auth/login",
        headers={"Authorization": "Bearer mock-token-for-testing"},
    )


def test_login_sets_server_session_and_returns_user_data(client):
    response = _login(client)

    assert response.status_code == 200
    assert response.get_json() == {
        "user_id": 1,
        "created": True,
        "email": "student@example.com",
        "sso_id": "oid-123",
        "role": "Student",
    }

    protected_response = client.get("/api/sessions")
    assert protected_response.status_code == 200
    assert protected_response.get_json()["user_id"] == 1


def test_login_same_user_does_not_affect_pending_attempts(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={"q1": {"id": "q1"}},
    )

    relogin_response = _login(client)
    assert relogin_response.status_code == 200

    assert qr._pending.get(attempt_id) is not None


def test_login_rejects_missing_authorization_header(client):
    """Test that login rejects requests without Authorization header."""
    response = client.post("/api/auth/login")

    assert response.status_code == 401
    assert "Missing Authorization header" in response.get_json()["error"]


def test_logout_clears_session(client):
    _login(client)

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert client.get("/api/sessions").status_code == 401


def test_csrf_origin_blocks_disallowed_post(client):
    response = client.post(
        "/api/auth/logout",
        json={},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert "CSRF check failed" in response.get_json()["error"]


def test_not_found_and_method_not_allowed_return_json(client):
    assert client.get("/this-does-not-exist").status_code == 404
    assert client.get("/this-does-not-exist").get_json() == {"error": "Not found"}

    response = client.get("/login")
    assert response.status_code == 200
    assert response.get_json() == {"message": "Login endpoint"}

    response = client.delete("/api/auth/logout")
    assert response.status_code == 405
    assert response.get_json() == {"error": "Method not allowed"}



def test_internal_error_handler_returns_json(app_module):
    with app_module.app.app_context():
        response, status = app_module._internal_error(Exception("boom"))

    assert status == 500
    assert response.get_json() == {"error": "Internal server error"}


def test_session_routes_require_authentication(client):
    response = client.get("/api/sessions")

    assert response.status_code == 401
    assert response.get_json() == {"error": "Authentication required"}

    response = client.get("/api/sessions/1")
    assert response.status_code == 401
    assert response.get_json() == {"error": "Authentication required"}


def test_question_and_cat_routes_require_authentication(client):
    assert client.get("/api/categories").status_code == 401
    assert client.post("/api/questions", json={}).status_code == 401
    assert client.post("/api/attempts/submit", json={"attempt_id": "abc", "answers": {}}).status_code == 401


def test_question_post_rejects_invalid_payload(client):
    _login(client)
    response = client.post("/api/questions", json={})

    assert response.status_code == 400
    assert "Invalid payload" in response.get_json()["error"]


def test_question_post_rejects_too_many_courses(client):
    _login(client)
    payload = {
        "questions_request": {
            "course": {
                f"COURSE-{index}": {"Category": 1}
                for index in range(1, 12)
            }
        }
    }

    response = client.post("/api/questions", json=payload)
    assert response.status_code == 400
    assert "Too many courses" in response.get_json()["error"]


def test_question_post_rejects_invalid_course_code_length(client):
    _login(client)
    payload = {
        "questions_request": {
            "course": {
                "X" * 51: {"Category": 1}
            }
        }
    }

    response = client.post("/api/questions", json=payload)
    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid course code"}


def test_question_post_rejects_too_many_categories_for_course(client, monkeypatch):
    import routes.question_routes as qr

    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    f"Category-{index}": 1
                    for index in range(1, 22)
                }
            }
        }
    }

    response = client.post("/api/questions", json=payload)
    assert response.status_code == 400
    assert "Too many categories" in response.get_json()["error"]


def test_question_post_rejects_invalid_category_name_length(client, monkeypatch):
    import routes.question_routes as qr

    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "C" * 151: 1,
                }
            }
        }
    }

    response = client.post("/api/questions", json=payload)
    assert response.status_code == 400
    assert "Invalid category name" in response.get_json()["error"]


def test_question_post_rejects_invalid_requested_count(client, monkeypatch):
    import routes.question_routes as qr

    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "Derivatives": -1,
                }
            }
        }
    }

    response = client.post("/api/questions", json=payload)
    assert response.status_code == 400
    assert "Invalid requested count" in response.get_json()["error"]


def test_question_post_rejects_requested_count_above_per_category_limit(client, monkeypatch):
    import routes.question_routes as qr

    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "Derivatives": 51,
                }
            }
        }
    }

    response = client.post("/api/questions", json=payload)
    assert response.status_code == 400
    assert "Requested count too high" in response.get_json()["error"]


def test_question_post_rejects_total_questions_above_limit(client, monkeypatch):
    import routes.question_routes as qr

    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_category_by_name_and_course_id",
        lambda _session, category_name, _course_id: {
            "id": {"A": 1, "B": 2, "C": 3}[category_name],
            "name": category_name,
        },
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_question_templates_by_course_and_category",
        lambda session, course_id, category_id, limit: [
            {"id": f"qt-{course_id}-{category_id}-{index}"}
            for index in range(limit)
        ],
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "A": 50,
                    "B": 50,
                    "C": 1,
                }
            }
        }
    }

    response = client.post("/api/questions", json=payload)
    assert response.status_code == 400
    assert "Total questions requested exceeds limit" in response.get_json()["error"]


def test_question_post_rejects_unknown_category_for_course(client, monkeypatch):
    import routes.question_routes as qr

    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_category_by_name_and_course_id",
        lambda _session, _category_name, _course_id: None,
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "Derivatives": 1,
                }
            }
        }
    }

    response = client.post("/api/questions", json=payload)
    assert response.status_code == 400
    assert "Unknown category for course" in response.get_json()["error"]


def test_question_post_returns_questions_for_valid_request(client, monkeypatch):
    import routes.question_routes as qr
    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_category_by_name_and_course_id",
        lambda _session, category_name, _course_id: {"id": 42, "name": category_name},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_template_count_by_course_and_category",
        lambda _session, _course_id, _category_id: 3,
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_question_templates_by_course_and_category",
        lambda session, course_id, category_id, limit: [
            {"id": "qt-1", "course_id": course_id, "category_id": category_id},
            {"id": "qt-2", "course_id": course_id, "category_id": category_id},
        ][:limit],
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "Derivatives": 2,
                }
            }
        }
    }
    response = client.post("/api/questions", json=payload)

    assert response.status_code == 200
    response_json = response.get_json()
    assert isinstance(response_json.get("attempt_id"), str)
    assert response_json["questions"] == {
        "TMA4100": {
            "Derivatives": [
                {"id": "qt-1", "course_id": 7, "category_id": 42},
                {"id": "qt-2", "course_id": 7, "category_id": 42},
            ]
        }
    }


def test_question_post_returns_attempt_id_for_multiple_courses_and_categories(
    client, monkeypatch
):
    import routes.question_routes as qr
    _login(client)
    course_lookup = {
        "TMA4100": {"id": 101, "course_code": "TMA4100"},
        "TMA4200": {"id": 202, "course_code": "TMA4200"},
    }
    category_lookup = {
        (101, "Derivatives"): {"id": 11, "name": "Derivatives"},
        (101, "Integrals"): {"id": 12, "name": "Integrals"},
        (202, "Probability"): {"id": 21, "name": "Probability"},
    }
    available_counts = {
        (101, 11): 3,
        (101, 12): 2,
        (202, 21): 4,
    }

    def fake_course_by_code(_session, course_code):
        return course_lookup.get(course_code)

    def fake_category_by_name(_session, category_name, course_id):
        return category_lookup.get((course_id, category_name))

    def fake_available_count(_session, course_id, category_id):
        return available_counts[(course_id, category_id)]

    def fake_templates(session, course_id, category_id, limit):
        return [
            {
                "id": f"qt-{course_id}-{category_id}-{index}",
                "course_id": course_id,
                "category_id": category_id,
            }
            for index in range(1, limit + 1)
        ]

    monkeypatch.setattr(qr, "retrieve_course_by_code", fake_course_by_code)
    monkeypatch.setattr(qr, "retrieve_category_by_name_and_course_id", fake_category_by_name)
    monkeypatch.setattr(
        qr,
        "retrieve_active_template_count_by_course_and_category",
        fake_available_count,
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_question_templates_by_course_and_category",
        fake_templates,
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "Derivatives": 2,
                    "Integrals": 1,
                },
                "TMA4200": {
                    "Probability": 3,
                },
            }
        }
    }

    response = client.post("/api/questions", json=payload)

    assert response.status_code == 200
    response_json = response.get_json()
    assert isinstance(response_json.get("attempt_id"), str)
    assert response_json["questions"] == {
        "TMA4100": {
            "Derivatives": [
                {"id": "qt-101-11-1", "course_id": 101, "category_id": 11},
                {"id": "qt-101-11-2", "course_id": 101, "category_id": 11},
            ],
            "Integrals": [
                {"id": "qt-101-12-1", "course_id": 101, "category_id": 12},
            ],
        },
        "TMA4200": {
            "Probability": [
                {"id": "qt-202-21-1", "course_id": 202, "category_id": 21},
                {"id": "qt-202-21-2", "course_id": 202, "category_id": 21},
                {"id": "qt-202-21-3", "course_id": 202, "category_id": 21},
            ]
        },
    }


def test_question_post_rejects_zero_total_questions(client, monkeypatch):
    import routes.question_routes as qr
    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_category_by_name_and_course_id",
        lambda _session, category_name, _course_id: {"id": 42, "name": category_name},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_template_count_by_course_and_category",
        lambda _session, _course_id, _category_id: 5,
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_question_templates_by_course_and_category",
        lambda session, course_id, category_id, limit: [],
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "Derivatives": 0,
                }
            }
        }
    }

    response = client.post("/api/questions", json=payload)

    assert response.status_code == 400
    assert "At least one question must be requested" in response.get_json()["error"]


def test_question_post_rejects_unknown_course_code(client, monkeypatch):
    import routes.question_routes as qr
    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, _course_code: None,
    )

    payload = {
        "questions_request": {
            "course": {
                "UNKNOWN": {"Derivatives": 1}
            }
        }
    }
    response = client.post("/api/questions", json=payload)

    assert response.status_code == 400
    assert "Unknown course code" in response.get_json()["error"]


def test_question_post_rejects_invalid_category_map(client, monkeypatch):
    import routes.question_routes as qr
    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": ["not-a-dict"]
            }
        }
    }
    response = client.post("/api/questions", json=payload)

    assert response.status_code == 400
    assert "Invalid category map" in response.get_json()["error"]


def test_question_post_rejects_request_over_available_count(client, monkeypatch):
    import routes.question_routes as qr
    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_category_by_name_and_course_id",
        lambda _session, category_name, _course_id: {"id": 42, "name": category_name},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_template_count_by_course_and_category",
        lambda _session, _course_id, _category_id: 1,
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_question_templates_by_course_and_category",
        lambda session, course_id, category_id, limit: [],
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "Derivatives": 2,
                }
            }
        }
    }
    response = client.post("/api/questions", json=payload)

    assert response.status_code == 400
    assert "only 1 available" in response.get_json()["error"]


def test_question_post_rejects_invalid_template_configuration(client, monkeypatch):
    import routes.question_routes as qr
    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, course_code: {"id": 7, "course_code": course_code},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_category_by_name_and_course_id",
        lambda _session, category_name, _course_id: {"id": 42, "name": category_name},
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_template_count_by_course_and_category",
        lambda _session, _course_id, _category_id: 1,
    )
    monkeypatch.setattr(
        qr,
        "retrieve_active_question_templates_by_course_and_category",
        lambda session, course_id, category_id, limit: [
            {
                "id": "qt-invalid",
                "template": "Dose for {weight}",
                "variables": {"weight": {"min": 60, "max": 60, "decimals": 0}},
                "formula": "weight / (weight - 60)",
                "course_id": course_id,
                "category_id": category_id,
            }
        ][:limit],
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "Derivatives": 1,
                }
            }
        }
    }
    response = client.post("/api/questions", json=payload)

    assert response.status_code == 400
    assert "Invalid question template configuration" in response.get_json()["error"]


def test_question_post_returns_json_for_unexpected_server_error(client, monkeypatch):
    import routes.question_routes as qr

    _login(client)
    monkeypatch.setattr(
        qr,
        "retrieve_course_by_code",
        lambda _session, _course_code: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    payload = {
        "questions_request": {
            "course": {
                "TMA4100": {
                    "Derivatives": 1,
                }
            }
        }
    }

    response = client.post("/api/questions", json=payload)

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}


def test_cat_request_returns_course_category_map(client, monkeypatch):
    import routes.cat_routes as cr
    _login(client)
    monkeypatch.setattr(
        cr._cache,
        "get",
        lambda _session: (
            {"TMA4100": ["Derivatives", "Integrals"]},
            {"TMA4100": {"Derivatives": 4, "Integrals": 2}},
        ),
    )

    response = client.get("/api/categories")

    assert response.status_code == 200
    assert response.get_json() == {
        "courses": {
            "TMA4100": ["Derivatives", "Integrals"],
        },
        "max_questions": {
            "TMA4100": {
                "Derivatives": 4,
                "Integrals": 2,
            }
        },
    }


def test_question_submit_requires_attempt_id(client):
    _login(client)
    response = client.post("/api/attempts/submit", json={"answers": {}})

    assert response.status_code == 400
    assert "attempt_id" in response.get_json()["error"]


def test_question_submit_requires_answers_object(client):
    _login(client)
    response = client.post(
        "/api/attempts/submit",
        json={"attempt_id": "attempt-1", "answers": []},
    )

    assert response.status_code == 400
    assert "requires answers to be an object" in response.get_json()["error"]


def test_question_submit_returns_404_for_missing_attempt(client):
    _login(client)
    response = client.post(
        "/api/attempts/submit",
        json={"attempt_id": "missing", "answers": {}},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Attempt not found or expired"}


def test_question_submit_rejects_attempt_owned_by_other_user(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=2,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={"q1": {"id": "q1", "is_scored": False}},
    )

    response = client.post(
        "/api/attempts/submit",
        json={"attempt_id": attempt_id, "answers": {}},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "Attempt does not belong to authenticated user"}


def test_question_submit_rejects_attempt_without_questions(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={},
    )

    response = client.post(
        "/api/attempts/submit",
        json={"attempt_id": attempt_id, "answers": {}},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Stored attempt has no questions"}


def test_question_submit_rejects_attempt_missing_metadata(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={"q1": {"id": "q1", "is_scored": False}},
    )
    qr._pending._mem[attempt_id]["course_id"] = None

    response = client.post(
        "/api/attempts/submit",
        json={"attempt_id": attempt_id, "answers": {}},
    )

    assert response.status_code == 400
    assert "missing course/category metadata" in response.get_json()["error"]


def test_question_submit_returns_500_when_persist_fails(client, monkeypatch):
    import routes.question_routes as qr

    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={
            "q1": {
                "id": "q1",
                "correct_answer": 10,
                "tolerance": 0,
                "is_scored": True,
            }
        },
    )

    monkeypatch.setattr(
        qr,
        "create_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("db fail")),
    )

    response = client.post(
        "/api/attempts/submit",
        json={"attempt_id": attempt_id, "answers": {"q1": 10}},
    )

    assert response.status_code == 500
    assert response.get_json() == {"error": "Unable to persist session result"}


def test_question_submit_grades_and_persists_session(client, app_module):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={
            "q1": {
                "id": "q1",
                "correct_answer": 10,
                "tolerance": 0.5,
                "is_scored": True,
            },
            "q2": {
                "id": "q2",
                "correct_answer": 3.5,
                "tolerance": 0.0,
                "is_scored": True,
            },
        },
    )

    response = client.post(
        "/api/attempts/submit",
        json={
            "attempt_id": attempt_id,
            "answers": {
                "q1": 10.3,
                "q2": 4,
            },
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "session_id": 1,
        "score": 50.0,
        "correct_count": 1,
        "scored_count": 2,
        "answered_count": 2,
    }

    assert len(app_module.fake_db.session.created_sessions) == 1
    created = app_module.fake_db.session.created_sessions[0]
    assert created["user_id"] == 1
    assert created["course_id"] == 7
    assert created["category_id"] == 42
    assert created["score"] == 50.0
    assert created["questions"]["questions"]["q1"]["is_correct"] is True
    assert created["questions"]["questions"]["q2"]["is_correct"] is False

    assert qr._pending.get(attempt_id) is None


def test_grade_question_returns_404_for_expired_attempt(client):
    import routes.question_routes as qr

    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=1,
        category_id=1,
        category_ids=[1],
        question_snapshots={
            "q1": {"id": "q1", "correct_answer": 5, "tolerance": 0}
        },
    )
    qr._pending._mem[attempt_id]["created_at"] = time.time() - 7200

    response = client.post(
        "/api/questions/grade",
        json={"attempt_id": attempt_id, "question_id": "q1", "user_answer": "5"},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Attempt not found or expired"}


def test_grade_question_uses_snapshot_unit_when_correct_answer_is_numeric(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=7,
        category_id=42,
        category_ids=[42],
        question_snapshots={
            "q1": {
                "id": "q1",
                "correct_answer": 937.5,
                "unit": "mg",
                "tolerance": 0.0,
                "is_scored": True,
            }
        },
    )

    response = client.post(
        "/api/questions/grade",
        json={
            "attempt_id": attempt_id,
            "question_id": "q1",
            "user_answer": "937.5 mg",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["hasUnit"] is True
    assert response.get_json()["correctUnit"] is True
    assert response.get_json()["correctValue"] is True
    assert response.get_json()["correct"] is True


def test_session_request_returns_authenticated_user_sessions(client, monkeypatch):
    import routes.session_routes as sr
    _login(client)
    monkeypatch.setattr(
        sr,
        "retrieve_sessions_by_user_id",
        lambda _session, user_id: [{"id": 5, "user_id": user_id, "score": "87.50"}],
    )

    response = client.get("/api/sessions")

    assert response.status_code == 200
    assert response.get_json() == {
        "user_id": 1,
        "sessions": [{"id": 5, "user_id": 1, "score": "87.50"}],
    }


def test_session_post_returns_only_user_owned_session(client, monkeypatch):
    import routes.session_routes as sr
    _login(client)
    monkeypatch.setattr(
        sr,
        "retrieve_session_by_user_id_and_session_id",
        lambda _session, user_id, session_id: {"id": session_id, "user_id": user_id},
    )

    response = client.get("/api/sessions/12")

    assert response.status_code == 200
    assert response.get_json() == {
        "user_id": 1,
        "session": {"id": 12, "user_id": 1},
    }


def test_session_post_rejects_invalid_or_missing_session_id(client):
    _login(client)

    response = client.get("/api/sessions/0")
    assert response.status_code == 400
    assert "session_id must be a positive integer" in response.get_json()["error"]


def test_session_post_returns_404_for_non_owned_session(client, monkeypatch):
    import routes.session_routes as sr
    _login(client)
    monkeypatch.setattr(
        sr,
        "retrieve_session_by_user_id_and_session_id",
        lambda _session, _user_id, _session_id: None,
    )

    response = client.get("/api/sessions/99")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Session not found for authenticated user"}


# ── grade_question endpoint ────────────────────────────────────────────────────

def test_grade_question_requires_attempt_id(client):
    _login(client)
    response = client.post(
        "/api/questions/grade",
        json={"question_id": "q1", "user_answer": "5"},
    )

    assert response.status_code == 400
    assert "attempt_id" in response.get_json()["error"]


def test_grade_question_requires_question_id(client):
    _login(client)
    response = client.post(
        "/api/questions/grade",
        json={"attempt_id": "some-attempt", "user_answer": "5"},
    )

    assert response.status_code == 400
    assert "question_id" in response.get_json()["error"]


def test_grade_question_requires_auth(client):
    response = client.post(
        "/api/questions/grade",
        json={"attempt_id": "a", "question_id": "q1", "user_answer": "5"},
    )

    assert response.status_code == 401


def test_grade_question_returns_404_for_missing_attempt(client):
    _login(client)
    response = client.post(
        "/api/questions/grade",
        json={"attempt_id": "nonexistent", "question_id": "q1", "user_answer": "5"},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Attempt not found or expired"}


def test_grade_question_returns_403_for_attempt_owned_by_other_user(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=99,
        course_id=1,
        category_id=1,
        category_ids=[1],
        question_snapshots={
            "q1": {"id": "q1", "correct_answer": 5, "tolerance": 0}
        },
    )

    response = client.post(
        "/api/questions/grade",
        json={"attempt_id": attempt_id, "question_id": "q1", "user_answer": "5"},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "Attempt does not belong to authenticated user"}


def test_grade_question_returns_404_for_unknown_question_id(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=1,
        category_id=1,
        category_ids=[1],
        question_snapshots={
            "q1": {"id": "q1", "correct_answer": 5, "tolerance": 0}
        },
    )

    response = client.post(
        "/api/questions/grade",
        json={
            "attempt_id": attempt_id,
            "question_id": "missing-q",
            "user_answer": "5",
        },
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Question not found in attempt"}


def test_grade_question_returns_correct_for_matching_answer(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=1,
        category_id=1,
        category_ids=[1],
        question_snapshots={
            "q1": {
                "id": "q1",
                "correct_answer": 10,
                "tolerance": 0.5,
                "is_scored": True,
            }
        },
    )

    response = client.post(
        "/api/questions/grade",
        json={"attempt_id": attempt_id, "question_id": "q1", "user_answer": "10.3"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["correct"] is True
    assert body["correctValue"] is True
    assert body["correctAnswer"] == 10.0
    assert body["hasUnit"] is False
    assert body["correctUnit"] is True


def test_grade_question_returns_incorrect_for_wrong_answer(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=1,
        category_id=1,
        category_ids=[1],
        question_snapshots={
            "q1": {
                "id": "q1",
                "correct_answer": 10,
                "tolerance": 0,
                "is_scored": True,
            }
        },
    )

    response = client.post(
        "/api/questions/grade",
        json={"attempt_id": attempt_id, "question_id": "q1", "user_answer": "99"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["correct"] is False
    assert body["correctValue"] is False


def test_grade_question_validates_unit_when_expected(client):
    import routes.question_routes as qr
    _login(client)

    attempt_id = qr._pending.store(
        user_id=1,
        course_id=1,
        category_id=1,
        category_ids=[1],
        question_snapshots={
            "q1": {
                "id": "q1",
                "correct_answer": 5,
                "tolerance": 0,
                "unit": "ml",
                "is_scored": True,
            }
        },
    )

    # correct value, correct unit
    response = client.post(
        "/api/questions/grade",
        json={"attempt_id": attempt_id, "question_id": "q1", "user_answer": "5 ml"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["correct"] is True
    assert body["hasUnit"] is True
    assert body["correctUnit"] is True

    # correct value, wrong unit
    response2 = client.post(
        "/api/questions/grade",
        json={"attempt_id": attempt_id, "question_id": "q1", "user_answer": "5 mg"},
    )
    assert response2.status_code == 200
    body2 = response2.get_json()
    assert body2["correct"] is False
    assert body2["correctUnit"] is False
