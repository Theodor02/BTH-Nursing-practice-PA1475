"""Analytics queries for admin dashboards and user progress views.

Admin functions are fully anonymous — they aggregate across all users without
exposing individual identifiers. The caller is responsible for enforcing role
checks before invoking them.

Per-question stats use raw SQL with jsonb_each() to unnest the JSONB question
blob directly in Postgres, which is far cheaper than loading every session row
into Python and iterating there.

Per-category stats for admins use Python-side aggregation (not SQL) because
a single session can span multiple categories — counting at the SQL level would
double-count sessions that include questions from more than one category.
"""
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import Date, Float, Integer, cast, distinct, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as SQLSession

from logic.database.init.class_db import Category, Course, QuestionTemplate, Session

logger = logging.getLogger(__name__)


def _scored_count_expr():
    """SQLAlchemy expression: JSONB summary.scored_count cast to INTEGER."""
    return func.coalesce(
        cast(Session.questions['summary']['scored_count'].as_string(), Integer),
        0,
    )


def _correct_count_expr():
    """SQLAlchemy expression: JSONB summary.correct_count cast to INTEGER."""
    return func.coalesce(
        cast(Session.questions['summary']['correct_count'].as_string(), Integer),
        0,
    )


def _accuracy(correct: int, total: int) -> float | None:
    """Return accuracy percentage rounded to 1 decimal, or None if total == 0."""
    if not total:
        return None
    return round(correct / total * 100, 1)


def _difficulty_label(accuracy_pct: float | None) -> str:
    """
    Classify an accuracy percentage into a human-readable difficulty label.

      easy   — accuracy_pct >= 80 %
      medium — accuracy_pct in [50, 80)
      hard   — accuracy_pct < 50 %
      unknown — no data (accuracy_pct is None)
    """
    if accuracy_pct is None:
        return "unknown"
    if accuracy_pct >= 80:
        return "easy"
    if accuracy_pct >= 50:
        return "medium"
    return "hard"


def get_admin_overview_stats(
    db_session: SQLSession,
    from_dt: datetime,
    to_dt: datetime,
) -> dict:
    """
    Platform-wide aggregate statistics for a time period.

    ANONYMOUS — no user identifiers appear in the output.

    Args:
        db_session: Active SQLAlchemy session.
        from_dt:    Period start (inclusive).
        to_dt:      Period end (inclusive, end-of-day recommended).

    Returns:
        {
          "total_sessions":          int,   # sessions in [from_dt, to_dt]
          "total_questions_answered": int,   # sum of summary.scored_count
          "total_correct":           int,   # sum of summary.correct_count
          "overall_accuracy_pct":    float | None,  # null if no questions answered
          "active_courses":          int,   # distinct courses with ≥1 session
          "active_categories":       int,   # distinct categories with ≥1 session
        }

    Raises:
        SQLAlchemyError on database failure.
    """
    try:
        row = db_session.execute(
            select(
                func.count(Session.id).label("total_sessions"),
                func.sum(_scored_count_expr()).label("total_questions"),
                func.sum(_correct_count_expr()).label("total_correct"),
                func.count(distinct(Session.course_id)).label("active_courses"),
                func.count(distinct(Session.category_id)).label("active_categories"),
            ).where(
                Session.created_at >= from_dt,
                Session.created_at <= to_dt,
            )
        ).one()
    except SQLAlchemyError as e:
        logger.error("get_admin_overview_stats error: %s", e)
        raise

    total_q = int(row.total_questions or 0)
    total_c = int(row.total_correct or 0)
    return {
        "total_sessions": int(row.total_sessions or 0),
        "total_questions_answered": total_q,
        "total_correct": total_c,
        "overall_accuracy_pct": _accuracy(total_c, total_q),
        "active_courses": int(row.active_courses or 0),
        "active_categories": int(row.active_categories or 0),
    }


