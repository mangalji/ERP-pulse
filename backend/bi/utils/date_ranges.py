"""
Date-range resolution for BI endpoints.

Executives pick a named range (Today, Yesterday, Last 7 Days, ...) or a
custom start/end. ``resolve_date_range`` returns a half-open window
``[start_date, end_date)`` as ``datetime.date`` objects, where
``start_date`` is inclusive and ``end_date`` is exclusive — matching the
convention already used by ``AnalyticsService.get_revenue_for_period``.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone

# Named ranges supported by the BI filter bar.
VALID_PRESETS = {
    'today',
    'yesterday',
    'last_7_days',
    'last_30_days',
    'this_month',
    'last_month',
    'this_quarter',
    'this_year',
    'custom',
}


def _today() -> date:
    return timezone.localdate()


def resolve_date_range(*, preset: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict:
    """
    Resolve any supported time filter into a half-open ``[start, end)``
    date window.

    Supports:
        - ``preset``: one of ``VALID_PRESETS``.
        - ``custom``: requires ``start_date`` and ``end_date`` (inclusive
          of ``end_date`` at the user's intent — the returned ``end_date``
          is bumped to the next day so the window is half-open).

    Returns a dict with ``preset``, ``start_date`` and ``end_date`` as
    ISO ``'YYYY-MM-DD'`` strings, plus ``label`` for display.
    """
    today = _today()

    if preset is None:
        preset = 'last_30_days'

    preset = preset.lower().strip()
    if preset not in VALID_PRESETS:
        raise ValueError(f"Unsupported preset: {preset}")

    if preset == 'today':
        start = today
        end = today + timedelta(days=1)
        label = 'Today'
    elif preset == 'yesterday':
        start = today - timedelta(days=1)
        end = today
        label = 'Yesterday'
    elif preset == 'last_7_days':
        start = today - timedelta(days=6)
        end = today + timedelta(days=1)
        label = 'Last 7 Days'
    elif preset == 'last_30_days':
        start = today - timedelta(days=29)
        end = today + timedelta(days=1)
        label = 'Last 30 Days'
    elif preset == 'this_month':
        start = today.replace(day=1)
        # First day of next month
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1, day=1)
        else:
            end = start.replace(month=start.month + 1, day=1)
        label = 'This Month'
    elif preset == 'last_month':
        first_this = today.replace(day=1)
        if first_this.month == 1:
            end = first_this.replace(year=first_this.year, month=1, day=1)
            start = end - timedelta(days=1)
            start = start.replace(day=1)
        else:
            end = first_this.replace(month=first_this.month - 1, day=1)
            start = end - timedelta(days=1)
            start = start.replace(day=1)
        label = 'Last Month'
    elif preset == 'this_quarter':
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=quarter_month, day=1)
        if quarter_month == 10:
            end = start.replace(year=start.year + 1, month=1, day=1)
        else:
            end = start.replace(month=quarter_month + 3, day=1)
        label = 'This Quarter'
    elif preset == 'this_year':
        start = today.replace(month=1, day=1)
        end = start.replace(year=start.year + 1, month=1, day=1)
        label = 'This Year'
    else:  # custom
        if not start_date or not end_date:
            raise ValueError('start_date and end_date are required for a custom range.')
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError:
            raise ValueError('start_date and end_date must be valid YYYY-MM-DD dates.')
        if end < start:
            raise ValueError('end_date must be on or after start_date.')
        # Inclusive end -> half-open by bumping one day.
        end = end + timedelta(days=1)
        label = 'Custom Range'

    return {
        'preset': preset,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
        'label': label,
    }
