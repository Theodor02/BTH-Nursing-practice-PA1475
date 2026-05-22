import pytest

from logic.database.operations.sql_setters import (
    QUESTION_TEMPLATE_UPDATE_FIELDS,
    _sanitize_updates,
    _validate_category_ids,
    _validate_course_id,
)


def test_sanitize_updates_returns_only_allowed_fields():
    updates = {
        "template": "Compute x",
        "active": False,
    }

    sanitized = _sanitize_updates(updates, QUESTION_TEMPLATE_UPDATE_FIELDS, "QuestionTemplate")

    assert sanitized == updates


def test_sanitize_updates_rejects_unsupported_fields():
    updates = {
        "subject": "Legacy Subject",
        "drop_table": True,
    }

    with pytest.raises(ValueError, match="Unsupported fields"):
        _sanitize_updates(updates, QUESTION_TEMPLATE_UPDATE_FIELDS, "QuestionTemplate")


def test_validate_category_ids_deduplicates_preserving_order():
    category_ids = [3, 1, 3, 2, 1]

    validated = _validate_category_ids(category_ids)

    assert validated == [3, 1, 2]


def test_validate_category_ids_rejects_non_positive_integers():
    with pytest.raises(ValueError, match="positive integers"):
        _validate_category_ids([1, 0, 2])


def test_sanitize_updates_with_category_update_fields():
    from logic.database.operations.sql_setters import CATEGORY_UPDATE_FIELDS

    updates = {"name": "New Name", "active": True, "history": {"v": 1}}
    sanitized = _sanitize_updates(updates, CATEGORY_UPDATE_FIELDS, "Category")

    assert sanitized == updates


def test_sanitize_updates_category_rejects_unsupported_fields():
    from logic.database.operations.sql_setters import CATEGORY_UPDATE_FIELDS

    with pytest.raises(ValueError, match="Unsupported fields"):
        _sanitize_updates({"unknown_field": True}, CATEGORY_UPDATE_FIELDS, "Category")


def test_sanitize_updates_with_unit_update_fields():
    from logic.database.operations.sql_setters import UNIT_UPDATE_FIELDS

    updates = {"name": "kg", "active": False}
    sanitized = _sanitize_updates(updates, UNIT_UPDATE_FIELDS, "Unit")

    assert sanitized == updates


def test_sanitize_updates_unit_rejects_unsupported_fields():
    from logic.database.operations.sql_setters import UNIT_UPDATE_FIELDS

    with pytest.raises(ValueError, match="Unsupported fields"):
        _sanitize_updates({"created_at": "now"}, UNIT_UPDATE_FIELDS, "Unit")


def test_course_update_fields_now_includes_active():
    from logic.database.operations.sql_setters import COURSE_UPDATE_FIELDS

    assert "active" in COURSE_UPDATE_FIELDS
