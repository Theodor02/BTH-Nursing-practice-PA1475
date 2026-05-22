"""Question grading logic.

Provides ``grade_attempt``, which scores a complete set of student answers
against the backend question snapshots created at attempt generation time.
Supports three answer types: ``numeric``, ``duration``, and ``time_of_day``.

The grader mutates ``question_snapshots`` in place (adding ``user_answer`` and
``is_correct`` fields) and returns a ``GradeResult`` summary. Callers must
treat the returned snapshot dict as the authoritative per-question record for
persistence.
"""
from dataclasses import dataclass

from logic.answer_utils import (
    compute_effective_tolerance,
    normalize_unit,
    parse_duration,
    parse_numeric_answer,
    parse_numeric_with_unit,
    parse_time_of_day,
)

_DURATION_ROUND_STEPS = {"s": 1, "min": 60, "h": 3600, "d": 86400}
_TIME_OF_DAY_ROUND_STEPS = {"min": 1, "h": 60}


def _apply_round_to_unit(value, round_to_unit, answer_type="duration"):
    """Round a duration (seconds) or time_of_day (minutes) to the nearest unit.

    For duration, steps are in seconds. For time_of_day, steps are in minutes.
    """
    if value is None or not round_to_unit:
        return value
    if answer_type == "time_of_day":
        steps = _TIME_OF_DAY_ROUND_STEPS.get(round_to_unit)
    else:
        steps = _DURATION_ROUND_STEPS.get(round_to_unit)
    if not steps:
        return value
    return round(value / steps) * steps


@dataclass
class GradeResult:
    """Aggregated outcome of a single quiz attempt.

    Attributes:
        score: Percentage of scored questions answered correctly (0–100).
        correct_count: Number of questions graded as correct.
        scored_count: Number of questions that have a gradeable correct answer.
            Unscored questions (``is_scored=False``) are excluded.
        answered_count: Number of questions the student provided any answer for.
        question_snapshots: The mutated snapshot dict with ``user_answer`` and
            ``is_correct`` fields populated for every question.
    """

    score: float
    correct_count: int
    scored_count: int
    answered_count: int
    question_snapshots: dict


def grade_attempt(question_snapshots: dict, answers: dict) -> GradeResult:
    """Grade all answers in a quiz attempt and return the aggregated result.

    Mutates ``question_snapshots`` in place, adding ``user_answer`` and
    ``is_correct`` to each entry. Dispatches to the appropriate parser
    (duration, time_of_day, or numeric) based on the snapshot's
    ``answer_type`` field.

    Args:
        question_snapshots: Dict mapping question instance id → snapshot dict.
            Each snapshot must contain ``correct_answer``, ``answer_type``, and
            ``is_scored``. Snapshots with ``is_scored=False`` are skipped for
            correctness but still receive a ``user_answer`` annotation.
        answers: Dict mapping question instance id → raw student answer string.

    Returns:
        A ``GradeResult`` with score, counts, and the annotated snapshots.
    """
    correct_count = 0
    scored_count = 0
    answered_count = 0

    for question_id, original_snapshot in question_snapshots.items():
        if not isinstance(original_snapshot, dict):
            continue

        snapshot = dict(original_snapshot)
        question_snapshots[question_id] = snapshot

        raw_answer = answers.get(question_id)
        if raw_answer is not None:
            answered_count += 1

        answer_type = snapshot.get("answer_type", "numeric") or "numeric"
        round_answer = bool(snapshot.get("round_answer", False))
        round_to_unit = snapshot.get("round_to_unit") or None

        snapshot['user_answer'] = raw_answer

        if not snapshot.get('is_scored', False):
            snapshot['is_correct'] = None
            continue

        raw_correct = snapshot.get('correct_answer')
        tolerance_raw = parse_numeric_answer(snapshot.get('tolerance'))
        tolerance_percent = snapshot.get('tolerance_percent')

        if answer_type == "duration":
            user_number = parse_duration(raw_answer)
            correct_number = parse_duration(raw_correct)

            if correct_number is None:
                snapshot['is_correct'] = None
                continue

            correct_number = _apply_round_to_unit(correct_number, round_to_unit, "duration")
            user_number = _apply_round_to_unit(user_number, round_to_unit, "duration")

            scored_count += 1
            tolerance_value = compute_effective_tolerance(
                correct_number=correct_number,
                tolerance=tolerance_raw,
                tolerance_percent=tolerance_percent,
            )
            is_correct = (
                user_number is not None
                and abs(user_number - correct_number) <= tolerance_value
            )
            snapshot['is_correct'] = bool(is_correct)
            if is_correct:
                correct_count += 1
            continue

        if answer_type == "time_of_day":
            user_number = parse_time_of_day(raw_answer)
            correct_number = parse_time_of_day(raw_correct)

            if correct_number is None:
                snapshot['is_correct'] = None
                continue

            correct_number = _apply_round_to_unit(correct_number, round_to_unit, "time_of_day")
            user_number = _apply_round_to_unit(user_number, round_to_unit, "time_of_day")

            scored_count += 1
            tolerance_value = compute_effective_tolerance(
                correct_number=correct_number,
                tolerance=tolerance_raw,
                tolerance_percent=tolerance_percent,
            )

            is_correct = (
                user_number is not None
                and abs(user_number - correct_number) <= tolerance_value
            )
            snapshot['is_correct'] = bool(is_correct)
            if is_correct:
                correct_count += 1
            continue

        # Standard numeric answer path.
        parsed_answer = parse_numeric_answer(raw_answer)
        if parsed_answer is not None:
            user_number, user_unit = parsed_answer, ""
        else:
            user_number, user_unit = parse_numeric_with_unit(raw_answer)

        user_unit = normalize_unit(user_unit, allow_blank_alias=True)

        correct_number, correct_unit = parse_numeric_with_unit(raw_correct)
        correct_unit = normalize_unit(correct_unit) or normalize_unit(
            snapshot.get('unit')
        )

        if correct_number is None:
            snapshot['is_correct'] = None
            continue

        scored_count += 1

        if round_answer:
            if user_number is not None:
                user_number = round(user_number)
            correct_number = round(correct_number)

        tolerance_value = compute_effective_tolerance(
            correct_number=correct_number,
            tolerance=tolerance_raw,
            tolerance_percent=tolerance_percent,
        )

        number_correct = (
            user_number is not None
            and abs(user_number - correct_number) <= tolerance_value
        )

        if correct_unit:
            unit_correct = user_unit == correct_unit
            is_correct = number_correct and unit_correct
        else:
            is_correct = number_correct

        snapshot['is_correct'] = bool(is_correct)
        if is_correct:
            correct_count += 1

    score = round((correct_count / scored_count) * 100.0, 2) if scored_count > 0 else 0.0
    return GradeResult(
        score=score,
        correct_count=correct_count,
        scored_count=scored_count,
        answered_count=answered_count,
        question_snapshots=question_snapshots,
    )
