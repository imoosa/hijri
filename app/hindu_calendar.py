

"""
Hindu (luni-solar, Amanta) calendar -- tithi, paksha, and masa (lunar month)
computed from real Sun/Moon sidereal positions via the Swiss Ephemeris
(`pyswisseph`), NOT the mean-synodic-month approximation `hindu_events()`
in interfaith_calendar.py used to use. That approximation could drift a
full lunar month in a year with an inserted leap month (Adhik Maas) --
see this module's replacement of that function at the bottom of the file.

Requires: pip install pyswisseph
(This builds a small C extension -- needs a C compiler on whatever host
you deploy to, same as any other compiled wheel. It does NOT require
downloading Swiss Ephemeris data files for dates in this app's range;
without them it silently falls back to the Moshier analytical model,
which is accurate to a few arcseconds -- far under the ~0.5 degree that
would matter for a tithi boundary.)
"""

from datetime import date, timedelta
from functools import lru_cache

# Try to import swisseph, fall back to approximate calculations if not available
try:
    import swisseph as swe
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    _HAS_SWISSEPH = True
except ImportError:
    _HAS_SWISSEPH = False
    print("WARNING: swisseph not installed. Hindu calendar will use approximate calculations.")

# Only define these if swisseph is available
if _HAS_SWISSEPH:
    REF_LAT, REF_LNG = 23.1765, 75.7679  # Ujjain

    MASA_NAMES = [
        "Chaitra", "Vaishakha", "Jyeshtha", "Ashadha", "Shravana", "Bhadrapada",
        "Ashwin", "Kartik", "Margashirsha", "Pausha", "Magha", "Phalguna",
    ]

    PAKSHA_SHUKLA = "Shukla"
    PAKSHA_KRISHNA = "Krishna"
else:
    # Fallback for when swisseph is not installed
    MASA_NAMES = [
        "Chaitra", "Vaishakha", "Jyeshtha", "Ashadha", "Shravana", "Bhadrapada",
        "Ashwin", "Kartik", "Margashirsha", "Pausha", "Magha", "Phalguna",
    ]
    PAKSHA_SHUKLA = "Shukla"
    PAKSHA_KRISHNA = "Krishna"


# ==================== low-level ephemeris helpers ====================

def _sidereal_lon(jd_ut: float, body: int) -> float:
    values, _ = swe.calc_ut(jd_ut, body, swe.FLG_SIDEREAL)
    return values[0] % 360


def _elongation(jd_ut: float) -> float:
    """Moon - Sun sidereal longitude, 0-360. 0 = new moon, 180 = full moon."""
    return (_sidereal_lon(jd_ut, swe.MOON) - _sidereal_lon(jd_ut, swe.SUN)) % 360


def _signed_elongation(jd_ut: float) -> float:
    e = _elongation(jd_ut)
    return e - 360 if e > 180 else e


