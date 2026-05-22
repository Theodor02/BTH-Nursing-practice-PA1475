"""Admin routes: content management and user administration.

All routes require Admin or SuperAdmin role (enforced by @require_admin /
@require_roles). SuperAdmin-only operations (user role changes, user deactivation)
are gated separately within this file.

Two mutation interfaces exist side-by-side:
  POST /api/admin/mutate  — batch command-bus (original); accepts a JSON array
                            of { type, action, body } operations in one DB tx.
  REST equivalents        — conventional per-resource endpoints added later for
                            new frontend code; they delegate to the same handler
                            functions as the batch endpoint.

New frontend code should use the REST endpoints. /api/admin/mutate is kept for
backwards compatibility until the frontend has fully migrated off it.
"""
import logging

from flask import Blueprint, jsonify, request
from enum import IntEnum
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from logic.database.init.init_db import db
from logic.database.init.class_db import Category, Course, QuestionTemplate, Unit, UnitAlias
from logic.auth import require_admin, require_roles
from logic.answer_utils import invalidate_unit_cache, is_known_unit
from routes.cat_routes import invalidate_cat_request_cache
from logic.database.operations.sql_setters import (
    attach_category_to_course,
    create_category,
    create_course,
    create_question_template,
    create_unit,
    create_unit_alias,
    delete_unit_alias,
    detach_category_from_course,
    replace_template_categories,
    replace_template_courses,
    set_category_active,
    set_course_active,
    set_question_template_active,
    set_unit_active,
    set_user_admin_by_email,
    update_category,
    update_course,
    update_question_template,
    update_unit,
    update_unit_alias,
    write_history_entry,
)

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

class EntityType(IntEnum):
    """Integer codes for the entity types accepted by ``POST /api/admin/mutate``."""

    COURSE = 0
    CATEGORY = 1
    QUESTION = 2
    UNIT = 3
    UNIT_ALIAS = 4


class ActionType(IntEnum):
    """Integer codes for the operations accepted by ``POST /api/admin/mutate``."""

    CREATE = 0
    ARCHIVE = 1   # Use body.get('archive', True) to toggle between archive/unarchive
    EDIT = 2


@admin_bp.route('/api/admin/categories', methods=['GET'])
@require_admin
def get_categories_nested():
    """
    GET /admin/categories_nested

    Returns all categories, the questions belonging to each category,
    and which courses are linked to each category.
    Question bodies are NOT included — only IDs and short excerpts.

    Request:  No body or query parameters needed.

    Response 200:
    [
      {
        "id": 1,
        "name": "Mechanics",
        "active": true,
        "courses": [
          { "id": 3, "course_code": "MEK101", "name": "Introduction to Mechanics" }
        ],
        "questions": [
          { "id": "Mek_1_1", "excerpt": "A ball is thrown...", "active": true }
        ]
      },
      ...
    ]

    Response 500: { "error": "<message>" }
    """
    try:
        categories = db.session.execute(
            select(Category).options(
                selectinload(Category.courses),
                selectinload(Category.question_templates),
            )
        ).scalars().unique().all()
        response_data = []

        for category in categories:
            cat_data = {
                "id": category.id,
                "name": category.name,
                "active": category.active,
                "courses": [{"id": c.id, "course_code": c.course_code, "name": c.name} for c in category.courses],
                "questions": []
            }

            for q in category.question_templates:
                # Add an excerpt to act as a human-understandable identifier alongside the string ID
                excerpt = q.template[:50] + "..." if q.template and len(q.template) > 50 else q.template
                cat_data["questions"].append({
                    "id": q.id,
                    "question_number": q.question_number,
                    "excerpt": excerpt,
                    "active": q.active
                })

            response_data.append(cat_data)

        return jsonify(response_data), 200
    except Exception:
        logger.exception("Failed in get_categories_nested")
        return jsonify({"error": "Internal server error"}), 500

@admin_bp.route('/api/admin/units', methods=['GET'])
@require_admin
def get_units():
    """
    GET /admin/units

    Returns all units with their aliases.

    Response 200:
    [
      { "id": 1, "name": "m/s", "active": true, "aliases": [{"id": 1, "alias": "meters per second"}] },
      ...
    ]

    Response 500: { "error": "<message>" }
    """
    try:
        units = db.session.execute(select(Unit)).scalars().unique().all()
        return jsonify([{
            "id": u.id,
            "name": u.name,
            "active": u.active,
            "aliases": [{"id": a.id, "alias": a.alias} for a in u.aliases],
        } for u in units]), 200
    except Exception:
        logger.exception("Failed in get_units")
        return jsonify({"error": "Internal server error"}), 500

