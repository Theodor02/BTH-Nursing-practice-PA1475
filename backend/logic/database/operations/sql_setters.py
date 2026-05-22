"""Write database helpers.

All functions call session.flush() after their write so the caller gets back
a populated object (auto-generated id, server defaults) without committing the
transaction — the route handler is responsible for db.session.commit(). On
error, functions call session.rollback() before re-raising so the session is
always in a clean state.

Update functions use allowlists (QUESTION_TEMPLATE_UPDATE_FIELDS, etc.) to
reject unexpected keys rather than silently ignoring them, preventing accidental
mass-assignment of protected fields.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SQLSession

from logic.database.init.class_db import (
    Category,
    Course,
    CourseCategory,
    QuestionTemplate,
    Session,
    Unit,
    UnitAlias,
    User,
    USER_ROLE_ADMIN,
    USER_ROLE_STUDENT,
    USER_ROLES,
)

logger = logging.getLogger(__name__)

# Allowed fields for updates
QUESTION_TEMPLATE_CREATE_FIELDS = {
    "question_number",
    "template",
    "variables",
    "formula",
    "unit",
    "tolerance",
    "hints",
    "link",
    "active",
    # Answer-behaviour fields (see class_db.QuestionTemplate for docs):
    "round_answer",
    "answer_type",
    "answer_min",
    "answer_max",
    "tolerance_percent",
    "round_to_unit",
}

QUESTION_TEMPLATE_UPDATE_FIELDS = {
    "template",
    "variables",
    "formula",
    "unit",
    "tolerance",
    "hints",
    "link",
    "active",
    # Answer-behaviour fields:
    "round_answer",
    "answer_type",
    "answer_min",
    "answer_max",
    "tolerance_percent",
    "round_to_unit",
}

COURSE_UPDATE_FIELDS = {"course_code", "name", "history", "active"}

CATEGORY_UPDATE_FIELDS = {"name", "history", "active"}

UNIT_UPDATE_FIELDS = {"name", "active"}


def _sanitize_updates(
    updates: dict, allowed_fields: set[str], model_name: str
) -> dict:
    """Validate and sanitize update payloads against an allowlist."""
    if not isinstance(updates, dict):
        raise ValueError("updates must be a dictionary.")

    disallowed_fields = sorted(set(updates.keys()) - allowed_fields)
    if disallowed_fields:
        raise ValueError(
            f"Unsupported fields for {model_name}: "
            f"{', '.join(disallowed_fields)}"
        )

    sanitized_updates = {
        k: v for k, v in updates.items() if k in allowed_fields
    }
    if not sanitized_updates:
        raise ValueError(
            f"No valid fields provided for {model_name} update."
        )

    return sanitized_updates


def _validate_category_ids(category_ids: list[int]) -> list[int]:
    """Validate category id lists coming from external callers."""
    if not isinstance(category_ids, list):
        raise ValueError("category_ids must be a list of integers.")
    if any(
        not isinstance(cid, int) or cid <= 0 for cid in category_ids
    ):
        raise ValueError(
            "category_ids must contain only positive integers."
        )
    return list(dict.fromkeys(category_ids))


def _validate_course_id(course_ids: list[int]) -> list[int]:
    if not isinstance(course_ids, list):
        raise ValueError("course_id must be a list of integers.")
    if any(
        not isinstance(cid, int) or cid <= 0 for cid in course_ids
    ):
        raise ValueError(
            "course_id must contain only positive integers."
        )
    return list(dict.fromkeys(course_ids))


def _dict_to_model(model_class, data_dict):
    """Convert a dictionary to a SQLAlchemy model instance."""
    return model_class(**data_dict)


def _dicts_to_models(model_class, data_dicts):
    """Convert a list of dicts to a list of SQLAlchemy model instances."""
    return [_dict_to_model(model_class, d) for d in data_dicts]


# user and session setters

def create_or_get_user_by_sso(
    session: SQLSession, sso_id: str, email: str
) -> tuple[User, bool]:
    """Return (user, created) created is True if a new row was inserted."""
    try:
        user = session.execute(
            select(User).where(User.sso_id == sso_id)
        ).scalar_one_or_none()

        if user:
            return user, False

        user = User(sso_id=sso_id, email=email, role=USER_ROLE_STUDENT)
        session.add(user)
        session.flush()
        return user, True
    except SQLAlchemyError as e:
        logger.error("Error in create_or_get_user_by_sso: %s", e)
        session.rollback()
        raise


def set_user_admin_by_email(
    session: SQLSession, email: str, is_admin: bool
) -> User | None:
    """Compatibility helper that maps the old is_admin flag to roles."""
    try:
        user = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if user is None:
            return None
        if user.blocked_at is not None:
            return None
        user.role = USER_ROLE_ADMIN if is_admin else USER_ROLE_STUDENT
        session.flush()
        return user
    except SQLAlchemyError as e:
        logger.error("Error in set_user_admin_by_email: %s", e)
        session.rollback()
        raise


def update_user_role(session: SQLSession, user_id: int, role: str) -> User:
    """Update a user's role to one of the supported application roles."""
    if role not in USER_ROLES:
        raise ValueError("Invalid user role.")

    try:
        user = session.get(User, user_id)
        if user is None:
            raise ValueError(f"User with id {user_id} not found.")
        if user.blocked_at is not None:
            raise ValueError("User account is deactivated.")

        user.role = role
        session.flush()
        return user
    except SQLAlchemyError as e:
        logger.error("Error in update_user_role: %s", e)
        session.rollback()
        raise


