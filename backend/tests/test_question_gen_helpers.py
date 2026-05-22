import ast
from decimal import Decimal

import pytest

from logic.question_gen.question_gen import generate_question_instance
from logic.answer_utils import compute_effective_tolerance
from logic.question_gen.question_gen_helpers import (
    _coerce_number,
    _extract_formula_names,
    _random_range,
    _step_choices,
    _validate_formula_ast,
    evaluate_formula,
    generate_variables,
    render_question_text,
    validate_template_consistency,
)


def test_generate_variables_supports_choice_list():
    variables = generate_variables({"name": ["Anna", "Ali", "Maria"]})
    assert variables["name"] in {"Anna", "Ali", "Maria"}


def test_generate_variables_rejects_invalid_decimals_range():
    with pytest.raises(ValueError, match="decimals must be between 0 and 4"):
        generate_variables({"dose": {"min": 1, "max": 2, "decimals": 5}})


def test_validate_template_consistency_rejects_unknown_placeholder():
    with pytest.raises(ValueError, match="unknown variable placeholders"):
        validate_template_consistency(
            template_text="Dose for {weight} kg and {missing}",
            variables_config={"weight": {"min": 50, "max": 70, "decimals": 0}},
            formula="weight * 2",
        )


def test_validate_template_consistency_rejects_unknown_formula_variable():
    with pytest.raises(ValueError, match="Unknown variable in formula"):
        validate_template_consistency(
            template_text="Dose for {weight} kg",
            variables_config={"weight": {"min": 50, "max": 70, "decimals": 0}},
            formula="weight * factor",
        )


def test_evaluate_formula_requires_declared_variables():
    with pytest.raises(ValueError, match="Unknown variable in formula"):
        evaluate_formula("weight * factor", {"weight": 60})


def test_generate_variables_step_snaps_to_grid():
    for _ in range(50):
        variables = generate_variables(
            {"dose": {"min": 25, "max": 40, "step": 5}}
        )
        assert variables["dose"] in {25, 30, 35, 40}


def test_generate_variables_step_float_snaps_to_grid():
    for _ in range(50):
        variables = generate_variables(
            {"rate": {"min": 0.5, "max": 3.0, "step": 0.5}}
        )
        assert variables["rate"] in {0.5, 1.0, 1.5, 2.0, 2.5, 3.0}


def test_generate_variables_step_rejects_non_positive():
    with pytest.raises(ValueError, match="step must be positive"):
        generate_variables({"dose": {"min": 10, "max": 20, "step": 0}})


def test_generate_variables_step_defaults_null_to_one():
    for _ in range(20):
        variables = generate_variables({"dose": {"min": 10, "max": 20, "step": None}})
        assert 10 <= variables["dose"] <= 20
        assert isinstance(variables["dose"], int)


def test_generate_variables_rejects_unsafe_dependent_formula():
    with pytest.raises(
        ValueError, match="Unsupported formula expression element"
    ):
        generate_variables(
            {
                "x": {"min": 1, "max": 1, "decimals": 0},
                "y": {
                    "depends_on": "x",
                    "formula": "(1).__class__",
                    "decimals": 0,
                },
            }
        )


def test_generate_question_instance_supports_list_variables():
    template = {
        "category_id": 1,
        "question_number": 1,
        "template": "Patient {name} weighs {weight} kg.",
        "variables": {
            "name": ["Anna", "Ali"],
            "weight": {"min": 60, "max": 60, "decimals": 0},
        },
        "formula": "weight * 2",
        "unit": "mg",
        "tolerance": 0.5,
    }

    frontend_question, snapshot = generate_question_instance(template)

    assert frontend_question["question"].startswith("Patient ")
    assert snapshot["correct_answer"] == 120
    assert isinstance(snapshot["correct_answer"], int)
    assert snapshot["variables"]["name"] in {"Anna", "Ali"}


def test_evaluate_formula_returns_int_for_whole_number():
    result = evaluate_formula("weight * 2", {"weight": 60})
    assert result == 120
    assert isinstance(result, int)


def test_evaluate_formula_preserves_decimal_when_fractional():
    result = evaluate_formula("dose / concentration", {"dose": 1, "concentration": 4})
    assert result == 0.25
    assert isinstance(result, float)


def test_generate_variables_dependent_var_returns_int_when_whole():
    variables = generate_variables({
        "x": {"min": 10, "max": 10, "decimals": 0},
        "y": {"depends_on": "x", "formula": "x * 2", "decimals": 0},
    })
    assert variables["y"] == 20
    assert isinstance(variables["y"], int)