@admin_bp.route('/api/admin/courses', methods=['GET'])
@require_admin
def get_courses():
    """Return all courses (including inactive) with metadata for the admin panel."""
    try:
        courses = db.session.execute(select(Course)).scalars().unique().all()
        return jsonify([{
            "id": c.id,
            "course_code": c.course_code,
            "name": c.name,
            "active": c.active,
            "created_at": c.created_at,
            "last_updated": c.last_updated,
            "history": c.history,
        } for c in courses]), 200
    except Exception:
        logger.exception("Failed in get_courses")
        return jsonify({"error": "Internal server error"}), 500

@admin_bp.route('/api/admin/entity/<int:entity_type>/<entity_id>', methods=['GET'])
@require_admin
def get_entity(entity_type, entity_id):
    """
    GET /admin/entity/<entity_type>/<entity_id>

    Returns the full object for a single entity.

    URL parameters:
      entity_type  integer  0=Course, 1=Category, 2=Question, 3=Unit
      entity_id    string   Numeric ID for Course/Category/Unit; string ID for Question (e.g. "Mek_1_1")

    Examples:
      GET /admin/entity/0/3        -> Course with ID 3
      GET /admin/entity/1/5        -> Category with ID 5
      GET /admin/entity/2/Mek_1_1 -> Question with ID "Mek_1_1"
      GET /admin/entity/3/2        -> Unit with ID 2

    Response 200 — Course:
      { "id", "course_code", "name", "active", "created_at", "last_updated", "history" }

    Response 200 — Category:
      { "id", "name", "active", "created_at", "last_updated", "history" }

    Response 200 — Question:
      {
        "id", "category_id", "question_number",
        "template", "variables", "formula",
        "unit", "tolerance", "hints", "link", "active",
        "answer_type",       -- "numeric" | "time_of_day" | "duration"
        "answer_min",        -- float | null
        "answer_max",        -- float | null
        "tolerance_percent", -- float | null
        "round_answer",      -- bool | null
        "round_to_unit"      -- "s" | "min" | "h" | "d" | null
      }

    Response 200 — Unit:
      { "id", "name", "active", "created_at", "last_updated" }

    Response 400: { "error": "Invalid entity type" | "Invalid ID format" }
    Response 404: { "error": "<entity> not found" }
    Response 500: { "error": "<message>" }
    """
    try:
        if entity_type == EntityType.COURSE:
            entity = db.session.get(Course, int(entity_id))
            if not entity:
                return jsonify({"error": "Course not found"}), 404

            return jsonify({
                "id": entity.id,
                "course_code": entity.course_code,
                "name": entity.name,
                "active": entity.active,
                "created_at": entity.created_at,
                "last_updated": entity.last_updated,
                "history": entity.history
            }), 200

        elif entity_type == EntityType.CATEGORY:
            entity = db.session.get(Category, int(entity_id))
            if not entity:
                return jsonify({"error": "Category not found"}), 404

            return jsonify({
                "id": entity.id,
                "name": entity.name,
                "active": entity.active,
                "created_at": entity.created_at,
                "last_updated": entity.last_updated,
                "history": entity.history
            }), 200

        elif entity_type == EntityType.QUESTION:
            entity = db.session.get(QuestionTemplate, int(entity_id))
            if not entity:
                return jsonify({"error": "Question not found"}), 404

            return jsonify({
                "id": entity.id,
                "category_id": entity.category_id,
                "question_number": entity.question_number,
                "template": entity.template,
                "variables": entity.variables,
                "formula": entity.formula,
                "unit": entity.unit,
                "tolerance": float(entity.tolerance) if entity.tolerance is not None else None,
                "hints": entity.hints,
                "link": entity.link,
                "active": entity.active,
                "answer_type": entity.answer_type,
                "answer_min": float(entity.answer_min) if entity.answer_min is not None else None,
                "answer_max": float(entity.answer_max) if entity.answer_max is not None else None,
                "tolerance_percent": float(entity.tolerance_percent) if entity.tolerance_percent is not None else None,
                "round_answer": entity.round_answer,
                "round_to_unit": entity.round_to_unit,
            }), 200

        elif entity_type == EntityType.UNIT:
            entity = db.session.get(Unit, int(entity_id))
            if not entity:
                return jsonify({"error": "Unit not found"}), 404

            return jsonify({
                "id": entity.id,
                "name": entity.name,
                "active": entity.active,
                "created_at": entity.created_at,
                "last_updated": entity.last_updated,
                "aliases": [{"id": a.id, "alias": a.alias} for a in entity.aliases],
            }), 200

        else:
            return jsonify({"error": "Invalid entity type"}), 400

    except ValueError:
        return jsonify({"error": "Invalid ID format"}), 400
    except Exception:
        logger.exception("Failed in get_entity entity_type=%s entity_id=%s", entity_type, entity_id)
        return jsonify({"error": "Internal server error"}), 500