def get_admin_course_stats(
    db_session: SQLSession,
    from_dt: datetime,
    to_dt: datetime,
) -> list[dict]:
    """
    Per-course aggregate statistics for a time period, ordered hardest-first.

    ANONYMOUS — no user identifiers appear in the output.

    Args:
        db_session: Active SQLAlchemy session.
        from_dt:    Period start (inclusive).
        to_dt:      Period end (inclusive).

    Returns:
        List of dicts ordered by accuracy_pct ASC (hardest courses first).
        Courses with no accuracy data appear last.

        Each dict:
        {
          "course_id":          int,
          "course_code":        str,   # e.g. "OM125G"
          "course_name":        str,   # e.g. "Omvårdnad"
          "session_count":      int,
          "questions_answered": int,   # sum of summary.scored_count
          "correct_count":      int,   # sum of summary.correct_count
          "accuracy_pct":       float | None,
          "avg_score":          float | None,  # mean of Session.score
        }

    Raises:
        SQLAlchemyError on database failure.
    """
    try:
        rows = db_session.execute(
            select(
                Course.id.label("course_id"),
                Course.course_code,
                Course.name.label("course_name"),
                func.count(Session.id).label("session_count"),
                func.sum(_scored_count_expr()).label("questions_answered"),
                func.sum(_correct_count_expr()).label("correct_count"),
                func.avg(cast(Session.score, Float)).label("avg_score"),
            )
            .join(Course, Session.course_id == Course.id)
            .where(Session.created_at >= from_dt, Session.created_at <= to_dt)
            .group_by(Course.id, Course.course_code, Course.name)
        ).all()
    except SQLAlchemyError as e:
        logger.error("get_admin_course_stats error: %s", e)
        raise

    results = []
    for row in rows:
        q = int(row.questions_answered or 0)
        c = int(row.correct_count or 0)
        results.append({
            "course_id": row.course_id,
            "course_code": row.course_code,
            "course_name": row.course_name,
            "session_count": int(row.session_count or 0),
            "questions_answered": q,
            "correct_count": c,
            "accuracy_pct": _accuracy(c, q),
            "avg_score": round(float(row.avg_score), 1) if row.avg_score is not None else None,
        })

    results.sort(key=lambda x: (x["accuracy_pct"] is None, x["accuracy_pct"] or 0))
    return results


