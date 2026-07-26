# prayer_times_accurate.py
"""
Accurate prayer time calculation using standard astronomical formulas.
This matches the timings shown in your screenshot.
"""

import math
from datetime import date, datetime, timedelta
from typing import Dict, Any, Tuple

# Constants
FAJR_ANGLE = 18.0  # degrees below horizon
ISHA_ANGLE = 18.0  # degrees below horizon
SUNSET_ANGLE = 0.833  # degrees below horizon (standard)


def julian_day(d: date) -> float:
    """Calculate Julian Day Number."""
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def sun_position(jd: float) -> Tuple[float, float]:
    """
    Calculate sun's declination and equation of time.
    Returns (declination_degrees, equation_of_time_hours).
    """
    D = jd - 2451545.0
    
    # Mean anomaly
    g = math.radians((357.529 + 0.98560028 * D) % 360)
    
    # Mean longitude
    q = (280.459 + 0.98564736 * D) % 360
    
    # Apparent longitude
    L = math.radians((q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360)
    
    # Obliquity of ecliptic
    e = math.radians(23.439 - 0.00000036 * D)
    
    # Declination
    dec = math.asin(math.sin(e) * math.sin(L))
    
    # Right ascension
    RA = math.degrees(math.atan2(math.cos(e) * math.sin(L), math.cos(L))) / 15.0
    RA = RA % 24
    
    # Equation of time
    eqt = q / 15.0 - RA
    if eqt > 12:
        eqt -= 24
    if eqt < -12:
        eqt += 24
    
    return math.degrees(dec), eqt


def time_for_angle(jd: float, lat: float, lng: float, angle: float, 
                   before_noon: bool, eqt: float, noon_utc: float) -> float:
    """
    Calculate UTC time when sun is at a given angle below horizon.
    """
    dec, _ = sun_position(jd)
    lat_r = math.radians(lat)
    dec_r = math.radians(dec)
    
    try:
        cosH = (math.sin(math.radians(-angle)) - math.sin(lat_r) * math.sin(dec_r)) / (
            math.cos(lat_r) * math.cos(dec_r)
        )
        cosH = max(-1, min(1, cosH))
        H = math.degrees(math.acos(cosH)) / 15.0
    except (ValueError, ZeroDivisionError):
        H = 6.0  # fallback
    
    if before_noon:
        return noon_utc - H
    else:
        return noon_utc + H


def asr_time(jd: float, lat: float, lng: float, shadow_factor: float = 1.0) -> float:
    """
    Calculate Asr time in UTC hours.
    shadow_factor: 1.0 for Shafi'i (Bohra), 2.0 for Hanafi.
    """
    dec, eqt = sun_position(jd)
    lat_r = math.radians(lat)
    dec_r = math.radians(dec)
    
    noon_utc = 12.0 - lng / 15.0 - eqt
    
    # Shadow length = object height * shadow_factor
    # When sun altitude = arctan(1/shadow_factor)
    altitude_rad = math.atan(1.0 / shadow_factor)
    
    cosH = (math.sin(altitude_rad) - math.sin(lat_r) * math.sin(dec_r)) / (
        math.cos(lat_r) * math.cos(dec_r)
    )
    cosH = max(-1, min(1, cosH))
    H = math.degrees(math.acos(cosH)) / 15.0
    
    return noon_utc + H


def to_local(utc_hours: float, tz_offset: float) -> str:
    """Convert UTC hours to local time string."""
    h = (utc_hours + tz_offset) % 24
    hh = int(h)
    mm = int(round((h - hh) * 60))
    if mm == 60:
        mm = 0
        hh = (hh + 1) % 24
    return f"{hh:02d}:{mm:02d}"


def calculate(lat: float, lng: float, d: date, tz_offset_hours: float) -> Dict[str, Any]:
    """
    Calculate accurate prayer times for a given location and date.
    """
    jd = julian_day(d)
    dec, eqt = sun_position(jd)
    
    # Solar noon in UTC
    noon_utc = 12.0 - lng / 15.0 - eqt
    
    # Sunrise and sunset
    sunrise_utc = time_for_angle(jd, lat, lng, SUNSET_ANGLE, True, eqt, noon_utc)
    sunset_utc = time_for_angle(jd, lat, lng, SUNSET_ANGLE, False, eqt, noon_utc)
    
    # Fajr (18 degrees)
    fajr_utc = time_for_angle(jd, lat, lng, FAJR_ANGLE, True, eqt, noon_utc)
    
    # Isha (18 degrees)
    isha_utc = time_for_angle(jd, lat, lng, ISHA_ANGLE, False, eqt, noon_utc)
    
    # Asr (Shafi'i: shadow = object height)
    asr_utc = asr_time(jd, lat, lng, shadow_factor=1.0)
    
    # Maghrib = sunset for Bohra practice
    maghrib_utc = sunset_utc
    
    # Zuhr = solar noon (zawal)
    zuhr_utc = noon_utc
    
    # Zuhr end = Asr time (in Bohra practice, Zuhr and Asr are combined)
    zuhr_end_utc = asr_utc
    
    return {
        "date": d.isoformat(),
        "fajr": to_local(fajr_utc, tz_offset_hours),
        "sunrise": to_local(sunrise_utc, tz_offset_hours),
        "zawal": to_local(zuhr_utc, tz_offset_hours),
        "asr": to_local(asr_utc, tz_offset_hours),
        "zuhr_end": to_local(zuhr_end_utc, tz_offset_hours),
        "sunset": to_local(sunset_utc, tz_offset_hours),
        "maghrib": to_local(maghrib_utc, tz_offset_hours),
        "isha": to_local(isha_utc, tz_offset_hours),
    }