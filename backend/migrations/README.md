# Database migrations

Alembic-managed schema for QTrain. Migrations replace the brittle
`_ensure_user_role_schema` / `_ensure_question_template_schema` startup
backfills that previously ran inline in `init_db.py`.

## Running

From `backend/`:

```bash
# Apply all pending migrations
alembic upgrade head

# Show current revision
alembic current

# Generate a new revision after editing models in class_db.py
alembic revision --autogenerate -m "describe the change"
```

## Existing deployments

If your database was created before Alembic was adopted (i.e. the schema
was bootstrapped via `db.create_all()` plus the legacy `_ensure_*`
helpers), run the one-time stamp **before** the first `upgrade`:

```bash
alembic stamp head
```

This marks the current schema as already at HEAD without re-running the
baseline migration. Subsequent migrations will then apply normally.

## Fresh deployments

`alembic upgrade head` against a blank Postgres DB creates the full schema
defined in `0001_baseline.py`.

## Migrating to a cloud database

See [migration.md](../../migration.md) at the repo root for a full walkthrough: provider options, `pg_dump`/restore steps, Redis provisioning, env var changes, and rollback plan.

## Connection settings

`env.py` reads `ALEMBIC_DATABASE_URL` (or `DATABASE_URL`) first; otherwise
falls back to the same `POSTGRES_*` env vars the Flask app uses, so the
deploy entrypoint can run `alembic upgrade head` before Gunicorn boots
with no extra config.
