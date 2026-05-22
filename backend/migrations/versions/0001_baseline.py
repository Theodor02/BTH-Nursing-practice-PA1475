"""Baseline schema.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-10

Captures the schema as it stood after the legacy
``_ensure_user_role_schema`` and ``_ensure_question_template_schema``
backfills had run, so that fresh deployments and existing prod databases
converge on the same shape.

For an existing prod DB that already has this schema (created via
``db.create_all()`` + the legacy ensure helpers), run
``alembic stamp head`` once before applying any later migrations — this
marks the baseline as already applied without re-running it.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False, unique=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.literal(True),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_updated",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "unit_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "unit_id",
            sa.Integer(),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("alias", sa.String(length=100), nullable=False, unique=True),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_code", sa.String(length=20), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.literal(True),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("history", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.literal(True),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("history", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "course_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "course_id",
            sa.Integer(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    op.create_table(
        "question_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.JSONB(), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=100), nullable=True),
        sa.Column("tolerance", sa.Numeric(10, 4), nullable=False),
        sa.Column("hints", postgresql.JSONB(), nullable=True),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.literal(True),
        ),
        sa.Column("round_answer", sa.Boolean(), nullable=True, server_default=sa.literal(False)),
        sa.Column("answer_type", sa.String(length=20), nullable=True, server_default="numeric"),
        sa.Column("answer_min", sa.Numeric(10, 4), nullable=True),
        sa.Column("answer_max", sa.Numeric(10, 4), nullable=True),
        sa.Column("tolerance_percent", sa.Numeric(6, 4), nullable=True),
        sa.Column("round_to_unit", sa.String(length=10), nullable=True),
        sa.UniqueConstraint("category_id", "question_number", name="uq_question_category_number"),
    )
    op.create_index(
        "idx_question_templates_active",
        "question_templates",
        ["active"],
    )

    op.create_table(
        "course_question_templates",
        sa.Column(
            "course_id",
            sa.Integer(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "question_template_id",
            sa.Integer(),
            sa.ForeignKey("question_templates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sso_id", sa.String(length=100), nullable=False, unique=True),
        sa.Column("email", sa.String(length=100), nullable=False, unique=True),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="Student",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "role IN ('Student', 'Admin', 'SuperAdmin')",
            name="ck_users_role",
        ),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "course_id",
            sa.Integer(),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("questions", postgresql.JSONB(), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("course_question_templates")
    op.drop_index("idx_question_templates_active", table_name="question_templates")
    op.drop_table("question_templates")
    op.drop_table("course_categories")
    op.drop_table("categories")
    op.drop_table("courses")
    op.drop_table("unit_aliases")
    op.drop_table("units")
