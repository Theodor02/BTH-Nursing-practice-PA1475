from flask import Flask
import pytest

from config import configure_app


def test_configure_app_uses_redis_rate_limit_storage_when_redis_url_set(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("APP_ENV", "production")

    app = Flask(__name__)
    configure_app(app)

    assert app.config["RATELIMIT_STORAGE_URI"] == "redis://localhost:6379/0"


def test_configure_app_uses_memory_rate_limit_storage_for_local_dev(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "development")

    app = Flask(__name__)
    configure_app(app)

    assert app.config["RATELIMIT_STORAGE_URI"] == "memory://"


def test_configure_app_requires_redis_rate_limit_storage_in_production(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    app = Flask(__name__)

    with pytest.raises(RuntimeError) as exc_info:
        configure_app(app)

    assert "REDIS_URL must be set for rate limiting" in str(exc_info.value)