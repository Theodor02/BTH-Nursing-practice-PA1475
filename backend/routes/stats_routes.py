"""Statistics endpoints for both admins and students.

Admin endpoints (/api/admin/stats/*) return fully anonymous aggregate data —
no user identifiers ever appear in their responses. They require Admin or
SuperAdmin role.

User endpoints (/api/stats/*) return data scoped to the authenticated user only.
All date windows default to an open-ended all-time query when no ?days= param is
supplied.
"""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from logic.auth import get_current_user_id, require_admin, require_auth
from logic.database.init.init_db import db
from logic.database.operations.sql_stats import (
    get_admin_category_stats,
    get_admin_course_stats,
    get_admin_overview_stats,
    get_admin_question_stats,
    get_user_activity_stats,
    get_user_mastery_stats,
    get_user_overview_stats,
)

stats_bp = Blueprint("stats", __name__)

_DEFAULT_ADMIN_WINDOW_DAYS = 90
_VALID_SORT_BY = {"accuracy", "attempts"}
_MAX_QUESTION_LIMIT = 200


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _parse_date_range(args):
    """
    Parse ?from_date=YYYY-MM-DD &to_date=YYYY-MM-DD from request.args.

    Defaults:
      from_date → today - 90 days, midnight
      to_date   → end of today (23:59:59)

    to_dt is set to 23:59:59 so sessions created at any point on the
    to_date day are included in queries using `<= to_dt`.

    Returns:
        (from_dt: datetime, to_dt: datetime)

    Raises:
        ValueError if either param is present but not a valid YYYY-MM-DD date.
    """
    today = datetime.now(timezone.utc).date()
    default_from = today - timedelta(days=_DEFAULT_ADMIN_WINDOW_DAYS)

    from_str = args.get("from_date")
    to_str = args.get("to_date")

    if from_str:
        from_date = datetime.strptime(from_str, "%Y-%m-%d").date()
    else:
        from_date = default_from

    if to_str:
        to_date = datetime.strptime(to_str, "%Y-%m-%d").date()
    else:
        to_date = today

    from_dt = datetime(from_date.year, from_date.month, from_date.day, 0, 0, 0)
    to_dt = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59)
    return from_dt, to_dt


def _period_obj(from_dt: datetime, to_dt: datetime) -> dict:
    """Return a ``{"from": ..., "to": ...}`` dict with ISO date strings for the response body."""
    return {
        "from": from_dt.date().isoformat(),
        "to": to_dt.date().isoformat(),
    }


def _parse_positive_int(args, key: str) -> int | None:
    """
    Parse an optional positive-integer query param.

    Returns the parsed value if present, None if absent.
    Raises ValueError if present but invalid or non-positive.
    """
    if key not in args:
        return None
    try:
        val = int(args[key])
    except (ValueError, TypeError):
        raise ValueError(f"{key} must be a positive integer.")
    if val <= 0:
        raise ValueError(f"{key} must be a positive integer.")
    return val


# ─── Admin endpoints ──────────────────────────────────────────────────────────

@stats_bp.get("/api/admin/stats/overview")
@require_admin
def admin_stats_overview():
    """
    GET /admin/stats/overview

    Platform-wide aggregate statistics for a configurable time window.
    Fully anonymous — no user identifiers in response.

    Query params:
        from_date  (str, optional)  YYYY-MM-DD. Default: 90 days ago.
        to_date    (str, optional)  YYYY-MM-DD. Default: today.

    Response 200:
        {
          "period": {
            "from": "2024-01-01",
            "to":   "2024-04-28"
          },
          "total_sessions":           1250,
          "total_questions_answered": 8750,
          "total_correct":            6125,
          "overall_accuracy_pct":     70.0,   // null if no questions answered
          "active_courses":           4,
          "active_categories":        12
        }
    """
    try:
        from_dt, to_dt = _parse_date_range(request.args)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    stats = get_admin_overview_stats(db.session, from_dt, to_dt)
    return jsonify({"period": _period_obj(from_dt, to_dt), **stats})


@stats_bp.get("/api/admin/stats/courses")
@require_admin
def admin_stats_courses():
    """
    GET /admin/stats/courses

    Per-course aggregate statistics, ordered hardest-first (lowest accuracy_pct).
    Fully anonymous — no user identifiers in response.

    Query params:
        from_date  (str, optional)  YYYY-MM-DD. Default: 90 days ago.
        to_date    (str, optional)  YYYY-MM-DD. Default: today.

    Response 200:
        {
          "period": {"from": "...", "to": "..."},
          "courses": [
            {
              "course_id":          1,
              "course_code":        "OM125G",
              "course_name":        "Omvårdnad",
              "session_count":      420,
              "questions_answered": 2940,
              "correct_count":      2058,
              "accuracy_pct":       70.0,  // null if no questions answered
              "avg_score":          70.0   // mean Session.score; null if no sessions
            }
          ]
        }
    """
    try:
        from_dt, to_dt = _parse_date_range(request.args)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    courses = get_admin_course_stats(db.session, from_dt, to_dt)
    return jsonify({"period": _period_obj(from_dt, to_dt), "courses": courses})


