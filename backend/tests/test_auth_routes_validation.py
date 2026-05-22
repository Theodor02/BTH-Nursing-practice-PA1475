import pytest

import routes.auth_routes as auth_routes


@pytest.fixture(autouse=True)
def hermetic_auth_env(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "student.bth.se,bth.se")


def test_resolve_rejects_missing_authorization_header():
    with pytest.raises(auth_routes.AuthenticationError) as exc_info:
        auth_routes.resolve_verified_request_context(None)

    assert str(exc_info.value) == "Missing Authorization header."


def test_resolve_rejects_non_bearer_authorization_scheme():
    with pytest.raises(auth_routes.AuthenticationError) as exc_info:
        auth_routes.resolve_verified_request_context("Basic abc123")

    assert str(exc_info.value) == "Authorization header must use Bearer token auth."


def test_resolve_rejects_empty_bearer_token():
    with pytest.raises(auth_routes.AuthenticationError) as exc_info:
        auth_routes.resolve_verified_request_context("Bearer   ")

    assert str(exc_info.value) == "Authorization header must use Bearer token auth."


def test_resolve_rejects_disallowed_email_domain(monkeypatch):
    monkeypatch.setattr(
        auth_routes,
        "_decode_and_validate_claims",
        lambda _token: {
            "oid": "oid-123",
            "email": "student@example.com",
            "tid": "00000000-0000-0000-0000-000000000000",
        },
    )

    with pytest.raises(auth_routes.AuthenticationError) as exc_info:
        auth_routes.resolve_verified_request_context("Bearer token")

    assert str(exc_info.value) == "This account is not allowed to use the application."


def test_resolve_accepts_allowed_domain_from_preferred_username(monkeypatch):
    expected_tenant_id = "00000000-0000-0000-0000-000000000000"
    monkeypatch.setattr(
        auth_routes,
        "_decode_and_validate_claims",
        lambda _token: {
            "oid": "oid-456",
            "preferred_username": "student@bth.se",
            "tid": expected_tenant_id,
        },
    )

    context = auth_routes.resolve_verified_request_context("Bearer token")

    assert context.sso_id == "oid-456"
    assert context.email == "student@bth.se"
    assert context.tenant_id == expected_tenant_id


def test_resolve_propagates_scope_validation_failure(monkeypatch):
    def mock_decode(_token):
        raise auth_routes.AuthenticationError(
            "Microsoft access token is missing the required API scope."
        )

    monkeypatch.setattr(auth_routes, "_decode_and_validate_claims", mock_decode)

    with pytest.raises(auth_routes.AuthenticationError) as exc_info:
        auth_routes.resolve_verified_request_context("Bearer token")

    assert str(exc_info.value) == "Microsoft access token is missing the required API scope."