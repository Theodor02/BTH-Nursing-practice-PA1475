"""Session history endpoints.

Returns completed quiz attempts for the authenticated user. Raw JSONB data
stored in the DB is not modified — answer formatting (seconds → "2h", minutes →
"17:30") happens only when building the HTTP response.
"""
from flask import Blueprint, jsonify

from logic.answer_utils import format_answer_for_display
from logic.auth import get_current_user_id, require_auth
from logic.database.init.init_db import db
from logic.database.operations.sql_getters import (
    retrieve_session_by_user_id_and_session_id,
    retrieve_sessions_by_user_id,
)

session_bp = Blueprint('session', __name__)


def _format_session_answers(session: dict) -> dict:
    """Format correct_answer values for display in history.

    Duration answers are stored as raw seconds; time_of_day as minutes since midnight.
    This converts them to human-readable strings so the history page shows e.g. "2h" not 7200.
    The raw JSONB in the DB is not modified — formatting happens only in the response.
    """
    qs = (session.get("questions") or {}).get("questions") or {}
    for q in qs.values():
        if not isinstance(q, dict):
            continue
        atype = q.get("answer_type", "numeric") or "numeric"
        if atype in ("duration", "time_of_day"):
            q["correct_answer"] = format_answer_for_display(q.get("correct_answer"), atype)
    return session


@session_bp.get('/api/sessions')
@require_auth
def session_request():
    """
    GET /session_request

    Returns all sessions for the authenticated user.

    Response 200:
    {
      "user_id": <int>,
      "sessions": [
        {
          "id":            <int>,
          "user_id":       <int>,
          "course_id":     <int>,
          "category_id":   <int>,
          "course_code":   <str>,   e.g. "MEK101"
          "category_name": <str>,   e.g. "Mechanics"
          "questions":     <object>,  -- per-question snapshots; correct_answer for
                                         duration/time_of_day is formatted for display
                                         (e.g. "2h", "17:30") not raw seconds/minutes
          "score":         <str>,
          "created_at":    <datetime>
        },
        ...
      ]
    }

    Response 401: { "error": "Authentication required" }
    """
    user_id = get_current_user_id()
    sessions = retrieve_sessions_by_user_id(db.session, user_id)
    return jsonify({
        'user_id': user_id,
        'sessions': [_format_session_answers(s) for s in sessions],
    })


@session_bp.get('/api/sessions/<int:session_id>')
@require_auth
def session_get(session_id: int):
    """GET /api/sessions/<session_id> — return a single session for the authenticated user."""
    if session_id <= 0:
        return jsonify({'error': 'session_id must be a positive integer'}), 400
    user_id = get_current_user_id()
    user_session = retrieve_session_by_user_id_and_session_id(db.session, user_id, session_id)
    if user_session is None:
        return jsonify({'error': 'Session not found for authenticated user'}), 404
    return jsonify({
        'user_id': user_id,
        'session': _format_session_answers(user_session),
    })


