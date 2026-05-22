"""Template variable generation and safe formula evaluation.

This module provides three public helpers used by ``question_gen.py``:

- ``generate_variables``: samples random values for each variable defined in a
  template's ``variables`` JSON field (choices, ranges, stepped ranges, and
  dependents).
- ``evaluate_formula``: evaluates the template's answer formula in a sandboxed
  Python AST context with a strict allowlist of node types and functions.
- ``validate_template_consistency``: checks at admin write-time that all
  placeholder names in the template text and formula exist in ``variables``.

Security note: ``_validate_formula_ast`` enforces a strict allowlist before
any ``eval`` is called. See the ``ALLOWED_FUNCTIONS`` block for what is
permitted.
"""
import ast
import random
import re

from logic.answer_utils import _coerce_number, _to_int_if_whole

STANDARD_NAMES=[
    "Anna", "Ali", "Maria", "Omar", "Karin", "Fatima", "Johan", "Aisha",
    "Erik", "Hassan", "Eva", "Lars", "Mikael", "Sara", "Anders", "Elin",
    "Karl", "Emma", "Per", "Lina", "Sven", "Ida", "Nils", "Hanna",
    "Bo", "Amanda", "Göran", "Julia", "Lennart", "Klara", "Bengt", "Sofia",
    "Olof", "Isabella", "Mats", "Ebba", "Jonas", "Alice", "Stefan", "Maja",
    "Jan", "Astrid", "Peter", "Agnes", "Hans", "Freja", "Magnus", "Olivia"
]


def _decimal_places(v):
    """Return the number of decimal places in a numeric value."""
    s = str(v)
    return len(s.split(".")[-1]) if "." in s else 0


def _step_choices(min_val, max_val, step):
    """Build the list of valid values for a stepped range variable."""
    dp = max(_decimal_places(min_val), _decimal_places(step))
    n = round((max_val - min_val) / step)
    return [round(min_val + i * step, dp) for i in range(n + 1)]


def _random_range(min_val, max_val, decimals=0):
    """Generate a random number within range with specified decimals.

    Used in depends_on formulas to generate randomized values based
    on other variables.
    """
    decimals = int(decimals)
    if decimals == 0:
        return random.randint(int(min_val), int(max_val))
    random_value = random.uniform(float(min_val), float(max_val))
    return round(random_value, decimals)


# Security invariants for the sandboxed eval used in this module:
#   1. __builtins__ is suppressed entirely in the eval globals.
#   2. Only AST node types in _validate_formula_ast's allowlist pass;
#      any other node (Import, Attribute, Subscript, …) raises before
#      eval is ever called.
#   3. Only the names in ALLOWED_FUNCTIONS can be called; any other
#      call site is rejected by the AST validator.
# Do NOT add functions with side-effects or filesystem/network access
# to ALLOWED_FUNCTIONS without re-auditing the sandbox.
ALLOWED_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "random": _random_range,
}

PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::[^}]*)?\}")
_PLACEHOLDER_RENDER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


def generate_variables(variables_config):
    """Generate random variable values from template variable config.

    Supports four variable configuration types:
    1. List of choices: ["v1", "v2", ...] — picks one randomly
    2. Range config: {"min": 10, "max": 20, "decimals": 0}
    3. Stepped range: {"min": 10, "max": 20, "step": 5}
    4. Dependent: {"depends_on": "x", "formula": "x * 2"}
    """
    if not isinstance(variables_config, dict):
        raise ValueError("variables_config must be a dictionary")

    generated = {}

    for variable_name, config in variables_config.items():

        if isinstance(config, str) and config == "$STANDARD_NAMES":
            generated[variable_name] = random.choice(STANDARD_NAMES)
            continue

        if isinstance(config, list):
            if not config:
                raise ValueError(
                    f"Variable {variable_name} choice list "
                    f"cannot be empty"
                )
            generated[variable_name] = random.choice(config)
            continue

        if not isinstance(config, dict):
            raise ValueError(
                f"Variable config for {variable_name} must be "
                f"a dictionary or non-empty list"
            )

        if "depends_on" in config:
            continue

        min_value = config.get("min")
        max_value = config.get("max")

        if min_value is None or max_value is None:
            raise ValueError(
                f"Variable {variable_name} requires min and max"
            )
        if min_value > max_value:
            raise ValueError(
                f"Variable {variable_name} has invalid range"
            )

        if "step" in config:
            step = config["step"]
            if step is None:
                step = 1
            if not isinstance(step, (int, float)):
                raise ValueError(
                    f"Variable {variable_name} step must be "
                    f"a number"
                )
            if step <= 0:
                raise ValueError(
                    f"Variable {variable_name} step must be "
                    f"positive"
                )
            generated[variable_name] = random.choice(
                _step_choices(min_value, max_value, step)
            )
            continue

        decimals = int(config.get("decimals", 0))
        if decimals < 0 or decimals > 4:
            raise ValueError(
                f"Variable {variable_name} decimals must be "
                f"between 0 and 4"
            )

        if decimals == 0:
            generated[variable_name] = random.randint(
                int(min_value), int(max_value)
            )
            continue

        random_value = random.uniform(
            float(min_value), float(max_value)
        )
        generated[variable_name] = round(random_value, decimals)

    for variable_name, config in variables_config.items():
        if (
            not isinstance(config, dict)
            or "depends_on" not in config
        ):
            continue

        formula = config.get("formula")
        decimals = int(config.get("decimals", 0))

        if not formula:
            raise ValueError(
                f"Dependent variable {variable_name} requires "
                f"a formula"
            )
        if decimals < 0 or decimals > 4:
            raise ValueError(
                f"Variable {variable_name} decimals must be "
                f"between 0 and 4"
            )

        try:
            parsed = ast.parse(formula, mode="eval")
            _validate_formula_ast(
                parsed,
                allowed_variable_names=set(generated.keys()),
            )

            safe_globals = {"__builtins__": {}}
            safe_locals = {**ALLOWED_FUNCTIONS, **generated}
            result = eval(
                compile(
                    parsed,
                    "<formula>",
                    "eval",
                ),
                safe_globals,
                safe_locals,
            )
            generated[variable_name] = _to_int_if_whole(
                round(_coerce_number(result), decimals)
            )
        except Exception as e:
            raise ValueError(
                f"Failed to evaluate formula for "
                f"{variable_name}: {e}"
            )

    return generated


