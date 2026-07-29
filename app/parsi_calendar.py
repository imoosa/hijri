"""
Parsi (Shahenshahi) calendar -- the Zoroastrian calendar used by most Indian
Parsis. See interfaith_calendar.py's module docstring for the accuracy note
on _REF_NAVROZ; that calibration caveat applies to every date this module
produces too, since everything here is computed from it.

Structure: 12 months of 30 days each (360 days) + 5 intercalary Gatha days
= 365 days flat, no leap year ever. Fravardin 1 (Navroz) is New Year's Day;
the 5 Gatha days sit at the very end of the year, right before the next
Navroz -- they're modelled here as a pseudo-13th "month".

There's no Zoroastrian-era (Yazdegerdi) year count wired up here, only
month/day -- the "year" this module reports is just the Gregorian year
Navroz fell in, which is enough to build a month grid but isn't a
traditional Parsi year number.
"""

from datetime import date, timedelta

MONTH_NAMES = [
    "Fravardin", "Ardibehesht", "Khordad", "Tir", "Amardad", "Shehrevar",
    "Meher", "Avan", "Adar", "Dae", "Bahman", "Aspandarmad",
]
GATHA_MONTH = 13
GATHA_LABEL = "Gatha days"

# [likely, unverified] Reference Navroz (Parsi New Year) date -- see
# interfaith_calendar.py's module docstring for the accuracy caveat.
# Kept here as the single source of truth; interfaith_calendar.py imports
# this module for its Parsi festival dates rather than duplicating it.
_REF_NAVROZ = date(2026, 8, 16)


def shahenshahi_navroz(year: int) -> date:
    """Navroz (Parsi New Year) for a given Gregorian year.

    The Shahenshahi year is a flat 365 days with no leap-year correction,
    so this is just whole 365-day steps from the reference date -- no
    lunar/solar position calculation needed, unlike the Hindu section of
    interfaith_calendar.py."""
    candidate = _REF_NAVROZ
    while candidate.year < year:
        candidate += timedelta(days=365)
    while candidate.year > year:
        candidate -= timedelta(days=365)
    return candidate


def month_name(month: int) -> str:
    if month == GATHA_MONTH:
        return GATHA_LABEL
    return MONTH_NAMES[month - 1]


def _navroz_bracketing(g: date):
    """Return (parsi_year, navroz_date) such that navroz_date <= g < the
    following Navroz."""
    year = g.year
    navroz = shahenshahi_navroz(year)
    if g < navroz:
        year -= 1
        navroz = shahenshahi_navroz(year)
    else:
        nxt = shahenshahi_navroz(year + 1)
        if g >= nxt:
            year += 1
            navroz = nxt
    return year, navroz


def gregorian_to_parsi(g: date):
    year, navroz = _navroz_bracketing(g)
    offset = (g - navroz).days  # 0..364
    if offset < 360:
        month = offset // 30 + 1
        day = offset % 30 + 1
    else:
        month = GATHA_MONTH
        day = offset - 360 + 1  # 1..5
    return year, month, day


def parsi_to_gregorian(year: int, month: int, day: int) -> date:
    navroz = shahenshahi_navroz(year)
    if month == GATHA_MONTH:
        offset = 360 + (day - 1)
    else:
        offset = (month - 1) * 30 + (day - 1)
    return navroz + timedelta(days=offset)


def month_grid(year: int, month: int):
    """List of {"gregorian": iso, "day": n} for every day in this Parsi month
    (or the 5 Gatha days, when month == GATHA_MONTH)."""
    length = 5 if month == GATHA_MONTH else 30
    days = []
    for d in range(1, length + 1):
        g = parsi_to_gregorian(year, month, d)
        days.append({"gregorian": g.isoformat(), "day": d})
    return days


def next_month(year: int, month: int):
    if month == GATHA_MONTH:
        return year + 1, 1
    if month == 12:
        return year, GATHA_MONTH
    return year, month + 1


def prev_month(year: int, month: int):
    if month == 1:
        return year - 1, GATHA_MONTH
    if month == GATHA_MONTH:
        return year, 12
    return year, month - 1
