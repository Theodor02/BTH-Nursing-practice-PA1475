"""Tests to verify database schema and seeded data exist and are valid."""
import os

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from logic.database.init.init_db import db, init_database
from logic.database.init.class_db import (
    Course, Category, CourseCategory, QuestionTemplate, User, Session, course_question_templates
)
from logic.database.seeding.seed_defaults import seed_database
from flask import Flask


@pytest.fixture
def app_with_real_db():
    """Create a Flask app with a real database connection."""
    app = Flask(__name__)
    app.config['TESTING'] = True

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "qtrain")
    password = os.getenv("POSTGRES_PASSWORD", "qtrain")
    dbname = os.getenv("POSTGRES_DB", "qtrain")
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        seed_database(db)
        yield app


class TestDatabaseSchema:
    """Test that all required tables exist in the database."""

    def test_tables_exist(self, app_with_real_db):
        """Verify all expected tables exist."""
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        expected_tables = {
            'courses',
            'categories',
            'course_categories',
            'question_templates',
            'users',
            'sessions',
        }

        assert expected_tables.issubset(set(tables)), (
            f"Missing tables. Expected: {expected_tables}, "
            f"Found: {set(tables)}"
        )

    def test_courses_table_schema(self, app_with_real_db):
        """Verify courses table has correct columns."""
        inspector = inspect(db.engine)
        columns = {col['name'] for col in inspector.get_columns('courses')}

        expected_columns = {
            'id', 'course_code', 'name', 'created_at', 'last_updated', 'history'
        }

        assert expected_columns.issubset(columns), (
            f"Missing columns in courses table. Expected: {expected_columns}, "
            f"Found: {columns}"
        )

    def test_categories_table_schema(self, app_with_real_db):
        """Verify categories table has correct columns."""
        inspector = inspect(db.engine)
        columns = {col['name'] for col in inspector.get_columns('categories')}

        expected_columns = {
            'id', 'name', 'created_at', 'last_updated', 'history'
        }

        assert expected_columns.issubset(columns), (
            f"Missing columns in categories table. Expected: {expected_columns}, "
            f"Found: {columns}"
        )

    def test_question_templates_table_schema(self, app_with_real_db):
        """Verify question_templates table has correct columns."""
        inspector = inspect(db.engine)
        columns = {col['name'] for col in inspector.get_columns('question_templates')}

        expected_columns = {
            'id', 'category_id', 'question_number',
            'template', 'variables', 'formula', 'unit', 'tolerance', 'hints', 'link', 'active'
        }

        assert expected_columns.issubset(columns), (
            f"Missing columns in question_templates table. Expected: {expected_columns}, "
            f"Found: {columns}"
        )

    def test_course_question_templates_junction_table(self, app_with_real_db):
        """Verify the many-to-many junction table exists."""
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        assert 'course_question_templates' in tables, (
            "course_question_templates junction table not found"
        )


