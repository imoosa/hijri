# prayer_times.py
"""
Prayer time calculation using the prayer-times-calculator library.
This provides accurate times based on standard Islamic calculation methods.
"""

from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional

# Use the prayer-times-calculator library
try:
    from prayer_times_calculator import PrayerTimesCalculator
    HAS_LIBRARY = True
except ImportError:
    HAS_LIBRARY = False
    print("WARNING: prayer-times-calculator not installed. Run: pip install prayer-times-calculator")


# Bohra-specific settings
# For Bohra practice, we use:
# - Fajr angle: 18 degrees (standard)
# - Isha angle: 18 degrees (standard) 
# - Asr method: Shafi'i (shadow = 1x object height)
# - Maghrib: Sunset (0.833 degrees below horizon)
CALCULATION_METHOD = "MWL"  # Muslim World League - uses 18° for Fajr and Isha
ASR_METHOD = "Shafi"  # Standard for Bohra
ADJUST_HIGH_LATITUDES = "NightMiddle"  # For locations above 48° latitude


def calculate(lat: float, lng: float, d: date, tz_offset_hours: float) -> Dict[str, Any]:
    """
    Calculate all prayer times for a given location and date.
    
    Args:
        lat: Latitude in decimal degrees
        lng: Longitude in decimal degrees
        d: Date to calculate for
        tz_offset_hours: Timezone offset from UTC (e.g., 5.5 for India)
    
    Returns:
        Dict with prayer times as strings in HH:MM format
    """
    if not HAS_LIBRARY:
        # Fallback to approximate calculation if library not available
        return _calculate_approximate(lat, lng, d, tz_offset_hours)
    
    # Create calculator instance
    calculator = PrayerTimesCalculator(
        latitude=lat,
        longitude=lng,
        calculation_method=CALCULATION_METHOD,
        asr_method=ASR_METHOD,
        adjust_high_latitudes=ADJUST_HIGH_LATITUDES,
        timezone=tz_offset_hours
    )
    
    # Calculate times for the given date
    times = calculator.calc(date=d)
    
    # Extract times - the library returns datetime objects
    def format_time(dt):
        if dt is None:
            return "--:--"
        return dt.strftime("%H:%M")
    
    return {
        "date": d.isoformat(),
        "fajr": format_time(times["fajr"]),
        "sunrise": format_time(times["sunrise"]),
        "dhuhr": format_time(times["dhuhr"]),  # Zawal / Zuhr begins
        "asr": format_time(times["asr"]),
        "maghrib": format_time(times["maghrib"]),
        "isha": format_time(times["isha"]),
        "zuhr_end": format_time(times["asr"]),  # In Bohra practice, Zuhr window ends at Asr
        "zawal": format_time(times["dhuhr"]),   # Same as Dhuhr
        "sunset": format_time(times["maghrib"]), # Same as Maghrib
    }


def _calculate_approximate(lat: float, lng: float, d: date, tz_offset_hours: float) -> Dict[str, Any]:
    """
    Fallback approximate calculation when the library is not installed.
    This is less accurate but provides reasonable estimates.
    """
    import math
    
    # Simplified calculation - for demonstration only
    # Real calculations require proper solar position algorithms
    
    # Estimate based on latitude and date
    day_of_year = d.timetuple().tm_yday
    
    # Rough sunrise/sunset times (very approximate)
    # For Kolkata (~22°N)
    lat_rad = math.radians(lat)
    declination = 23.44 * math.sin(math.radians(360/365 * (day_of_year - 81)))
    decl_rad = math.radians(declination)
    
    # Hour angle for sunrise/sunset
    cos_hour_angle = -math.tan(lat_rad) * math.tan(decl_rad)
    cos_hour_angle = max(-1, min(1, cos_hour_angle))
    hour_angle = math.degrees(math.acos(cos_hour_angle)) / 15
    
    # Solar noon (LST)
    noon_lst = 12.0 - (lng / 15.0)
    
    sunrise = noon_lst - hour_angle
    sunset = noon_lst + hour_angle
    
    def to_local(utc_hours):
        h = (utc_hours + tz_offset_hours) % 24
        hh = int(h)
        mm = int((h - hh) * 60)
        if mm == 60:
            mm = 0
            hh = (hh + 1) % 24
        return f"{hh:02d}:{mm:02d}"
    
    # Rough estimates
    fajr_offset = 1.5  # hours before sunrise (varies by location)
    fajr = sunrise - fajr_offset
    
    # Asr: about 2 hours before sunset (very rough)
    asr = sunset - 1.5
    
    # Isha: about 1.5 hours after sunset
    isha = sunset + 1.5
    
    return {
        "date": d.isoformat(),
        "fajr": to_local(fajr),
        "sunrise": to_local(sunrise),
        "dhuhr": to_local(noon_lst),
        "asr": to_local(asr),
        "maghrib": to_local(sunset),
        "isha": to_local(isha),
        "zawal": to_local(noon_lst),
        "zuhr_end": to_local(asr),
        "sunset": to_local(sunset),
    }