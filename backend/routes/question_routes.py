"""Quiz question generation, per-question grading, and attempt submission.

The three endpoints form a session lifecycle:
  1. POST /api/questions       — generate questions, get attempt_id
  2. POST /api/questions/grade — grade a single question for immediate feedback
                                 (attempt stays open, not consumed)
  3. POST /api/attempts/submit — submit all answers, grade everything, persist
                                 a Session row, consume the attempt

Pending attempts are stored in Redis keyed by UUID. The attempt is popped
(consumed) on submit so the same attempt_id cannot be submitted twice.
"""
import logging

import sqlalchemy as sa
from flask import Blueprint, jsonify, request

from config import (
    _MAX_CATEGORIES_PER_COURSE,
    _MAX_CATEGORY_NAME_LEN,
    _MAX_COURSE_CODE_LEN,
    _MAX_COURSES_PER_REQUEST,
    _MAX_QUESTIONS_PER_CATEGORY,
    _MAX_QUESTIONS_TOTAL,
)
from logic.auth import get_current_user_id, require_auth
from logic.database.init.init_db import db
from logic.database.operations.sql_getters import (
    retrieve_active_question_templates_by_course_and_category,
    retrieve_active_template_count_by_course_and_category,
    retrieve_category_by_name_and_course_id,
    retrieve_course_by_code,
)
from logic.database.operations.sql_setters import create_session
from logic.answer_utils import (
    format_answer_for_display,
    format_duration_for_display,
    normalize_unit,
    parse_duration,
    parse_numeric_answer,
    parse_numeric_with_unit,
)
from logic.grader import grade_attempt
from logic.pending_attempts import PendingAttemptsManager
from logic.question_gen.question_gen import build_generated_payload

logger = logging.getLogger(__name__)

question_bp = Blueprint('question', __name__)
_pending = PendingAttemptsManager()