def block_user_by_id(session: SQLSession, user_id: int) -> bool:
    """Deactivate a user locally and delete their completed sessions."""
    try:
        user = session.get(User, user_id)
        if user is None:
            return False

        session.execute(delete(Session).where(Session.user_id == user_id))
        if user.blocked_at is None:
            user.blocked_at = datetime.now(timezone.utc)
        session.flush()
        return True
    except SQLAlchemyError as e:
        logger.error("Error in block_user_by_id: %s", e)
        session.rollback()
        raise


def activate_user_by_id(session: SQLSession, user_id: int) -> bool:
    """Reactivate a locally deactivated user."""
    try:
        user = session.get(User, user_id)
        if user is None:
            return False

        user.blocked_at = None
        session.flush()
        return True
    except SQLAlchemyError as e:
        logger.error("Error in activate_user_by_id: %s", e)
        session.rollback()
        raise


def create_session(
    session: SQLSession,
    user_id: int,
    course_id: int,
    category_id: int,
    questions: dict,
    score: float,
) -> Session:
    """Create a new session record for a completed attempt."""
    try:
        if not isinstance(questions, dict):
            raise ValueError("questions must be a dictionary.")

        new_session = Session(
            user_id=user_id,
            course_id=course_id,
            category_id=category_id,
            questions=questions,
            score=score,
        )
        session.add(new_session)
        session.flush()
        return new_session
    except SQLAlchemyError as e:
        logger.error("Error in create_session: %s", e)
        session.rollback()
        raise


def update_session_score(
    session: SQLSession, session_id: int, score: float
) -> Session:
    """Update the score of an existing session."""
    try:
        stmt = (
            update(Session)
            .where(Session.id == session_id)
            .values(score=score)
            .returning(Session)
        )
        result = session.execute(stmt).scalar_one_or_none()
        if not result:
            raise ValueError(
                f"Session with id {session_id} not found."
            )
        session.flush()
        return result
    except SQLAlchemyError as e:
        logger.error("Error in update_session_score: %s", e)
        session.rollback()
        raise


def append_session_question_result(
    session: SQLSession, session_id: int, question_result: dict
) -> Session:
    """Append or update a question result in a session questions dict."""
    try:
        db_session = session.execute(
            select(Session).where(Session.id == session_id)
        ).scalar_one_or_none()
        if not db_session:
            raise ValueError(
                f"Session with id {session_id} not found."
            )

        if not isinstance(question_result, dict):
            raise ValueError("question_result must be a dictionary.")

        current_questions = db_session.questions or {}
        if not isinstance(current_questions, dict):
            raise ValueError(
                "Session questions must be a dictionary."
            )

        result_key = question_result.get("id")
        if result_key is None:
            raise ValueError(
                "question_result must include an 'id' key."
            )
        if not isinstance(result_key, (str, int)):
            raise ValueError(
                "question_result 'id' must be a string or integer."
            )

        current_questions[str(result_key)] = question_result

        stmt = (
            update(Session)
            .where(Session.id == session_id)
            .values(questions=current_questions)
            .returning(Session)
        )
        result = session.execute(stmt).scalar_one_or_none()
        session.flush()
        return result
    except SQLAlchemyError as e:
        logger.error("Error in append_session_question_result: %s", e)
        session.rollback()
        raise