@admin_bp.route('/api/admin/questions', methods=['GET'])
@require_admin
def get_questions():
    """
    GET /admin/questions

    Returns a paginated list of all question templates.
    Each item is a summary (ID + short excerpt), not the full question body.
    Use GET /admin/entity/2/<id> to fetch the full details of a single question.

    Query parameters (all optional):
      limit       integer  Max number of results to return (default 50, max 200)
      offset      integer  Number of results to skip for pagination (default 0)
      course_id   integer  Filter to questions belonging to this course
      category_id integer  Filter to questions belonging to this category

    Examples:
      GET /admin/questions                          -> First 50 questions
      GET /admin/questions?limit=20&offset=40       -> Questions 41–60
      GET /admin/questions?course_id=3              -> Questions in course 3
      GET /admin/questions?category_id=7&limit=10   -> First 10 questions in category 7

    Response 200:
    [
      { "id": "Mek_1_1", "excerpt": "A ball is thrown...", "unit": "m/s", "active": true },
      ...
    ]

    Response 400: { "error": "limit and offset must be integers" }
    Response 500: { "error": "<message>" }
    """
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = max(int(request.args.get('offset', 0)), 0)
    except (TypeError, ValueError):
        return jsonify({"error": "limit and offset must be integers"}), 400

    course_id = request.args.get('course_id', type=int)
    category_id = request.args.get('category_id', type=int)

    try:
        query = select(QuestionTemplate)
        if course_id:
            query = query.join(QuestionTemplate.courses).where(Course.id == course_id)
        if category_id:
            query = query.where(QuestionTemplate.category_id == category_id)
        query = query.order_by(QuestionTemplate.category_id, QuestionTemplate.question_number).limit(limit).offset(offset)

        templates = db.session.execute(query).scalars().unique().all()
        return jsonify([{
            "id": t.id,
            "question_number": t.question_number,
            "excerpt": (t.template[:50] + "...") if t.template and len(t.template) > 50 else t.template,
            "unit": t.unit,
            "active": t.active,
        } for t in templates]), 200
    except Exception:
        logger.exception("Failed in get_questions")
        return jsonify({"error": "Internal server error"}), 500


@admin_bp.route('/api/admin/users/set_admin', methods=['POST'])
@require_roles("SuperAdmin")
def set_admin():
    """Toggle a user between Student and Admin role by email address.

    Legacy endpoint kept for backwards compatibility with management scripts
    that predate the role-management UI. New code should use
    PATCH /api/admin/users/<id>/role instead.
    """
    body = request.get_json(silent=True) or {}
    email = body.get('email', '').strip().lower()
    is_admin = body.get('is_admin', True)

    if not email:
        return jsonify({'error': 'email required'}), 400
    if not isinstance(is_admin, bool):
        return jsonify({'error': 'is_admin must be a boolean'}), 400

    try:
        user = set_user_admin_by_email(db.session, email, is_admin)
        if user is None:
            return jsonify({'error': f'No user found with email {email}'}), 404
        db.session.commit()
        role = getattr(
            user,
            "role",
            "Admin" if getattr(user, "is_admin", False) else "Student",
        )
        return jsonify(
            {
                'user_id': user.id,
                'email': user.email,
                'role': role,
                'is_admin': role == "Admin",
            }
        ), 200
    except Exception:
        logger.exception("Failed in set_admin")
        return jsonify({'error': 'Internal server error'}), 500


# mutation routes