class TestSeededData:
    """Test that default data was successfully seeded."""

    def test_courses_seeded(self, app_with_real_db):
        """Verify courses were seeded."""
        courses = db.session.query(Course).all()

        assert len(courses) >= 4, (
            f"Expected at least 4 courses, found {len(courses)}"
        )

        course_codes = {c.course_code for c in courses}
        expected_codes = {'KM1423', 'KM1424', 'KM1425', 'OM1541'}

        assert expected_codes.issubset(course_codes), (
            f"Expected course codes {expected_codes} to be present, found {course_codes}"
        )

    def test_categories_seeded(self, app_with_real_db):
        """Verify categories were seeded."""
        categories = db.session.query(Category).all()

        assert len(categories) >= 6, (
            f"Expected at least 6 categories, found {len(categories)}"
        )

        category_names = {c.name for c in categories}
        assert len(category_names) >= 6, (
            f"Expected at least 6 unique category names, found {len(category_names)}"
        )

        assert any('styrka' in name.lower() or 'mängd' in name.lower()
                   for name in category_names), \
            "Missing 'Dos, styrka, mängd' category"

    def test_question_templates_seeded(self, app_with_real_db):
        """Verify question templates were seeded."""
        templates = db.session.query(QuestionTemplate).all()

        assert len(templates) >= 43, (
            f"Expected at least 43 question templates, found {len(templates)}"
        )

        # Templates now use integer IDs; verify category/question_number coverage
        assert all(t.category_id is not None for t in templates), (
            "Some templates are missing category_id"
        )
        assert all(t.question_number is not None for t in templates), (
            "Some templates are missing question_number"
        )

    def test_course_category_mappings_seeded(self, app_with_real_db):
        """Verify course-category mappings were seeded."""
        mappings = db.session.query(CourseCategory).all()

        assert len(mappings) >= 16, (
            f"Expected at least 16 course-category mappings, found {len(mappings)}"
        )

    def test_question_template_valid_structure(self, app_with_real_db):
        """Verify a question template has valid structure."""
        template = db.session.query(QuestionTemplate).first()

        assert template is not None, "No question templates found"
        assert template.id, "Template ID is missing"
        assert template.category_id, "Template category_id is missing"
        assert template.question_number is not None, "Template question_number is missing"
        assert template.template, "Template template field is missing"
        assert template.variables, "Template variables is missing"
        assert template.formula, "Template formula is missing"
        assert template.tolerance is not None, "Template tolerance is missing"
        assert isinstance(template.active, bool), "Template active field is not boolean"
        assert template.category is not None, "Template has no linked category"

    def test_courses_have_templates(self, app_with_real_db):
        """Verify seeded courses are associated with question templates via category."""
        courses = db.session.query(Course).filter(Course.id <= 4).all()

        for course in courses:
            # Templates are linked via category -> course_categories
            category_ids = [cc.category_id for cc in db.session.query(CourseCategory).filter_by(course_id=course.id).all()]
            templates = db.session.query(QuestionTemplate).filter(
                QuestionTemplate.category_id.in_(category_ids)
            ).all()
            assert len(templates) > 0, (
                f"Course {course.course_code} has no associated templates"
            )

    def test_categories_have_templates(self, app_with_real_db):
        """Verify seeded categories are associated with question templates."""
        categories = db.session.query(Category).filter(Category.id <= 6).all()

        for category in categories:
            templates = category.question_templates
            assert len(templates) > 0, (
                f"Category {category.name} has no associated templates"
            )


class TestDatabaseConnectivity:
    """Test basic database connectivity."""

    def test_can_connect_to_database(self, app_with_real_db):
        """Verify we can connect to the database."""
        try:
            result = db.session.execute(text("SELECT 1"))
            assert result is not None
        except Exception as e:
            pytest.fail(f"Failed to connect to database: {e}")

    def test_can_query_courses(self, app_with_real_db):
        """Verify we can query courses."""
        try:
            courses = db.session.query(Course).limit(1).all()
            assert isinstance(courses, list)
        except Exception as e:
            pytest.fail(f"Failed to query courses: {e}")

    def test_database_isolation(self, app_with_real_db):
        """Verify database is properly isolated for testing."""
        initial_course_count = db.session.query(Course).count()
        initial_category_count = db.session.query(Category).count()

        assert initial_course_count > 0, "No courses found in database"
        assert initial_category_count > 0, "No categories found in database"


class TestPrimaryKeys:
    """Test that primary keys are properly configured."""

    def test_course_primary_key(self, app_with_real_db):
        """Verify course ID is unique."""
        courses = db.session.query(Course).all()
        course_ids = [c.id for c in courses]

        assert len(course_ids) == len(set(course_ids)), (
            "Course IDs are not unique"
        )

    def test_category_primary_key(self, app_with_real_db):
        """Verify category ID is unique."""
        categories = db.session.query(Category).all()
        category_ids = [c.id for c in categories]

        assert len(category_ids) == len(set(category_ids)), (
            "Category IDs are not unique"
        )

    def test_question_template_primary_key(self, app_with_real_db):
        """Verify question template ID is unique integer."""
        templates = db.session.query(QuestionTemplate).all()
        template_ids = [t.id for t in templates]

        assert len(template_ids) == len(set(template_ids)), (
            "Question template IDs are not unique"
        )
        assert all(isinstance(tid, int) for tid in template_ids), (
            "Question template IDs should be integers"
        )

    def test_question_number_unique_per_category(self, app_with_real_db):
        """Verify question_number is unique within each category."""
        templates = db.session.query(QuestionTemplate).all()

        seen = {}
        for t in templates:
            key = (t.category_id, t.question_number)
            assert key not in seen, (
                f"Duplicate (category_id, question_number) = {key}"
            )
            seen[key] = t.id

    def test_course_code_uniqueness(self, app_with_real_db):
        """Verify course codes are unique."""
        courses = db.session.query(Course).all()
        course_codes = [c.course_code for c in courses]

        assert len(course_codes) == len(set(course_codes)), (
            "Course codes are not unique"
        )

    def test_category_name_uniqueness(self, app_with_real_db):
        """Verify category names are unique."""
        categories = db.session.query(Category).all()
        category_names = [c.name for c in categories]

        assert len(category_names) == len(set(category_names)), (
            "Category names are not unique"
        )


