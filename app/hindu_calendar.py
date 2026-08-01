

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


def _sunrise_jd(g: date, lat: float = None, lng: float = None) -> float:
    """Julian day (UT) of sunrise on Gregorian date g, at (lat, lng) if
    given, else the Ujjain reference point. Tithi/nakshatra lookups always
    used Ujjain regardless of where the user actually is -- that's wrong
    for anyone outside India by more than a rounding error, and wrong for
    Rahu Kalam/Abhijit even within India, since those need the ACTUAL
    local sunrise-sunset span, not a fixed reference city's."""
    lat = REF_LAT if lat is None else lat
    lng = REF_LNG if lng is None else lng
    jd_midnight_ut = swe.julday(g.year, g.month, g.day, 0) - 5.5 / 24
    _, times = swe.rise_trans(jd_midnight_ut, swe.SUN, swe.CALC_RISE, (lng, lat, 0))
    return times[0]


def _sunset_jd(g: date, lat: float = None, lng: float = None) -> float:
    """Julian day (UT) of sunset on Gregorian date g, at (lat, lng)."""
    lat = REF_LAT if lat is None else lat
    lng = REF_LNG if lng is None else lng
    jd_midnight_ut = swe.julday(g.year, g.month, g.day, 0) - 5.5 / 24
    _, times = swe.rise_trans(jd_midnight_ut, swe.SUN, swe.CALC_SET, (lng, lat, 0))
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


def tithi_on(g: date, lat: float = None, lng: float = None):
    """(tithi, paksha) for a Gregorian civil day, per the sunrise rule, at
    (lat, lng) if given else Ujjain."""
    return tithi_at(_sunrise_jd(g, lat, lng))


NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]


def nakshatra_at(jd_ut: float) -> str:
    """Moon's sidereal nakshatra (1 of 27 equal 360/27-degree divisions) at
    a given instant -- same sidereal longitude the tithi/masa math already
    uses, just a different division of the circle (27 slices instead of
    30-degree rashis)."""
    lon = _sidereal_lon(jd_ut, swe.MOON)
    return NAKSHATRA_NAMES[int(lon // (360 / 27))]


def nakshatra_on(g: date, lat: float = None, lng: float = None) -> str:
    """Nakshatra for a Gregorian civil day, at the same sunrise instant
    tithi_on() uses -- panchang convention is to report both tithi and
    nakshatra as of sunrise, not as of "now"."""
    return nakshatra_at(_sunrise_jd(g, lat, lng))


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


def gregorian_to_hindu(g: date, lat: float = None, lng: float = None):
    """(hindu_year, month_number, (tithi, paksha)) for a Gregorian date, at
    (lat, lng) if given else Ujjain."""
    js = _sunrise_jd(g, lat, lng)
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


def month_grid(hindu_year: int, month: int, lat: float = None, lng: float = None):
    """List of {"gregorian": iso, "ordinal": n, "tithi": n, "paksha": str,
    "label": str, "is_ekadashi": bool, "is_purnima": bool} for every civil
    day whose local sunrise (at lat/lng, else Ujjain) falls in this lunar
    month.

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
        js = _sunrise_jd(g, lat, lng)
        if mo["start_jd"] <= js < mo["end_jd"]:
            t, paksha = tithi_at(js)
            ordinal += 1
            days.append({
                "gregorian": g.isoformat(), "ordinal": ordinal, "tithi": t,
                "paksha": paksha, "label": native_label((t, paksha)),
                "is_ekadashi": t == 11,
                "is_purnima": t == 15 and paksha == PAKSHA_SHUKLA,
            })
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


# ==================== daily muhurats (Rahu Kalam, Abhijit) ====================
# Both split the ACTUAL local sunrise-to-sunset span at the user's own
# lat/lng -- unlike the festival-date math above, these are meaningless if
# pinned to a reference city someone isn't standing in.

# Rahu Kalam segment (1-8, of 8 equal divisions of sunrise-sunset), keyed
# by Python's date.weekday() (Monday=0 ... Sunday=6). Standard tabular
# assignment used across Panchang references.
_RAHU_KALAM_SEGMENT = {0: 2, 1: 7, 2: 5, 3: 6, 4: 4, 5: 3, 6: 8}

# Abhijit is the 8th of 15 equal muhurtas spanning sunrise-to-sunset --
# roughly the ~24 minutes either side of local solar noon.
_ABHIJIT_MUHURTA_INDEX = 7  # 0-based: 8th muhurta


def _jd_to_local_hhmm(jd_ut: float, tz_offset: float) -> str:
    """Same HH:MM-string convention prayer_times_accurate.py already uses,
    so the frontend can treat Rahu Kalam/Abhijit boundaries exactly like
    azaan times -- one scheduling code path, not two."""
    _, _, _, h = swe.revjul(jd_ut)
    total = (h + tz_offset) % 24
    hh = int(total)
    mm = int(round((total - hh) * 60))
    if mm == 60:
        mm = 0
        hh = (hh + 1) % 24
    return f"{hh:02d}:{mm:02d}"


def daily_muhurats(lat: float, lng: float, g: date, tz_offset: float) -> dict:
    """Sunrise, sunset, Rahu Kalam window, and Abhijit Muhurat window for
    one civil day at (lat, lng), all as local HH:MM strings.

    [likely] Rahu Kalam's weekday->segment table and Abhijit's "8th of 15
    muhurtas" rule are the versions most Panchang sources agree on, not
    independently re-derived here -- cross-check against a published
    Panchang for your exact location before treating either window as
    authoritative for something time-sensitive."""
    sunrise_jd = _sunrise_jd(g, lat, lng)
    sunset_jd = _sunset_jd(g, lat, lng)
    day_len = sunset_jd - sunrise_jd
    if day_len <= 0:
        raise ValueError(f"sunset before sunrise for {g} at ({lat},{lng}) -- polar location?")

    eighth = day_len / 8
    rk_idx = _RAHU_KALAM_SEGMENT[g.weekday()] - 1
    rk_start_jd = sunrise_jd + rk_idx * eighth
    rk_end_jd = rk_start_jd + eighth

    muhurta = day_len / 15
    ab_start_jd = sunrise_jd + _ABHIJIT_MUHURTA_INDEX * muhurta
    ab_end_jd = ab_start_jd + muhurta

    return {
        "sunrise": _jd_to_local_hhmm(sunrise_jd, tz_offset),
        "sunset": _jd_to_local_hhmm(sunset_jd, tz_offset),
        "rahu_kalam": {
            "start": _jd_to_local_hhmm(rk_start_jd, tz_offset),
            "end": _jd_to_local_hhmm(rk_end_jd, tz_offset),
        },
        "abhijit": {
            "start": _jd_to_local_hhmm(ab_start_jd, tz_offset),
            "end": _jd_to_local_hhmm(ab_end_jd, tz_offset),
        },
    }
