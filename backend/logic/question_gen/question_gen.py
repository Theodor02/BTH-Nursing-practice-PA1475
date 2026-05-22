"""Question instance generation from parametrised templates.

``generate_question_instance`` is the core entry point: given a template dict
it samples random variable values, evaluates the formula in a sandboxed AST,
and returns a (frontend_question, backend_snapshot) tuple.

``build_generated_payload`` calls it for every selected template and assembles
the nested dict structure expected by the quiz API response.

The generation loop retries up to 10 times if the formula raises an
``ArithmeticError`` (e.g. division by zero from bad variable combinations) or
if the result falls outside ``answer_min`` / ``answer_max`` bounds.
"""
import uuid
from decimal import Decimal

from logic.answer_utils import compute_effective_tolerance, _to_int_if_whole
from logic.question_gen.question_gen_helpers import (
    evaluate_formula,
    generate_variables,
    render_question_text,
)


def _to_float(value, default=0.0):
    """Coerce a value to float, returning ``default`` on failure."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_float_or_none(value):
    """Coerce a value to float, returning ``None`` on failure or for ``None`` input."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def generate_question_instance(template):
    """Generate one randomized question and backend snapshot from a template."""
    if not isinstance(template, dict):
        raise ValueError("template must be a dictionary")

    required_fields = {"category_id", "template", "variables", "formula"}
    if not required_fields.issubset(template.keys()):
        return template, {
            "id": str(template.get("id", uuid.uuid4())),
            "template_id": template.get("id"),
            "correct_answer": None,
            "tolerance": None,
            "is_scored": False,
        }

    # Template consistency is validated at admin write-time
    # (admin_routes._validate_template_consistency_from_state); skipping here
    # avoids surfacing 400s to students from malformed admin edits.

    round_answer = bool(template.get("round_answer", False))
    answer_type = template.get("answer_type") or "numeric"
    round_to_unit = template.get("round_to_unit") or None
    answer_min = _to_float_or_none(template.get("answer_min"))
    answer_max = _to_float_or_none(template.get("answer_max"))
    tolerance_raw = _to_float(template.get("tolerance"), default=0.0)
    tolerance_percent = _to_float_or_none(template.get("tolerance_percent"))

    _MAX_ATTEMPTS = 10
    for attempt in range(_MAX_ATTEMPTS):
        generated_variables = generate_variables(template.get("variables", {}))
        try:
            correct_answer = evaluate_formula(template.get("formula", ""), generated_variables)
        except ArithmeticError:
            if attempt == _MAX_ATTEMPTS - 1:
                raise ValueError(
                    f"Formula '{template.get('formula')}' produced an arithmetic error "
                    f"(e.g. division by zero) on every attempt"
                )
            continue

        if round_answer:
            correct_answer = _to_int_if_whole(round(float(correct_answer)))

        # For duration/time_of_day: round to the specified unit granularity.
        # Duration values are in seconds; time_of_day values are in minutes.
        if round_to_unit and answer_type in ("duration", "time_of_day"):
            if answer_type == "time_of_day":
                _steps = {"min": 1, "h": 60}.get(round_to_unit)
            else:
                _steps = {"s": 1, "min": 60, "h": 3600, "d": 86400}.get(round_to_unit)
            if _steps:
                correct_answer = round(float(correct_answer) / _steps) * _steps

        # Retry if outside allowed answer range.
        ca_float = float(correct_answer)
        if answer_min is not None and ca_float < answer_min:
            if attempt == _MAX_ATTEMPTS - 1:
                raise ValueError(
                    f"Generated answer {correct_answer} is below answer_min={answer_min} "
                    f"on every attempt"
                )
            continue
        if answer_max is not None and ca_float > answer_max:
            if attempt == _MAX_ATTEMPTS - 1:
                raise ValueError(
                    f"Generated answer {correct_answer} is above answer_max={answer_max} "
                    f"on every attempt"
                )
            continue

        break

    question_text = render_question_text(template.get("template", ""), generated_variables)
    question_instance_id = f"{template['category_id']}-{template.get('question_number', 0)}-{uuid.uuid4().hex[:10]}"

    effective_tolerance = compute_effective_tolerance(
        correct_number=float(correct_answer),
        tolerance=tolerance_raw,
        tolerance_percent=tolerance_percent,
    )

    template_id = template.get("id")

    frontend_question = {
        "id": question_instance_id,
        "template_id": template_id,
        "question": question_text,
        "correct_answer": correct_answer,
        "tolerance": effective_tolerance,
        "unit": template.get("unit"),
        "hints": template.get("hints") or [],
        "link": template.get("link"),
        "answer_type": answer_type,
        "round_answer": round_answer,
        "round_to_unit": round_to_unit,
    }

    snapshot = {
        "id": question_instance_id,
        "template_id": template_id,
        "question": question_text,
        "variables": generated_variables,
        "correct_answer": correct_answer,
        "tolerance": effective_tolerance,
        "unit": template.get("unit"),
        "user_answer": None,
        "is_correct": None,
        "is_scored": True,
        "answer_type": answer_type,
        "round_answer": round_answer,
        "round_to_unit": round_to_unit,
        "tolerance_percent": tolerance_percent,
    }

    return frontend_question, snapshot


def build_generated_payload(selected_templates):
    """Generate frontend payload and backend snapshot from selected templates."""
    generated_questions = {}
    question_snapshots = {}

    for course_code, category_templates in selected_templates.items():
        generated_questions[course_code] = {}

        for category_name, templates in category_templates.items():
            generated_questions[course_code][category_name] = []

            for template in templates:
                frontend_question, snapshot = generate_question_instance(template)
                generated_questions[course_code][category_name].append(frontend_question)
                question_snapshots[str(snapshot["id"])] = snapshot

    return generated_questions, question_snapshots