def get_admin_category_stats(
    db_session: SQLSession,
    from_dt: datetime,
    to_dt: datetime,
    course_id: int | None = None,
) -> list[dict]:
    """
    Per-category aggregate statistics for a time period, ordered hardest-first.

    ANONYMOUS — no user identifiers appear in the output.

    Per-category question counts are derived by unnesting the per-session
    answer JSONB and joining to question_templates, so multi-category sessions
    are correctly attributed to each category they covered.

    Args:
        db_session: Active SQLAlchemy session.
        from_dt:    Period start (inclusive).
        to_dt:      Period end (inclusive).
        course_id:  Optional. If provided, only sessions for this course are
                    counted. linked_courses still reflects all courses the
                    category belongs to, not just the filtered one.

    Returns:
        List of dicts ordered by accuracy_pct ASC (hardest categories first).

        Each dict:
        {
          "category_id":        int,
          "category_name":      str,
          "session_count":      int,
          "questions_answered": int,
          "correct_count":      int,
          "accuracy_pct":       float | None,
          "avg_score":          float | None,
          "linked_courses": [...],
        }

    Raises:
        SQLAlchemyError on database failure.
    """
    try:
        stmt = select(Session).where(
            Session.created_at >= from_dt,
            Session.created_at <= to_dt,
        )
        if course_id is not None:
            stmt = stmt.where(Session.course_id == course_id)
        sessions = db_session.execute(stmt).scalars().all()
    except SQLAlchemyError as e:
        logger.error("get_admin_category_stats error: %s", e)
        raise

    if not sessions:
        return []

    # Collect every template_id referenced across all sessions.
    all_template_ids: set[int] = set()
    for s in sessions:
        for q in (s.questions.get("questions") or {}).values():
            try:
                all_template_ids.add(int(q["template_id"]))
            except (KeyError, TypeError, ValueError):
                pass

    try:
        templates = db_session.execute(
            select(QuestionTemplate).where(
                QuestionTemplate.id.in_(all_template_ids)
            )
        ).scalars().all()
        tmpl_cat_map = {t.id: t.category_id for t in templates}

        cat_ids = list({t.category_id for t in templates})
        categories = db_session.execute(
            select(Category).where(Category.id.in_(cat_ids))
        ).scalars().all()
    except SQLAlchemyError as e:
        logger.error("get_admin_category_stats lookup error: %s", e)
        raise

    cat_name_map = {cat.id: cat.name for cat in categories}
    courses_by_cat: dict[int, list[dict]] = {
        cat.id: [
            {
                "course_id": c.id,
                "course_code": c.course_code,
                "course_name": c.name,
            }
            for c in cat.courses
        ]
        for cat in categories
    }

    # Per-category aggregation in Python so each category in a mixed session
    # is counted independently with its own question-level correct/total.
    cat_agg: dict[int, dict] = {}
    for s in sessions:
        score = float(s.score)
        seen_cats: set[int] = set()  # tracks first occurrence per session

        for q in (s.questions.get("questions") or {}).values():
            if q.get("is_correct") is None:
                continue
            try:
                tid = int(q["template_id"])
            except (KeyError, TypeError, ValueError):
                continue
            cat_id = tmpl_cat_map.get(tid)
            if cat_id is None:
                continue

            if cat_id not in cat_agg:
                cat_agg[cat_id] = {
                    "session_ids": set(),
                    "q_count": 0,
                    "correct": 0,
                    "scores": [],
                }
            agg = cat_agg[cat_id]
            agg["q_count"] += 1
            if q.get("is_correct"):
                agg["correct"] += 1
            if cat_id not in seen_cats:
                agg["session_ids"].add(s.id)
                agg["scores"].append(score)
                seen_cats.add(cat_id)

    results = []
    for cat_id, agg in cat_agg.items():
        q_count = agg["q_count"]
        correct = agg["correct"]
        scores = agg["scores"]
        avg_score = round(sum(scores) / len(scores), 1) if scores else None
        results.append({
            "category_id": cat_id,
            "category_name": cat_name_map.get(cat_id),
            "session_count": len(agg["session_ids"]),
            "questions_answered": q_count,
            "correct_count": correct,
            "accuracy_pct": _accuracy(correct, q_count),
            "avg_score": avg_score,
            "linked_courses": courses_by_cat.get(cat_id, []),
        })

    results.sort(
        key=lambda x: (x["accuracy_pct"] is None, x["accuracy_pct"] or 0)
    )
    return results