@admin_bp.route('/api/admin/mutate', methods=['POST'])
@require_admin
def batch_mutate():
    """
    POST /admin/mutate

    Single endpoint for all create, edit, and archive operations on
    Courses, Categories, Questions, and Units. Accepts a JSON array of
    operations. All operations run in one database transaction — if any
    operation fails the entire batch is rolled back.

    Request body: JSON array of operation objects.
    Each operation object:
      {
        "type":   <EntityType int>   0=Course, 1=Category, 2=Question, 3=Unit
        "action": <ActionType int>   0=CREATE, 1=ARCHIVE, 2=EDIT
        "body":   { ... }            fields depend on type + action (see handlers below)
      }

    Response 200:
      { "results": [ { "status": "success"|"error", "type": "...", "action": ..., "id": ... }, ... ] }

    Response 400: { "error": "Expected a list of operations" }
    Response 500: { "error": "<message>" }   (entire batch rolled back)

    ── COURSE (type: 0) ────────────────────────────────────────────────────────
    CREATE (action: 0):
      Required: course_code (string), name (string)
      Optional: history (any), add_category_ids (int[])
      Returns:  { "status": "success", "type": "course", "action": 0, "id": <new id> }

    EDIT (action: 2):
      Required: id (int)
      Optional: course_code, name, history, add_category_ids (int[]), remove_category_ids (int[])
      Returns:  { "status": "success", "type": "course", "action": 2 }

    ARCHIVE / UNARCHIVE (action: 1):
      Required: id (int)
      Optional: archive (bool, default true)  — set false to unarchive
      Returns:  { "status": "success", "type": "course", "action": 1 }

    ── CATEGORY (type: 1) ──────────────────────────────────────────────────────
    CREATE (action: 0):
      Required: name (string)
      Optional: history (any), course_ids (int[])
      Returns:  { "status": "success", "type": "category", "action": 0, "id": <new id> }

    EDIT (action: 2):
      Required: id (int)
      Optional: name, history, active (bool), add_course_ids (int[]), remove_course_ids (int[])
      Returns:  { "status": "success", "type": "category", "action": 2 }

    ARCHIVE / UNARCHIVE (action: 1):
      Required: id (int)
      Optional: archive (bool, default true)
      Returns:  { "status": "success", "type": "category", "action": 1 }

    ── QUESTION (type: 2) ──────────────────────────────────────────────────────
    CREATE (action: 0):
      Required: category_id (int)
      Optional: template (string), variables (any), formula (string),
                unit (string), tolerance (float), hints (any), link (string),
                active (bool), course_ids (int[])
      Answer-behaviour fields (all optional):
        round_answer      bool   – Round correct answer to nearest integer before grading (numeric only).
        answer_type       string – "numeric" (default) | "time_of_day" (answer entered as HH:MM,
                                  stored/compared as minutes since midnight; use unit "kl") |
                                  "duration" (answer entered as compound string e.g. "1h 20min",
                                  "2d 3h 15s", "90min"; formula must return seconds; supports
                                  Swedish aliases: timmar/minuter/sekunder/dagar).
        answer_min        float  – Minimum acceptable generated correct answer; generation retries
                                  if the result is below this value. In seconds for duration questions.
        answer_max        float  – Maximum acceptable generated correct answer; generation retries
                                  if the result is above this value. In seconds for duration questions.
        tolerance_percent float  – Tolerance as % of the correct answer; overrides absolute tolerance.
        round_to_unit     string – For duration/time_of_day only: round both correct answer and user
                                  answer to this granularity before comparison.
                                  "s" | "min" | "h" | "d" for duration (values in seconds).
                                  "min" | "h" for time_of_day (values in minutes).
                                  Example: round_to_unit="min" means "10h 4min 30s" grades as "10h 4min".
      Validation: answer_type must be "numeric", "time_of_day", or "duration";
                  round_to_unit must be "s", "min", "h", or "d";
                  unit must already exist in the Units table (add via Units admin panel first).
      Returns:  { "status": "success", "type": "question", "action": 0, "id": <new id> }

    EDIT (action: 2):
      Required: id (int)
      Optional: template, variables, formula, unit, tolerance, hints, link, active,
                round_answer, answer_type, answer_min, answer_max, tolerance_percent, round_to_unit,
                category_id (int, REPLACES existing), course_ids (int[], REPLACES existing)
      Same validation as CREATE applies to answer_type, round_to_unit, and unit.
      Returns:  { "status": "success", "type": "question", "action": 2 }

    ARCHIVE / UNARCHIVE (action: 1):
      Required: id (string)
      Optional: archive (bool, default true)
      Returns:  { "status": "success", "type": "question", "action": 1 }

    ── UNIT (type: 3) ──────────────────────────────────────────────────────────
    All Unit mutations invalidate the in-memory unit alias cache immediately.

    CREATE (action: 0):
      Required: name (string)
      Optional: active (bool, default true)
      Returns:  { "status": "success", "type": "unit", "action": 0, "id": <new id> }

    EDIT (action: 2):
      Required: id (int)
      Optional: name, active
      Returns:  { "status": "success", "type": "unit", "action": 2 }

    ARCHIVE / UNARCHIVE (action: 1):
      Required: id (int)
      Optional: archive (bool, default true)
      Returns:  { "status": "success", "type": "unit", "action": 1 }

    ── UNIT_ALIAS (type: 4) ─────────────────────────────────────────────────────
    All UnitAlias mutations invalidate the in-memory unit alias cache immediately.

    CREATE (action: 0):
      Required: unit_id (int), alias (string)
      Returns:  { "status": "success", "type": "unit_alias", "action": 0, "id": <new id> }

    EDIT (action: 2):
      Required: id (int), alias (string)
      Returns:  { "status": "success", "type": "unit_alias", "action": 2 }

    DELETE (action: 1):
      Required: id (int)
      Returns:  { "status": "success", "type": "unit_alias", "action": 1 }
    """
    operations = request.get_json()
    if not isinstance(operations, list):
        return jsonify({"error": "Expected a list of operations"}), 400

    results = []

    try:
        for op in operations:
            entity_type = op.get("type")
            action = op.get("action")
            body = op.get("body", {})

            try:
                if entity_type == EntityType.COURSE:
                    results.append(handle_course_action(action, body))
                elif entity_type == EntityType.CATEGORY:
                    results.append(handle_category_action(action, body))
                elif entity_type == EntityType.QUESTION:
                    results.append(handle_question_action(action, body))
                elif entity_type == EntityType.UNIT:
                    results.append(handle_unit_action(action, body))
                elif entity_type == EntityType.UNIT_ALIAS:
                    results.append(handle_unit_alias_action(action, body))
                else:
                    results.append({"status": "error", "message": f"Unknown entity type: {entity_type}"})
            except (ValueError, SQLAlchemyError) as e:
                raise RuntimeError(str(e)) from e

        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed in batch_mutate")
        return jsonify({"error": "Internal server error"}), 500

    invalidate_cat_request_cache()
    return jsonify({"results": results})


