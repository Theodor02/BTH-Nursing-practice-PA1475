"""Read-only database helpers.

All functions return plain dicts (via _model_to_dict) rather than SQLAlchemy
ORM objects so callers cannot accidentally trigger lazy-load queries after the
session closes. Errors are logged and safe empty values (None / []) are
returned; callers that need to distinguish "not found" from "DB error" should
check the return value against None/[].
"""
import logging
import random

from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SQLSession

from logic.database.init.class_db import (
    Category,
    Course,
    CourseCategory,
    QuestionTemplate,
    Session,
    User,
)

logger = logging.getLogger(__name__)


def _model_to_dict(model_instance):
    """Convert a single model instance to a dictionary."""
    if model_instance is None:
        return None
    return {
        col.name: getattr(model_instance, col.name)
        for col in model_instance.__table__.columns
    }


def _models_to_dicts(model_instances):
    """Convert a list of model instances to a list of dictionaries."""
    return [_model_to_dict(m) for m in model_instances]


# course getters

def retrieve_courses(session: SQLSession):
    """Retrieve all active courses from the database."""
    try:
        courses = session.execute(
            select(Course).where(Course.active.is_(True))
        ).scalars().all()
        return _models_to_dicts(courses)
    except SQLAlchemyError as e:
        logger.error("Error retrieving courses: %s", e)
        return []


def retrieve_courses_with_code(session: SQLSession):
    """Retrieve all active courses ordered by code."""
    try:
        courses = session.execute(
            select(Course)
            .where(Course.active.is_(True))
            .order_by(Course.course_code)
        ).scalars().all()
        return _models_to_dicts(courses)
    except SQLAlchemyError as e:
        logger.error("Error retrieving courses with code: %s", e)
        return []


def retrieve_course_by_code(session: SQLSession, course_code):
    """Retrieve an active course by its code."""
    try:
        course = session.execute(
            select(Course)
            .where(Course.course_code == course_code)
            .where(Course.active.is_(True))
        ).scalars().first()
        return _model_to_dict(course)
    except SQLAlchemyError as e:
        logger.error("Error retrieving course by code %s: %s", course_code, e)
        return None


def retrieve_course_by_id(session: SQLSession, course_id):
    """Retrieve a course by its ID."""
    try:
        course = session.get(Course, course_id)
        return _model_to_dict(course)
    except SQLAlchemyError as e:
        logger.error("Error retrieving course by ID %s: %s", course_id, e)
        return None


# category getters

def retrieve_categories(session: SQLSession):
    """Retrieve all active categories from the database."""
    try:
        categories = session.execute(
            select(Category).where(Category.active.is_(True))
        ).scalars().all()
        return _models_to_dicts(categories)
    except SQLAlchemyError as e:
        logger.error("Error retrieving categories: %s", e)
        return []


def retrieve_category_by_id(session: SQLSession, category_id):
    """Retrieve a specific category by ID."""
    try:
        category = session.get(Category, category_id)
        return _model_to_dict(category)
    except SQLAlchemyError as e:
        logger.error("Error retrieving category by ID %s: %s", category_id, e)
        return None


def retrieve_categories_by_course_id(
    session: SQLSession, course_id
):
    """Retrieve all active categories for a course, ordered by name."""
    try:
        categories = session.execute(
            select(Category)
            .join(Course.categories)
            .where(Course.id == course_id)
            .where(Course.active.is_(True))
            .where(Category.active.is_(True))
            .order_by(Category.name)
        ).scalars().all()
        return _models_to_dicts(categories)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving categories for course %s: %s", course_id, e
        )
        return []


def retrieve_category_by_name_and_course_id(
    session: SQLSession, category_name, course_id
):
    """Retrieve an active category by name and course ID."""
    try:
        category = session.execute(
            select(Category)
            .join(Course.categories)
            .where(Course.id == course_id)
            .where(Course.active.is_(True))
            .where(Category.active.is_(True))
            .where(
                func.lower(Category.name)
                == func.lower(category_name)
            )
        ).scalars().first()
        return _model_to_dict(category)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving category by name %s and course %s: %s",
            category_name,
            course_id,
            e,
        )
        return None


# question template getters

def retrieve_question_templates(session: SQLSession):
    """Retrieve all question templates from the database."""
    try:
        templates = session.execute(
            select(QuestionTemplate)
        ).scalars().all()
        return _models_to_dicts(templates)
    except SQLAlchemyError as e:
        logger.error("Error retrieving question templates: %s", e)
        return []


