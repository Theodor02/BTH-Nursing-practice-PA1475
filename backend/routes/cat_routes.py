"""Category and unit discovery endpoints.

GET /api/categories — used by the frontend to populate the quiz-builder UI.
  Cached in Redis (5 min TTL) so the response is fast even under load.
  Cache is invalidated by any admin mutation that changes the template pool.

GET /api/units — used by the admin UI to display valid units for question fields.
"""
from flask import Blueprint, jsonify
from sqlalchemy import select

from logic.auth import require_auth
from logic.cat_request_cache import CatRequestCache
from logic.database.init.class_db import Unit
from logic.database.init.init_db import db

cat_bp = Blueprint('cat', __name__)
_cache = CatRequestCache()


def invalidate_cat_request_cache():
    """Invalidate the shared category-request cache across all workers.

    Called by any admin mutation that changes the active template pool so the
    next ``GET /api/categories`` response reflects the updated state.
    """
    _cache.invalidate()


@cat_bp.get('/api/categories')
@require_auth
def cat_request():
    """Return available courses/categories and max question count per category.

    Response is Redis-cached (5 min TTL, shared across all Gunicorn workers).
    Any admin mutation that changes the template pool calls
    invalidate_cat_request_cache() to keep the response fresh.
    """
    payload_courses, payload_max_questions = _cache.get(db.session)
    return jsonify({
        'courses': payload_courses,
        'max_questions': payload_max_questions,
    })


@cat_bp.get('/api/units')
@require_auth
def get_units():
    """Return all active units with their aliases, ordered by name."""
    units = db.session.execute(
        select(Unit).where(Unit.active.is_(True)).order_by(Unit.name)
    ).scalars().unique().all()
    return jsonify([
        {
            'id': u.id,
            'name': u.name,
            'aliases': [a.alias for a in u.aliases],
        }
        for u in units
    ])
