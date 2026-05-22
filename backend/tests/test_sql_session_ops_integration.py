import os
import uuid

import pytest
from flask import Flask

from logic.database.init.class_db import Category, Course, CourseCategory
from logic.database.init.init_db import db
from logic.database.operations.sql_getters import (
    retrieve_session_by_user_id_and_session_id,
    retrieve_sessions_by_user_id,
)
from logic.database.operations.sql_setters import (
    append_session_question_result,
    create_or_get_user_by_sso,
    create_session,
    delete_session,
    update_session_score,
)


@pytest.fixture
def app_with_real_db_sql_ops():
    app = Flask(__name__)
    app.config["TESTING"] = True

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "qtrain")
    password = os.getenv("POSTGRES_PASSWORD", "qtrain")
    dbname = os.getenv("POSTGRES_DB", "qtrain")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        yield app


def _get_valid_course_category_ids():
    mapping = db.session.query(CourseCategory).first()
    if mapping is not None:
        return mapping.course_id, mapping.category_id

    course = db.session.query(Course).first()
    category = db.session.query(Category).first()
    return course.id, category.id


def test_sql_user_and_session_lifecycle(app_with_real_db_sql_ops):
    with app_with_real_db_sql_ops.app_context():
        sso_id = f"sql-ops-{uuid.uuid4()}"
        email = f"sql-ops-{uuid.uuid4().hex[:8]}@example.com"

        user, created = create_or_get_user_by_sso(db.session, sso_id, email)
        assert created is True
        same_user, created_again = create_or_get_user_by_sso(db.session, sso_id, email)
        assert created_again is False
        assert same_user.id == user.id

        course_id, category_id = _get_valid_course_category_ids()

        created_session = create_session(
            db.session,
            user_id=user.id,
            course_id=course_id,
            category_id=category_id,
            questions={"attempt_id": "a1", "questions": {}},
            score=0.0,
        )
        session_id = created_session.id

        updated = update_session_score(db.session, session_id, 88.25)
        assert float(updated.score) == pytest.approx(88.25)

        appended = append_session_question_result(
            db.session,
            session_id,
            {"id": "q1", "is_correct": True, "user_answer": 1.0},
        )
        assert "q1" in appended.questions

        db.session.commit()

        sessions = retrieve_sessions_by_user_id(db.session, user.id)
        assert any(s["id"] == session_id for s in sessions)

        session_row = retrieve_session_by_user_id_and_session_id(
            db.session,
            user.id,
            session_id,
        )
        assert session_row is not None
        assert session_row["id"] == session_id

        assert delete_session(db.session, session_id, user_id=user.id) is True
        db.session.commit()
        assert retrieve_session_by_user_id_and_session_id(db.session, user.id, session_id) is None


def test_sql_session_validation_errors(app_with_real_db_sql_ops):
    with app_with_real_db_sql_ops.app_context():
        sso_id = f"sql-ops-{uuid.uuid4()}"
        email = f"sql-ops-{uuid.uuid4().hex[:8]}@example.com"
        user, _ = create_or_get_user_by_sso(db.session, sso_id, email)
        course_id, category_id = _get_valid_course_category_ids()

        with pytest.raises(ValueError, match="questions must be a dictionary"):
            create_session(
                db.session,
                user_id=user.id,
                course_id=course_id,
                category_id=category_id,
                questions="not-a-dict",
                score=0.0,
            )

        created_session = create_session(
            db.session,
            user_id=user.id,
            course_id=course_id,
            category_id=category_id,
            questions={"attempt_id": "a1", "questions": {}},
            score=0.0,
        )

        with pytest.raises(ValueError, match="include an 'id' key"):
            append_session_question_result(
                db.session,
                created_session.id,
                {"is_correct": True},
            )

        with pytest.raises(ValueError, match="must be a dictionary"):
            append_session_question_result(
                db.session,
                created_session.id,
                "not-a-dict",
            )

        with pytest.raises(ValueError, match="not found"):
            update_session_score(db.session, 99999999, 1.0)

        db.session.rollback()
