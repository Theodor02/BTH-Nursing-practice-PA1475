import math

from logic.grader import (
    grade_attempt,
    normalize_unit,
    parse_numeric_answer,
    parse_numeric_with_unit,
)


def test_parse_numeric_answer_handles_valid_and_invalid_inputs():
    assert parse_numeric_answer(3) == 3.0
    assert parse_numeric_answer(" 2,5 ") == 2.5
    assert parse_numeric_answer("") is None
    assert parse_numeric_answer(True) is None
    assert parse_numeric_answer(None) is None
    assert parse_numeric_answer("not-a-number") is None


def test_grade_attempt_handles_scored_and_unscored_questions():
    snapshots = {
        "q1": {
            "id": "q1",
            "correct_answer": 10,
            "tolerance": 0.5,
            "is_scored": True,
        },
        "q2": {
            "id": "q2",
            "correct_answer": 5,
            "tolerance": 0,
            "is_scored": True,
        },
        "q3": {
            "id": "q3",
            "correct_answer": None,
            "tolerance": 0,
            "is_scored": True,
        },
        "q4": {
            "id": "q4",
            "is_scored": False,
        },
        "q5": "invalid-snapshot",
    }
    answers = {
        "q1": "10.4",
        "q2": 4,
        "q4": "anything",
    }

    result = grade_attempt(snapshots, answers)

    assert result.answered_count == 3
    assert result.scored_count == 2
    assert result.correct_count == 1
    assert result.score == 50.0
    assert result.question_snapshots["q1"]["is_correct"] is True
    assert result.question_snapshots["q2"]["is_correct"] is False
    assert result.question_snapshots["q3"]["is_correct"] is None
    assert result.question_snapshots["q4"]["is_correct"] is None


def test_grade_attempt_accepts_unit_aliases_from_default_units():
    snapshots = {
        "q1": {
            "id": "q1",
            "correct_answer": "10 ml",
            "tolerance": 0,
            "is_scored": True,
        },
        "q2": {
            "id": "q2",
            "correct_answer": "12 kl",
            "tolerance": 0,
            "is_scored": True,
        },
    }
    answers = {
        "q1": "10 milliliter",
        "q2": "12",
    }

    result = grade_attempt(snapshots, answers)

    assert result.correct_count == 2
    assert result.scored_count == 2
    assert result.score == 100.0
    assert result.question_snapshots["q1"]["is_correct"] is True
    assert result.question_snapshots["q2"]["is_correct"] is True


def test_grade_attempt_uses_snapshot_unit_when_correct_answer_is_numeric():
    snapshots = {
        "q1": {
            "id": "q1",
            "correct_answer": 10,
            "unit": "ml",
            "tolerance": 0,
            "is_scored": True,
        }
    }

    result_with_unit = grade_attempt(
        {"q1": dict(snapshots["q1"])},
        {"q1": "10 ml"},
    )
    result_without_unit = grade_attempt(
        {"q1": dict(snapshots["q1"])},
        {"q1": "10"},
    )

    assert result_with_unit.question_snapshots["q1"]["is_correct"] is True
    assert result_without_unit.question_snapshots["q1"]["is_correct"] is False