def retrieve_question_template_by_id(
    session: SQLSession, template_id
):
    """Retrieve a specific question template by ID."""
    try:
        template = session.get(QuestionTemplate, template_id)
        return _model_to_dict(template)
    except SQLAlchemyError as e:
        logger.error("Error retrieving template by ID %s: %s", template_id, e)
        return None


def retrieve_question_templates_by_course(
    session: SQLSession, course_id
):
    """Retrieve all question templates for a specific course."""
    try:
        templates = session.execute(
            select(QuestionTemplate)
            .join(CourseCategory, CourseCategory.category_id == QuestionTemplate.category_id)
            .where(CourseCategory.course_id == course_id)
        ).scalars().all()
        return _models_to_dicts(templates)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving templates for course %s: %s", course_id, e
        )
        return []


def retrieve_question_templates_by_category(
    session: SQLSession, category_id
):
    """Retrieve all question templates for a specific category."""
    try:
        templates = session.execute(
            select(QuestionTemplate)
            .where(QuestionTemplate.category_id == category_id)
        ).scalars().all()
        return _models_to_dicts(templates)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving templates for category %s: %s", category_id, e
        )
        return []


def retrieve_question_templates_by_course_and_category(
    session: SQLSession, course_id, category_id
):
    """Retrieve all active templates for a course/category pair."""
    try:
        templates = session.execute(
            select(QuestionTemplate)
            .join(CourseCategory, CourseCategory.category_id == QuestionTemplate.category_id)
            .where(CourseCategory.course_id == course_id)
            .where(QuestionTemplate.category_id == category_id)
            .where(QuestionTemplate.active.is_(True))
        ).scalars().all()
        return _models_to_dicts(templates)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving templates for course %s and category %s: %s",
            course_id,
            category_id,
            e,
        )
        return []


def retrieve_active_question_templates_by_course_and_category(
    session: SQLSession, course_id, category_id, limit
):
    """Retrieve random active templates for a course and category.

    Single round-trip: fetches matching templates, samples in Python.
    """
    try:
        templates = session.execute(
            select(QuestionTemplate)
            .join(CourseCategory, CourseCategory.category_id == QuestionTemplate.category_id)
            .where(CourseCategory.course_id == course_id)
            .where(QuestionTemplate.category_id == category_id)
            .where(QuestionTemplate.active.is_(True))
        ).scalars().all()

        if not templates:
            return []

        sampled = random.sample(
            list(templates), min(limit, len(templates))
        )
        return _models_to_dicts(sampled)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving active templates for course %s and category %s: %s",
            course_id,
            category_id,
            e,
        )
        return []


def retrieve_inactive_question_templates_by_course(
    session: SQLSession, course_id
):
    """Retrieve inactive question templates for a course."""
    try:
        templates = session.execute(
            select(QuestionTemplate)
            .join(CourseCategory, CourseCategory.category_id == QuestionTemplate.category_id)
            .where(CourseCategory.course_id == course_id)
            .where(QuestionTemplate.active.is_(False))
        ).scalars().all()
        return _models_to_dicts(templates)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving inactive templates for course %s: %s",
            course_id,
            e,
        )
        return []


def retrieve_active_template_count_by_course_and_category(
    session: SQLSession, course_id, category_id
):
    """Count active templates for a course/category combination."""
    try:
        count = session.execute(
            select(func.count(QuestionTemplate.id))
            .join(CourseCategory, CourseCategory.category_id == QuestionTemplate.category_id)
            .where(CourseCategory.course_id == course_id)
            .where(QuestionTemplate.category_id == category_id)
            .where(QuestionTemplate.active.is_(True))
        ).scalar()
        return count or 0
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving template count for course %s and category %s: %s",
            course_id,
            category_id,
            e,
        )
        return 0


