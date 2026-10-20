import json

from app.core.middleware import RequestLoggingMiddleware


def test_request_body_logging_redacts_google_oauth_tokens() -> None:
    middleware = object.__new__(RequestLoggingMiddleware)
    body = json.dumps(
        {
            "access_token": "oauth-secret",
            "external_account_id": "account-123",
            "nested": [{"refresh_token": "refresh-secret"}],
        }
    ).encode()

    logged_body = middleware._filter_request_body(body)

    assert "oauth-secret" not in logged_body
    assert "refresh-secret" not in logged_body
    assert logged_body == (
        '{"access_token": "***HIDDEN***", "external_account_id": "account-123", '
        '"nested": [{"refresh_token": "***HIDDEN***"}]}'
    )


def test_request_body_logging_omits_unstructured_body() -> None:
    middleware = object.__new__(RequestLoggingMiddleware)

    assert middleware._filter_request_body(b"secret=raw-token") == (
        "<non-JSON request body, 16 bytes>"
    )