def get_admin_question_stats(
    db_session: SQLSession,
    from_dt: datetime,
    to_dt: datetime,
    course_id: int | None = None,
    category_id: int | None = None,
    sort_by: str = "accuracy",
    limit: int = 50,
) -> list[dict]:
    """
    Per-question-template difficulty statistics, derived by unnesting Session JSONB.

    ANONYMOUS — no user identifiers appear in the output.

    Each question instance stored in Session.questions['questions'] carries a
    template_id back-reference; this function aggregates across all instances
    for each unique template_id.

    Args:
        db_session:   Active SQLAlchemy session.
        from_dt:      Period start (inclusive).
        to_dt:        Period end (inclusive).
        course_id:    Optional. Filter to sessions for a specific course.
        category_id:  Optional. Filter to sessions for a specific category.
        sort_by:      "accuracy" → hardest-first (lowest accuracy_pct, default).
                      "attempts" → most-attempted-first.
        limit:        Max results (1–200). Caller must validate.

    Returns:
        List of dicts:
        {
          "template_id":   str,
          "template_text": str | None,  # QuestionTemplate.template; None if template deleted
          "unit":          str | None,
          "attempt_count": int,
          "correct_count": int,
          "accuracy_pct":  float | None,
          "difficulty":    "easy" | "medium" | "hard" | "unknown",
          "categories": [{"category_id": int, "name": str}],
          "courses":    [{"course_id": int, "course_code": str, "name": str}],
        }

    Raises:
        SQLAlchemyError on database failure.
    """
    where_parts = [
        "s.created_at BETWEEN :from_dt AND :to_dt",
        "(q.value->>'is_correct') IS NOT NULL",
    ]
    params: dict = {"from_dt": from_dt, "to_dt": to_dt, "limit": limit}
    join_parts = ""

    if course_id is not None:
        where_parts.append("s.course_id = :course_id")
        params["course_id"] = course_id
    if category_id is not None:
        # Filter on the question template's own category_id, not the session's
        # primary category. Multi-category sessions cover several categories,
        # so each question must be attributed by its template's category.
        join_parts = (
            "JOIN question_templates qt "
            "ON qt.id = (q.value->>'template_id')::int"
        )
        where_parts.append("qt.category_id = :category_id")
        params["category_id"] = category_id

    if sort_by == "accuracy":
        order_clause = (
            "(SUM(CASE WHEN (q.value->>'is_correct')::boolean THEN 1 ELSE 0 END)::float"
            " / NULLIF(COUNT(*), 0)) ASC NULLS LAST"
        )
    else:
        order_clause = "COUNT(*) DESC"

    sql = text(
        f"""
        SELECT
            q.value->>'template_id'                                               AS template_id,
            COUNT(*)                                                               AS attempt_count,
            SUM(CASE WHEN (q.value->>'is_correct')::boolean THEN 1 ELSE 0 END)   AS correct_count
        FROM sessions s
        CROSS JOIN LATERAL jsonb_each(s.questions->'questions') q
        {join_parts}
        WHERE {' AND '.join(where_parts)}
        GROUP BY template_id
        ORDER BY {order_clause}
        LIMIT :limit
        """
    )

    try:
        agg_rows = db_session.execute(sql, params).fetchall()

        if not agg_rows:
            return []

        template_ids = [int(r.template_id) for r in agg_rows]
        templates = db_session.execute(
            select(QuestionTemplate).where(QuestionTemplate.id.in_(template_ids))
        ).scalars().all()
        tmpl_map = {t.id: t for t in templates}
    except SQLAlchemyError as e:
        logger.error("get_admin_question_stats error: %s", e)
        raise

    results = []
    for row in agg_rows:
        tmpl = tmpl_map.get(int(row.template_id))
        attempt_count = int(row.attempt_count or 0)
        correct_count = int(row.correct_count or 0)
        accuracy = _accuracy(correct_count, attempt_count)
        results.append({
            "template_id": row.template_id,
            "template_text": tmpl.template if tmpl else None,
            "unit": tmpl.unit if tmpl else None,
            "attempt_count": attempt_count,
            "correct_count": correct_count,
            "accuracy_pct": accuracy,
            "difficulty": _difficulty_label(accuracy),
            "categories": (
                [{"category_id": tmpl.category.id, "name": tmpl.category.name}]
                if tmpl and tmpl.category else []
            ),
            "courses": (
                [
                    {
                        "course_id": c.id,
                        "course_code": c.course_code,
                        "name": c.name,
                    }
                    for c in tmpl.courses
                ]
                if tmpl else []
            ),
        })
    return results


# ─── User statistics ──────────────────────────────────────────────────────────