@stats_bp.get("/api/admin/stats/categories")
@require_admin
def admin_stats_categories():
    """
    GET /admin/stats/categories

    Per-category aggregate statistics with linked course metadata, ordered
    hardest-first. Fully anonymous — no user identifiers in response.

    Note: linked_courses reflects all courses the category belongs to in the
    schema, not just the course filtered by course_id.

    Query params:
        from_date   (str, optional)  YYYY-MM-DD. Default: 90 days ago.
        to_date     (str, optional)  YYYY-MM-DD. Default: today.
        course_id   (int, optional)  Filter sessions to a specific course.

    Response 200:
        {
          "period": {"from": "...", "to": "..."},
          "categories": [
            {
              "category_id":        1,
              "category_name":      "Dosberäkning",
              "session_count":      280,
              "questions_answered": 1960,
              "correct_count":      1372,
              "accuracy_pct":       70.0,
              "avg_score":          70.0,
              "linked_courses": [
                {
                  "course_id":   1,
                  "course_code": "OM125G",
                  "course_name": "Omvårdnad"
                }
              ]
            }
          ]
        }
    """
    try:
        from_dt, to_dt = _parse_date_range(request.args)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    try:
        course_id = _parse_positive_int(request.args, "course_id")
    except ValueError:
        return jsonify({"error": "course_id must be a positive integer."}), 400

    categories = get_admin_category_stats(
        db.session, from_dt, to_dt, course_id=course_id
    )
    return jsonify({"period": _period_obj(from_dt, to_dt), "categories": categories})


@stats_bp.get("/api/admin/stats/questions")
@require_admin
def admin_stats_questions():
    """
    GET /admin/stats/questions

    Per-question-template difficulty statistics, derived by unnesting the
    per-session answer JSONB. Fully anonymous — no user identifiers in response.

    Query params:
        from_date    (str, optional)  YYYY-MM-DD. Default: 90 days ago.
        to_date      (str, optional)  YYYY-MM-DD. Default: today.
        course_id    (int, optional)  Filter sessions to a specific course.
        category_id  (int, optional)  Filter sessions to a specific category.
        sort_by      (str, optional)  "accuracy" (default) — hardest-first.
                                      "attempts"           — most-attempted-first.
        limit        (int, optional)  Max results. Range 1–200. Default 50.

    Response 200:
        {
          "period": {"from": "...", "to": "..."},
          "questions": [
            {
              "template_id":   "Mek_1_1",
              "template_text": "A patient needs ...",
              "unit":          "ml",           // null if template has no unit
              "attempt_count": 450,
              "correct_count": 270,
              "accuracy_pct":  60.0,           // null if attempt_count == 0
              "difficulty":    "medium",       // "easy" ≥80%, "medium" 50–79%, "hard" <50%
              "categories": [
                {"category_id": 1, "name": "Dosberäkning"}
              ],
              "courses": [
                {"course_id": 1, "course_code": "OM125G", "name": "Omvårdnad"}
              ]
            }
          ]
        }

    Notes:
        - template_text / unit / categories / courses will be null / empty if the
          QuestionTemplate has been deleted since the session was recorded.
        - Only question instances with a recorded is_correct value are counted
          (unanswered questions are excluded).
    """
    try:
        from_dt, to_dt = _parse_date_range(request.args)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    sort_by = request.args.get("sort_by", "accuracy")
    if sort_by not in _VALID_SORT_BY:
        return jsonify({"error": "sort_by must be 'accuracy' or 'attempts'."}), 400

    try:
        limit_raw = request.args.get("limit", "50")
        limit = int(limit_raw)
        if not 1 <= limit <= _MAX_QUESTION_LIMIT:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "limit must be an integer between 1 and 200."}), 400

    try:
        course_id = _parse_positive_int(request.args, "course_id")
    except ValueError:
        return jsonify({"error": "course_id must be a positive integer."}), 400

    try:
        category_id = _parse_positive_int(request.args, "category_id")
    except ValueError:
        return jsonify({"error": "category_id must be a positive integer."}), 400

    questions = get_admin_question_stats(
        db.session,
        from_dt,
        to_dt,
        course_id=course_id,
        category_id=category_id,
        sort_by=sort_by,
        limit=limit,
    )
    return jsonify({"period": _period_obj(from_dt, to_dt), "questions": questions})


