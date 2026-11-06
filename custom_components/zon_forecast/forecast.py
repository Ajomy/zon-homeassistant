"""Parse a Zon Forecast API payload.

The public contract is ``GET /api/v1/forecast`` (see
https://zonforecast.com/api/v1/openapi.json). This module does not compute a
forecast. ``result.watts`` is average watts for each 15-minute period, stamped
at the period end. ``result.watts_hourly`` is average watts for each local
clock hour, stamped at the hour end. ``result.watt_hours_day`` is watt-hours
for the local calendar days the API returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ForecastParseError(ValueError):
    """The JSON body does not match the forecast schema."""


def _require_dict(value: Any, what: str) -> dict[str, Any]:
    """Return ``value`` when it is an object."""
    if not isinstance(value, dict):
        raise ForecastParseError(f"{what} must be an object")
    return value


def _require_str(value: Any, what: str) -> str:
    """Return ``value`` when it is a string."""
    if not isinstance(value, str):
        raise ForecastParseError(f"{what} must be a string")
    return value


def _as_int(value: Any, what: str) -> int:
    """Return an integer field. Booleans and fractional numbers are rejected."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ForecastParseError(f"{what} must be an integer")
    if isinstance(value, float) and not value.is_integer():
        raise ForecastParseError(f"{what} must be an integer")
    return int(value)


def _parse_offset_timestamp(raw: Any, what: str, timezone: ZoneInfo) -> datetime:
    """Parse an ISO-8601 timestamp that carries a numeric offset."""
    text = _require_str(raw, what).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as err:
        raise ForecastParseError(f"{what} is not ISO-8601") from err
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ForecastParseError(f"{what} must include a numeric offset")
    return parsed.astimezone(timezone)


def _parse_series(raw: Any, timezone: ZoneInfo, *, what: str) -> dict[datetime, int]:
    """Parse a map of offset timestamps to integer watts or watt-hours."""
    body = _require_dict(raw, what)
    parsed = {
        _parse_offset_timestamp(key, f"{what} timestamp", timezone): _as_int(
            value, f"{what} value"
        )
        for key, value in body.items()
    }
    return dict(sorted(parsed.items()))


def _parse_days(raw: Any, *, what: str) -> dict[date, int]:
    """Parse ``YYYY-MM-DD`` day totals."""
    body = _require_dict(raw, what)
    days: dict[date, int] = {}
    for key, value in body.items():
        text = _require_str(key, f"{what} date")
        if len(text) != 10 or text[4] != "-" or text[7] != "-":
            raise ForecastParseError(f"{what} keys must be YYYY-MM-DD")
        try:
            day = date.fromisoformat(text)
        except ValueError as err:
            raise ForecastParseError(f"{what} keys must be YYYY-MM-DD") from err
        days[day] = _as_int(value, f"{what} value")
    return days


def _sum_periods(data: dict[datetime, int], after: datetime, until: datetime) -> int:
    """Sum period-end samples in ``(after, until]``."""
    total = 0
    for timestamp, watt_hours in data.items():
        if timestamp <= after:
            continue
        if timestamp > until:
            break
        total += watt_hours
    return total


@dataclass(frozen=True)
class Forecast:
    """One successful ``GET /api/v1/forecast`` body."""

    watts: dict[datetime, int]
    watts_hourly: dict[datetime, int]
    wh_period: dict[datetime, int]
    wh_days: dict[date, int]
    timezone: str
    system_id: str
    generated_at: datetime
    period_minutes: int
    scale: str | None
    text: str
    rate_limit: int
    rate_remaining: int
    rate_reset_seconds: int | None = None

    def now(self) -> datetime:
        """Return the current time in the system's timezone."""
        return datetime.now(tz=ZoneInfo(self.timezone))

    def day_production(self, specific_date: date) -> int:
        """Return watt-hours for one local calendar day."""
        return self.wh_days.get(specific_date, 0)

    @property
    def energy_production_today(self) -> int:
        """Return watt-hours for today."""
        return self.day_production(self.now().date())

    @property
    def energy_production_tomorrow(self) -> int:
        """Return watt-hours for tomorrow."""
        return self.day_production(self.now().date() + timedelta(days=1))

    @property
    def energy_production_today_remaining(self) -> int:
        """Return watt-hours for periods that end after now and today."""
        midnight = self.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return _sum_periods(self.wh_period, self.now(), midnight + timedelta(days=1))

    @property
    def power_production_now(self) -> int:
        """Return average watts of the 15-minute period that contains now."""
        return self.power_production_at_time(self.now())

    @property
    def power_highest_peak_time_today(self) -> datetime | None:
        """Return the period end with the highest watts today."""
        return self.peak_production_time(self.now().date())

    @property
    def power_highest_peak_time_tomorrow(self) -> datetime | None:
        """Return the period end with the highest watts tomorrow."""
        return self.peak_production_time(self.now().date() + timedelta(days=1))

    @property
    def energy_current_hour(self) -> int:
        """Return watt-hours for periods that end during the current hour."""
        start = self.now().replace(minute=0, second=0, microsecond=0)
        return _sum_periods(self.wh_period, start, start + timedelta(hours=1))

    def peak_production_time(self, specific_date: date) -> datetime | None:
        """Return the period-end timestamp of the highest sample on a date."""
        peak = max(
            (
                (timestamp, watt)
                for timestamp, watt in self.watts.items()
                if timestamp.date() == specific_date
            ),
            key=lambda item: item[1],
            default=None,
        )
        return peak[0] if peak is not None else None

    def power_production_at_time(self, moment: datetime) -> int:
        """Return watts for the period that contains ``moment``.

        Each sample covers the ``period_minutes`` ending at its timestamp.
        A moment that falls in a gap, or after the last period, is 0.
        """
        zone = ZoneInfo(self.timezone)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=zone)
        else:
            moment = moment.astimezone(zone)
        length = timedelta(minutes=self.period_minutes)
        for end, power in self.watts.items():
            if end - length < moment <= end:
                return power
        return 0

    def sum_energy_production(self, period_hours: int) -> int:
        """Return watt-hours over the next clock hours, excluding the current one."""
        start = self.now().replace(minute=0, second=0, microsecond=0) + timedelta(
            hours=1
        )
        return _sum_periods(
            self.wh_period, start, start + timedelta(hours=period_hours)
        )

    def watt_hours_by_period_start(self) -> dict[datetime, int]:
        """Return period watt-hours keyed by when each period starts.

        The API stamps the end. The energy dashboard buckets a timestamp into
        the clock hour it falls in, so the start of the period is the key.
        """
        delta = timedelta(minutes=self.period_minutes)
        return {end - delta: watt_hours for end, watt_hours in self.wh_period.items()}


