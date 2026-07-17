"""
Bohra (Fatimid) tabular Hijri calendar conversion.

IMPORTANT ACCURACY NOTE:
The Dawoodi Bohra calendar is a fixed, pre-calculated ("tabular") Islamic
calendar -- it does NOT depend on moon sighting, so it can be computed
exactly, unlike Sunni/civil Islamic calendars. However there are two things
you MUST verify against an official Bohra source (e.g. misbah.co, thali
dates published by your jamaat) before shipping this:

1. LEAP_YEARS: the set of years (position within a 30-year cycle) that get
   an extra day in month 12 (Zilhaj). This implementation uses the common
   Fatimid/tabular set {2,5,8,10,13,16,19,21,24,27,29}. This is a
   [likely-correct but unverified] value pulled from general tabular-Islamic-
   calendar literature, not a Bohra primary source.
2. EPOCH_JD: the Julian Day Number of 1 Moharram, 1 AH. Small errors here
   shift EVERY date by a fixed number of days. There's a CALIBRATION_OFFSET
   below specifically so you can correct this by comparing a known date
   (e.g. today's date on your official calendar) against this module's
   output and adjusting the offset until they match.

Do not trust this for religious observance until you've calibrated it.
"""

from datetime import date, timedelta

# Civil epoch of the Islamic calendar (Julian Day Number for 1 Moharram, 1 AH)
EPOCH_JD = 1948440

# Leap years within each 30-year cycle (1-indexed position in cycle).
# [guessing] verify against your jamaat's official calendar.
LEAP_YEARS = {2, 5, 8, 10, 13, 16, 19, 21, 24, 27, 29}

# Manual day-offset to calibrate this calculation against the official
# Bohra calendar. Adjust this integer (+/- a few days) until a known
# reference date matches. Start at 0.
CALIBRATION_OFFSET = -1

MONTH_NAMES = [
    "Moharram al-Haraam", "Safar al-Muzaffar", "Rabi al-Awwal",
    "Rabi al-Aakhar", "Jumada al-Ula", "Jumada al-Ukhra",
    "Rajab al-Asab", "Shabaan al-Karim", "Ramadaan al-Moazzam",
    "Shawwal al-Mukarram", "Zilqadah al-Haraam", "Zilhaj al-Haraam",
]


def _is_leap(year: int) -> bool:
    pos = ((year - 1) % 30) + 1
    return pos in LEAP_YEARS


def _year_length(year: int) -> int:
    return 355 if _is_leap(year) else 354


def _month_length(year: int, month: int) -> int:
    # Odd months 30 days, even months 29 days, except month 12 in a leap year -> 30
    if month == 12 and _is_leap(year):
        return 30
    return 30 if month % 2 == 1 else 29


def hijri_to_jd(year: int, month: int, day: int) -> int:
    jd = EPOCH_JD + CALIBRATION_OFFSET
    jd += (year - 1) * 354
    # add leap days from completed years
    for y in range(1, year):
        if _is_leap(y):
            jd += 1
    for m in range(1, month):
        jd += _month_length(year, m)
    jd += day - 1
    return jd


def jd_to_hijri(jd: int):
    jd -= (EPOCH_JD + CALIBRATION_OFFSET)
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


def gregorian_to_jd(g: date) -> int:
    # Standard Gregorian -> JD (proleptic, fine for modern dates)
    a = (14 - g.month) // 12
    y = g.year + 4800 - a
    m = g.month + 12 * a - 3
    jdn = g.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    return jdn


def jd_to_gregorian(jd: int) -> date:
    a = jd + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + m // 10
    return date(year, month, day)


def gregorian_to_hijri(g: date):
    return jd_to_hijri(gregorian_to_jd(g))


def hijri_to_gregorian(year: int, month: int, day: int) -> date:
    return jd_to_gregorian(hijri_to_jd(year, month, day))


def hijri_month_name(month: int) -> str:
    return MONTH_NAMES[month - 1]


def to_arabic_indic_numerals(n: int) -> str:
    """Convert an integer to Arabic-Indic numerals (used for Hijri day display, matching your screenshot)."""
    digits = "٠١٢٣٤٥٦٧٨٩"
    return "".join(digits[int(c)] for c in str(n))


def month_grid(hijri_year: int, hijri_month: int):
    """Return list of (gregorian_date, hijri_day) for every day in this Hijri month."""
    days = []
    length = _month_length(hijri_year, hijri_month)
    for d in range(1, length + 1):
        g = hijri_to_gregorian(hijri_year, hijri_month, d)
        days.append({"gregorian": g.isoformat(), "hijri_day": d})
    return days