# mutation handlers

def handle_course_action(action, body):
    """Execute a CREATE, EDIT, or ARCHIVE operation on a Course.

    Called by both ``batch_mutate`` and the individual REST endpoints.
    Returns a result dict with ``"status": "success"|"error"``.
    """
    if action == ActionType.CREATE:
        course_code = body.get('course_code')
        name = body.get('name')
        if not course_code or not name:
            return {"status": "error", "message": "course_code and name are required"}
        course = create_course(db.session, course_code=course_code, name=name, history=body.get('history'))
        db.session.flush()
        for cid in body.get('add_category_ids', []):
            attach_category_to_course(db.session, course_id=course.id, category_id=cid)
        return {"status": "success", "type": "course", "action": action, "id": course.id}

    elif action == ActionType.EDIT:
        course_id = body.get('id')
        if not course_id:
            return {"status": "error", "message": "id is required for course edit"}
        updates = {k: body[k] for k in ('course_code', 'name', 'history') if k in body}
        if updates:
            update_course(db.session, course_id=course_id, updates=updates)
        for cid in body.get('add_category_ids', []):
            attach_category_to_course(db.session, course_id=course_id, category_id=cid)
        for cid in body.get('remove_category_ids', []):
            detach_category_from_course(db.session, course_id=course_id, category_id=cid)
        return {"status": "success", "type": "course", "action": action}

    elif action == ActionType.ARCHIVE:
        course_id = body.get('id')
        if not course_id:
            return {"status": "error", "message": "id is required for course archive"}
        archive = body.get('archive', True)
        set_course_active(db.session, course_id=course_id, active=not archive)
        write_history_entry(db.session, Course, course_id, {"event": "archive" if archive else "unarchive"})
        return {"status": "success", "type": "course", "action": action}

    return {"status": "error", "message": f"Unknown action: {action}"}


def handle_category_action(action, body):
    """Execute a CREATE, EDIT, or ARCHIVE operation on a Category.

    Called by both ``batch_mutate`` and the individual REST endpoints.
    Returns a result dict with ``"status": "success"|"error"``.
    """
    if action == ActionType.CREATE:
        name = body.get('name')
        if not name:
            return {"status": "error", "message": "name is required for category creation"}
        category = create_category(db.session, name=name, history=body.get('history'))
        db.session.flush()
        for cid in body.get('course_ids', []):
            attach_category_to_course(db.session, course_id=cid, category_id=category.id)
        return {"status": "success", "type": "category", "action": action, "id": category.id}

    elif action == ActionType.EDIT:
        category_id = body.get('id')
        if not category_id:
            return {"status": "error", "message": "id is required for category edit"}
        updates = {k: body[k] for k in ('name', 'history', 'active') if k in body}
        if updates:
            update_category(db.session, category_id=category_id, updates=updates)
        for cid in body.get('add_course_ids', []):
            attach_category_to_course(db.session, course_id=cid, category_id=category_id)
        for cid in body.get('remove_course_ids', []):
            detach_category_from_course(db.session, course_id=cid, category_id=category_id)
        return {"status": "success", "type": "category", "action": action}

    elif action == ActionType.ARCHIVE:
        category_id = body.get('id')
        if not category_id:
            return {"status": "error", "message": "id is required for category archive"}
        archive = body.get('archive', True)
        set_category_active(db.session, category_id=category_id, active=not archive)
        write_history_entry(db.session, Category, category_id, {"event": "archive" if archive else "unarchive"})
        return {"status": "success", "type": "category", "action": action}

    return {"status": "error", "message": f"Unknown action: {action}"}


_QUESTION_SCALAR_FIELDS = (
    # Core fields
    'id', 'template', 'variables', 'formula', 'unit', 'tolerance', 'hints', 'link', 'active',
    # Answer-behaviour fields (all optional):
    #   round_answer      bool   – Round correct answer to nearest integer before grading/display.
    #   answer_type       str    – "numeric" (default) | "time_of_day" | "duration"
    #   answer_min        float  – Min acceptable generated correct answer; gen retries if below.
    #   answer_max        float  – Max acceptable generated correct answer; gen retries if above.
    #   tolerance_percent float  – Tolerance as % of correct answer (overrides absolute tolerance).
    #   round_to_unit     str    – For duration/time_of_day: round to "s"|"min"|"h"|"d" before grading.
    'round_answer', 'answer_type', 'answer_min', 'answer_max', 'tolerance_percent', 'round_to_unit',
)