def get_user_overview_stats(
    db_session: SQLSession, 
    user_id: int, 
    from_dt: datetime | None = None, 
    to_dt: datetime | None = None
) -> dict:
    """
    Personal all-time performance summary for a single user.

    Args:
        db_session: Active SQLAlchemy session.
        user_id:    The authenticated user's primary key.
        from_dt:    Period start (inclusive).
        to_dt:      Period end (inclusive).

    Returns:
        {
          "total_sessions":             int,
          "total_questions":            int,   # sum of summary.scored_count
          "overall_accuracy_pct":       float | None,
          "current_streak":             int,   # consecutive days up to today/yesterday
          "longest_streak":             int,   # longest ever consecutive-day run
          "best_category":  {           # null if user has no sessions
            "category_id":  int,
            "name":         str | None,
            "accuracy_pct": float,
          } | None,
          "worst_category": {           # null if user has no sessions
            "category_id":  int,
            "name":         str | None,
            "accuracy_pct": float,
          } | None,
          "estimated_practice_minutes": int,   # total_questions * 1.2, rounded
        }

    Raises:
        SQLAlchemyError on database failure.
    """
    try:
        query = select(Session).where(Session.user_id == user_id)
        if from_dt is not None:
            query = query.where(Session.created_at >= from_dt)
        if to_dt is not None:
            query = query.where(Session.created_at <= to_dt)
            
        sessions = db_session.execute(query).scalars().all()
    except SQLAlchemyError as e:
        logger.error("get_user_overview_stats error: %s", e)
        raise

    if not sessions:
        return {
            "total_sessions": 0,
            "total_questions": 0,
            "overall_accuracy_pct": None,
            "current_streak": 0,
            "longest_streak": 0,
            "best_category": None,
            "worst_category": None,
            "estimated_practice_minutes": 0,
        }

    total_q = sum(
        int((s.questions.get("summary") or {}).get("scored_count") or 0)
        for s in sessions
    )
    total_c = sum(
        int((s.questions.get("summary") or {}).get("correct_count") or 0)
        for s in sessions
    )

    # ── Streak calculation ────────────────────────────────────────────────────
    practice_dates = sorted(
        {s.created_at.date() for s in sessions}, reverse=True
    )
    today = date.today()
    yesterday = today - timedelta(days=1)

    current_streak = 0
    if practice_dates:
        start_day = today if today in practice_dates else (
            yesterday if yesterday in set(practice_dates) else None
        )
        if start_day is not None:
            check = start_day
            for d in practice_dates:
                if d == check:
                    current_streak += 1
                    check -= timedelta(days=1)
                elif d < check:
                    break

    longest_streak = 0
    if practice_dates:
        dates_asc = sorted(practice_dates)
        run = 1
        longest_streak = 1
        for i in range(1, len(dates_asc)):
            if dates_asc[i] == dates_asc[i - 1] + timedelta(days=1):
                run += 1
                if run > longest_streak:
                    longest_streak = run
            else:
                run = 1

    # ── Best / worst category by mean score ──────────────────────────────────
    cat_scores: dict[int, list[float]] = defaultdict(list)
    for s in sessions:
        cat_scores[s.category_id].append(float(s.score))
    cat_avgs = {cid: sum(v) / len(v) for cid, v in cat_scores.items()}

    best_cat = worst_cat = None
    if cat_avgs:
        best_id = max(cat_avgs, key=cat_avgs.__getitem__)
        worst_id = min(cat_avgs, key=cat_avgs.__getitem__)
        try:
            cat_objs = db_session.execute(
                select(Category).where(Category.id.in_([best_id, worst_id]))
            ).scalars().all()
        except SQLAlchemyError as e:
            logger.error("get_user_overview_stats category lookup error: %s", e)
            raise
        cat_name_map = {c.id: c.name for c in cat_objs}
        best_cat = {
            "category_id": best_id,
            "name": cat_name_map.get(best_id),
            "accuracy_pct": round(cat_avgs[best_id], 1),
        }
        worst_cat = {
            "category_id": worst_id,
            "name": cat_name_map.get(worst_id),
            "accuracy_pct": round(cat_avgs[worst_id], 1),
        }

    return {
        "total_sessions": len(sessions),
        "total_questions": total_q,
        "overall_accuracy_pct": _accuracy(total_c, total_q),
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "best_category": best_cat,
        "worst_category": worst_cat,
        "estimated_practice_minutes": round(total_q * 1.2),
    }