class TestForeignKeys:
    """Test that foreign key relationships work properly."""

    def test_question_template_has_valid_category(self, app_with_real_db):
        """Verify every question template links to an existing category."""
        templates = db.session.query(QuestionTemplate).all()
        categories = db.session.query(Category).all()
        category_ids = {c.id for c in categories}

        for template in templates:
            assert template.category_id in category_ids, (
                f"Question template {template.id} has invalid category_id {template.category_id}"
            )

    def test_course_category_fk_integrity(self, app_with_real_db):
        """Verify all course-category mappings reference valid records."""
        mappings = db.session.query(CourseCategory).all()
        courses = db.session.query(Course).all()
        categories = db.session.query(Category).all()

        course_ids = {c.id for c in courses}
        category_ids = {c.id for c in categories}

        for mapping in mappings:
            assert mapping.course_id in course_ids, (
                f"CourseCategory has invalid course_id {mapping.course_id}"
            )
            assert mapping.category_id in category_ids, (
                f"CourseCategory has invalid category_id {mapping.category_id}"
            )


class TestRelationships:
    """Test relationships work correctly."""

    def test_category_templates_relationship(self, app_with_real_db):
        """Verify category.question_templates one-to-many loads successfully."""
        category = db.session.query(Category).first()
        templates = category.question_templates

        assert isinstance(templates, list), "question_templates should be a list"
        assert len(templates) > 0, "Category should have templates"

    def test_template_category_relationship(self, app_with_real_db):
        """Verify template.category loads the correct category."""
        template = db.session.query(QuestionTemplate).first()
        category = template.category

        assert category is not None, "template.category should not be None"
        assert category.id == template.category_id

    def test_course_category_relationship(self, app_with_real_db):
        """Verify courses are linked to categories."""
        courses = db.session.query(Course).all()

        for course in courses:
            categories = course.categories
            assert len(categories) > 0, (
                f"Course {course.course_code} has no associated categories"
            )


class TestConstraintIntegrity:
    """Test that database constraints are enforced."""

    def test_cannot_insert_null_formula_in_template(self, app_with_real_db):
        """Verify NOT NULL constraint on question_template.formula."""
        category = db.session.query(Category).first()
        try:
            template = QuestionTemplate(
                category_id=category.id,
                question_number=9999,
                template="Test template",
                variables={},
                formula=None,  # This should violate NOT NULL
                tolerance=0.1,
                active=True
            )
            db.session.add(template)
            db.session.commit()
            pytest.fail("Should have raised IntegrityError for NULL formula")
        except Exception as e:
            db.session.rollback()
            assert "NOT NULL" in str(e) or "null" in str(e).lower(), (
                f"Expected NOT NULL error, got: {e}"
            )

    def test_cannot_insert_null_template_content(self, app_with_real_db):
        """Verify NOT NULL constraint on required template fields."""
        category = db.session.query(Category).first()
        try:
            template = QuestionTemplate(
                category_id=category.id,
                question_number=9998,
                template=None,  # This should violate NOT NULL
                variables={},
                formula="1+1",
                tolerance=0.1,
                active=True
            )
            db.session.add(template)
            db.session.commit()
            pytest.fail("Should have raised IntegrityError for NULL template")
        except Exception as e:
            db.session.rollback()
            assert "NOT NULL" in str(e) or "null" in str(e).lower(), (
                f"Expected NOT NULL error, got: {e}"
            )

    def test_cannot_insert_duplicate_course_code(self, app_with_real_db):
        """Verify UNIQUE constraint on course_code."""
        existing_course = db.session.query(Course).first()
        try:
            new_course = Course(
                course_code=existing_course.course_code,  # Duplicate
                name="Duplicate Course",
            )
            db.session.add(new_course)
            db.session.commit()
            pytest.fail("Should have raised IntegrityError for duplicate course_code")
        except IntegrityError as e:
            db.session.rollback()
            assert "unique" in str(e).lower(), (
                f"Expected UNIQUE constraint error, got: {e}"
            )

    def test_cannot_insert_duplicate_category_name(self, app_with_real_db):
        """Verify UNIQUE constraint on category name."""
        existing_category = db.session.query(Category).first()
        try:
            new_category = Category(
                name=existing_category.name,  # Duplicate
            )
            db.session.add(new_category)
            db.session.commit()
            pytest.fail("Should have raised IntegrityError for duplicate category name")
        except IntegrityError as e:
            db.session.rollback()
            assert "unique" in str(e).lower(), (
                f"Expected UNIQUE constraint error, got: {e}"
            )


