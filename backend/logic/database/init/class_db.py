"""SQLAlchemy ORM models for all domain entities.

Models defined here:
- ``Unit`` / ``UnitAlias`` — measurement units and their accepted aliases.
- ``Course`` — a study course identified by a short code (e.g. "OM125G").
- ``Category`` — a topic area shared across courses.
- ``CourseCategory`` — the many-to-many join between Course and Category.
- ``QuestionTemplate`` — a parametrised question that generates instances at
  quiz time.
- ``User`` — an authenticated user, linked to Microsoft Entra via ``sso_id``.
- ``Session`` — a persisted quiz attempt with per-question snapshots (JSONB).

Role constants (``USER_ROLE_*``) are defined here so both models and auth
helpers can import them without circular dependencies.
"""
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import CheckConstraint, Index, Numeric, Boolean, ForeignKey, UniqueConstraint
from .init_db import db

USER_ROLE_STUDENT = "Student"
USER_ROLE_ADMIN = "Admin"
USER_ROLE_SUPER_ADMIN = "SuperAdmin"
USER_ROLES = (USER_ROLE_STUDENT, USER_ROLE_ADMIN, USER_ROLE_SUPER_ADMIN)

# Many-to-many join table: a QuestionTemplate can belong to multiple Courses
# (e.g. the same dosage questions used in two nursing courses).
course_question_templates = db.Table(
    'course_question_templates',
    db.Column('course_id', db.Integer, ForeignKey('courses.id', ondelete='CASCADE'), primary_key=True),
    db.Column('question_template_id', db.Integer, ForeignKey('question_templates.id', ondelete='CASCADE'), primary_key=True)
)


class Unit(db.Model):
    """A measurement unit used in question answers (e.g. "mg/kg", "ml/h")."""

    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    active = db.Column(Boolean, nullable=False, default=True, server_default=db.literal(True))
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    last_updated = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now())


class UnitAlias(db.Model):
    """Alternative spelling or abbreviation for a ``Unit`` (e.g. "mcg" → "µg")."""

    __tablename__ = "unit_aliases"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = db.Column(db.String(100), nullable=False, unique=True)

    unit = db.relationship("Unit", backref="aliases")


class Course(db.Model):
    """A study course identified by a unique code (e.g. "OM125G").

    A course groups categories and question templates. The many-to-many
    ``question_templates`` relationship is mediated by
    ``course_question_templates`` so the same template can appear in multiple
    courses.
    """

    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(20), nullable=False, unique=True, index=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    active = db.Column(Boolean, nullable=False, default=True, server_default=db.literal(True))
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    last_updated = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    history = db.Column(JSONB, nullable=True)

    question_templates = db.relationship("QuestionTemplate", secondary=course_question_templates, back_populates="courses")


class CourseCategory(db.Model):
    """Join table linking courses to categories (many-to-many)."""

    __tablename__ = "course_categories"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(
        db.Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False
    )
    category_id = db.Column(
        db.Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False
    )


class Category(db.Model):
    """A topic area (e.g. "Dosberäkning") that groups question templates.

    A category can belong to multiple courses via the ``CourseCategory`` join
    table so the same topic can be reused across curricula without duplicating
    question templates.
    """

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    active = db.Column(Boolean, nullable=False, default=True, server_default=db.literal(True))
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    last_updated = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    history = db.Column(JSONB, nullable=True)

    courses = db.relationship("Course", secondary="course_categories", backref="categories")
    # One-to-many relationship with question templates
    question_templates = db.relationship("QuestionTemplate", back_populates="category")


class QuestionTemplate(db.Model):
    """A parametrised question definition that generates concrete instances at quiz time.

    The ``template`` text contains ``{variableName}`` placeholders that are
    substituted with randomly sampled values from ``variables``. The
    ``formula`` is evaluated in a sandboxed Python AST to produce the correct
    answer. See ``logic/question_gen/`` for the generation logic.

    Answer-behaviour fields (``round_answer``, ``answer_type``, ``answer_min``,
    ``answer_max``, ``tolerance_percent``, ``round_to_unit``) are documented
    inline below.
    """

    __tablename__ = "question_templates"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category_id = db.Column(db.Integer, ForeignKey('categories.id'), nullable=False, index=True)
    question_number = db.Column(db.Integer, nullable=False)

    template = db.Column(
        db.Text,
        nullable=False
    )

    variables = db.Column(
        JSONB,
        nullable=False
    )

    formula = db.Column(
        db.Text,
        nullable=False
    )

    unit = db.Column(
        db.String(100),
        nullable=True
    )

    tolerance = db.Column(
        Numeric(10, 4),
        nullable=False
    )

    hints = db.Column(
        JSONB,
        nullable=True
    )

    link = db.Column(
        db.String(500),
        nullable=True
    )

    active = db.Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=db.literal(True)
    )

    # Answer-behaviour fields
    # round_answer: round the correct answer to the nearest integer before grading/display.
    # answer_type:  "numeric" (default) | "time_of_day" (user enters HH:MM; stored as minutes since midnight).
    # answer_min:   minimum acceptable generated correct answer; question gen retries if below.
    # answer_max:   maximum acceptable generated correct answer; question gen retries if above.
    # tolerance_percent: tolerance as a % of the correct answer (overrides absolute tolerance when set).
    round_answer = db.Column(
        Boolean,
        nullable=True,
        server_default=db.literal(False)
    )

    answer_type = db.Column(
        db.String(20),
        nullable=True,
        server_default="numeric"
    )

    answer_min = db.Column(
        Numeric(10, 4),
        nullable=True
    )

    answer_max = db.Column(
        Numeric(10, 4),
        nullable=True
    )

    tolerance_percent = db.Column(
        Numeric(6, 4),
        nullable=True
    )

    # For duration/time_of_day: round both correct and user answer to this unit before comparison.
    # Valid values: "s" | "min" | "h" | "d" — null means no rounding.
    round_to_unit = db.Column(
        db.String(10),
        nullable=True
    )

    # Relationships
    courses = db.relationship("Course", secondary=course_question_templates, back_populates="question_templates")
    category = db.relationship("Category", back_populates="question_templates")

    __table_args__ = (
        UniqueConstraint('category_id', 'question_number', name='uq_question_category_number'),
        Index('idx_question_templates_active', 'active'),
    )

class User(db.Model):
    """Application user, authenticated via Microsoft Entra SSO.

    No password is stored. sso_id is the Entra object ID (oid claim) — stable
    even if the user changes their email. role is enforced both by a DB CHECK
    constraint and by the require_roles decorator in logic/auth.py.
    """
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('Student', 'Admin', 'SuperAdmin')",
            name="ck_users_role",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    sso_id = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(100), nullable=False, unique=True)
    role = db.Column(
        db.String(20),
        nullable=False,
        default=USER_ROLE_STUDENT,
        server_default=USER_ROLE_STUDENT,
    )
    blocked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    last_updated = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    sessions = db.relationship("Session", backref="user", lazy=True)


class Session(db.Model):
    """A completed quiz attempt.

    questions is a JSONB blob with the following shape:
        {
          "attempt_id":   "<uuid>",
          "category_ids": [<int>, ...],
          "questions":    { "<question_instance_id>": { snapshot fields } },
          "summary":      { "answered_count", "scored_count", "correct_count", "score" }
        }

    category_id (FK) holds the primary category for the session. Multi-category
    sessions also record all category IDs in questions.category_ids so stats can
    attribute each question to the correct category.
    """
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    course_id = db.Column(
        db.Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    category_id = db.Column(
        db.Integer,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    questions = db.Column(JSONB, nullable=False)
    score = db.Column(Numeric(5, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