def retrieve_cat_request_payload(session: SQLSession):
    """Return all (course, category, active_template_count) rows.
    """
    try:
        counts_sq = (
            select(
                CourseCategory.course_id,
                QuestionTemplate.category_id,
                func.count(QuestionTemplate.id).label("count"),
            )
            .join(CourseCategory, CourseCategory.category_id == QuestionTemplate.category_id)
            .where(QuestionTemplate.active.is_(True))
            .group_by(
                CourseCategory.course_id,
                QuestionTemplate.category_id,
            )
            .subquery()
        )

        rows = session.execute(
            select(
                Course.id.label("course_id"),
                Course.course_code,
                Course.name.label("course_name"),
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                func.coalesce(
                    counts_sq.c.count, 0
                ).label("template_count"),
            )
            .join(CourseCategory, CourseCategory.course_id == Course.id)
            .join(
                Category,
                Category.id == CourseCategory.category_id,
            )
            .outerjoin(
                counts_sq,
                and_(
                    counts_sq.c.course_id == Course.id,
                    counts_sq.c.category_id == Category.id,
                ),
            )
            .where(Course.active.is_(True))
            .where(Category.active.is_(True))
            .order_by(Course.course_code, Category.name)
        ).all()

        payload_courses: dict = {}
        payload_max_questions: dict = {}
        for row in rows:
            code = row.course_code
            if code not in payload_courses:
                payload_courses[code] = {"id": row.course_id, "name": row.course_name, "categories": []}
                payload_max_questions[code] = {}
            payload_courses[code]["categories"].append(row.category_name)
            payload_max_questions[code][row.category_name] = (
                row.template_count
            )

        return payload_courses, payload_max_questions
    except SQLAlchemyError as e:
        logger.error("Error retrieving cat_request payload: %s", e)
        return {}, {}


def retrieve_active_template_counts_by_course_id(
    session: SQLSession, course_id
):
    """Return active template counts per category for a course.
    """
    try:
        counts_sq = (
            select(
                QuestionTemplate.category_id,
                func.count(QuestionTemplate.id).label("count"),
            )
            .join(CourseCategory, CourseCategory.category_id == QuestionTemplate.category_id)
            .where(QuestionTemplate.active.is_(True))
            .where(CourseCategory.course_id == course_id)
            .group_by(QuestionTemplate.category_id)
            .subquery()
        )

        rows = session.execute(
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                func.coalesce(
                    counts_sq.c.count, 0
                ).label("template_count"),
            )
            .join(
                CourseCategory,
                CourseCategory.category_id == Category.id,
            )
            .where(CourseCategory.course_id == course_id)
            .where(Category.active.is_(True))
            .outerjoin(
                counts_sq,
                counts_sq.c.category_id == Category.id,
            )
            .order_by(Category.name)
        ).all()

        return [
            {
                'category_id': row.category_id,
                'category_name': row.category_name,
                'template_count': row.template_count,
            }
            for row in rows
        ]
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving template counts for course %s: %s",
            course_id,
            e,
        )
        return []


# user getters

def retrieve_users(
    session: SQLSession,
    limit: int | None = None,
    offset: int = 0,
):
    """Retrieve users with optional pagination.

    `limit=None` keeps the legacy unbounded behaviour for callers that need
    a full materialization (e.g. seeding helpers); routes that face the
    public must always pass an explicit cap.
    """
    try:
        query = select(User).order_by(User.id)
        if offset:
            query = query.offset(int(offset))
        if limit is not None:
            query = query.limit(int(limit))
        users = session.execute(query).scalars().all()
        return _models_to_dicts(users)
    except SQLAlchemyError as e:
        logger.error("Error retrieving users: %s", e)
        return []


def count_users_by_role(session: SQLSession) -> dict[str, int]:
    """Return user counts grouped by role.

    Avoids loading the entire users table into memory just to count rows.
    """
    try:
        rows = session.execute(
            select(User.role, func.count(User.id))
            .where(User.blocked_at.is_(None))
            .group_by(User.role)
        ).all()
        return {role: count for role, count in rows if role}
    except SQLAlchemyError as e:
        logger.error("Error counting users by role: %s", e)
        return {}


def retrieve_users_by_sso_id(session: SQLSession, sso_id):
    """Retrieve users by their SSO ID."""
    try:
        users = session.execute(
            select(User).where(User.sso_id == sso_id)
        ).scalars().all()
        return _models_to_dicts(users)
    except SQLAlchemyError as e:
        logger.error("Error retrieving users by SSO ID %s: %s", sso_id, e)
        return []


def retrieve_user_by_id(session: SQLSession, user_id):
    """Retrieve a user by their ID."""
    try:
        user = session.get(User, user_id)
        return _model_to_dict(user)
    except SQLAlchemyError as e:
        logger.error("Error retrieving user by ID %s: %s", user_id, e)
        return None


def retrieve_users_by_email(session: SQLSession, email):
    """Retrieve users by their email address."""
    try:
        users = session.execute(
            select(User).where(User.email == email)
        ).scalars().all()
        return _models_to_dicts(users)
    except SQLAlchemyError as e:
        logger.error("Error retrieving users by email %s: %s", email, e)
        return []


