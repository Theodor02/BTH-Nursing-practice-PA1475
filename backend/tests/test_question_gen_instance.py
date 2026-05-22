"""Tests for generate_question_instance and build_generated_payload."""
from decimal import Decimal

import pytest

from logic.question_gen.question_gen import (
    _to_float,
    build_generated_payload,
    generate_question_instance,
)


# ── _to_float ────────────────────────────────────────────────────────────────

def test_to_float_returns_default_for_none():
    assert _to_float(None) == 0.0
    assert _to_float(None, default=1.5) == 1.5


def test_to_float_converts_decimal():
    assert _to_float(Decimal("3.14")) == pytest.approx(3.14)


def test_to_float_converts_int_and_float():
    assert _to_float(5) == 5.0
    assert _to_float(2.5) == 2.5


# ── generate_question_instance ───────────────────────────────────────────────

def test_generate_question_instance_raises_for_non_dict():
    with pytest.raises(ValueError, match="template must be a dictionary"):
        generate_question_instance("not-a-dict")


def test_generate_question_instance_returns_unscored_for_missing_fields():
    """When required fields are absent, the template is echoed back as unscored."""
    template = {"id": "tpl-incomplete", "template": "Hello"}

    frontend_question, snapshot = generate_question_instance(template)

    assert snapshot["is_scored"] is False
    assert snapshot["correct_answer"] is None
    assert snapshot["template_id"] == "tpl-incomplete"
    assert frontend_question == template


def test_generate_question_instance_returns_unscored_with_uuid_when_id_absent():
    template = {"template": "Hello"}

    _frontend, snapshot = generate_question_instance(template)

    assert snapshot["is_scored"] is False
    assert snapshot["template_id"] is None
    # id should be a non-empty string (a uuid4)
    assert isinstance(snapshot["id"], str)
    assert len(snapshot["id"]) > 0


def test_generate_question_instance_raises_on_persistent_arithmetic_error(monkeypatch):
    """If the formula always raises ArithmeticError, ValueError is raised after all retries."""
    import logic.question_gen.question_gen as qg

    monkeypatch.setattr(
        qg,
        "evaluate_formula",
        lambda formula, variables: (_ for _ in ()).throw(ArithmeticError("division by zero")),
    )

    template = {
        "category_id": 1,
        "question_number": 1,
        "template": "Dose: {weight}",
        "variables": {"weight": {"min": 1, "max": 1, "decimals": 0}},
        "formula": "weight / 0",
    }

    with pytest.raises(ValueError, match="arithmetic error"):
        generate_question_instance(template)


# ── build_generated_payload ──────────────────────────────────────────────────

def test_build_generated_payload_creates_correct_structure():
    templates = {
        "TMA4100": {
            "Derivatives": [
                {
                    "category_id": 1,
                    "question_number": 1,
                    "template": "Dose for {weight} kg.",
                    "variables": {"weight": {"min": 60, "max": 60, "decimals": 0}},
                    "formula": "weight * 2",
                    "tolerance": 0,
                }
            ]
        }
    }

    generated_questions, question_snapshots = build_generated_payload(templates)

    assert "TMA4100" in generated_questions
    assert "Derivatives" in generated_questions["TMA4100"]
    assert len(generated_questions["TMA4100"]["Derivatives"]) == 1

    question = generated_questions["TMA4100"]["Derivatives"][0]
    assert "id" in question
    assert "question" in question

    # snapshot should have an entry
    assert len(question_snapshots) == 1
    snapshot = next(iter(question_snapshots.values()))
    assert snapshot["is_scored"] is True
    assert snapshot["correct_answer"] == 120.0
