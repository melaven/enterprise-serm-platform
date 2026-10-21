import json

from app.core.middleware import RequestLoggingMiddleware


def test_request_body_logging_omits_sensitive_review_payloads() -> None:
    middleware = object.__new__(RequestLoggingMiddleware)
    body = json.dumps(
        {
            "access_token": "oauth-secret",
            "external_account_id": "account-123",
            "nested": [{"refresh_token": "refresh-secret"}],
        }
    ).encode()

    logged_body = middleware._filter_request_body(body)

    assert logged_body == "<omitted>"


def test_request_body_logging_omits_unstructured_body() -> None:
    middleware = object.__new__(RequestLoggingMiddleware)

    assert middleware._filter_request_body(b"secret=raw-token") == ("<omitted>")
