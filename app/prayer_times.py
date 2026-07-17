"""
Prayer time calculation using standard solar astronomy.

Bohra (Dawoodi Bohra / Mustaali Shia) practice combines prayers:
  - Zuhr + Asr prayed together in the Zuhr window ("Zuhrayn")
  - Maghrib + Isha prayed together in the Maghrib window ("Maghribayn")

So the times that matter and are commonly displayed (matching your
screenshot: sunrise / zawal / zuhr end / sunset) are:
  - Fajr (dawn)
  - Sunrise
  - Zawal (solar noon - start of Zuhr window)
  - Zuhr end (end of the recommended combined Zuhr+Asr window)
  - Maghrib (sunset - start of Maghrib+Isha window)
  - Nisful Layl / midnight (end of Isha window), optional

[likely] "Zuhr end" in these apps is typically defined as a fixed offset
after zawal (commonly used convention: ~1.5-2 hours, or "before sunset"),
rather than a shadow-length calc like Sunni Asr. This module gives you a
configurable offset (ZUHR_WINDOW_MINUTES) -- verify the exact convention
your jamaat's calendar uses and adjust.
"""

import math
from datetime import datetime, timedelta, date, timezone

ZUHR_WINDOW_MINUTES = 150  # [guessing - verify] gap between zawal and "zuhr end"
FAJR_ANGLE = 18.0          # degrees below horizon, commonly used
ISHA_ANGLE = 18.0          # degrees below horizon (if computing standalone Isha)


def _julian_day(d: date) -> float:
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def _sun_position(jd: float):
    D = jd - 2451545.0
    g = math.radians((357.529 + 0.98560028 * D) % 360)
    q = (280.459 + 0.98564736 * D) % 360
    L = math.radians((q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360)
    e = math.radians(23.439 - 0.00000036 * D)
    dec = math.asin(math.sin(e) * math.sin(L))
    RA = math.degrees(math.atan2(math.cos(e) * math.sin(L), math.cos(L))) / 15.0
    RA = RA % 24
    eqt = q / 15.0 - RA
    if eqt > 12:
        eqt -= 24
    if eqt < -12:
        eqt += 24
    return math.degrees(dec), eqt


def _time_for_angle(jd, lat, lng, angle_deg, before_noon, eqt, noon_utc):
    lat_r = math.radians(lat)
    dec, _ = _sun_position(jd)
    dec_r = math.radians(dec)
    try:
        cosH = (math.sin(math.radians(-angle_deg)) - math.sin(lat_r) * math.sin(dec_r)) / (
            math.cos(lat_r) * math.cos(dec_r)
        )
        cosH = max(-1, min(1, cosH))
        H = math.degrees(math.acos(cosH)) / 15.0
    except ValueError:
        H = 6.0  # polar edge-case fallback
    return noon_utc - H if before_noon else noon_utc + H


def calculate(lat: float, lng: float, d: date, tz_offset_hours: float):
    """
    Returns dict of prayer-relevant times (local, tz_offset_hours from UTC),
    matching the Bohra combined-prayer display convention.
    """
    jd = _julian_day(d)
    dec, eqt = _sun_position(jd)
    noon_utc = 12.0 - lng / 15.0 - eqt

    sunrise_utc = _time_for_angle(jd, lat, lng, 0.833, True, eqt, noon_utc)
    sunset_utc = _time_for_angle(jd, lat, lng, 0.833, False, eqt, noon_utc)
    fajr_utc = _time_for_angle(jd, lat, lng, FAJR_ANGLE, True, eqt, noon_utc)

    def to_local(hours_utc):
        h = (hours_utc + tz_offset_hours) % 24
        hh = int(h)
        mm = int(round((h - hh) * 60))
        if mm == 60:
            mm = 0
            hh = (hh + 1) % 24
        return f"{hh:02d}:{mm:02d}"

    zawal_local = to_local(noon_utc)
    zuhr_end_local = to_local(noon_utc + ZUHR_WINDOW_MINUTES / 60.0)

    return {
        "date": d.isoformat(),
        "fajr": to_local(fajr_utc),
        "sunrise": to_local(sunrise_utc),
        "zawal": zawal_local,
        "zuhr_end": zuhr_end_local,
        "maghrib": to_local(sunset_utc),
        "sunset": to_local(sunset_utc),
    }
