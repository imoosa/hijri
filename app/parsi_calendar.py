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

from datetime import date, datetime, timedelta

from . import prayer_times_accurate as _pta

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


# ==================== Gah (5 daily watches) ====================
# [likely -- simplified] The five Gahs in Zoroastrian practice: Havan
# (sunrise-noon), Rapithwin (noon-mid-afternoon), Uzerin (mid-afternoon-
# sunset), Aiwisruthrem (sunset-midnight), Ushahin (midnight-sunrise).
# Real practice in some traditions suspends Rapithwin in the winter half
# of the year, merging it into Havan/Uzerin -- that seasonal rule is NOT
# modelled here; this uses a flat year-round 5-way split anchored to
# sunrise/noon/+3h/sunset/midnight. Verify against your community's Gah
# timetable if this matters for religious observance.

GAHS = [
    {"name": "Havan",        "desc": "Morning watch -- sunrise to noon"},
    {"name": "Rapithwin",    "desc": "Midday watch -- noon to mid-afternoon"},
    {"name": "Uzerin",       "desc": "Afternoon watch -- mid-afternoon to sunset"},
    {"name": "Aiwisruthrem", "desc": "Evening watch -- sunset to midnight"},
    {"name": "Ushahin",      "desc": "Night watch -- midnight to dawn"},
]

# 30 Roj (day-name) list for the Shahenshahi calendar. [likely] -- standard
# published list; spelling/transliteration varies by source.
ROJ_NAMES = [
    "Hormazd", "Bahman", "Ardibehesht", "Shehrevar", "Aspandard", "Khordad",
    "Amardad", "Dae-pa-Adar", "Adar", "Aban", "Khorshed", "Mohor",
    "Tir", "Gosh", "Dae-pa-Meher", "Meher", "Srosh", "Rashne",
    "Fravardin", "Behram", "Ram", "Govad", "Dae-pa-Din", "Din",
    "Ashishvangh", "Ashtad", "Asman", "Zamyad", "Mareshpand", "Aneran",
]


def roj_name(day: int) -> str:
    """Name of the Roj (1-30) in the Shahenshahi calendar. The 5 Gatha
    days have no Roj name in this implementation -- [guessing] returns
    'Gatha' for those rather than inventing one."""
    if day < 1 or day > 30:
        return "Gatha"
    return ROJ_NAMES[day - 1]


def gah_now(now_local: datetime, lat: float, lng: float, tz_offset: float) -> dict:
    """Which Gah it is right now, plus minutes until the next Gah change
    (for a change-alert trigger). See the accuracy note above GAHS."""
    g = now_local.date()
    jd = _pta.julian_day(g)
    dec, eqt = _pta.sun_position(jd)
    noon_utc = 12.0 - lng / 15.0 - eqt
    sunrise_utc = _pta.time_for_angle(jd, lat, lng, _pta.SUNSET_ANGLE, True, eqt, noon_utc)
    sunset_utc = _pta.time_for_angle(jd, lat, lng, _pta.SUNSET_ANGLE, False, eqt, noon_utc)

    segments = [
        ("Havan", sunrise_utc, noon_utc),
        ("Rapithwin", noon_utc, noon_utc + 3.0),
        ("Uzerin", noon_utc + 3.0, sunset_utc),
        ("Aiwisruthrem", sunset_utc, 24.0),
        ("Ushahin", 24.0, 24.0 + sunrise_utc),
    ]

    now_utc_hours = now_local.hour + now_local.minute / 60 + now_local.second / 3600 - tz_offset
    if now_utc_hours < sunrise_utc:
        now_utc_hours += 24  # so "just after local midnight" lands inside Ushahin, not before Havan

    current, next_change_utc = "Ushahin", 24.0 + sunrise_utc
    for name, start, end in segments:
        if start <= now_utc_hours < end:
            current, next_change_utc = name, end
            break

    return {"gah": current, "minutes_to_change": max(0, round((next_change_utc - now_utc_hours) * 60))}
