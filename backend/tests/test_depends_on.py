import json
from pathlib import Path
import pytest
from logic.question_gen.question_gen import generate_question_instance

_TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "logic" / "default" / "question_templates.json"


def test_depends_on_variation():
    """Test that templates with depends_on variable variation work."""
    # Load a real template that has 'depends_on'
    with open(_TEMPLATES_PATH, encoding='utf-8-sig') as f:
        templates = json.load(f)

    # Find templates with depends_on
    depends_on_templates = []
    for t in templates:
        for var_name, var_config in (t.get('variables', {}) or {}).items():
            if isinstance(var_config, dict) and 'depends_on' in var_config:
                depends_on_templates.append((t["category_id"], var_name, var_config))

    assert depends_on_templates, "No templates with depends_on found"

    # Try to generate from each
    for i, t in enumerate(templates):
        if any(isinstance(v, dict) and 'depends_on' in v for v in (t.get('variables', {}) or {}).values()):
            print(f"\nTesting template: category={t['category_id']} index={i}")
            print(f"Variables: {t.get('variables')}")
            result = generate_question_instance(t)
            print(f"Success! Generated: {result[0]}")

if __name__ == '__main__':
    test_depends_on_variation()