@question_bp.post('/api/questions')
@require_auth
def question_post():
    """Generate a set of randomised questions and register a pending attempt.

    Validates the request against config limits, fetches randomly-sampled active
    templates, generates question instances (variable substitution + formula
    evaluation), and stores the attempt in Redis keyed by a UUID.

    The pending attempt is consumed once by POST /api/attempts/submit. Attempts
    expire after PENDING_ATTEMPT_TTL seconds (default 1 hour), so a student
    abandoning a quiz mid-way does not leave stale state indefinitely.
    """
    payload = request.get_json(silent=True) or {}
    questions_request = payload.get("questions_request", {})
    course_requests = questions_request.get("course", {})

    if not isinstance(course_requests, dict) or not course_requests:
        return jsonify(
            {'error': 'Invalid payload: expected '
             'questions_request.course object'}
        ), 400

    if len(course_requests) > _MAX_COURSES_PER_REQUEST:
        return jsonify(
            {'error': f'Too many courses in request '
             f'(max {_MAX_COURSES_PER_REQUEST})'}
        ), 400

    selected_templates = {}
    total_questions = 0
    first_course_id = None
    first_category_id = None
    all_category_ids = []

    for course_code, category_requests in course_requests.items():
        if (
            not isinstance(course_code, str)
            or len(course_code) > _MAX_COURSE_CODE_LEN
        ):
            return jsonify({'error': 'Invalid course code'}), 400

        course = retrieve_course_by_code(db.session, course_code)
        if course is None:
            return jsonify(
                {'error': f'Unknown course code: {course_code}'}
            ), 400

        if not isinstance(category_requests, dict):
            return jsonify(
                {'error': f'Invalid category map for course: '
                 f'{course_code}'}
            ), 400

        if len(category_requests) > _MAX_CATEGORIES_PER_COURSE:
            return jsonify(
                {'error': f'Too many categories for course: '
                 f'{course_code} (max {_MAX_CATEGORIES_PER_COURSE})'}
            ), 400

        selected_templates[course_code] = {}

        for category_name, requested_count in (
            category_requests.items()
        ):
            if (
                not isinstance(category_name, str)
                or len(category_name) > _MAX_CATEGORY_NAME_LEN
            ):
                return jsonify(
                    {'error': f'Invalid category name for course: '
                     f'{course_code}'}
                ), 400

            if (
                not isinstance(requested_count, int)
                or requested_count < 0
            ):
                return jsonify(
                    {'error': f'Invalid requested count for '
                     f'{course_code}/{category_name}'}
                ), 400

            if requested_count > _MAX_QUESTIONS_PER_CATEGORY:
                return jsonify(
                    {'error': f'Requested count too high for '
                     f'{course_code}/{category_name} '
                     f'(max {_MAX_QUESTIONS_PER_CATEGORY})'}
                ), 400

            total_questions += requested_count
            if total_questions > _MAX_QUESTIONS_TOTAL:
                return jsonify(
                    {'error': f'Total questions requested exceeds '
                     f'limit of {_MAX_QUESTIONS_TOTAL}'}
                ), 400

            category = retrieve_category_by_name_and_course_id(
                db.session, category_name, course["id"]
            )
            if category is None:
                return jsonify(
                    {'error': f'Unknown category for course: '
                     f'{course_code}/{category_name}'}
                ), 400

            if requested_count > 0:
                if first_course_id is None:
                    first_course_id = course["id"]
                    first_category_id = category["id"]
                all_category_ids.append(category["id"])

            templates = (
                retrieve_active_question_templates_by_course_and_category(
                    session=db.session,
                    course_id=course["id"],
                    category_id=category["id"],
                    limit=requested_count,
                )
            )
            if len(templates) < requested_count:
                available_count = (
                    retrieve_active_template_count_by_course_and_category(
                        db.session, course["id"], category["id"]
                    )
                )
                return jsonify(
                    {'error': f'Requested {requested_count} questions '
                     f'for {course_code}/{category_name}, only '
                     f'{available_count} available'}
                ), 400
            selected_templates[course_code][category_name] = (
                templates
            )

    if total_questions <= 0:
        return jsonify(
            {'error': 'At least one question must be requested'}
        ), 400

    try:
        generated_questions, question_snapshots = (
            build_generated_payload(selected_templates)
        )
    except ValueError as exc:
        return jsonify(
            {'error': f'Invalid question template configuration: '
             f'{exc}'}
        ), 400

    user_id = get_current_user_id()
    if first_course_id is None or first_category_id is None:
        return jsonify(
            {'error': 'Could not determine course/category for '
             'requested questions'}
        ), 400

    attempt_id = _pending.store(
        user_id=user_id,
        course_id=first_course_id,
        category_id=first_category_id,
        category_ids=all_category_ids,
        question_snapshots=question_snapshots,
    )

    return jsonify({
        'attempt_id': attempt_id,
        'questions': generated_questions,
    })


@question_bp.post('/api/questions/grade')
@require_auth
def grade_question():
    """Grade a single question within an active attempt.

    Returns per-component feedback: correctValue (numeric proximity), correctUnit, and
    correctAnswer formatted for display — trailing .0 stripped for numeric answers,
    HH:MM format for time_of_day answers, compact string (e.g. "2h 30min") for duration answers.
    """
    payload = request.get_json(silent=True) or {}
    attempt_id = payload.get('attempt_id')
    question_id = payload.get('question_id')
    user_answer = payload.get('user_answer')

    if not isinstance(attempt_id, str) or not attempt_id.strip():
        return jsonify({'error': 'grade_question requires attempt_id'}), 400
    if not isinstance(question_id, str) or not question_id.strip():
        return jsonify({'error': 'grade_question requires question_id'}), 400

    user_id = get_current_user_id()
    attempt = _pending.get(attempt_id)
    if attempt is None:
        return jsonify({'error': 'Attempt not found or expired'}), 404
    if attempt.get('user_id') != user_id:
        return jsonify(
            {'error': 'Attempt does not belong to authenticated user'}
        ), 403

    snapshot = attempt.get('question_snapshots', {}).get(question_id)
    if snapshot is None:
        return jsonify({'error': 'Question not found in attempt'}), 404

    # Route single-question grading through the same grader as submit.
    result = grade_attempt(
        {question_id: dict(snapshot)},
        {question_id: user_answer},
    )
    graded_snapshot = result.question_snapshots.get(question_id, {})

    is_correct = graded_snapshot.get('is_correct')
    correct = bool(is_correct)
    answer_type = graded_snapshot.get('answer_type', 'numeric') or 'numeric'

    # Derive per-component feedback from authoritative graded snapshot.
    # Re-parse user and correct values to report correctValue / correctUnit separately.
    tolerance_val = max(parse_numeric_answer(graded_snapshot.get('tolerance')) or 0.0, 0.0)

    if answer_type == "duration":
        correct_secs = parse_duration(graded_snapshot.get('correct_answer'))
        user_secs = parse_duration(user_answer)
        correct_value = (
            user_secs is not None
            and correct_secs is not None
            and abs(user_secs - correct_secs) <= tolerance_val
        )
        has_unit = False
        correct_unit = True
        display_answer = format_duration_for_display(correct_secs)
    else:
        correct_number, correct_unit_str = parse_numeric_with_unit(
            graded_snapshot.get('correct_answer')
        )
        correct_answer_raw = parse_numeric_answer(correct_number)

        user_number, user_unit = parse_numeric_with_unit(user_answer)
        user_unit = normalize_unit(user_unit, allow_blank_alias=True)
        normalized_correct_unit = normalize_unit(correct_unit_str) or normalize_unit(
            graded_snapshot.get('unit')
        )
        has_unit = bool(normalized_correct_unit)

        correct_value = (
            user_number is not None
            and correct_answer_raw is not None
            and abs(user_number - correct_answer_raw) <= tolerance_val
        )
        correct_unit = (
            not has_unit
            or user_unit == normalized_correct_unit
        )

        # Format the correct answer for display (strips .0, converts time_of_day to HH:MM).
        display_answer = format_answer_for_display(correct_answer_raw, answer_type)

    return jsonify({
        'correct': correct,
        'correctValue': correct_value,
        'correctAnswer': display_answer,
        'hasUnit': has_unit,
        'correctUnit': correct_unit,
    })