def delete_session(
    session: SQLSession,
    session_id: int,
    user_id: int = None,
) -> bool:
    """Delete a session, optionally scoped to a specific user."""
    try:
        stmt = delete(Session).where(Session.id == session_id)
        if user_id is not None:
            stmt = stmt.where(Session.user_id == user_id)
        result = session.execute(stmt)
        session.flush()
        return result.rowcount > 0
    except SQLAlchemyError as e:
        logger.error("Error in delete_session: %s", e)
        session.rollback()
        raise


# question template setters

def create_question_template(
    session: SQLSession,
    template_data: dict,
    category_id: int,
) -> QuestionTemplate:
    """Create a new question template and associate it with a category."""
    try:
        if not isinstance(category_id, int) or category_id <= 0:
            raise ValueError("category_id must be a positive integer.")

        template_data = _sanitize_updates(
            template_data,
            QUESTION_TEMPLATE_CREATE_FIELDS,
            "QuestionTemplate",
        )

        category = session.get(Category, category_id)
        if not category:
            raise ValueError(f"Category {category_id} does not exist.")

        qt = QuestionTemplate(**template_data)
        qt.category_id = category_id
        session.add(qt)
        session.flush()
        return qt
    except SQLAlchemyError as e:
        logger.error("Error in create_question_template: %s", e)
        session.rollback()
        raise


def update_question_template(
    session: SQLSession, template_id: int, updates: dict
) -> QuestionTemplate:
    """Update an existing question template."""
    try:
        updates = _sanitize_updates(
            updates, QUESTION_TEMPLATE_UPDATE_FIELDS, "QuestionTemplate"
        )

        stmt = (
            update(QuestionTemplate)
            .where(QuestionTemplate.id == template_id)
            .values(**updates)
            .returning(QuestionTemplate)
        )
        result = session.execute(stmt).scalar_one_or_none()
        if not result:
            raise ValueError(
                f"QuestionTemplate with id {template_id} not found."
            )
        session.flush()
        return result
    except SQLAlchemyError as e:
        logger.error("Error in update_question_template: %s", e)
        session.rollback()
        raise


def set_question_template_active(
    session: SQLSession, template_id: int, active: bool
) -> QuestionTemplate:
    """Set the active status of a question template."""
    return update_question_template(
        session, template_id, {"active": active}
    )


def set_course_active(
    session: SQLSession, course_id: int, active: bool
) -> Course:
    """Set the active status of a course."""
    return update_course(session, course_id, {"active": active})


def replace_template_categories(
    session: SQLSession,
    template_id: int,
    category_id: int,
) -> QuestionTemplate:
    """Update the category for a question template."""
    try:
        if not isinstance(category_id, int) or category_id <= 0:
            raise ValueError("category_id must be a positive integer.")

        qt = session.get(QuestionTemplate, template_id)
        if not qt:
            raise ValueError(
                f"QuestionTemplate with id {template_id} not found."
            )

        category = session.get(Category, category_id)
        if not category:
            raise ValueError(f"Category {category_id} does not exist.")

        qt.category_id = category_id
        session.flush()
        return qt
    except SQLAlchemyError as e:
        logger.error("Error in replace_template_categories: %s", e)
        session.rollback()
        raise


def replace_template_courses(
    session: SQLSession,
    template_id: int,
    course_ids: list[int],
) -> QuestionTemplate:
    """Replace the associated courses for a question template."""
    try:
        course_ids = _validate_course_id(course_ids)

        qt = session.execute(
            select(QuestionTemplate).where(
                QuestionTemplate.id == template_id
            )
        ).scalar_one_or_none()

        if not qt:
            raise ValueError(
                f"QuestionTemplate with id {template_id} not found."
            )

        courses = session.execute(
            select(Course).where(Course.id.in_(course_ids))
        ).scalars().all()
        if len(courses) != len(set(course_ids)):
            raise ValueError(
                "One or more course_ids do not exist."
            )

        qt.courses = courses
        session.flush()
        return qt
    except SQLAlchemyError as e:
        logger.error("Error in replace_template_courses: %s", e)
        session.rollback()
        raise