# ─── User endpoints ───────────────────────────────────────────────────────────

@stats_bp.get("/api/stats/overview")
@require_auth
def user_stats_overview():
    """
    GET /stats/overview

    Personal performance summary for the authenticated user.

    Query params:
        days (int, optional) Number of past days to include. 0 or empty for all-time.

    Response 200:
        {
          "period": { "from": "...", "to": "..." }, // from and to are null if all-time
          "user_id": 42,
          "total_sessions":             25,
          "total_questions":            175,
          "overall_accuracy_pct":       74.3,   // null if no questions answered
          "current_streak":             7,      // consecutive days ending today or yesterday
          "longest_streak":             14,
          "best_category": {                    // null if user has no sessions
            "category_id":  3,
            "name":         "Enhetsbyte",
            "accuracy_pct": 95.0
          },
          "worst_category": {                   // null if user has no sessions
            "category_id":  2,
            "name":         "Infusion",
            "accuracy_pct": 41.7
          },
          "estimated_practice_minutes": 210     // total_questions * 1.2, rounded
        }
    """
    days_str = request.args.get("days")
    from_dt = None
    to_dt = None
    if days_str:
        try:
            days = int(days_str)
            if days > 0:
                today = datetime.now(timezone.utc).date()
                from_date = today - timedelta(days=days)
                from_dt = datetime(from_date.year, from_date.month, from_date.day, 0, 0, 0)
                to_dt = datetime(today.year, today.month, today.day, 23, 59, 59)
        except ValueError:
            pass

    user_id = get_current_user_id()
    stats = get_user_overview_stats(db.session, user_id, from_dt, to_dt)
    stats["period"] = {
        "from": from_dt.date().isoformat() if from_dt else None,
        "to": to_dt.date().isoformat() if to_dt else None,
    }
    return jsonify({"user_id": user_id, **stats})


@stats_bp.get("/api/stats/mastery")
@require_auth
def user_stats_mastery():
    """
    GET /stats/mastery

    Per-course, per-category mastery for the authenticated user.

    mastery_pct is the mean Session.score (0–100) over all of the user's
    sessions for that course + category combination. The course-level
    mastery_pct is a session-count-weighted average of its categories.

    Query params:
        days (int, optional) Number of past days to include. 0 or empty for all-time.

    Response 200:
        {
          "period": { "from": "...", "to": "..." }, // from and to are null if all-time
          "user_id": 42,
          "courses": [
            {
              "course_id":     1,
              "course_code":   "OM125G",
              "course_name":   "Omvårdnad",
              "session_count": 10,
              "mastery_pct":   74.0,
              "categories": [
                {
                  "category_id":    1,
                  "category_name":  "Dosberäkning",
                  "session_count":  5,
                  "mastery_pct":    82.0,
                  "last_practiced": "2024-04-25T10:30:00"   // ISO 8601
                }
              ]
            }
          ]
        }
    """
    days_str = request.args.get("days")
    from_dt = None
    to_dt = None
    if days_str:
        try:
            days = int(days_str)
            if days > 0:
                today = datetime.now(timezone.utc).date()
                from_date = today - timedelta(days=days)
                from_dt = datetime(from_date.year, from_date.month, from_date.day, 0, 0, 0)
                to_dt = datetime(today.year, today.month, today.day, 23, 59, 59)
        except ValueError:
            pass

    user_id = get_current_user_id()
    courses = get_user_mastery_stats(db.session, user_id, from_dt, to_dt)

    period = {
        "from": from_dt.date().isoformat() if from_dt else None,
        "to": to_dt.date().isoformat() if to_dt else None,
    }
    
    return jsonify({"period": period, "user_id": user_id, "courses": courses})


@stats_bp.get("/api/stats/activity")
@require_auth
def user_stats_activity():
    """
    GET /stats/activity

    Daily session counts for the authenticated user over the past N weeks.
    Every calendar day in the window is present, including zero-session days.
    Suitable for rendering a contribution-style heatmap.

    Query params:
        weeks  (int, optional)  Weeks of history to return (1–52). Default 14.
                                Values outside range are silently clamped.

    Response 200:
        {
          "user_id": 42,
          "weeks":   14,
          "days": [
            {"date": "2024-01-29", "session_count": 0},
            {"date": "2024-01-30", "session_count": 2},
            ...
          ]
        }
        Length of "days" is always weeks * 7, ordered oldest → newest.
    """
    user_id = get_current_user_id()

    try:
        weeks = int(request.args.get("weeks", 14))
    except (ValueError, TypeError):
        weeks = 14
    weeks = max(1, min(52, weeks))

    days = get_user_activity_stats(db.session, user_id, weeks=weeks)
    return jsonify({"user_id": user_id, "weeks": weeks, "days": days})
