"""Unit tests for auth_routes helper functions that don't require a live JWT."""
import pytest

import routes.auth_routes as auth_routes


# ── _split_env_list ───────────────────────────────────────────────────────────

def test_split_env_list_returns_empty_list_for_none():
    assert auth_routes._split_env_list(None) == []


def test_split_env_list_returns_empty_list_for_empty_string():
    assert auth_routes._split_env_list("") == []


def test_split_env_list_parses_comma_separated_values():
    result = auth_routes._split_env_list("a,b,c")
    assert result == ["a", "b", "c"]


def test_split_env_list_strips_whitespace_from_items():
    result = auth_routes._split_env_list(" a , b , c ")
    assert result == ["a", "b", "c"]


def test_split_env_list_skips_blank_items():
    result = auth_routes._split_env_list("a,,b,")
    assert result == ["a", "b"]


# ── _normalize_string ─────────────────────────────────────────────────────────

def test_normalize_string_returns_none_for_non_string():
    assert auth_routes._normalize_string(42) is None
    assert auth_routes._normalize_string(None) is None


def test_normalize_string_returns_none_for_whitespace_only():
    assert auth_routes._normalize_string("   ") is None


def test_normalize_string_strips_and_returns():
    assert auth_routes._normalize_string("  hello  ") == "hello"


# ── _get_frontend_client_ids ──────────────────────────────────────────────────

def test_get_frontend_client_ids_uses_multi_value_env_var(monkeypatch):
    monkeypatch.setenv("AZURE_FRONTEND_CLIENT_IDS", "id-1,id-2")
    monkeypatch.delenv("AZURE_FRONTEND_CLIENT_ID", raising=False)

    result = auth_routes._get_frontend_client_ids()

    assert result == {"id-1", "id-2"}


def test_get_frontend_client_ids_falls_back_to_single_env_var(monkeypatch):
    monkeypatch.delenv("AZURE_FRONTEND_CLIENT_IDS", raising=False)
    monkeypatch.setenv("AZURE_FRONTEND_CLIENT_ID", "single-client-id")

    result = auth_routes._get_frontend_client_ids()

    assert "single-client-id" in result


def test_get_frontend_client_ids_requires_single_env_when_multi_env_missing(monkeypatch):
    monkeypatch.delenv("AZURE_FRONTEND_CLIENT_IDS", raising=False)
    monkeypatch.delenv("AZURE_FRONTEND_CLIENT_ID", raising=False)

    with pytest.raises(RuntimeError, match="AZURE_FRONTEND_CLIENT_ID"):
        auth_routes._get_frontend_client_ids()


# ── _get_expected_audiences ───────────────────────────────────────────────────

def test_get_expected_audiences_uses_configured_value(monkeypatch):
    monkeypatch.setenv("AZURE_API_AUDIENCES", "aud-1,aud-2")

    result = auth_routes._get_expected_audiences()

    assert result == {"aud-1", "aud-2"}


def test_get_expected_audiences_returns_defaults_when_not_configured(monkeypatch):
    monkeypatch.delenv("AZURE_API_AUDIENCES", raising=False)
    monkeypatch.setenv("AZURE_API_CLIENT_ID", "my-backend-id")

    result = auth_routes._get_expected_audiences()

    assert "my-backend-id" in result
    assert "api://my-backend-id" in result


# ── _get_allowed_domains ──────────────────────────────────────────────────────

def test_get_allowed_domains_requires_env(monkeypatch):
    monkeypatch.delenv("ALLOWED_EMAIL_DOMAINS", raising=False)

    with pytest.raises(RuntimeError, match="ALLOWED_EMAIL_DOMAINS"):
        auth_routes._get_allowed_domains()


def test_get_allowed_domains_lowercases_configured_domains(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "Example.Com,TEST.ORG")

    result = auth_routes._get_allowed_domains()

    assert result == {"example.com", "test.org"}


# ── _get_required_scope ───────────────────────────────────────────────────────

def test_get_required_scope_returns_configured_value(monkeypatch):
    monkeypatch.setenv("AZURE_API_REQUIRED_SCOPE", "custom_scope")

    assert auth_routes._get_required_scope() == "custom_scope"


def test_get_required_scope_returns_default_when_not_configured(monkeypatch):
    monkeypatch.delenv("AZURE_API_REQUIRED_SCOPE", raising=False)

    assert auth_routes._get_required_scope() == auth_routes.DEFAULT_REQUIRED_SCOPE


# ── _extract_email ────────────────────────────────────────────────────────────

def test_extract_email_prefers_email_claim():
    claims = {
        "email": "primary@example.com",
        "preferred_username": "secondary@example.com",
    }
    assert auth_routes._extract_email(claims) == "primary@example.com"


def test_extract_email_falls_back_to_preferred_username():
    claims = {"preferred_username": "user@example.com"}
    assert auth_routes._extract_email(claims) == "user@example.com"


def test_extract_email_falls_back_to_upn():
    claims = {"upn": "user@example.com"}
    assert auth_routes._extract_email(claims) == "user@example.com"


def test_extract_email_falls_back_to_unique_name():
    claims = {"unique_name": "user@example.com"}
    assert auth_routes._extract_email(claims) == "user@example.com"


def test_extract_email_raises_when_no_usable_claim():
    with pytest.raises(auth_routes.AuthenticationError, match="missing a usable email claim"):
        auth_routes._extract_email({})


# ── _validate_email_domain ────────────────────────────────────────────────────

def test_validate_email_domain_raises_for_email_without_at_sign(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "example.com")

    # "user@" → rpartition("@") gives domain="" which is falsy
    with pytest.raises(auth_routes.AuthenticationError, match="email claim is invalid"):
        auth_routes._validate_email_domain("user@")


def test_validate_email_domain_raises_for_disallowed_domain(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "allowed.com")

    with pytest.raises(auth_routes.AuthenticationError, match="not allowed to use the application"):
        auth_routes._validate_email_domain("user@evil.com")


def test_validate_email_domain_accepts_allowed_domain(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "allowed.com")

    # Should not raise
    auth_routes._validate_email_domain("user@allowed.com")


# ── resolve_verified_request_context — missing oid ───────────────────────────

def test_resolve_raises_for_missing_oid_claim(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "example.com")

    monkeypatch.setattr(
        auth_routes,
        "_decode_and_validate_claims",
        lambda _token: {
            # oid is absent
            "email": "user@example.com",
            "tid": "00000000-0000-0000-0000-000000000000",
        },
    )

    with pytest.raises(auth_routes.AuthenticationError, match="missing the oid claim"):
        auth_routes.resolve_verified_request_context("Bearer some-token")