def _find_new_moon_after(jd_start: float) -> float:
    """First new-moon instant (elongation crosses 0 going up) strictly
    after jd_start. Scans forward a day at a time for the crossing, then
    bisects -- a fixed +/-N-day bracket isn't safe because elongation
    wraps 360->0 every synodic month and a wide bracket can straddle
    more than one wrap."""
    lo, hi = jd_start, jd_start + 1.0
    flo, fhi = _signed_elongation(lo), _signed_elongation(hi)
    tries = 0
    while not (flo < 0 <= fhi) and tries < 40:
        lo, flo = hi, fhi
        hi = lo + 1.0
        fhi = _signed_elongation(hi)
        tries += 1
    if tries >= 40:
        raise RuntimeError("could not bracket a new moon -- ephemeris problem?")
    for _ in range(60):
        mid = (lo + hi) / 2
        if _signed_elongation(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _sunrise_jd(g: date) -> float:
    """Julian day (UT) of sunrise at the Ujjain reference point on Gregorian date g."""
    jd_midnight_ut = swe.julday(g.year, g.month, g.day, 0) - 5.5 / 24
    _, times = swe.rise_trans(jd_midnight_ut, swe.SUN, swe.CALC_RISE, (REF_LNG, REF_LAT, 0))
    return times[0]


def _jd_to_date(jd_ut: float) -> date:
    y, m, d, _ = swe.revjul(jd_ut)
    return date(y, m, d)


def tithi_at(jd_ut: float):
    """(tithi 1-30, paksha) at a given instant."""
    t = int(_elongation(jd_ut) // 12) + 1
    if t <= 15:
        return t, PAKSHA_SHUKLA
    return t - 15, PAKSHA_KRISHNA


def tithi_on(g: date):
    """(tithi, paksha) for a Gregorian civil day, per the sunrise rule."""
    return tithi_at(_sunrise_jd(g))


def _masa_of(nm_start: float, nm_end: float):
    """(masa_index 0-11, is_adhika) for the lunar month spanning
    [nm_start, nm_end). Rule: a lunar month is named for the sidereal
    rashi the Sun occupies at the new moon that starts it, offset by one
    (the month in which Mesha Sankranti falls is Chaitra -- verified
    against Gudi Padwa above). It's Adhika (no festivals, "extra") if no
    sankranti (rashi change) happens between the start and end new moons."""
    rashi_start = int(_sidereal_lon(nm_start, swe.SUN) // 30)
    rashi_end = int(_sidereal_lon(nm_end, swe.SUN) // 30)
    masa_index = (rashi_start + 1) % 12
    is_adhika = (rashi_start == rashi_end)
    return masa_index, is_adhika


# ==================== year/month structure ====================

@lru_cache(maxsize=64)
def year_months(hindu_year: int):
    """Ordered tuple of month dicts for one Hindu year: starts at the true
    (non-adhika) Chaitra new moon falling in Gregorian `hindu_year`, runs
    through Phalguna. 12 entries in an ordinary year, 13 in a year with
    an inserted Adhik Maas. Each dict: {masa, is_adhika, start_jd, end_jd}.

    `hindu_year` is just "the Gregorian year Chaitra started in" -- like
    parsi_calendar.py's Navroz-anchored year, this is NOT a traditional
    era year number (Vikram Samvat, Shaka Samvat, etc.), just enough
    structure to drive a month-grid UI."""
    nm = _find_new_moon_after(swe.julday(hindu_year, 1, 1) - 1)
    while True:
        nm_next = _find_new_moon_after(nm + 1)
        masa, adhika = _masa_of(nm, nm_next)
        if masa == 0 and not adhika:
            break
        nm = nm_next

    months = []
    cur = nm
    while True:
        cur_next = _find_new_moon_after(cur + 1)
        masa, adhika = _masa_of(cur, cur_next)
        if masa == 0 and not adhika and months:
            break  # this is next year's Chaitra -- stop before including it
        months.append({"masa": masa, "is_adhika": adhika, "start_jd": cur, "end_jd": cur_next})
        cur = cur_next
    return tuple(months)


def is_leap(hindu_year: int) -> bool:
    return len(year_months(hindu_year)) == 13


def month_name(year: int, month: int) -> str:
    mo = year_months(year)[month - 1]
    name = MASA_NAMES[mo["masa"]]
    return f"Adhik {name}" if mo["is_adhika"] else name


def native_label(tithi_paksha) -> str:
    """Compact per-day label for a month grid, e.g. 'S1', 'K15'."""
    t, paksha = tithi_paksha
    return f"{'S' if paksha == PAKSHA_SHUKLA else 'K'}{t}"


def next_month(year: int, month: int):
    months = year_months(year)
    if month < len(months):
        return year, month + 1
    return year + 1, 1


def prev_month(year: int, month: int):
    if month > 1:
        return year, month - 1
    return year - 1, len(year_months(year - 1))


def gregorian_to_hindu(g: date):
    """(hindu_year, month_number, (tithi, paksha)) for a Gregorian date."""
    js = _sunrise_jd(g)
    # hindu_year is whichever year-table's Chaitra-to-Phalguna span contains js;
    # try g's own year first, then the neighbours, since Chaitra can start
    # anywhere Feb-Apr and a date in Jan/Feb belongs to the PREVIOUS hindu_year.
    for candidate_year in (g.year, g.year - 1, g.year + 1):
        months = year_months(candidate_year)
        if months[0]["start_jd"] <= js < months[-1]["end_jd"]:
            for i, mo in enumerate(months, start=1):
                if mo["start_jd"] <= js < mo["end_jd"]:
                    return candidate_year, i, tithi_at(js)
    raise ValueError(f"could not place {g} in any Hindu year table")


def month_grid(hindu_year: int, month: int):
    """List of {"gregorian": iso, "ordinal": n, "tithi": n, "paksha": str,
    "label": str} for every civil day whose Ujjain sunrise falls in this
    lunar month.

    `ordinal` is a plain 1-based sequential count through this month's
    day list -- NOT the tithi. A lunar month has no native "day 1, day
    2, ..." numbering the way a solar calendar does (a tithi can be
    skipped or repeated relative to the civil day count), so `ordinal`
    exists purely to give callers -- URL routing, "which day is
    selected" -- a stable, round-trippable integer key. Use
    `tithi`/`paksha`/`label` for anything user-facing."""
    mo = year_months(hindu_year)[month - 1]
    g = _jd_to_date(mo["start_jd"]) - timedelta(days=1)
    end_bound = _jd_to_date(mo["end_jd"]) + timedelta(days=1)
    days = []
    ordinal = 0
    while g <= end_bound:
        js = _sunrise_jd(g)
        if mo["start_jd"] <= js < mo["end_jd"]:
            t, paksha = tithi_at(js)
            ordinal += 1
            days.append({"gregorian": g.isoformat(), "ordinal": ordinal, "tithi": t,
                         "paksha": paksha, "label": native_label((t, paksha))})
        g += timedelta(days=1)
    return days


# ==================== festival dates (replaces the mean-motion version) ====================

# (masa_index, paksha, tithi, title, is_holiday)
_FESTIVAL_DEFS = [
    (11, PAKSHA_SHUKLA, 15, "Holi", True),                       # Phalguna Purnima
    (4, PAKSHA_SHUKLA, 15, "Raksha Bandhan", False),              # Shravana Purnima
    (5, PAKSHA_KRISHNA, 8, "Janmashtami", True),                  # Bhadrapada Krishna Ashtami
    (5, PAKSHA_SHUKLA, 4, "Ganesh Chaturthi", True),              # Bhadrapada Shukla Chaturthi
    (6, PAKSHA_SHUKLA, 1, "Navratri begins", False),              # Ashwin Shukla Pratipada
    (6, PAKSHA_SHUKLA, 10, "Dussehra (Vijayadashami)", True),     # Ashwin Shukla Dashami
    (6, PAKSHA_KRISHNA, 15, "Diwali", True),                      # Ashwin Krishna Amavasya (Amanta)
]


def _festival_date_in_month(mo) -> dict:
    """Return {title: date} for every festival def matching this month's masa,
    skipping Adhika occurrences (festivals only occur in the nija month)."""
    if mo["is_adhika"]:
        return {}
    out = {}
    g = _jd_to_date(mo["start_jd"]) - timedelta(days=1)
    end_bound = _jd_to_date(mo["end_jd"]) + timedelta(days=1)
    while g <= end_bound:
        js = _sunrise_jd(g)
        if mo["start_jd"] <= js < mo["end_jd"]:
            t, paksha = tithi_at(js)
            for masa_idx, want_paksha, want_tithi, title, is_holiday in _FESTIVAL_DEFS:
                if mo["masa"] == masa_idx and paksha == want_paksha and t == want_tithi:
                    out.setdefault(title, (g, is_holiday))
        g += timedelta(days=1)
    return out


def hindu_events(year: int):
    """Drop-in replacement for the old mean-motion hindu_events() in
    interfaith_calendar.py -- same return shape (list of event dicts with
    date/title/is_holiday/tradition/color), computed from real ephemeris
    instead of a mean synodic-month model. Scans this Gregorian year's
    Hindu-year table plus the previous one (Holi/Navratri-adjacent dates
    can fall right at the Gregorian year boundary) and keeps whatever
    lands in `year`."""
    events = []
    for hy in (year - 1, year):
        for mo in year_months(hy):
            for title, (g, is_holiday) in _festival_date_in_month(mo).items():
                if g.year == year:
                    events.append({
                        "date": g, "title": title, "is_holiday": is_holiday,
                        "tradition": "hindu", "color": "hindu",
                    })
    events.sort(key=lambda e: e["date"])
    return events
