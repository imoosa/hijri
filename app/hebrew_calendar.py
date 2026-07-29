"""
Hebrew (Jewish) calendar -- month-grid layer on top of `convertdate.hebrew`,
the same library interfaith_calendar.py already uses for Jewish holiday
dates. [certain] -- deterministic, agreed civil algorithm, not an
approximation (unlike hindu_events in interfaith_calendar.py).

IMPORTANT QUIRK -- month numbering is NOT chronological within one year:
convertdate numbers months Nisan=1 ... Elul=6, Tishri=7 ... Adar=12 (or
Adar=12/Adar Bet=13 in a leap year). But the Hebrew YEAR number increments
at Tishri, not at Nisan -- so within "year 5786", Tishri (month 7) falls
chronologically BEFORE Nisan (month 1). Iterating range(1, 13) in a UI
would jump backward in time in the middle of the year. Use
`chronological_months()` / `next_month()` / `prev_month()` below instead
of the raw month numbers for any "next/previous month" navigation.
"""

from datetime import date

from convertdate import hebrew as _hebrew

MONTHS_HEB = _hebrew.MONTHS  # index 0 = Nisan (month 1), matches convertdate's 1-based numbering

# Chronological month order (year starts at Tishri) -- what a calendar UI
# should page through, not convertdate's raw 1-13 numbering.
_CHRONO_COMMON = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
_CHRONO_LEAP = [7, 8, 9, 10, 11, 12, 13, 1, 2, 3, 4, 5, 6]


def is_leap(year: int) -> bool:
    return _hebrew.leap(year)


def chronological_months(year: int):
    return _CHRONO_LEAP if is_leap(year) else _CHRONO_COMMON


def month_name(month: int) -> str:
    return MONTHS_HEB[month - 1]


def next_month(year: int, month: int):
    order = chronological_months(year)
    idx = order.index(month)
    if idx == len(order) - 1:  # was Elul (year-end) -> Tishri of next year
        return year + 1, 7
    return year, order[idx + 1]


def prev_month(year: int, month: int):
    order = chronological_months(year)
    idx = order.index(month)
    if idx == 0:  # was Tishri (year-start) -> Elul of previous year
        return year - 1, 6
    return year, order[idx - 1]


def gregorian_to_hebrew(g: date):
    return _hebrew.from_gregorian(g.year, g.month, g.day)


def hebrew_to_gregorian(year: int, month: int, day: int) -> date:
    gy, gm, gd = _hebrew.to_gregorian(year, month, day)
    return date(gy, gm, gd)


def month_grid(year: int, month: int):
    """List of {"gregorian": iso, "day": n} for every day in this Hebrew month."""
    length = _hebrew.month_length(year, month)
    days = []
    for d in range(1, length + 1):
        g = hebrew_to_gregorian(year, month, d)
        days.append({"gregorian": g.isoformat(), "day": d})
    return days
