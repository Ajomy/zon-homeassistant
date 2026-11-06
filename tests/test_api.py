"""Tests for rate-limit header selection."""

from __future__ import annotations

from custom_components.zon_forecast.api import missing_fields, retry_after_seconds
from custom_components.zon_forecast.const import DEFAULT_RETRY_AFTER_SECONDS

from .payload import NOT_CONFIGURED, RATE_LIMITED


def test_retry_after_prefers_header_then_reset_then_body() -> None:
    """429 wait is Retry-After, then RateLimit-Reset, then body retry_after."""
    assert (
        retry_after_seconds(
            {"Retry-After": "120", "RateLimit-Reset": "10"}, RATE_LIMITED
        )
        == 120
    )
    assert retry_after_seconds({"RateLimit-Reset": "90"}, None) == 90
    body = {
        "message": {
            "code": 429,
            "type": "error",
            "text": "Too many requests",
            "ratelimit": {
                "period": 3600,
                "limit": 60,
                "remaining": 0,
                "retry_after": 45,
            },
        }
    }
    assert retry_after_seconds({}, body) == 45
    assert retry_after_seconds({}, None) == DEFAULT_RETRY_AFTER_SECONDS
    assert retry_after_seconds({"Retry-After": "0"}, None) == 1


def test_missing_fields_keeps_known_enum_order() -> None:
    """409 missing values are the documented enum, in API order."""
    assert missing_fields(NOT_CONFIGURED) == ["location", "tilt"]
    assert missing_fields(
        {"message": {"text": "x", "missing": ["nope", "azimuth"]}}
    ) == ["azimuth"]