@question_bp.post('/api/attempts/submit')
@require_auth
def question_submit():
    """Grade and persist a completed quiz attempt.

    Pops (consume-once) the pending attempt from Redis, grades every submitted
    answer, and writes a Session row. Popping is atomic — a duplicate submit
    with the same attempt_id returns 404, preventing double-scoring.
    """
    payload = request.get_json(silent=True) or {}
    attempt_id = payload.get('attempt_id')
    answers = payload.get('answers')

    if not isinstance(attempt_id, str) or not attempt_id.strip():
        return jsonify(
            {'error': 'question_submit requires a non-empty '
             'attempt_id'}
        ), 400

    if not isinstance(answers, dict):
        return jsonify(
            {'error': 'question_submit requires answers to be an '
             'object keyed by question id'}
        ), 400

    user_id = get_current_user_id()

    attempt = _pending.pop(attempt_id)
    if attempt is None:
        return jsonify(
            {'error': 'Attempt not found or expired'}
        ), 404

    if attempt.get('user_id') != user_id:
        return jsonify(
            {'error': 'Attempt does not belong to authenticated user'}
        ), 403

    question_snapshots = attempt.get('question_snapshots') or {}
    if (
        not isinstance(question_snapshots, dict)
        or not question_snapshots
    ):
        return jsonify(
            {'error': 'Stored attempt has no questions'}
        ), 400

    result = grade_attempt(question_snapshots, answers)

    course_id = attempt.get('course_id')
    category_id = attempt.get('category_id')
    category_ids = attempt.get('category_ids') or [category_id]
    if (
        not isinstance(course_id, int)
        or not isinstance(category_id, int)
    ):
        return jsonify(
            {'error': 'Stored attempt is missing course/category '
             'metadata'}
        ), 400

    try:
        created_session = create_session(
            db.session,
            user_id=user_id,
            course_id=course_id,
            category_id=category_id,
            questions={
                'attempt_id': attempt_id,
                'category_ids': category_ids,
                'questions': result.question_snapshots,
                'summary': {
                    'answered_count': result.answered_count,
                    'scored_count': result.scored_count,
                    'correct_count': result.correct_count,
                    'score': result.score,
                },
            },
            score=result.score,
        )
        db.session.commit()
    except (ValueError, sa.exc.SQLAlchemyError):
        logger.exception("Failed to persist session result")
        db.session.rollback()
        return jsonify(
            {'error': 'Unable to persist session result'}
        ), 500

    return jsonify({
        'session_id': created_session.id,
        'score': result.score,
        'correct_count': result.correct_count,
        'scored_count': result.scored_count,
        'answered_count': result.answered_count,
    })
