"""
Accurate UTC offset lookup from (lat, lng).

Why this exists: a longitude-based estimate (offset = round(lng/15)) is wrong
for any country whose civil timezone doesn't sit on a meridian boundary --
India (UTC+5:30), Iran (UTC+3:30), parts of Australia, etc. It also can't
account for DST. This module looks up the real IANA timezone polygon that
contains the point, then asks that timezone what its actual UTC offset is
on a given date -- which is correct for political borders and DST both.

Requires: pip install timezonefinder
(pulls in real tz boundary shapefiles; first import is slightly slow while
it loads them, subsequent lookups are fast)
"""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

try:
    from timezonefinder import TimezoneFinder
    _TF = TimezoneFinder()
    HAS_TIMEZONEFINDER = True
except ImportError:
    _TF = None
    HAS_TIMEZONEFINDER = False


def tz_name_at(lat: float, lng: float) -> Optional[str]:
    """IANA timezone name (e.g. 'Asia/Kolkata') for a lat/lng, or None if
    unavailable (library not installed, or point over open ocean)."""
    if not HAS_TIMEZONEFINDER:
        return None
    return _TF.timezone_at(lat=lat, lng=lng)


def utc_offset_hours(lat: float, lng: float, for_date: Optional[date] = None) -> Optional[float]:
    """
    Real UTC offset in hours (e.g. 5.5 for India) for a lat/lng, evaluated
    on `for_date` (defaults to today) so DST-observing zones get the right
    offset for that time of year. Returns None if it can't be resolved --
    callers should fall back to manual entry, not silently guess.
    """
    tzname = tz_name_at(lat, lng)
    if not tzname:
        return None
    d = for_date or date.today()
    # noon avoids any DST-transition-boundary edge cases at midnight
    dt = datetime(d.year, d.month, d.day, 12, 0, tzinfo=ZoneInfo(tzname))
    offset = dt.utcoffset()
    if offset is None:
        return None
    return offset.total_seconds() / 3600