# session getters

def retrieve_sessions(session: SQLSession):
    """Retrieve all sessions from the database."""
    try:
        sessions = session.execute(
            select(Session)
        ).scalars().all()
        return _models_to_dicts(sessions)
    except SQLAlchemyError as e:
        logger.error("Error retrieving sessions: %s", e)
        return []


def retrieve_sessions_by_user_id(session: SQLSession, user_id):
    """Retrieve all sessions for a specific user with all category names."""
    try:
        rows = session.execute(
            select(Session, Course.course_code)
            .join(Course, Course.id == Session.course_id)
            .where(Session.user_id == user_id)
        ).all()

        all_cat_ids: set[int] = set()
        for row in rows:
            ids = (row.Session.questions or {}).get("category_ids")
            if ids:
                all_cat_ids.update(ids)
            else:
                all_cat_ids.add(row.Session.category_id)

        cat_name_map: dict[int, str] = {}
        if all_cat_ids:
            cats = session.execute(
                select(Category).where(Category.id.in_(all_cat_ids))
            ).scalars().all()
            cat_name_map = {c.id: c.name for c in cats}

        result = []
        for row in rows:
            ids = (row.Session.questions or {}).get("category_ids") or [row.Session.category_id]
            names = [cat_name_map[i] for i in ids if i in cat_name_map]
            result.append({
                **_model_to_dict(row.Session),
                "course_code": row.course_code,
                "category_name": names[0] if names else "",
                "category_names": names,
            })
        return result
    except SQLAlchemyError as e:
        logger.error("Error retrieving sessions for user %s: %s", user_id, e)
        return []


def retrieve_session_by_id(session: SQLSession, session_id):
    """Retrieve a specific session by its ID."""
    try:
        db_session = session.get(Session, session_id)
        return _model_to_dict(db_session)
    except SQLAlchemyError as e:
        logger.error("Error retrieving session by ID %s: %s", session_id, e)
        return None


def retrieve_session_by_user_id_and_session_id(
    session: SQLSession, user_id, session_id
):
    """Retrieve a session by user ID and session ID."""
    try:
        row = session.execute(
            select(Session, Course.course_code, Category.name.label("category_name"))
            .join(Course, Course.id == Session.course_id)
            .join(Category, Category.id == Session.category_id)
            .where(Session.user_id == user_id)
            .where(Session.id == session_id)
        ).first()
        if row is None:
            return None
        return {**_model_to_dict(row.Session), "course_code": row.course_code, "category_name": row.category_name}
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving session %s for user %s: %s",
            session_id,
            user_id,
            e,
        )
        return None


def retrieve_sessions_by_user_id_and_course_id(
    session: SQLSession, user_id, course_id
):
    """Retrieve all sessions for a user in a specific course."""
    try:
        sessions = session.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .where(Session.course_id == course_id)
        ).scalars().all()
        return _models_to_dicts(sessions)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving sessions for user %s and course %s: %s",
            user_id,
            course_id,
            e,
        )
        return []


def retrieve_sessions_by_course_id(session: SQLSession, course_id):
    """Retrieve all sessions for a specific course."""
    try:
        sessions = session.execute(
            select(Session).where(Session.course_id == course_id)
        ).scalars().all()
        return _models_to_dicts(sessions)
    except SQLAlchemyError as e:
        logger.error("Error retrieving sessions for course %s: %s", course_id, e)
        return []


def retrieve_sessions_by_category_id(
    session: SQLSession, category_id
):
    """Retrieve all sessions for a specific category."""
    try:
        sessions = session.execute(
            select(Session).where(
                Session.category_id == category_id
            )
        ).scalars().all()
        return _models_to_dicts(sessions)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving sessions for category %s: %s",
            category_id,
            e,
        )
        return []


def retrieve_sessions_by_course_and_category(
    session: SQLSession, course_id, category_id
):
    """Retrieve all sessions for a course/category combination."""
    try:
        sessions = session.execute(
            select(Session)
            .where(Session.course_id == course_id)
            .where(Session.category_id == category_id)
        ).scalars().all()
        return _models_to_dicts(sessions)
    except SQLAlchemyError as e:
        logger.error(
            "Error retrieving sessions for course %s and category %s: %s",
            course_id,
            category_id,
            e,
        )
        return []
