"""
Occurrence expansion for recurring personal events (birthdays, anniversaries,
etc.). Each event is stored as ONE anchor date plus a repeat rule -- not one
database row per year -- so this module is what turns that into concrete
dates whenever the calendar needs to know what falls on which day.

Repeat rules:
  never   - the anchor date only, a single occurrence, no recurrence.
  weekly  - same weekday as the anchor date, every week from then on.
  monthly - same day-of-month as the anchor date, every month from then on.
            Clamped to the last day of a shorter month -- an anchor of the
            31st shows on the 30th in a 30-day month, the 28th/29th in Feb.
  yearly  - same month/day as the anchor date, every year from then on.
            A Feb 29 anchor falls back to Feb 28 in non-leap years (common
            convention for leap-day birthdays/anniversaries).

An event never produces an occurrence before its own anchor date -- it
doesn't recur backward into the past relative to when it started.
"""

import calendar
from datetime import date, timedelta
from typing import List

from . import hijri_calendar as hc

VALID_REPEATS = {"never", "weekly", "monthly", "yearly"}
VALID_RECUR_CALENDARS = {"gregorian", "hijri"}


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def occurrences_in_range(anchor: date, repeat: str, range_start: date, range_end: date) -> List[date]:
    """All occurrence dates for one event that fall within [range_start, range_end]
    (inclusive on both ends). Returns [] if the event hasn't started yet by
    range_end, if the range is invalid, or if repeat isn't recognized."""
    if range_end < range_start or range_end < anchor:
        return []

    if repeat == "never":
        return [anchor] if range_start <= anchor <= range_end else []

    if repeat == "weekly":
        d = anchor
        if d < range_start:
            # jump close to range_start in one step instead of looping day by day
            weeks = (range_start - d).days // 7
            d += timedelta(days=7 * weeks)
        while d < range_start:
            d += timedelta(days=7)
        results = []
        while d <= range_end:
            results.append(d)
            d += timedelta(days=7)
        return results

    if repeat == "monthly":
        results = []
        y, m = anchor.year, anchor.month
        while True:
            day = min(anchor.day, _last_day_of_month(y, m))
            candidate = date(y, m, day)
            if candidate > range_end:
                break
            if candidate >= range_start:
                results.append(candidate)
            m += 1
            if m > 12:
                m = 1
                y += 1
        return results

    if repeat == "yearly":
        results = []
        y = anchor.year
        while True:
            month, day = anchor.month, anchor.day
            if month == 2 and day == 29 and not calendar.isleap(y):
                day = 28
            candidate = date(y, month, day)
            if candidate > range_end:
                break
            if candidate >= range_start:
                results.append(candidate)
            y += 1
        return results

    return []


def hijri_yearly_occurrences_in_range(hijri_month: int, hijri_day: int, anchor: date,
                                       range_start: date, range_end: date) -> List[date]:
    """Occurrences of a Hijri month/day, recurring once per Hijri year, mapped
    onto Gregorian dates -- for anniversaries that should track the lunar
    calendar (drifting ~11 days earlier each Gregorian year) rather than the
    fixed Gregorian date. `anchor` is only used as the "don't recur before
    this" floor, same rule as the Gregorian yearly case.

    NOTE [likely]: accuracy is bounded by hijri_calendar.py's own accuracy --
    see that module's docstring on LEAP_YEARS/EPOCH_JD calibration. This
    function does not add or remove any error on top of that."""
    if range_end < range_start:
        return []

    start_hy, _, _ = hc.gregorian_to_hijri(range_start)
    end_hy, _, _ = hc.gregorian_to_hijri(range_end)

    results = []
    # +/-1 buffer: a Hijri year boundary can shift the mapped Gregorian date
    # just outside a naive [start_hy, end_hy] window.
    for hy in range(start_hy - 1, end_hy + 2):
        try:
            candidate = hc.hijri_to_gregorian(hy, hijri_month, hijri_day)
        except Exception:
            continue
        if candidate < anchor:
            continue
        if range_start <= candidate <= range_end:
            results.append(candidate)
    return sorted(results)


def age_on(anchor: date, as_of: date = None) -> int:
    """Whole years elapsed from `anchor` to `as_of` (defaults to today) --
    the usual birthday/anniversary calculation: the current year doesn't
    count until the anniversary month/day has actually been reached.
    Returns 0 if `as_of` is before `anchor` (event hasn't happened yet)."""
    as_of = as_of or date.today()
    if as_of < anchor:
        return 0
    years = as_of.year - anchor.year
    if (as_of.month, as_of.day) < (anchor.month, anchor.day):
        years -= 1
    return years


def event_occurrences_in_range(event, range_start: date, range_end: date) -> List[date]:
    """Dispatcher for a PersonalEvent-like object (needs .anchor_date, .repeat,
    .hijri_month, .hijri_day, .recur_calendar). Routes to the Hijri-yearly
    calculator only when repeat is 'yearly', a Hijri date is actually set,
    and the user chose to recur by it -- every other case falls back to the
    plain Gregorian-anchor logic above."""
    use_hijri = (
        event.repeat == "yearly"
        and getattr(event, "recur_calendar", "gregorian") == "hijri"
        and event.hijri_month
        and event.hijri_day
    )
    if use_hijri:
        return hijri_yearly_occurrences_in_range(
            event.hijri_month, event.hijri_day, event.anchor_date, range_start, range_end
        )
    return occurrences_in_range(event.anchor_date, event.repeat, range_start, range_end)
