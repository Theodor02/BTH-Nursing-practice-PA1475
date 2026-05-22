import pytest

from logic.database.seeding.seed_defaults import _assert_safe_to_drop_schema


def test_assert_safe_to_drop_schema_allows_compose_db_host_in_dev(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("CONFIRM_DROP_SCHEMA", "true")
    monkeypatch.setenv("POSTGRES_HOST", "db")

    _assert_safe_to_drop_schema()


@pytest.mark.parametrize(
    "env, confirm_drop_schema, postgres_host",
    [
        ("production", "true", "db"),
        ("dev", "false", "db"),
        ("dev", "true", "example.com"),
    ],
)
def test_assert_safe_to_drop_schema_rejects_unsafe_combinations(
    monkeypatch,
    env,
    confirm_drop_schema,
    postgres_host,
):
    monkeypatch.setenv("ENV", env)
    monkeypatch.setenv("CONFIRM_DROP_SCHEMA", confirm_drop_schema)
    monkeypatch.setenv("POSTGRES_HOST", postgres_host)

    with pytest.raises(RuntimeError):
        _assert_safe_to_drop_schema()
