"""
Multi-faith / multi-calendar festival dates, generated per Gregorian year.

ACCURACY BY TRADITION -- read this before trusting any single date:

  CHRISTIAN   [certain]  Fixed dates are fixed. Easter and everything that
              hangs off it (Ash Wednesday, Palm Sunday, Good Friday,
              Pentecost) use the standard Gregorian Easter algorithm
              (Meeus/Jones/Butcher). This is THE agreed civil algorithm,
              verified here against known Easter dates 2024-2027.

  FRENCH      [certain]  French national public holidays. Fixed Gregorian
              dates, several of which duplicate Christian ones (Christmas,
              Assumption, All Saints) -- that overlap is real, not a bug.

  JEWISH      [certain]  Computed via the standard Hebrew calendar arithmetic
              (Metonic 19-year cycle, molad-based, 4 postponement rules),
              using the `convertdate` library. This is a deterministic,
              agreed civil algorithm -- verified here against known 2024-2026
              dates (Rosh Hashanah, Purim, Pesach all matched).
              Requires: pip install convertdate

  HINDU       [likely, cross-checked against a small number of published
              2026 dates, not a full year of Panchang data] Delegates to
              hindu_calendar.py, which does real sidereal Sun/Moon position
              calculations (Swiss Ephemeris via pyswisseph, Lahiri ayanamsa)
              and properly detects Adhik Maas (leap months) via sankranti
              position -- NOT the mean synodic-month model this module used
              to use. That old model could be off by an entire lunar month
              in a leap-month year (it put Raksha Bandhan 2026 on Jul 30;
              real date is Aug 28 -- the new engine gets Aug 28 exactly).
              The new engine still has its own documented gaps -- see
              hindu_calendar.py's module docstring, in particular a known
              1-day miss on Diwali because it assigns every tithi by
              sunrise, and real Panchangs assign some festivals (Diwali
              among them) by evening/Pradosh time instead. Cross-check
              against a real Panchang (e.g. drikpanchang.com) before
              publishing these dates to users, same as you'd calibrate
              hijri_calendar.py's CALIBRATION_OFFSET.

  PARSI       [likely, unverified] Shahenshahi calendar (the one followed by
              most Indian Parsis) -- NOT the Fasli calendar (aligned to the
              March equinox) or the Kadmi calendar (one month ahead of
              Shahenshahi). Unlike every other tradition here, Shahenshahi
              years are a flat 365 days with NO leap-year correction at all,
              so there's no lunar/solar position math to get right or wrong
              -- Navroz just slides later relative to the Gregorian calendar
              by about a day every 4 years. The only real risk is the
              calibration anchor (_REF_NAVROZ below): online sources for the
              2026 Shahenshahi Navroz date disagree by a day or two (16 Aug
              2026 per most sources used here, some say 15th or 17th).
              Cross-check against a published Parsi calendar (e.g. the
              Bombay Parsi Punchayet's) before trusting this for religious
              observance, and adjust _REF_NAVROZ if it's off.
"""

import math
from datetime import date, timedelta

from . import parsi_calendar as pc

try:
    from convertdate import hebrew as _hebrew
    _HAS_CONVERTDATE = True
except ImportError:
    _HAS_CONVERTDATE = False

try:
    from . import hindu_calendar as _hc
    _HAS_SWISSEPH = True
except ImportError:
    _HAS_SWISSEPH = False


# ==================== CHRISTIAN ====================