def delete_question_template(
    session: SQLSession, template_id: int
) -> bool:
    """Delete a question template from the database."""
    try:
        stmt = delete(QuestionTemplate).where(
            QuestionTemplate.id == template_id
        )
        result = session.execute(stmt)
        session.flush()
        return result.rowcount > 0
    except SQLAlchemyError as e:
        logger.error("Error in delete_question_template: %s", e)
        session.rollback()
        raise


# course setters

def create_course(
    session: SQLSession,
    course_code: str,
    name: str,
    history: dict = None,
) -> Course:
    """Create a new course."""
    try:
        course = Course(
            course_code=course_code, name=name, history=history
        )
        session.add(course)
        session.flush()
        return course
    except SQLAlchemyError as e:
        logger.error("Error in create_course: %s", e)
        session.rollback()
        raise


def update_course(
    session: SQLSession, course_id: int, updates: dict
) -> Course:
    """Update an existing course."""
    try:
        updates = _sanitize_updates(
            updates, COURSE_UPDATE_FIELDS, "Course"
        )

        stmt = (
            update(Course)
            .where(Course.id == course_id)
            .values(**updates)
            .returning(Course)
        )
        result = session.execute(stmt).scalar_one_or_none()
        if not result:
            raise ValueError(
                f"Course with id {course_id} not found."
            )
        session.flush()
        return result
    except SQLAlchemyError as e:
        logger.error("Error in update_course: %s", e)
        session.rollback()
        raise


# category setters

def create_category(
    session: SQLSession, name: str, history: dict = None
) -> Category:
    """Create a new category."""
    try:
        category = Category(name=name, history=history)
        session.add(category)
        session.flush()
        return category
    except SQLAlchemyError as e:
        logger.error("Error in create_category: %s", e)
        session.rollback()
        raise


def update_category(
    session: SQLSession, category_id: int, updates: dict
) -> Category:
    """Update an existing category."""
    try:
        updates = _sanitize_updates(
            updates, CATEGORY_UPDATE_FIELDS, "Category"
        )

        stmt = (
            update(Category)
            .where(Category.id == category_id)
            .values(**updates)
            .returning(Category)
        )
        result = session.execute(stmt).scalar_one_or_none()
        if not result:
            raise ValueError(
                f"Category with id {category_id} not found."
            )
        session.flush()
        return result
    except SQLAlchemyError as e:
        logger.error("Error in update_category: %s", e)
        session.rollback()
        raise


def set_category_active(
    session: SQLSession, category_id: int, active: bool
) -> Category:
    """Set the active status of a category."""
    return update_category(session, category_id, {"active": active})


def attach_category_to_course(
    session: SQLSession, course_id: int, category_id: int
) -> bool:
    """Attach a category to a course."""
    try:
        stmt = insert(CourseCategory).values(
            course_id=course_id, category_id=category_id
        ).on_conflict_do_nothing()
        session.execute(stmt)
        session.flush()
        return True
    except SQLAlchemyError as e:
        logger.error("Error in attach_category_to_course: %s", e)
        session.rollback()
        raise


def detach_category_from_course(
    session: SQLSession, course_id: int, category_id: int
) -> bool:
    """Detach a category from a course."""
    try:
        stmt = delete(CourseCategory).where(
            CourseCategory.course_id == course_id,
            CourseCategory.category_id == category_id,
        )
        result = session.execute(stmt)
        session.flush()
        return result.rowcount > 0
    except SQLAlchemyError as e:
        logger.error("Error in detach_category_from_course: %s", e)
        session.rollback()
        raise


def create_unit(
    session: SQLSession, name: str, active: bool = True
) -> Unit:
    """Create a new unit."""
    try:
        unit = Unit(name=name, active=active)
        session.add(unit)
        session.flush()
        return unit
    except SQLAlchemyError as e:
        logger.error("Error in create_unit: %s", e)
        session.rollback()
        raise


