"""Database initialisation and SQLAlchemy setup.

Provides ``init_database``, which configures SQLAlchemy, imports all ORM
models (so ``db.metadata`` is fully populated before any downstream code runs),
and optionally seeds the database when it is empty.

The ``_ensure_*`` helpers are legacy backfill routines retained for tests and
the standalone seeding script. Production deploys use Alembic migrations
(``alembic upgrade head``) instead of ``db.create_all()``.
"""
import json
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

from logic.database.seeding.seed_defaults import seed_database

db = SQLAlchemy()


def _ensure_user_role_schema():
    """Backfill role support for databases created before roles existed."""
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    has_is_admin = "is_admin" in columns

    with db.engine.begin() as connection:
        if "role" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'Student'"
                )
            )
        else:
            connection.execute(
                text("UPDATE users SET role = 'Student' WHERE role IS NULL")
            )

        if has_is_admin:
            connection.execute(
                text("UPDATE users SET role = 'Admin' WHERE is_admin = true")
            )

        connection.execute(
            text(
                "UPDATE users SET role = 'Student' "
                "WHERE role NOT IN ('Student', 'Admin', 'SuperAdmin')"
            )
        )

    if db.engine.dialect.name != "postgresql":
        return

    with db.engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'Student'")
        )
        connection.execute(text("ALTER TABLE users ALTER COLUMN role SET NOT NULL"))

    inspector = inspect(db.engine)
    constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("users")
    }
    if "ck_users_role" not in constraints:
        with db.engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD CONSTRAINT ck_users_role "
                    "CHECK (role IN ('Student', 'Admin', 'SuperAdmin'))"
                )
            )


def _ensure_user_blocked_schema():
    """Backfill local deactivation support for older databases."""
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "blocked_at" in columns:
        return

    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN blocked_at TIMESTAMP"))


def _backfill_template_answer_behaviour():
    """Sync answer-behaviour fields for existing templates from the default JSON.

    Runs on every startup but is safe to repeat — only overwrites NULL values, so
    admin edits on non-null rows are never clobbered.
    """
    json_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'default', 'question_templates.json')
    )
    try:
        with open(json_path, encoding='utf-8') as fh:
            templates = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return

    with db.engine.begin() as conn:
        for tmpl in templates:
            template_text = tmpl.get('template')
            if not template_text:
                continue
            round_to_unit = tmpl.get('round_to_unit')
            if round_to_unit:
                conn.execute(
                    text(
                        "UPDATE question_templates "
                        "SET round_to_unit = :v "
                        "WHERE template = :t AND round_to_unit IS NULL"
                    ),
                    {"v": round_to_unit, "t": template_text},
                )
            answer_type = tmpl.get('answer_type')
            if answer_type and answer_type != 'numeric':
                conn.execute(
                    text(
                        "UPDATE question_templates "
                        "SET answer_type = :v "
                        "WHERE template = :t AND (answer_type IS NULL OR answer_type = 'numeric')"
                    ),
                    {"v": answer_type, "t": template_text},
                )


def _ensure_question_template_schema():
    """Backfill new answer-behaviour columns for databases created before they existed."""
    inspector = inspect(db.engine)
    if "question_templates" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("question_templates")}
    with db.engine.begin() as conn:
        if "round_answer" not in columns:
            conn.execute(text(
                "ALTER TABLE question_templates ADD COLUMN round_answer BOOLEAN DEFAULT FALSE"
            ))
        if "answer_type" not in columns:
            conn.execute(text(
                "ALTER TABLE question_templates ADD COLUMN answer_type VARCHAR(20) DEFAULT 'numeric'"
            ))
        if "answer_min" not in columns:
            conn.execute(text(
                "ALTER TABLE question_templates ADD COLUMN answer_min NUMERIC(10,4)"
            ))
        if "answer_max" not in columns:
            conn.execute(text(
                "ALTER TABLE question_templates ADD COLUMN answer_max NUMERIC(10,4)"
            ))
        if "tolerance_percent" not in columns:
            conn.execute(text(
                "ALTER TABLE question_templates ADD COLUMN tolerance_percent NUMERIC(6,4)"
            ))
        if "round_to_unit" not in columns:
            conn.execute(text(
                "ALTER TABLE question_templates ADD COLUMN round_to_unit VARCHAR(10)"
            ))
    _backfill_template_answer_behaviour()


def init_database(app: Flask):
    """Configure SQLAlchemy and seed defaults if the DB is empty.

    Schema management is now Alembic-owned (see ``backend/migrations``).
    The legacy ``_ensure_*`` helpers above are retained because the
    seeding helpers and a couple of test fixtures still call them, but
    they are no longer invoked at app boot — production deploys must run
    ``alembic upgrade head`` before Gunicorn starts.

    Args:
        app: Flask application instance
    """
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"postgresql://{os.getenv('POSTGRES_USER', 'qtrain')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'qtrain')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'qtrain')}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', str(64 * 1024)))
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': int(os.getenv('DB_POOL_SIZE', '6')),
        'max_overflow': int(os.getenv('DB_POOL_MAX_OVERFLOW', '2')),
        'pool_pre_ping': True,
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '600')),
    }

    db.init_app(app)

    # Import models so SQLAlchemy registers them on db.metadata before any
    # downstream code (seeding, tests) consults the metadata.
    from .class_db import (
        Category,
        Course,
        CourseCategory,
        QuestionTemplate,
        Session,
        Unit,
        UnitAlias,
        User,
    )

    # Optional: in-process bootstrap for tests/dev that do not use Alembic.
    # In production, ALEMBIC_MANAGED=true skips this and assumes
    # ``alembic upgrade head`` has already run from the entrypoint script.
    alembic_managed = os.getenv("ALEMBIC_MANAGED", "false").lower() == "true"

    with app.app_context():
        if not alembic_managed:
            db.create_all()
            _ensure_user_blocked_schema()
        if Course.query.first() is None:
            print("Database is empty, seeding default data...")
            seed_database(db)
        else:
            print("Database already has data, skipping seeding.")

    return db