def get_user_mastery_stats(
    db_session: SQLSession,
    user_id: int,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None
) -> list[dict]:
    """
    Per-course, per-category mastery for a single user.

    Multi-category sessions (where the user mixed questions from several
    categories) are expanded: each category the session covered gets its own
    entry so no practiced category is hidden.

    mastery_pct per category = average Session.score over sessions that
    included that category.  The course-level mastery_pct is a
    session-count-weighted average of its categories.

    Args:
        db_session: Active SQLAlchemy session.
        user_id:    The authenticated user's primary key.
        from_dt:    Period start (inclusive).
        to_dt:      Period end (inclusive).

    Returns:
        List of course dicts, sorted by course_id.

    Raises:
        SQLAlchemyError on database failure.
    """
    try:
        query = select(Session).where(Session.user_id == user_id)
        if from_dt is not None:
            query = query.where(Session.created_at >= from_dt)
        if to_dt is not None:
            query = query.where(Session.created_at <= to_dt)
        sessions = db_session.execute(query).scalars().all()
    except SQLAlchemyError as e:
        logger.error("get_user_mastery_stats error: %s", e)
        raise

    if not sessions:
        return []

    # (course_id, category_id) -> {scores: [], created_ats: [], session_ids: set}
    by_course_cat: dict[tuple, dict] = {}
    course_session_ids: dict[int, set] = defaultdict(set)

    for s in sessions:
        cat_ids = (s.questions or {}).get("category_ids") or [s.category_id]
        course_session_ids[s.course_id].add(s.id)
        for cat_id in cat_ids:
            key = (s.course_id, cat_id)
            if key not in by_course_cat:
                by_course_cat[key] = {"scores": [], "created_ats": []}
            by_course_cat[key]["scores"].append(float(s.score))
            by_course_cat[key]["created_ats"].append(s.created_at)

    all_course_ids = list({k[0] for k in by_course_cat})
    all_cat_ids = list({k[1] for k in by_course_cat})
    try:
        courses = db_session.execute(
            select(Course).where(Course.id.in_(all_course_ids))
        ).scalars().all()
        cats = db_session.execute(
            select(Category).where(Category.id.in_(all_cat_ids))
        ).scalars().all()
    except SQLAlchemyError as e:
        logger.error("get_user_mastery_stats lookup error: %s", e)
        raise

    course_map = {c.id: c for c in courses}
    cat_map = {c.id: c for c in cats}

    by_course: dict[int, list] = defaultdict(list)
    for (course_id, cat_id), data in by_course_cat.items():
        by_course[course_id].append((cat_id, data))

    result = []
    for course_id, cat_data_list in sorted(by_course.items()):
        course_obj = course_map.get(course_id)
        unique_sessions = len(course_session_ids[course_id])

        categories_out = []
        weighted_sum = 0.0
        total_weight = 0

        for cat_id, data in sorted(cat_data_list, key=lambda x: x[0]):
            cat_obj = cat_map.get(cat_id)
            count = len(data["scores"])
            mastery = sum(data["scores"]) / count
            last_dt = max(data["created_ats"])
            weighted_sum += mastery * count
            total_weight += count
            categories_out.append({
                "category_id": cat_id,
                "category_name": cat_obj.name if cat_obj else None,
                "session_count": count,
                "mastery_pct": round(mastery, 1),
                "last_practiced": last_dt.isoformat() if last_dt else None,
            })

        course_mastery = weighted_sum / total_weight if total_weight else 0.0
        result.append({
            "course_id": course_id,
            "course_code": course_obj.course_code if course_obj else None,
            "course_name": course_obj.name if course_obj else None,
            "session_count": unique_sessions,
            "mastery_pct": round(course_mastery, 1),
            "categories": categories_out,
        })
    return result


def get_user_activity_stats(
    db_session: SQLSession,
    user_id: int,
    weeks: int = 14,
) -> list[dict]:
    """
    Daily session counts for a user over the past N weeks.

    Every calendar day in the window is included; days with no sessions have
    session_count = 0. Suitable for rendering a contribution-style heatmap.

    Args:
        db_session: Active SQLAlchemy session.
        user_id:    The authenticated user's primary key.
        weeks:      Number of weeks of history (1–52, already clamped by caller).

    Returns:
        List of dicts, oldest-first, length = weeks * 7:
        [
          {"date": "YYYY-MM-DD", "session_count": int},
          ...
        ]

    Raises:
        SQLAlchemyError on database failure.
    """
    today = date.today()
    # Window: weeks*7 days ending today (inclusive on both ends).
    start = today - timedelta(days=weeks * 7 - 1)
    start_dt = datetime.combine(start, time(0, 0, 0))
    end_dt = datetime.combine(today, time(23, 59, 59))

    try:
        rows = db_session.execute(
            select(
                cast(Session.created_at, Date).label("session_date"),
                func.count(Session.id).label("session_count"),
            )
            .where(
                Session.user_id == user_id,
                Session.created_at >= start_dt,
                Session.created_at <= end_dt,
            )
            .group_by(cast(Session.created_at, Date))
        ).all()
    except SQLAlchemyError as e:
        logger.error("get_user_activity_stats error: %s", e)
        raise

    count_map: dict[date, int] = {row.session_date: int(row.session_count) for row in rows}

    return [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "session_count": count_map.get(start + timedelta(days=i), 0),
        }
        for i in range(weeks * 7)
    ]
