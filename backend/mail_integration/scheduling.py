"""NetSuite-style recurring mailbox schedule validation and next-run calculation."""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone


TYPES = {"SINGLE", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"}
REPEAT_MINUTES = {15, 30, 60, 120, 240, 360, 480, 720}
WEEKDAYS = {"SUNDAY": 6, "MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3, "FRIDAY": 4, "SATURDAY": 5}


def validate_schedule(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Schedule must be an object.")
    result = dict(value)
    kind = str(result.get("type", "")).upper()
    if kind not in TYPES:
        raise ValueError("Choose a valid schedule type.")
    try:
        start_date = date.fromisoformat(str(result["start_date"]))
        start_time = time.fromisoformat(str(result["start_time"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Start date and start time are required.") from exc
    result["type"] = kind
    result["start_date"] = start_date.isoformat()
    result["start_time"] = start_time.strftime("%H:%M")
    result["timezone"] = str(result.get("timezone") or "UTC")
    try:
        ZoneInfo(result["timezone"])
    except Exception as exc:
        raise ValueError("Choose a valid timezone.") from exc
    end_date = result.get("end_date")
    if result.get("no_end_date", True):
        result["end_date"] = None
        result["no_end_date"] = True
    else:
        try:
            end_date = date.fromisoformat(str(end_date))
        except (TypeError, ValueError) as exc:
            raise ValueError("Choose an end date or select No end date.") from exc
        if end_date < start_date:
            raise ValueError("End date cannot be before the start date.")
        result["end_date"] = end_date.isoformat()
    try:
        result["repeat_minutes"] = int(result["repeat_minutes"]) if result.get("repeat_minutes") else None
    except (TypeError, ValueError) as exc:
        raise ValueError("Choose a valid repeat interval.") from exc
    if result["repeat_minutes"] not in (None, *REPEAT_MINUTES):
        raise ValueError("Choose a valid repeat interval.")
    if kind == "DAILY":
        result["daily_mode"] = str(result.get("daily_mode") or "INTERVAL").upper()
        if result["daily_mode"] == "INTERVAL":
            result["repeat_every"] = max(1, int(result.get("repeat_every") or 1))
        elif result["daily_mode"] == "WEEKDAYS":
            days = [str(day).upper() for day in result.get("weekdays", []) if str(day).upper() in WEEKDAYS]
            if not days:
                raise ValueError("Choose at least one weekday.")
            result["weekdays"] = days
        else:
            raise ValueError("Choose a valid daily schedule.")
    if kind == "WEEKLY":
        result["repeat_every"] = max(1, int(result.get("repeat_every") or 1))
        days = [str(day).upper() for day in result.get("weekdays", []) if str(day).upper() in WEEKDAYS]
        if not days:
            raise ValueError("Choose at least one weekday.")
        result["weekdays"] = days
    if kind in {"MONTHLY", "YEARLY"}:
        result["monthly_mode"] = str(result.get("monthly_mode") or "DAY_OF_MONTH").upper()
        if result["monthly_mode"] == "DAY_OF_MONTH":
            result["day_of_month"] = min(31, max(1, int(result.get("day_of_month") or start_date.day)))
        elif result["monthly_mode"] == "DAY_OF_WEEK":
            result["weekday"] = str(result.get("weekday") or "MONDAY").upper()
            if result["weekday"] not in WEEKDAYS:
                raise ValueError("Choose a valid weekday.")
            result["week_of_month"] = str(result.get("week_of_month") or "FIRST").upper()
            if result["week_of_month"] not in {"FIRST", "SECOND", "THIRD", "FOURTH", "LAST"}:
                raise ValueError("Choose a valid week of month.")
        else:
            raise ValueError("Choose a valid monthly schedule.")
    if kind == "YEARLY":
        result["month"] = min(12, max(1, int(result.get("month") or start_date.month)))
    return result


def _local_dt(config: dict, value: date) -> datetime:
    return datetime.combine(value, time.fromisoformat(config["start_time"]), tzinfo=ZoneInfo(config["timezone"]))


def _nth_weekday(year: int, month: int, weekday: int, ordinal: str) -> date | None:
    days = [date(year, month, d) for d in range(1, calendar.monthrange(year, month)[1] + 1) if date(year, month, d).weekday() == weekday]
    return (days[-1] if ordinal == "LAST" else days[int({"FIRST": 0, "SECOND": 1, "THIRD": 2, "FOURTH": 3}[ordinal])]) if days and (ordinal == "LAST" or len(days) > int({"FIRST": 0, "SECOND": 1, "THIRD": 2, "FOURTH": 3}[ordinal])) else None


def next_run_at(config: dict, now: datetime | None = None) -> datetime | None:
    config = validate_schedule(config)
    now = now or timezone.now()
    zone = ZoneInfo(config["timezone"])
    current = now.astimezone(zone)
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"]) if config.get("end_date") else None
    kind = config["type"]
    if kind == "SINGLE":
        candidate = _local_dt(config, start)
        return candidate.astimezone(timezone.get_current_timezone()) if candidate > current else None
    repeat_minutes = config.get("repeat_minutes")
    for offset in range(0, 3660):
        day = current.date() + timedelta(days=offset)
        if day < start or (end and day > end):
            continue
        match = False
        if kind == "DAILY":
            if config.get("daily_mode") == "WEEKDAYS":
                match = day.weekday() in [WEEKDAYS[d] for d in config["weekdays"]]
            else:
                match = (day - start).days % config["repeat_every"] == 0
        elif kind == "WEEKLY":
            match = ((day - start).days // 7) % config["repeat_every"] == 0 and day.weekday() in [WEEKDAYS[d] for d in config["weekdays"]]
        elif kind in {"MONTHLY", "YEARLY"}:
            if kind == "YEARLY" and day.month != config["month"]:
                continue
            if config["monthly_mode"] == "DAY_OF_MONTH":
                match = day.day == min(config["day_of_month"], calendar.monthrange(day.year, day.month)[1])
            else:
                match = _nth_weekday(day.year, day.month, WEEKDAYS[config["weekday"]], config["week_of_month"]) == day
        if match:
            candidate = _local_dt(config, day)
            if repeat_minutes:
                while candidate <= current and candidate.date() == day:
                    candidate += timedelta(minutes=repeat_minutes)
                # The next interval belongs to the next eligible schedule day.
                if candidate.date() != day:
                    continue
            if candidate > current:
                return candidate.astimezone(timezone.get_current_timezone())
    return None