_VALID_ANSWER_TYPES = {"numeric", "time_of_day", "duration"}
_VALID_ROUND_TO_UNITS = {"s", "min", "h", "d"}


def _validate_question_body(body):
    """Validate answer-behaviour fields; raise ValueError on bad input."""
    answer_type = body.get('answer_type')
    if answer_type is not None and answer_type not in _VALID_ANSWER_TYPES:
        raise ValueError(
            f"answer_type must be one of: {', '.join(sorted(_VALID_ANSWER_TYPES))}"
        )
    round_to_unit = body.get('round_to_unit')
    if round_to_unit is not None and round_to_unit not in _VALID_ROUND_TO_UNITS:
        raise ValueError(
            f"round_to_unit must be one of: {', '.join(sorted(_VALID_ROUND_TO_UNITS))}"
        )
    unit = body.get('unit')
    if unit and not is_known_unit(unit):
        raise ValueError(
            f"Unknown unit '{unit}'. Add it via the Units admin panel first."
        )


def _validate_template_consistency_from_state(template_text, variables_config, formula):
    """Run the question_gen consistency check on stored-or-incoming template state.

    Performed only at admin write-time so a bad template never surfaces as a
    400 to a student during ``question_post``.
    """
    from logic.question_gen.question_gen_helpers import validate_template_consistency

    if template_text is None or variables_config is None or formula is None:
        return
    if not (isinstance(template_text, str) and template_text.strip()):
        return
    if not (isinstance(formula, str) and formula.strip()):
        return
    validate_template_consistency(
        template_text=template_text,
        variables_config=variables_config,
        formula=formula,
    )


def handle_question_action(action, body):
    """Execute a CREATE, EDIT, or ARCHIVE operation on a QuestionTemplate.

    Validates ``answer_type``, ``round_to_unit``, ``unit`` (must exist in the
    Units table), and template/variable/formula consistency before writing.
    Called by both ``batch_mutate`` and the individual REST endpoints.
    Returns a result dict with ``"status": "success"|"error"``.
    """
    if action == ActionType.CREATE:
        category_id = body.get('category_id')
        if category_id is None:
            category_ids_list = body.get('category_ids', [])
            category_id = category_ids_list[0] if category_ids_list else None
        if not category_id or not isinstance(category_id, int):
            return {"status": "error", "message": "category_id (integer) is required for question creation"}
        try:
            _validate_question_body(body)
            _validate_template_consistency_from_state(
                body.get('template'),
                body.get('variables'),
                body.get('formula'),
            )
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        max_num = db.session.execute(
            select(func.max(QuestionTemplate.question_number)).where(QuestionTemplate.category_id == category_id)
        ).scalar() or 0
        question_number = max_num + 1
        _ANSWER_BEHAVIOR_FIELDS = (
            'round_answer', 'answer_type', 'answer_min', 'answer_max',
            'tolerance_percent', 'round_to_unit',
        )
        template_fields = {
            k: body[k] for k in (
                'template', 'variables', 'formula', 'unit', 'tolerance',
                'hints', 'link', 'active', *_ANSWER_BEHAVIOR_FIELDS
            ) if k in body
        }
        template_fields['question_number'] = question_number
        qt = create_question_template(db.session, template_data=template_fields, category_id=category_id)
        db.session.flush()
        course_ids = body.get('course_ids')
        if course_ids:
            replace_template_courses(db.session, template_id=qt.id, course_ids=course_ids)
        return {"status": "success", "type": "question", "action": action, "id": qt.id}

    elif action == ActionType.EDIT:
        template_id = body.get('id')
        if not template_id or not isinstance(template_id, int):
            return {"status": "error", "message": "id (integer) is required for question edit"}
        try:
            _validate_question_body(body)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        # Merge incoming updates against the persisted record so consistency
        # checks see the post-edit shape, not just the diff.
        existing = db.session.get(QuestionTemplate, template_id)
        if existing is None:
            return {"status": "error", "message": f"QuestionTemplate with id {template_id} not found."}
        merged_template = body['template'] if 'template' in body else existing.template
        merged_variables = body['variables'] if 'variables' in body else existing.variables
        merged_formula = body['formula'] if 'formula' in body else existing.formula
        try:
            _validate_template_consistency_from_state(
                merged_template, merged_variables, merged_formula
            )
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        update_keys = tuple(k for k in _QUESTION_SCALAR_FIELDS if k != 'id')
        updates = {k: body[k] for k in update_keys if k in body}
        if updates:
            update_question_template(db.session, template_id=template_id, updates=updates)
        if 'category_id' in body:
            replace_template_categories(db.session, template_id=template_id, category_id=body['category_id'])
        return {"status": "success", "type": "question", "action": action}

    elif action == ActionType.ARCHIVE:
        template_id = body.get('id')
        if not template_id or not isinstance(template_id, int):
            return {"status": "error", "message": "id (integer) is required for question archive"}
        archive = body.get('archive', True)
        set_question_template_active(db.session, template_id=template_id, active=not archive)
        return {"status": "success", "type": "question", "action": action}

    return {"status": "error", "message": f"Unknown action: {action}"}


