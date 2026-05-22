import os


bind = "0.0.0.0:5000"
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")


workers = int(os.getenv("WEB_CONCURRENCY", "3"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

preload_app = os.getenv("GUNICORN_PRELOAD_APP", "true").lower() == "true"
worker_tmp_dir = os.getenv("GUNICORN_WORKER_TMP_DIR", "/dev/shm")
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")


def post_fork(server, worker):
    """Dispose any DB connections inherited from the parent.

    `preload_app=true` opens the connection pool in the master before fork.
    Children that reuse those file descriptors corrupt SSL/TCP state under
    load, which surfaces as intermittent ``SSL SYSCALL error`` and
    ``connection already closed``. Disposing in each worker forces fresh
    connections per process.
    """
    try:
        from app import app as flask_app
        from logic.database.init.init_db import db

        with flask_app.app_context():
            db.engine.dispose()
    except Exception:  # noqa: BLE001
        worker.log.exception("post_fork engine dispose failed")