def update_unit(
    session: SQLSession, unit_id: int, updates: dict
) -> Unit:
    """Update an existing unit."""
    try:
        updates = _sanitize_updates(
            updates, UNIT_UPDATE_FIELDS, "Unit"
        )

        stmt = (
            update(Unit)
            .where(Unit.id == unit_id)
            .values(**updates)
            .returning(Unit)
        )
        result = session.execute(stmt).scalar_one_or_none()
        if not result:
            raise ValueError(
                f"Unit with id {unit_id} not found."
            )
        session.flush()
        return result
    except SQLAlchemyError as e:
        logger.error("Error in update_unit: %s", e)
        session.rollback()
        raise


def set_unit_active(
    session: SQLSession, unit_id: int, active: bool
) -> Unit:
    """Set the active status of a unit."""
    return update_unit(session, unit_id, {"active": active})


def create_unit_alias(
    session: SQLSession, unit_id: int, alias: str
) -> UnitAlias:
    try:
        unit_alias = UnitAlias(unit_id=unit_id, alias=alias)
        session.add(unit_alias)
        session.flush()
        return unit_alias
    except SQLAlchemyError as e:
        logger.error("Error in create_unit_alias: %s", e)
        session.rollback()
        raise


def update_unit_alias(
    session: SQLSession, alias_id: int, alias: str
) -> UnitAlias:
    try:
        stmt = (
            update(UnitAlias)
            .where(UnitAlias.id == alias_id)
            .values(alias=alias)
            .returning(UnitAlias)
        )
        result = session.execute(stmt).scalar_one_or_none()
        if not result:
            raise ValueError(f"UnitAlias with id {alias_id} not found.")
        session.flush()
        return result
    except SQLAlchemyError as e:
        logger.error("Error in update_unit_alias: %s", e)
        session.rollback()
        raise


def delete_unit_alias(session: SQLSession, alias_id: int) -> bool:
    try:
        stmt = delete(UnitAlias).where(UnitAlias.id == alias_id)
        result = session.execute(stmt)
        session.flush()
        return result.rowcount > 0
    except SQLAlchemyError as e:
        logger.error("Error in delete_unit_alias: %s", e)
        session.rollback()
        raise


def upsert_course(
    session: SQLSession,
    course_code: str,
    name: str,
    history: dict = None,
) -> Course:
    """Insert a course or update it if the course code already exists."""
    try:
        stmt = insert(Course).values(
            course_code=course_code, name=name, history=history
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=['course_code'],
            set_=dict(
                name=stmt.excluded.name,
                history=stmt.excluded.history,
            ),
        ).returning(Course)
        result = session.execute(stmt).scalar_one()
        session.flush()
        return result
    except SQLAlchemyError as e:
        logger.error("Error in upsert_course: %s", e)
        session.rollback()
        raise


def upsert_category(
    session: SQLSession, name: str, history: dict = None
) -> Category:
    """Insert a category or update it if the name already exists."""
    try:
        stmt = insert(Category).values(name=name, history=history)
        stmt = stmt.on_conflict_do_update(
            index_elements=['name'],
            set_=dict(history=stmt.excluded.history),
        ).returning(Category)
        result = session.execute(stmt).scalar_one()
        session.flush()
        return result
    except SQLAlchemyError as e:
        logger.error("Error in upsert_category: %s", e)
        session.rollback()
        raise


def write_history_entry(
    session: SQLSession,
    model_class,
    entity_id: int | str,
    entry: dict,
) -> None:
    """Append an entry to the history JSON list column for an entity."""
    try:
        if not hasattr(model_class, "history"):
            raise ValueError(
                "model_class does not support history entries."
            )
        if not isinstance(entry, dict):
            raise ValueError("entry must be a dictionary.")

        entity = session.execute(
            select(model_class).where(model_class.id == entity_id)
        ).scalar_one_or_none()
        if not entity:
            raise ValueError(
                f"Entity with id {entity_id} not found."
            )

        current_history = entity.history or []
        if not isinstance(current_history, list):
            raise ValueError("Entity history must be a list.")

        history_entry = {
            k: v for k, v in entry.items() if k != "timestamp"
        }
        history_entry["timestamp"] = (
            datetime.now(timezone.utc).isoformat()
        )
        current_history.append(history_entry)

        stmt = (
            update(model_class)
            .where(model_class.id == entity_id)
            .values(history=current_history)
        )
        session.execute(stmt)
        session.flush()
    except SQLAlchemyError as e:
        logger.error("Error in write_history_entry: %s", e)
        session.rollback()
        raise