def handle_unit_alias_action(action, body):
    """Execute a CREATE, EDIT, or DELETE operation on a UnitAlias.

    All mutations invalidate the shared unit-alias cache immediately.
    Returns a result dict with ``"status": "success"|"error"``.
    """
    if action == ActionType.CREATE:
        unit_id = body.get('unit_id')
        alias = body.get('alias')
        if not unit_id or not alias:
            return {"status": "error", "message": "unit_id and alias are required for unit alias creation"}
        unit_alias = create_unit_alias(db.session, unit_id=unit_id, alias=alias)
        db.session.flush()
        invalidate_unit_cache()
        return {"status": "success", "type": "unit_alias", "action": action, "id": unit_alias.id}

    elif action == ActionType.EDIT:
        alias_id = body.get('id')
        alias = body.get('alias')
        if not alias_id:
            return {"status": "error", "message": "id is required for unit alias edit"}
        if not alias:
            return {"status": "error", "message": "alias is required for unit alias edit"}
        update_unit_alias(db.session, alias_id=alias_id, alias=alias)
        invalidate_unit_cache()
        return {"status": "success", "type": "unit_alias", "action": action}

    elif action == ActionType.ARCHIVE:
        alias_id = body.get('id')
        if not alias_id:
            return {"status": "error", "message": "id is required for unit alias delete"}
        delete_unit_alias(db.session, alias_id=alias_id)
        invalidate_unit_cache()
        return {"status": "success", "type": "unit_alias", "action": action}

    return {"status": "error", "message": f"Unknown action: {action}"}


def handle_unit_action(action, body):
    """Execute a CREATE, EDIT, or ARCHIVE operation on a Unit.

    All mutations invalidate the shared unit-alias cache immediately.
    Returns a result dict with ``"status": "success"|"error"``.
    """
    if action == ActionType.CREATE:
        name = body.get('name')
        if not name:
            return {"status": "error", "message": "name is required for unit creation"}
        unit = create_unit(db.session, name=name, active=body.get('active', True))
        db.session.flush()
        invalidate_unit_cache()
        return {"status": "success", "type": "unit", "action": action, "id": unit.id}

    elif action == ActionType.EDIT:
        unit_id = body.get('id')
        if not unit_id:
            return {"status": "error", "message": "id is required for unit edit"}
        updates = {k: body[k] for k in ('name', 'active') if k in body}
        if updates:
            update_unit(db.session, unit_id=unit_id, updates=updates)
        invalidate_unit_cache()
        return {"status": "success", "type": "unit", "action": action}

    elif action == ActionType.ARCHIVE:
        unit_id = body.get('id')
        if not unit_id:
            return {"status": "error", "message": "id is required for unit archive"}
        archive = body.get('archive', True)
        set_unit_active(db.session, unit_id=unit_id, active=not archive)
        invalidate_unit_cache()
        return {"status": "success", "type": "unit", "action": action}

    return {"status": "error", "message": f"Unknown action: {action}"}


# ─── REST admin endpoints ─────────────────────────────────────────────────────
# Conventional REST replacements for the integer-dispatch ``POST /admin/mutate``
# command bus. New clients should target these; ``/admin/mutate`` stays
# registered for backwards-compat until the frontend has fully migrated.

