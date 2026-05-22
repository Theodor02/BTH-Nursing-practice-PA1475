"""Database seeding from bundled JSON default data.

Populates an empty database with courses, categories, course-category mappings,
question templates, and units from the ``logic/default/`` JSON files.

Safety: ``_assert_safe_to_drop_schema`` enforces that the destructive
``db.drop_all()`` path (used by the ``__main__`` entry point) can only run
when ``ENV=dev``, ``CONFIRM_DROP_SCHEMA=true``, and ``POSTGRES_HOST`` resolves
to a local address — preventing accidental data loss against shared or
production databases.

``seed_database`` is called at app startup (via ``init_database``) only when
the ``courses`` table is empty. IntegrityError rows are rolled back and skipped
rather than raising, so re-seeding an already-populated DB is safe.
"""
import json
import os
import sys
from pathlib import Path
from flask import Flask
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError

# Ensure the backend directory is importable when this file is run directly.
BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv()


def load_json_file(file_path):
    """Load and return parsed JSON from ``file_path`` (UTF-8 with BOM tolerated)."""
    with open(file_path, encoding="utf-8-sig") as f:
        return json.load(f)


def _parse_bool_env(value):
    """Return True if the string value represents a truthy boolean env var."""
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _assert_safe_to_drop_schema():
    """Raise RuntimeError if env conditions do not permit a destructive schema reset.

    Requires all three of: ``ENV=dev``, ``CONFIRM_DROP_SCHEMA=true``, and
    ``POSTGRES_HOST`` resolving to a local address. Prevents accidental
    ``db.drop_all()`` against a shared or production database.
    """
    env = str(os.getenv("ENV", "")).strip().lower()
    confirm_raw = os.getenv("CONFIRM_DROP_SCHEMA", "false")
    confirm_drop_schema = _parse_bool_env(confirm_raw)
    postgres_host = str(os.getenv("POSTGRES_HOST", "localhost")).strip().lower()
    is_local_host = postgres_host in {"localhost", "127.0.0.1", "::1", "db"}

    if env != "dev" or not confirm_drop_schema or not is_local_host:
        raise RuntimeError(
            "Refusing to run destructive schema reset. Required: "
            "ENV=dev, CONFIRM_DROP_SCHEMA=true, and "
            "POSTGRES_HOST must be local "
            "(localhost/127.0.0.1/::1) or the Compose service host 'db'. "
            f"Received ENV={env or '<unset>'}, "
            f"CONFIRM_DROP_SCHEMA={confirm_raw}, "
            f"POSTGRES_HOST={postgres_host or '<unset>'}."
        )