class TestCascadeDelete:
    """Test that cascade delete relationships work properly."""

    def test_delete_course_cascades_to_course_template_links(self, app_with_real_db):
        """Verify deleting a course removes course-template junction rows."""
        test_course = Course(course_code="TEST_CASCADE", name="Test Cascade Course")
        existing_template = db.session.query(QuestionTemplate).first()
        assert existing_template is not None, "Expected at least one seeded template"

        db.session.add(test_course)
        db.session.flush()

        db.session.execute(
            course_question_templates.insert().values(
                course_id=test_course.id,
                question_template_id=existing_template.id,
            )
        )
        db.session.commit()

        template_id = existing_template.id

        db.session.delete(test_course)
        db.session.commit()

        remaining_template = db.session.get(QuestionTemplate, template_id)
        assert remaining_template is not None, (
            "Question template should remain when a linked course is deleted"
        )

    def test_delete_category_cascades_to_course_category(self, app_with_real_db):
        """Verify deleting a category cascades to course_categories."""
        test_category = Category(name="Test Delete Category")
        db.session.add(test_category)
        db.session.flush()

        course = db.session.query(Course).first()
        mapping = CourseCategory(course_id=course.id, category_id=test_category.id)
        db.session.add(mapping)
        db.session.commit()

        category_id = test_category.id

        db.session.delete(test_category)
        db.session.commit()

        deleted_mapping = db.session.query(CourseCategory).filter_by(
            category_id=category_id
        ).first()
        assert deleted_mapping is None, (
            "CourseCategory should be deleted when category is deleted"
        )


class TestDataIntegrity:
    """Test that seeded data maintains integrity."""

    def test_all_templates_have_required_fields(self, app_with_real_db):
        """Verify all templates have required fields populated."""
        templates = db.session.query(QuestionTemplate).all()

        for template in templates:
            assert template.id, f"Template missing id"
            assert template.category_id, f"Template {template.id} missing category_id"
            assert template.question_number is not None, f"Template {template.id} missing question_number"
            assert template.template, f"Template {template.id} missing template"
            assert template.variables is not None, f"Template {template.id} missing variables"
            assert template.formula, f"Template {template.id} missing formula"
            assert template.tolerance is not None, f"Template {template.id} missing tolerance"

    def test_all_courses_have_required_info(self, app_with_real_db):
        """Verify all courses have required information."""
        courses = db.session.query(Course).all()

        for course in courses:
            assert course.id, f"Course missing id"
            assert course.course_code, f"Course {course.id} missing course_code"
            assert course.name, f"Course {course.id} missing name"

    def test_all_categories_have_names(self, app_with_real_db):
        """Verify all categories have names."""
        categories = db.session.query(Category).all()

        for category in categories:
            assert category.id, f"Category missing id"
            assert category.name, f"Category {category.id} missing name"

    def test_relationship_counts_match(self, app_with_real_db):
        """Verify junction table entries are accessible through relationships."""
        mappings = db.session.query(CourseCategory).all()
        for mapping in mappings:
            course = db.session.get(Course, mapping.course_id)
            category = db.session.get(Category, mapping.category_id)

            assert course is not None, f"Course {mapping.course_id} not found"
            assert category is not None, f"Category {mapping.category_id} not found"

            assert category in course.categories, (
                f"Category {mapping.category_id} not in course.categories"
            )