def _rest_run(handler, action, body):
    """Run a single ``handle_*_action`` call inside its own DB transaction.

    Mirrors what ``batch_mutate`` does for one operation, including the
    common cache-invalidation hook.
    """
    try:
        result = handler(action, body)
        if isinstance(result, dict) and result.get("status") == "error":
            db.session.rollback()
            return jsonify({"error": result.get("message", "Bad request")}), 400
        db.session.commit()
    except (ValueError, SQLAlchemyError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:  # noqa: BLE001
        db.session.rollback()
        logger.exception("REST admin handler failed")
        return jsonify({"error": "Internal server error"}), 500

    invalidate_cat_request_cache()
    return jsonify(result), 200


def _body() -> dict:
    """Parse the JSON request body, returning an empty dict on failure."""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


# Courses
@admin_bp.post('/api/admin/courses')
@require_admin
def rest_create_course():
    """POST /api/admin/courses — create a course."""
    return _rest_run(handle_course_action, ActionType.CREATE, _body())


@admin_bp.patch('/api/admin/courses/<int:course_id>')
@require_admin
def rest_update_course(course_id: int):
    """PATCH /api/admin/courses/<id> — update course fields."""
    body = {**_body(), "id": course_id}
    return _rest_run(handle_course_action, ActionType.EDIT, body)


@admin_bp.post('/api/admin/courses/<int:course_id>/archive')
@require_admin
def rest_archive_course(course_id: int):
    """POST /api/admin/courses/<id>/archive — archive or unarchive a course."""
    body = {**_body(), "id": course_id}
    body.setdefault("archive", True)
    return _rest_run(handle_course_action, ActionType.ARCHIVE, body)


# Categories
@admin_bp.post('/api/admin/categories')
@require_admin
def rest_create_category():
    """POST /api/admin/categories — create a category."""
    return _rest_run(handle_category_action, ActionType.CREATE, _body())


@admin_bp.patch('/api/admin/categories/<int:category_id>')
@require_admin
def rest_update_category(category_id: int):
    """PATCH /api/admin/categories/<id> — update category fields."""
    body = {**_body(), "id": category_id}
    return _rest_run(handle_category_action, ActionType.EDIT, body)


@admin_bp.post('/api/admin/categories/<int:category_id>/archive')
@require_admin
def rest_archive_category(category_id: int):
    """POST /api/admin/categories/<id>/archive — archive or unarchive a category."""
    body = {**_body(), "id": category_id}
    body.setdefault("archive", True)
    return _rest_run(handle_category_action, ActionType.ARCHIVE, body)


# Questions
@admin_bp.post('/api/admin/questions')
@require_admin
def rest_create_question():
    """POST /api/admin/questions — create a question template."""
    return _rest_run(handle_question_action, ActionType.CREATE, _body())


@admin_bp.get('/api/admin/questions/<int:question_id>')
@require_admin
def rest_get_question(question_id: int):
    """GET /api/admin/questions/<id> — fetch a single question template.

    Replaces ``GET /admin/entity/2/<id>`` for question reads.
    """
    return get_entity(int(EntityType.QUESTION), str(question_id))


@admin_bp.patch('/api/admin/questions/<int:question_id>')
@require_admin
def rest_update_question(question_id: int):
    """PATCH /api/admin/questions/<id> — update question template fields."""
    body = {**_body(), "id": question_id}
    return _rest_run(handle_question_action, ActionType.EDIT, body)


@admin_bp.post('/api/admin/questions/<int:question_id>/archive')
@require_admin
def rest_archive_question(question_id: int):
    """POST /api/admin/questions/<id>/archive — archive or unarchive a question."""
    body = {**_body(), "id": question_id}
    body.setdefault("archive", True)
    return _rest_run(handle_question_action, ActionType.ARCHIVE, body)


# Units
@admin_bp.post('/api/admin/units')
@require_admin
def rest_create_unit():
    """POST /api/admin/units — create a unit."""
    return _rest_run(handle_unit_action, ActionType.CREATE, _body())


@admin_bp.patch('/api/admin/units/<int:unit_id>')
@require_admin
def rest_update_unit(unit_id: int):
    """PATCH /api/admin/units/<id> — update unit fields."""
    body = {**_body(), "id": unit_id}
    return _rest_run(handle_unit_action, ActionType.EDIT, body)


@admin_bp.post('/api/admin/units/<int:unit_id>/archive')
@require_admin
def rest_archive_unit(unit_id: int):
    """POST /api/admin/units/<id>/archive — archive or unarchive a unit."""
    body = {**_body(), "id": unit_id}
    body.setdefault("archive", True)
    return _rest_run(handle_unit_action, ActionType.ARCHIVE, body)


# Unit aliases
@admin_bp.post('/api/admin/unit-aliases')
@require_admin
def rest_create_unit_alias():
    """POST /api/admin/unit-aliases — create a unit alias."""
    return _rest_run(handle_unit_alias_action, ActionType.CREATE, _body())


@admin_bp.patch('/api/admin/unit-aliases/<int:alias_id>')
@require_admin
def rest_update_unit_alias(alias_id: int):
    """PATCH /api/admin/unit-aliases/<id> — update a unit alias string."""
    body = {**_body(), "id": alias_id}
    return _rest_run(handle_unit_alias_action, ActionType.EDIT, body)


@admin_bp.delete('/api/admin/unit-aliases/<int:alias_id>')
@require_admin
def rest_delete_unit_alias(alias_id: int):
    """DELETE /api/admin/unit-aliases/<id> — delete a unit alias."""
    body = {"id": alias_id}
    return _rest_run(handle_unit_alias_action, ActionType.ARCHIVE, body)