def test_generate_question_instance_integer_answer_is_int_type():
    template = {
        "category_id": 1,
        "question_number": 1,
        "template": "Patient weighs {weight} kg.",
        "variables": {"weight": {"min": 60, "max": 60, "decimals": 0}},
        "formula": "weight * 2",
        "unit": "mg",
        "tolerance": 0,
    }
    _, snapshot = generate_question_instance(template)
    assert snapshot["correct_answer"] == 120
    assert isinstance(snapshot["correct_answer"], int)


# ── _coerce_number ────────────────────────────────────────────────────────────

def test_coerce_number_accepts_decimal():
    assert _coerce_number(Decimal("3.14")) == pytest.approx(3.14)


def test_coerce_number_accepts_int_and_float():
    assert _coerce_number(5) == 5.0
    assert _coerce_number(2.5) == 2.5


def test_coerce_number_raises_for_unsupported_type():
    with pytest.raises(ValueError, match="Unsupported numeric value"):
        _coerce_number("not-a-number")


# ── _random_range ─────────────────────────────────────────────────────────────

def test_random_range_with_decimals_returns_float_in_range():
    for _ in range(20):
        val = _random_range(1.0, 2.0, decimals=2)
        assert 1.0 <= val <= 2.0


def test_random_range_without_decimals_returns_integer():
    for _ in range(20):
        val = _random_range(1, 5)
        assert isinstance(val, int)
        assert 1 <= val <= 5


# ── _step_choices ─────────────────────────────────────────────────────────────

def test_step_choices_produces_correct_grid():
    choices = _step_choices(0, 10, 5)
    assert choices == [0, 5, 10]


# ── generate_variables ────────────────────────────────────────────────────────

def test_generate_variables_rejects_non_dict_config():
    with pytest.raises(ValueError, match="variables_config must be a dictionary"):
        generate_variables("not-a-dict")


def test_generate_variables_uses_standard_names_sentinel():
    variables = generate_variables({"name": "$STANDARD_NAMES"})
    from logic.question_gen.question_gen_helpers import STANDARD_NAMES
    assert variables["name"] in STANDARD_NAMES


def test_generate_variables_rejects_empty_choice_list():
    with pytest.raises(ValueError, match="choice list cannot be empty"):
        generate_variables({"x": []})


def test_generate_variables_rejects_invalid_config_type():
    with pytest.raises(ValueError, match="must be a dictionary or non-empty list"):
        generate_variables({"x": 42})


def test_generate_variables_rejects_missing_min_or_max():
    with pytest.raises(ValueError, match="requires min and max"):
        generate_variables({"x": {"max": 10}})


def test_generate_variables_rejects_invalid_range():
    with pytest.raises(ValueError, match="invalid range"):
        generate_variables({"x": {"min": 10, "max": 5}})


def test_generate_variables_with_decimals_produces_float():
    for _ in range(10):
        variables = generate_variables({"x": {"min": 1, "max": 2, "decimals": 2}})
        assert isinstance(variables["x"], float)
        assert 1.0 <= variables["x"] <= 2.0


def test_generate_variables_rejects_dependent_without_formula():
    with pytest.raises(ValueError, match="requires a formula"):
        generate_variables(
            {
                "x": {"min": 1, "max": 1, "decimals": 0},
                "y": {"depends_on": "x"},
            }
        )


def test_generate_variables_rejects_dependent_invalid_decimals():
    with pytest.raises(ValueError, match="decimals must be between 0 and 4"):
        generate_variables(
            {
                "x": {"min": 1, "max": 1, "decimals": 0},
                "y": {"depends_on": "x", "formula": "x * 2", "decimals": 9},
            }
        )


# ── render_question_text ──────────────────────────────────────────────────────

def test_render_question_text_replaces_placeholders():
    result = render_question_text(
        "Patient {name} weighs {weight} kg.",
        {"name": "Anna", "weight": 60},
    )
    assert result == "Patient Anna weighs 60 kg."


def test_render_question_text_leaves_unknown_placeholders_intact():
    result = render_question_text("Hello {unknown}!", {"name": "Anna"})
    assert result == "Hello {unknown}!"


def test_render_question_text_applies_zero_pad_format_spec():
    result = render_question_text("kl. {h}:{m:02}", {"h": 8, "m": 0})
    assert result == "kl. 8:00"


def test_render_question_text_format_spec_nonzero_value():
    result = render_question_text("kl. {h}:{m:02}", {"h": 14, "m": 30})
    assert result == "kl. 14:30"