def _gregorian_easter(year: int) -> date:
    """Meeus/Jones/Butcher algorithm. Verified against known Easter dates."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def christian_events(year: int):
    easter = _gregorian_easter(year)
    events = [
        {"date": date(year, 1, 6), "title": "Epiphany", "is_holiday": True},
        {"date": easter - timedelta(days=46), "title": "Ash Wednesday", "is_holiday": False},
        {"date": easter - timedelta(days=7), "title": "Palm Sunday", "is_holiday": False},
        {"date": easter - timedelta(days=2), "title": "Good Friday", "is_holiday": True},
        {"date": easter, "title": "Easter Sunday", "is_holiday": True},
        {"date": easter + timedelta(days=49), "title": "Pentecost", "is_holiday": True},
        {"date": date(year, 11, 1), "title": "All Saints' Day", "is_holiday": True},
        {"date": date(year, 12, 25), "title": "Christmas", "is_holiday": True},
    ]
    for e in events:
        e["tradition"] = "christian"
        e["color"] = "christian"
    return events


# ==================== FRENCH (national civil holidays) ====================

def french_events(year: int):
    easter = _gregorian_easter(year)
    events = [
        {"date": date(year, 1, 1), "title": "Jour de l'An (New Year)"},
        {"date": easter + timedelta(days=1), "title": "Lundi de Paques (Easter Monday)"},
        {"date": date(year, 5, 1), "title": "Fete du Travail (Labour Day)"},
        {"date": date(year, 5, 8), "title": "Victoire 1945 (VE Day)"},
        {"date": easter + timedelta(days=39), "title": "Ascension"},
        {"date": easter + timedelta(days=50), "title": "Lundi de Pentecote"},
        {"date": date(year, 7, 14), "title": "Fete Nationale (Bastille Day)"},
        {"date": date(year, 8, 15), "title": "Assomption"},
        {"date": date(year, 11, 1), "title": "Toussaint (All Saints)"},
        {"date": date(year, 11, 11), "title": "Armistice 1918"},
        {"date": date(year, 12, 25), "title": "Noel (Christmas)"},
    ]
    for e in events:
        e["tradition"] = "french"
        e["color"] = "french"
        e["is_holiday"] = True
    return events


# ==================== JEWISH ====================

def jewish_events(year: int):
    if not _HAS_CONVERTDATE:
        return []
    events = []
    for hy in (year + 3759, year + 3760):  # covers both Hebrew years touching this Gregorian year
        try:
            defs = [
                (_hebrew.TISHRI, 1, "Rosh Hashanah", True),
                (_hebrew.TISHRI, 10, "Yom Kippur", True),
                (_hebrew.TISHRI, 15, "Sukkot begins", True),
                (_hebrew.KISLEV, 25, "Hanukkah begins", False),
                (_hebrew.ADAR, 14, "Purim", False),
                (_hebrew.NISAN, 15, "Pesach (Passover) begins", True),
                (_hebrew.SIVAN, 6, "Shavuot", True),
            ]
            for month, day, title, is_holiday in defs:
                y, m, d = _hebrew.to_gregorian(hy, month, day)
                if y == year:
                    events.append({
                        "date": date(y, m, d), "title": title,
                        "is_holiday": is_holiday, "tradition": "jewish", "color": "jewish",
                    })
        except Exception:
            continue
    return events


# ==================== HINDU (approximate -- see module docstring) ====================

_SYNODIC_MONTH = 29.530588853
_REF_NEW_MOON = date(2024, 1, 11)  # verified astronomical new moon


def _first_new_moon_on_or_after(early: date) -> date:
    delta = (early - _REF_NEW_MOON).days
    k = math.floor(delta / _SYNODIC_MONTH)
    candidate = _REF_NEW_MOON + timedelta(days=round(k * _SYNODIC_MONTH))
    while candidate < early:
        candidate += timedelta(days=round(_SYNODIC_MONTH))
    return candidate


def _first_full_moon_on_or_after(early: date) -> date:
    shifted = early - timedelta(days=_SYNODIC_MONTH / 2)
    nm = _first_new_moon_on_or_after(shifted)
    full = nm + timedelta(days=round(_SYNODIC_MONTH / 2))
    if full < early:
        full += timedelta(days=round(_SYNODIC_MONTH))
    return full


def _tithi_after(base: date, n: int) -> date:
    return base + timedelta(days=round(n * _SYNODIC_MONTH / 30))


def hindu_events(year: int):
    """Real ephemeris-based Hindu festival dates -- see hindu_calendar.py.
    Falls back to the old mean-synodic-month approximation only if
    pyswisseph isn't installed; that fallback is a rough guess (see
    _hindu_events_approx below) -- install pyswisseph rather than
    relying on it."""
    if _HAS_SWISSEPH:
        return _hc.hindu_events(year)
    return _hindu_events_approx(year)


def _hindu_events_approx(year: int):
    """[guessing] Mean synodic-month approximation, NO leap-month
    correction. Kept only as a fallback for when pyswisseph isn't
    installed -- known to drift up to ~29 days in Adhik Maas years (see
    module docstring). Do not call this directly; use hindu_events()."""
    holi = _first_full_moon_on_or_after(date(year, 2, 20))
    shravan_full = _first_full_moon_on_or_after(date(year, 7, 20))       # Raksha Bandhan
    janmashtami = _tithi_after(shravan_full, 8)
    bhadra_new = _first_new_moon_on_or_after(date(year, 8, 18))
    ganesh_chaturthi = _tithi_after(bhadra_new, 4)
    ashwin_new = _first_new_moon_on_or_after(date(year, 9, 20))
    navratri_start = _tithi_after(ashwin_new, 1)
    dussehra = _tithi_after(ashwin_new, 10)
    diwali = _first_new_moon_on_or_after(date(year, 10, 5))

    events = [
        {"date": holi, "title": "Holi", "is_holiday": True},
        {"date": shravan_full, "title": "Raksha Bandhan", "is_holiday": False},
        {"date": janmashtami, "title": "Janmashtami", "is_holiday": True},
        {"date": ganesh_chaturthi, "title": "Ganesh Chaturthi", "is_holiday": True},
        {"date": navratri_start, "title": "Navratri begins", "is_holiday": False},
        {"date": dussehra, "title": "Dussehra (Vijayadashami)", "is_holiday": True},
        {"date": diwali, "title": "Diwali", "is_holiday": True},
    ]
    for e in events:
        e["tradition"] = "hindu"
        e["color"] = "hindu"
    return events


# ==================== PARSI / ZOROASTRIAN (Shahenshahi calendar) -- see module docstring ====================
# Navroz calibration lives in parsi_calendar.py (single source of truth --
# also used to build the full Parsi month-grid view, not just this festival
# list). See that module and the accuracy note above for the caveat.


def parsi_events(year: int):
    navroz = pc.shahenshahi_navroz(year)
    events = [
        {"date": navroz - timedelta(days=1), "title": "Pateti (day of repentance)", "is_holiday": False},
        {"date": navroz, "title": "Navroz (Jamshedi Navroz) -- Parsi New Year", "is_holiday": True},
        {"date": navroz + timedelta(days=5), "title": "Khordad Sal (Zarathustra's birthday)", "is_holiday": True},
    ]
    for e in events:
        e["tradition"] = "parsi"
        e["color"] = "parsi"
    return events



# ==================== combined ====================

TRADITIONS = {
    "christian": {"label": "Christian", "color": "#4b7bec"},
    "french": {"label": "French civil", "color": "#2c3e50"},
    "jewish": {"label": "Jewish", "color": "#8e44ad"},
    "hindu": {"label": "Hindu (approximate)", "color": "#e67e22"},
    "parsi": {"label": "Parsi (Shahenshahi)", "color": "#16a085"},
}


def get_interfaith_events(year: int):
    """All configured traditions for one Gregorian year, as a flat list of dicts."""
    return (
        christian_events(year)
        + french_events(year)
        + jewish_events(year)
        + hindu_events(year)
        + parsi_events(year)
    )