def _zone(name: str) -> ZoneInfo:
    """Return a timezone or raise a parse error."""
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as err:
        raise ForecastParseError(
            "message.info.timezone is not a known timezone"
        ) from err


def _optional_enum(info: dict[str, Any], key: str, allowed: set[str]) -> str | None:
    """Return an optional enum property."""
    if key not in info or info[key] is None:
        return None
    value = info[key]
    if not isinstance(value, str) or value not in allowed:
        raise ForecastParseError(f"message.info.{key} is invalid")
    return value


def parse_forecast(payload: Any) -> Forecast:
    """Build a forecast from a 200 ``Forecast`` document."""
    body = _require_dict(payload, "response")
    result = _require_dict(body.get("result"), "result")
    for key in ("watts", "watts_hourly", "watt_hours_day"):
        if key not in result:
            raise ForecastParseError(f"result.{key} is missing")

    message = _require_dict(body.get("message"), "message")
    for key in ("code", "type", "text", "info", "ratelimit"):
        if key not in message:
            raise ForecastParseError(f"message.{key} is missing")
    if _as_int(message.get("code"), "message.code") != 0:
        raise ForecastParseError("message.code must be 0")
    if message.get("type") != "success":
        raise ForecastParseError("message.type must be success")
    text = _require_str(message.get("text"), "message.text")

    info = _require_dict(message.get("info"), "message.info")
    for key in ("generated_at", "system_id", "timezone", "units"):
        if key not in info:
            raise ForecastParseError(f"message.info.{key} is missing")
    system_id = _require_str(info.get("system_id"), "message.info.system_id").strip()
    if not system_id:
        raise ForecastParseError("message.info.system_id is empty")
    timezone_name = _require_str(info.get("timezone"), "message.info.timezone")
    timezone = _zone(timezone_name)
    generated_at = _parse_offset_timestamp(
        info.get("generated_at"), "message.info.generated_at", timezone
    )

    period_minutes = 15
    if "period_minutes" in info and info["period_minutes"] is not None:
        period_minutes = _as_int(info["period_minutes"], "message.info.period_minutes")
        if period_minutes != 15:
            raise ForecastParseError("message.info.period_minutes must be 15")
    scale = _optional_enum(info, "scale", {"model", "nameplate"})

    units = _require_dict(info.get("units"), "message.info.units")
    expected_units = {
        "watts": "W",
        "watts_hourly": "W",
        "watt_hours_day": "Wh",
    }
    for key, expected in expected_units.items():
        if key in units and units[key] != expected:
            raise ForecastParseError(f"message.info.units.{key} must be {expected}")

    ratelimit = _require_dict(message.get("ratelimit"), "message.ratelimit")
    for key in ("period", "limit", "remaining"):
        if key not in ratelimit:
            raise ForecastParseError(f"message.ratelimit.{key} is missing")
    period = _as_int(ratelimit["period"], "message.ratelimit.period")
    if period != 3600:
        raise ForecastParseError("message.ratelimit.period must be 3600")
    limit = _as_int(ratelimit["limit"], "message.ratelimit.limit")
    remaining = _as_int(ratelimit["remaining"], "message.ratelimit.remaining")

    watts = _parse_series(result.get("watts"), timezone, what="result.watts")
    watts_hourly = _parse_series(
        result.get("watts_hourly"), timezone, what="result.watts_hourly"
    )
    hours = period_minutes / 60
    wh_period = {end: int(round(power * hours)) for end, power in watts.items()}
    wh_days = _parse_days(result.get("watt_hours_day"), what="result.watt_hours_day")

    return Forecast(
        watts=watts,
        watts_hourly=watts_hourly,
        wh_period=wh_period,
        wh_days=wh_days,
        timezone=timezone.key,
        system_id=system_id,
        generated_at=generated_at,
        period_minutes=period_minutes,
        scale=scale,
        text=text,
        rate_limit=limit,
        rate_remaining=remaining,
    )