def seed_database(db):
    """Populate an empty database with default courses, categories, templates, and units.

    Reads from the JSON files in ``logic/default/``. Each entity is inserted
    individually; ``IntegrityError`` (duplicate) rows are rolled back and skipped
    rather than raising, so calling this on a partially-seeded DB is safe.

    Args:
        db: The Flask-SQLAlchemy ``db`` object with an active app context.

    Raises:
        Exception: Re-raises any non-IntegrityError exception after rolling back,
            so the caller can decide whether to abort or continue.
    """
    from logic.database.operations.sql_setters import (
        create_course,
        create_category,
        attach_category_to_course,
        create_question_template,
        create_unit,
        create_unit_alias,
    )
    from logic.database.init.class_db import Course, Unit

    base_path = os.path.join(os.path.dirname(__file__), "..", "..", "default")

    print("\n--- Starting Automatic Seeding ---")
    print("Loading default data files...")

    # Load JSON data
    courses_data = load_json_file(f"{base_path}/courses.json")
    categories_data = load_json_file(f"{base_path}/categories.json")
    course_categories_data = load_json_file(f"{base_path}/course_categories.json")
    templates_data = load_json_file(f"{base_path}/question_templates.json")
    units_data = load_json_file(f"{base_path}/units.json")

    print(
        f"✓ Loaded {len(courses_data)} courses, {len(categories_data)} categories, "
        f"{len(course_categories_data)} mappings, {len(templates_data)} templates\n"
    )

    
    print(f"✓ Loaded {len(courses_data)} courses, {len(categories_data)} categories, "
          f"{len(course_categories_data)} mappings, {len(templates_data)} templates, ")
    
    try:
        # --- SEED COURSES ---
        courses_created, courses_skipped = 0, 0
        print("Seeding courses...")
        for course in courses_data:
            try:
                create_course(
                    db.session,
                    course["course_code"],
                    course["name"],
                    course.get("history"),
                )
                courses_created += 1
            except IntegrityError:
                db.session.rollback()
                courses_skipped += 1
        print(f"✓ Courses: {courses_created} created, {courses_skipped} skipped")

        # --- SEED CATEGORIES ---
        categories_created, categories_skipped = 0, 0
        print("Seeding categories...")
        for category in categories_data:
            try:
                create_category(
                    db.session,
                    category["name"],
                    category.get("history"),
                )
                categories_created += 1
            except IntegrityError:
                db.session.rollback()
                categories_skipped += 1
        print(f"✓ Categories: {categories_created} created, {categories_skipped} skipped")

        # --- SEED MAPPINGS ---
        mappings_created, mappings_skipped = 0, 0
        print("Seeding course-category mappings...")
        for mapping in course_categories_data:
            try:
                attach_category_to_course(
                    db.session,
                    mapping["course_id"],
                    mapping["category_id"],
                )
                mappings_created += 1
            except IntegrityError:
                db.session.rollback()
                mappings_skipped += 1
        print(f"✓ Mappings: {mappings_created} created, {mappings_skipped} skipped")

        # --- SEED TEMPLATES ---
        templates_created, templates_skipped = 0, 0
        print("Seeding question templates...")
        category_question_counters = {}
        for template in templates_data:
            try:
                category_id = template["category_id"]
                category_question_counters[category_id] = category_question_counters.get(category_id, 0) + 1
                question_number = category_question_counters[category_id]

                template_data = {
                    k: v
                    for k, v in template.items()
                    if k != "category_id"
                }
                template_data["question_number"] = question_number

                create_question_template(
                    db.session,
                    template_data,
                    category_id,
                )
                db.session.flush()

                templates_created += 1
            except IntegrityError:
                db.session.rollback()
                templates_skipped += 1
        print(f"✓ Templates: {templates_created} created, {templates_skipped} skipped")

        # --- SEED UNITS ---
        units_created, units_skipped = 0, 0
        aliases_created, aliases_skipped = 0, 0
        print("Seeding units...")

        for unit_group in units_data:
            for canonical, aliases in unit_group.items():
                try:
                    unit = create_unit(db.session, canonical)
                    db.session.flush()  # ensure ID is assigned
                    units_created += 1
                except IntegrityError:
                    db.session.rollback()
                    units_skipped += 1
                    unit = db.session.query(Unit).filter_by(name=canonical).first()

                for alias in aliases:
                    if not alias:
                        continue
                    try:
                        create_unit_alias(db.session, unit.id, alias)  # pass ID, not object
                        aliases_created += 1
                    except IntegrityError:
                        db.session.rollback()
                        aliases_skipped += 1

        print(f"✓ Units: {units_created} created, {units_skipped} skipped")
        print(f"✓ Unit aliases: {aliases_created} created, {aliases_skipped} skipped")

        # Final commit
        # Finally, commit all the seeded data!
        db.session.commit()

        print("\n============================================================")
        print("✓ Database seeding completed successfully!")
        print("============================================================\n")

    except Exception as e:
        db.session.rollback()
        print(f"\n✗ Error during seeding: {e}")
        raise

if __name__ == "__main__":
    _assert_safe_to_drop_schema()

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"postgresql://{os.getenv('POSTGRES_USER', 'qtrain')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'qtrain')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'qtrain')}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    from logic.database.init.init_db import db, _ensure_user_role_schema, _ensure_question_template_schema
    from logic.database.init.class_db import Course, Category, QuestionTemplate, Unit, UnitAlias, Session, User, CourseCategory
    
    db.init_app(app)

    with app.app_context():
        print("Dropping all existing tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        _ensure_user_role_schema()
        _ensure_question_template_schema()
        seed_database(db)