def test_validate_template_consistency_accepts_format_spec_placeholder():
    validate_template_consistency(
        template_text="kl. {startHour}:{startMinutes:02}",
        variables_config={
            "startHour": {"min": 0, "max": 23, "step": 1},
            "startMinutes": [0, 30],
        },
        formula="startHour * 60 + startMinutes",
    )


# ── _validate_formula_ast ─────────────────────────────────────────────────────

def test_validate_formula_ast_rejects_attribute_access():
    parsed = ast.parse("(1).__class__", mode="eval")
    with pytest.raises(ValueError, match="Unsupported formula expression element"):
        _validate_formula_ast(parsed)


def test_validate_formula_ast_rejects_disallowed_function_name():
    parsed = ast.parse("open('file')", mode="eval")
    with pytest.raises(ValueError, match="Unsupported function in formula"):
        _validate_formula_ast(parsed)


# ── validate_template_consistency ────────────────────────────────────────────

def test_validate_template_consistency_rejects_non_string_template():
    with pytest.raises(ValueError, match="template_text must be a string"):
        validate_template_consistency(
            template_text=123,
            variables_config={"x": {"min": 1, "max": 2}},
            formula="x * 2",
        )


def test_validate_template_consistency_rejects_non_dict_variables():
    with pytest.raises(ValueError, match="variables_config must be a dictionary"):
        validate_template_consistency(
            template_text="Hello {x}",
            variables_config=["x"],
            formula="x * 2",
        )


def test_validate_template_consistency_rejects_empty_formula():
    with pytest.raises(ValueError, match="formula must be a non-empty string"):
        validate_template_consistency(
            template_text="Hello",
            variables_config={"x": {"min": 1, "max": 2}},
            formula="   ",
        )


def test_validate_template_consistency_rejects_unknown_formula_variables():
    # _validate_formula_ast runs before the name-diff check and raises
    # "Unknown variable in formula" when a name is not in the variable set.
    with pytest.raises(ValueError, match="Unknown variable in formula"):
        validate_template_consistency(
            template_text="Hello",
            variables_config={"x": {"min": 1, "max": 2}},
            formula="x + unknown_var",
        )


# ── evaluate_formula ──────────────────────────────────────────────────────────

def test_evaluate_formula_rejects_non_string_formula():
    with pytest.raises(ValueError, match="formula must be a non-empty string"):
        evaluate_formula(42, {"x": 1})


def test_evaluate_formula_rejects_non_dict_variables():
    with pytest.raises(ValueError, match="variables must be a dictionary"):
        evaluate_formula("x * 2", [("x", 1)])


def test_evaluate_formula_computes_correctly():
    result = evaluate_formula("x * 2 + 1", {"x": 5})
    assert result == 11.0


# ── compute_effective_tolerance ──────────────────────────────────────────────
# (answer_within_tolerance was consolidated into answer_utils.compute_effective_tolerance)

def test_compute_effective_tolerance_exact_match():
    tol = compute_effective_tolerance(10, 0, None)
    assert abs(10 - 10) <= tol  # exact match always passes with tolerance=0


def test_compute_effective_tolerance_within():
    tol = compute_effective_tolerance(10, 0.5, None)
    assert abs(10 - 10.4) <= tol


def test_compute_effective_tolerance_outside():
    tol = compute_effective_tolerance(10, 0.5, None)
    assert not (abs(10 - 11) <= tol)


# ── additional coverage for remaining branches ────────────────────────────────

def test_validate_formula_ast_rejects_non_name_function_in_call():
    """A chained call like foo()() has an inner Call as the func — not a Name."""
    # Build AST for a call where .func is itself a Call, not a Name.
    # This exercises the "Only direct function calls are allowed" branch.
    inner_call = ast.Call(
        func=ast.Name(id="abs", ctx=ast.Load()),
        args=[],
        keywords=[],
    )
    outer_call = ast.Call(
        func=inner_call,  # func is a Call, not a Name
        args=[],
        keywords=[],
    )
    expr = ast.Expression(body=outer_call)
    ast.fix_missing_locations(expr)

    with pytest.raises(ValueError, match="Only direct function calls are allowed"):
        _validate_formula_ast(expr)


def test_extract_formula_names_skips_allowed_functions():
    """Names that are ALLOWED_FUNCTIONS should not be added to the result set."""
    # Parse "abs(x) + round(y)"
    node = ast.parse("abs(x) + round(y)", mode="eval")
    names = _extract_formula_names(node)
    # "abs" and "round" are allowed functions and must be excluded
    assert "abs" not in names
    assert "round" not in names
    # the variable names should be present
    assert "x" in names
    assert "y" in names
