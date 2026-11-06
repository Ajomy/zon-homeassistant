"""Schema-shaped API documents for tests.

Field names and error bodies follow the Zon Forecast OpenAPI document:
result.watts, result.watts_hourly, result.watt_hours_day, and message
(code, type, text, info, ratelimit). Periods are stamped at their end.
"""

from __future__ import annotations

from custom_components.zon_forecast.const import API_URL

# 15-minute period ends. Watt-hours are watts * 0.25.
WATTS: dict[str, int] = {
    "2026-11-06T08:00:00+01:00": 0,
    "2026-11-06T08:15:00+01:00": 400,
    "2026-11-06T08:30:00+01:00": 800,
    "2026-11-06T08:45:00+01:00": 1200,
    "2026-11-06T09:00:00+01:00": 1000,
    "2026-11-06T09:15:00+01:00": 600,
    "2026-11-06T09:30:00+01:00": 200,
    "2026-11-06T09:45:00+01:00": 0,
    "2026-11-06T10:00:00+01:00": 160,
    "2026-11-06T10:15:00+01:00": 100,
    "2026-11-06T10:30:00+01:00": 0,
    "2026-11-07T08:00:00+01:00": 0,
    "2026-11-07T08:15:00+01:00": 200,
    "2026-11-07T08:30:00+01:00": 900,
    "2026-11-07T08:45:00+01:00": 100,
    "2026-11-07T09:15:00+01:00": 400,
}

WATTS_HOURLY: dict[str, int] = {
    "2026-11-06T09:00:00+01:00": 700,
    "2026-11-06T10:00:00+01:00": 440,
    "2026-11-07T09:00:00+01:00": 400,
}

# Frozen clock: 2026-11-06 08:10 UTC == 09:10 in Europe/Amsterdam.
FROZEN_UTC = "2026-11-06T08:10:00+00:00"

SUCCESS_HEADERS = {
    "RateLimit-Limit": "60",
    "RateLimit-Remaining": "58",
    "RateLimit-Reset": "1800",
}

UNAUTHORIZED = {
    "message": {"code": 401, "type": "error", "text": "Unauthorized"},
}

NOT_CONFIGURED = {
    "message": {
        "code": 409,
        "type": "error",
        "text": "System is not configured",
        "missing": ["location", "tilt"],
    },
}

RATE_LIMITED = {
    "message": {
        "code": 429,
        "type": "error",
        "text": "Too many requests",
        "ratelimit": {
            "period": 3600,
            "limit": 60,
            "remaining": 0,
            "retry_after": 120,
        },
    },
}

RATE_LIMIT_HEADERS = {
    "Retry-After": "120",
    "RateLimit-Limit": "60",
    "RateLimit-Remaining": "0",
    "RateLimit-Reset": "120",
}

UNAVAILABLE = {
    "message": {"code": 503, "type": "error", "text": "Service unavailable"},
}


def forecast_body(
    *,
    system_id: str = "sys_1",
    remaining: int = 59,
    watts: dict[str, int] | None = None,
) -> dict:
    """Return a 200 Forecast document."""
    return {
        "result": {
            "watts": dict(WATTS if watts is None else watts),
            "watts_hourly": dict(WATTS_HOURLY),
            "watt_hours_day": {
                "2026-11-06": 18000,
                "2026-11-07": 9000,
            },
        },
        "message": {
            "code": 0,
            "type": "success",
            "text": "",
            "info": {
                "generated_at": "2026-11-06T09:10:00+01:00",
                "system_id": system_id,
                "timezone": "Europe/Amsterdam",
                "period_minutes": 15,
                "scale": "model",
                "units": {
                    "watts": "W",
                    "watts_hourly": "W",
                    "watt_hours_day": "Wh",
                },
            },
            "ratelimit": {"period": 3600, "limit": 60, "remaining": remaining},
        },
    }


__all__ = ["API_URL"]
