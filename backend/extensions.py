"""Rate limiter singleton shared across all Flask blueprints.

Defined at module level so blueprint modules can import and decorate routes
with ``@limiter.limit(...)`` without importing from ``app.py``, which would
create a circular import. Bound to the Flask app in ``configure_app()`` via
``limiter.init_app(app)``.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    default_limits=["200 per minute"],
)
