"""
Sunni (Umm al-Qura) Islamic calendar conversion.

The Umm al-Qura calendar is the official Saudi Arabian calendar, used by
many Sunni Muslims worldwide. Unlike the Bohra/Fatimid tabular calendar,
Umm al-Qura is based on astronomical calculations and follows a different
leap year pattern.

IMPORTANT ACCURACY NOTE:
The Umm al-Qura calendar is not a simple tabular calendar - it's based on
actual lunar visibility criteria. This implementation uses the standard
tabular approximation commonly used for civil purposes, but for religious
observance, actual moon sighting may vary.
"""

from datetime import date, timedelta
from . import hijri_calendar as hc

# Umm al-Qura uses a different leap year pattern than the Bohra calendar
# This is the standard Kuwaiti/Umm al-Qura 30-year cycle
UMM_AL_QURA_LEAP_YEARS = {2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29}

MONTH_NAMES = [
    "Muharram", "Safar", "Rabi' al-Awwal",
    "Rabi' al-Akhir", "Jumada al-Ula", "Jumada al-Akhirah",
    "Rajab", "Sha'ban", "Ramadan",
    "Shawwal", "Dhu al-Qi'dah", "Dhu al-Hijjah",
]

# Sunni-specific events (major holidays)
SUNNI_EVENTS = [
    {"month": 1, "day": 1, "title": "Islamic New Year", "is_holiday": True},
    {"month": 1, "day": 10, "title": "Day of Ashura", "is_holiday": False},
    {"month": 9, "day": 1, "title": "Ramadan begins", "is_holiday": False},
    {"month": 9, "day": 27, "title": "Laylat al-Qadr", "is_holiday": False},
    {"month": 10, "day": 1, "title": "Eid al-Fitr", "is_holiday": True},
    {"month": 12, "day": 9, "title": "Day of Arafah", "is_holiday": False},
    {"month": 12, "day": 10, "title": "Eid al-Adha", "is_holiday": True},
    {"month": 12, "day": 11, "title": "Eid al-Adha (2nd day)", "is_holiday": True},
    {"month": 12, "day": 12, "title": "Eid al-Adha (3rd day)", "is_holiday": True},
    {"month": 12, "day": 13, "title": "Eid al-Adha (4th day)", "is_holiday": True},
]


def _is_leap(year: int) -> bool:
    pos = ((year - 1) % 30) + 1
    return pos in UMM_AL_QURA_LEAP_YEARS


def _year_length(year: int) -> int:
    return 355 if _is_leap(year) else 354


def _month_length(year: int, month: int) -> int:
    # Odd months 30 days, even months 29 days, except month 12 in a leap year
    if month == 12 and _is_leap(year):
        return 30
    return 30 if month % 2 == 1 else 29


# Use the same JD conversion as hijri_calendar but with different leap years
# We need to override the leap year determination
def sunni_hijri_to_jd(year: int, month: int, day: int) -> int:
    """Convert Sunni Hijri date to Julian Day using Umm al-Qura rules."""
    jd = hc.EPOCH_JD + hc.CALIBRATION_OFFSET
    jd += (year - 1) * 354
    for y in range(1, year):
        if _is_leap(y):
            jd += 1
    for m in range(1, month):
        jd += _month_length(year, m)
    jd += day - 1
    return jd


def sunni_jd_to_hijri(jd: int):
    """Convert Julian Day to Sunni Hijri date using Umm al-Qura rules."""
    jd -= (hc.EPOCH_JD + hc.CALIBRATION_OFFSET)
    year = 1
    while True:
        yl = _year_length(year)
        if jd < yl:
            break
        jd -= yl
        year += 1
    month = 1
    while True:
        ml = _month_length(year, month)
        if jd < ml:
            break
        jd -= ml
        month += 1
    day = jd + 1
    return year, month, day


def sunni_gregorian_to_hijri(g: date):
    return sunni_jd_to_hijri(hc.gregorian_to_jd(g))


def sunni_hijri_to_gregorian(year: int, month: int, day: int) -> date:
    return hc.jd_to_gregorian(sunni_hijri_to_jd(year, month, day))


def sunni_month_name(month: int) -> str:
    return MONTH_NAMES[month - 1]


def sunni_month_grid(year: int, month: int):
    """Return list of (gregorian_date, hijri_day) for every day in this Hijri month."""
    days = []
    length = _month_length(year, month)
    for d in range(1, length + 1):
        g = sunni_hijri_to_gregorian(year, month, d)
        days.append({"gregorian": g.isoformat(), "hijri_day": d})
    return days


def get_sunni_events(year: int, month: int):
    """Get Sunni events for a specific Hijri month/year."""
    events_by_day = {}
    for event in SUNNI_EVENTS:
        if event["month"] == month:
            events_by_day.setdefault(event["day"], []).append({
                "title": event["title"],
                "is_holiday": event["is_holiday"],
                "color": "sunni",
                "description": None,
                "is_fasting_day": False,
            })
    return events_by_day