def render_question_text(template_text, variables):
    """Replace {variableName} and {variableName:spec} placeholders with generated values.

    An optional format spec after the colon is passed directly to Python's
    format() — e.g. {minutes:02} renders 0 as "00".  Without a spec, floats
    with no fractional part are displayed as integers (2.0 → "2").
    """
    def _replace(match):
        name = match.group(1)
        spec = match.group(2)
        if name not in variables:
            return match.group(0)
        value = variables[name]
        if spec:
            return format(value, spec)
        if isinstance(value, float):
            return str(_to_int_if_whole(value))
        return str(value)

    return _PLACEHOLDER_RENDER_PATTERN.sub(_replace, template_text)


def _extract_formula_names(node):
    """Extract variable-like names used in a formula AST."""
    names = set()
    for current_node in ast.walk(node):
        if not isinstance(current_node, ast.Name):
            continue
        if current_node.id in ALLOWED_FUNCTIONS:
            continue
        names.add(current_node.id)
    return names


def _validate_formula_ast(node, allowed_variable_names=None):
    """Allow only a strict safe subset of Python AST nodes."""
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Constant,
        ast.Name,
        ast.Call,
        ast.Load,
    )

    for current_node in ast.walk(node):
        if not isinstance(current_node, allowed_nodes):
            raise ValueError(
                f"Unsupported formula expression element: "
                f"{type(current_node).__name__}"
            )

        if isinstance(current_node, ast.Call):
            if not isinstance(current_node.func, ast.Name):
                raise ValueError(
                    "Only direct function calls are allowed"
                )
            if current_node.func.id not in ALLOWED_FUNCTIONS:
                raise ValueError(
                    f"Unsupported function in formula: "
                    f"{current_node.func.id}"
                )

        if isinstance(current_node, ast.Name):
            if current_node.id in ALLOWED_FUNCTIONS:
                continue
            if (
                allowed_variable_names is not None
                and current_node.id not in allowed_variable_names
            ):
                raise ValueError(
                    f"Unknown variable in formula: "
                    f"{current_node.id}"
                )


def validate_template_consistency(
    template_text, variables_config, formula
):
    """Validate placeholder and formula variable names."""
    if not isinstance(template_text, str):
        raise ValueError("template_text must be a string")
    if not isinstance(variables_config, dict):
        raise ValueError("variables_config must be a dictionary")
    if not isinstance(formula, str) or not formula.strip():
        raise ValueError("formula must be a non-empty string")

    variable_names = set(variables_config.keys())
    template_placeholders = set(
        PLACEHOLDER_PATTERN.findall(template_text)
    )
    missing_placeholder_variables = sorted(
        template_placeholders - variable_names
    )
    if missing_placeholder_variables:
        missing_display = ", ".join(missing_placeholder_variables)
        raise ValueError(
            f"Template uses unknown variable placeholders: "
            f"{missing_display}"
        )

    parsed = ast.parse(formula, mode="eval")
    _validate_formula_ast(
        parsed, allowed_variable_names=variable_names
    )

    formula_variable_names = _extract_formula_names(parsed)
    missing_formula_variables = sorted(
        formula_variable_names - variable_names
    )
    if missing_formula_variables:
        missing_display = ", ".join(missing_formula_variables)
        raise ValueError(
            f"Formula uses unknown variables: {missing_display}"
        )


def evaluate_formula(formula, variables):
    """Evaluate a formula in a constrained execution context."""
    if not isinstance(formula, str) or not formula.strip():
        raise ValueError("formula must be a non-empty string")
    if not isinstance(variables, dict):
        raise ValueError("variables must be a dictionary")

    parsed = ast.parse(formula, mode="eval")
    _validate_formula_ast(
        parsed, allowed_variable_names=set(variables.keys())
    )

    safe_globals = {"__builtins__": {}}
    safe_locals = {**ALLOWED_FUNCTIONS, **variables}
    result = eval(
        compile(parsed, "<formula>", "eval"),
        safe_globals,
        safe_locals,
    )
    return _to_int_if_whole(round(_coerce_number(result), 2))
