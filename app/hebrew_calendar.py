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

from datetime import date, datetime, timedelta

from convertdate import hebrew as _hebrew

from . import prayer_times_accurate as _pta

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


# ==================== Shabbat / Zmanim ====================
# [likely] -- sunrise/sunset math reuses prayer_times_accurate.py's
# astronomical formulas (same as used for Islamic prayer times), which is
# a solid, deterministic calculation. What's NOT solid is the minute
# offsets below, which vary by community/custom -- calibrate them the same
# way you'd calibrate hijri_calendar.py's CALIBRATION_OFFSET.

CANDLE_LIGHTING_MINUTES_BEFORE_SUNSET = 18  # [likely] common default; some communities use 20, 30, or 40
HAVDALAH_MINUTES_AFTER_SUNSET = 42          # [likely] "3 medium stars" convention; customs range ~42-72 min


def _sun_times_utc(g: date, lat: float, lng: float):
    """(sunrise_utc_hours, sunset_utc_hours) for a Gregorian date, via the
    same solar-position formulas prayer_times_accurate.py uses."""
    jd = _pta.julian_day(g)
    dec, eqt = _pta.sun_position(jd)
    noon_utc = 12.0 - lng / 15.0 - eqt
    sunrise_utc = _pta.time_for_angle(jd, lat, lng, _pta.SUNSET_ANGLE, True, eqt, noon_utc)
    sunset_utc = _pta.time_for_angle(jd, lat, lng, _pta.SUNSET_ANGLE, False, eqt, noon_utc)
    return sunrise_utc, sunset_utc


def _local_dt(day: date, utc_hours: float, tz_offset: float) -> datetime:
    return datetime(day.year, day.month, day.day) + timedelta(hours=utc_hours + tz_offset)


def shabbat_times(g: date, lat: float, lng: float, tz_offset: float) -> dict:
    """Candle lighting (this week's Friday, before sunset) and Havdalah
    (this week's Saturday, after sunset), for a Shabbat countdown clock.
    `g` can be any day of the week -- this always resolves to that week's
    Fri/Sat. [likely] -- see module-level offset caveats above."""
    weekday = g.weekday()  # Mon=0 ... Sun=6, Fri=4, Sat=5
    friday = g + timedelta(days=(4 - weekday) % 7)
    saturday = friday + timedelta(days=1)

    _, fri_sunset_utc = _sun_times_utc(friday, lat, lng)
    _, sat_sunset_utc = _sun_times_utc(saturday, lat, lng)

    candle_dt = _local_dt(friday, fri_sunset_utc - CANDLE_LIGHTING_MINUTES_BEFORE_SUNSET / 60.0, tz_offset)
    havdalah_dt = _local_dt(saturday, sat_sunset_utc + HAVDALAH_MINUTES_AFTER_SUNSET / 60.0, tz_offset)

    return {
        "friday": friday.isoformat(),
        "saturday": saturday.isoformat(),
        "candle_lighting": candle_dt.strftime("%H:%M"),
        "candle_lighting_iso": candle_dt.isoformat(),
        "havdalah": havdalah_dt.strftime("%H:%M"),
        "havdalah_iso": havdalah_dt.isoformat(),
    }


def zmanim(g: date, lat: float, lng: float, tz_offset: float) -> dict:
    """Halachic-day progress for today: sunrise-to-sunset divided into 12
    proportional 'shaos zmaniyos', with sof zman tefila (Shacharit deadline,
    end of the 4th halachic hour -- the GRA opinion) marked, plus whether
    time remains for Shacharit and for Mincha (deadline = sunset).
    [likely -- GRA-based]; the Magen Avraham opinion (dawn-to-nightfall
    instead of sunrise-to-sunset) would shift these times earlier and isn't
    modelled here."""
    sunrise_utc, sunset_utc = _sun_times_utc(g, lat, lng)
    day_length = sunset_utc - sunrise_utc
    if day_length <= 0:
        day_length += 24
    shaah_zmanit = day_length / 12.0

    sof_zman_tefila_utc = sunrise_utc + 4 * shaah_zmanit
    chatzot_utc = sunrise_utc + 6 * shaah_zmanit  # halachic midday

    now = datetime.utcnow()
    now_utc_hours = now.hour + now.minute / 60 + now.second / 3600 - tz_offset

    progress_pct = (now_utc_hours - sunrise_utc) / day_length * 100
    progress_pct = max(0, min(100, progress_pct))
    tefila_marker_pct = max(0, min(100, (sof_zman_tefila_utc - sunrise_utc) / day_length * 100))

    def _hhmm(utc_hours):
        h = (utc_hours + tz_offset) % 24
        hh = int(h)
        mm = int(round((h - hh) * 60))
        return f"{hh:02d}:{mm:02d}"

    return {
        "sunrise": _hhmm(sunrise_utc),
        "sunset": _hhmm(sunset_utc),
        "sof_zman_tefila": _hhmm(sof_zman_tefila_utc),
        "chatzot": _hhmm(chatzot_utc),
        "progress_pct": round(progress_pct, 1),
        "tefila_marker_pct": round(tefila_marker_pct, 1),
        "shacharit_time_left": now_utc_hours < sof_zman_tefila_utc,
        "mincha_time_left": now_utc_hours < sunset_utc,
    }
