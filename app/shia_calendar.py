"""
Shia (Jafari/Twelver) Islamic calendar.

Shia Muslims follow the same Hijri calendar structure as Sunni Muslims
but have different event dates and observances. The calendar conversion
itself is identical to the Umm al-Qura calendar used by Sunnis.

Key differences:
- Imamat days (birth/death of Imams)
- Ashura is observed more intensely
- Ghadir Khumm is a major holiday
- Different dates for certain events
"""

from datetime import date
from . import sunni_calendar as sc

MONTH_NAMES = sc.MONTH_NAMES

# Shia-specific events (Twelver Jafari tradition)
SHIA_EVENTS = [
    # Muharram
    {"month": 1, "day": 1, "title": "Islamic New Year", "is_holiday": True},
    {"month": 1, "day": 9, "title": "Tasu'a (night before Ashura)", "is_holiday": False},
    {"month": 1, "day": 10, "title": "Ashura (Martyrdom of Imam Husayn)", "is_holiday": True},
    # Safar
    {"month": 2, "day": 20, "title": "Arba'een (40th day after Ashura)", "is_holiday": True},
    {"month": 2, "day": 28, "title": "Martyrdom of Prophet Muhammad", "is_holiday": False},
    # Rabi al-Awwal
    {"month": 3, "day": 17, "title": "Birth of Prophet Muhammad", "is_holiday": True},
    # Ramadan
    {"month": 9, "day": 1, "title": "Ramadan begins", "is_holiday": False},
    {"month": 9, "day": 19, "title": "Striking of Imam Ali", "is_holiday": False},
    {"month": 9, "day": 21, "title": "Martyrdom of Imam Ali", "is_holiday": True},
    {"month": 9, "day": 23, "title": "Laylat al-Qadr (19th)", "is_holiday": False},
    {"month": 9, "day": 27, "title": "Laylat al-Qadr (21st/23rd)", "is_holiday": False},
    # Shawwal
    {"month": 10, "day": 1, "title": "Eid al-Fitr", "is_holiday": True},
    # Dhu al-Hijjah
    {"month": 12, "day": 10, "title": "Eid al-Adha", "is_holiday": True},
    {"month": 12, "day": 18, "title": "Eid al-Ghadeer (Imam Ali's succession)", "is_holiday": True},
    {"month": 12, "day": 24, "title": "Mubahala", "is_holiday": False},
]

# Use the same conversion functions as Sunni calendar
# (Shia use the same Umm al-Qura calendar system)
def shia_gregorian_to_hijri(g: date):
    return sc.sunni_gregorian_to_hijri(g)


def shia_hijri_to_gregorian(year: int, month: int, day: int) -> date:
    return sc.sunni_hijri_to_gregorian(year, month, day)


def shia_month_name(month: int) -> str:
    return sc.sunni_month_name(month)


def shia_month_grid(year: int, month: int):
    return sc.sunni_month_grid(year, month)


def get_shia_events(year: int, month: int):
    """Get Shia events for a specific Hijri month/year."""
    events_by_day = {}
    for event in SHIA_EVENTS:
        if event["month"] == month:
            events_by_day.setdefault(event["day"], []).append({
                "title": event["title"],
                "is_holiday": event["is_holiday"],
                "color": "shia",
                "description": None,
                "is_fasting_day": False,
            })
    return events_by_day