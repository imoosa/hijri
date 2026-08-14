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
# NOTE: "International Al-Quds Day" (last Friday of Ramadan) is intentionally
# NOT included here — it's a floating weekday rule, not a fixed hijri day,
# and this schema (month, day) has no way to express "last Friday of month X".
# If you want it, compute it at render time from shia_month_grid(), not as a
# static (month, day) row here.
SHIA_EVENTS = [
    # Muharram (1)
    {"month": 1, "day": 1, "title": "Islamic New Year", "is_holiday": True},
    {"month": 1, "day": 2, "title": "Arrival of Imam Hussain in Karbala", "is_holiday": False},
    {"month": 1, "day": 7, "title": "Water supply blocked to Imam Hussain's camp", "is_holiday": False},
    {"month": 1, "day": 9, "title": "Tasu'a (Eve of Ashura)", "is_holiday": False},
    {"month": 1, "day": 10, "title": "Ashura (Martyrdom of Imam Husayn)", "is_holiday": True},
    {"month": 1, "day": 11, "title": "Captivity and movement of the Ahl al-Bayt caravan", "is_holiday": False},
    {"month": 1, "day": 25, "title": "Martyrdom of Imam Ali Zain-ul-Abideen", "is_holiday": False},

    # Safar (2)
    {"month": 2, "day": 1, "title": "Entry of captives into Damascus", "is_holiday": False},
    {"month": 2, "day": 7, "title": "Birth of Imam Musa al-Kadhim / Martyrdom narration of Imam Hasan", "is_holiday": False},
    {"month": 2, "day": 17, "title": "Martyrdom of Imam Ali al-Ridha", "is_holiday": False},
    {"month": 2, "day": 20, "title": "Arba'een (40th day after Ashura)", "is_holiday": True},
    {"month": 2, "day": 28, "title": "Martyrdom of Prophet Muhammad and Imam Hasan", "is_holiday": False},

    # Rabi al-Awwal (3)
    {"month": 3, "day": 8, "title": "Martyrdom of Imam Hasan al-Askari", "is_holiday": False},
    {"month": 3, "day": 9, "title": "Eid-e-Zehra (Beginning of Imam Mahdi's imamate)", "is_holiday": False},
    {"month": 3, "day": 17, "title": "Birth of Prophet Muhammad and Imam Ja'far al-Sadiq", "is_holiday": False},

    # Rabi al-Thani (4)
    {"month": 4, "day": 8, "title": "Birth of Imam Hasan al-Askari", "is_holiday": False},
    {"month": 4, "day": 10, "title": "Demise of Fatima Masumeh of Qom", "is_holiday": False},

    # Jumada al-Awwal (5)
    {"month": 5, "day": 5, "title": "Birth of Sayyidah Zainab", "is_holiday": False},
    {"month": 5, "day": 13, "title": "First narration of the martyrdom of Sayyidah Fatimah (start of Fatimiyyah)", "is_holiday": False},

    # Jumada al-Thani (6)
    {"month": 6, "day": 3, "title": "Main narration of the martyrdom of Sayyidah Fatimah", "is_holiday": False},
    {"month": 6, "day": 20, "title": "Birth of Sayyidah Fatimah", "is_holiday": False},

    # Rajab (7)
    {"month": 7, "day": 1, "title": "Birth of Imam Muhammad al-Baqir", "is_holiday": False},
    {"month": 7, "day": 3, "title": "Martyrdom of Imam Ali al-Hadi", "is_holiday": False},
    {"month": 7, "day": 10, "title": "Birth of Imam Muhammad al-Jawad", "is_holiday": False},
    {"month": 7, "day": 13, "title": "Birth of Imam Ali ibn Abi Talib", "is_holiday": False},
    {"month": 7, "day": 15, "title": "Demise of Sayyidah Zainab", "is_holiday": False},
    {"month": 7, "day": 25, "title": "Martyrdom of Imam Musa al-Kadhim", "is_holiday": False},
    {"month": 7, "day": 27, "title": "Mab'ath (Declaration of Prophethood)", "is_holiday": False},

    # Shaban (8)
    {"month": 8, "day": 3, "title": "Birth of Imam Hussain", "is_holiday": False},
    {"month": 8, "day": 4, "title": "Birth of Hazrat Abbas", "is_holiday": False},
    {"month": 8, "day": 5, "title": "Birth of Imam Ali Zain-ul-Abideen", "is_holiday": False},
    {"month": 8, "day": 11, "title": "Birth of Ali Akbar", "is_holiday": False},
    {"month": 8, "day": 15, "title": "Birth of Imam Muhammad al-Mahdi", "is_holiday": False},

    # Ramadan (9)
    {"month": 9, "day": 10, "title": "Demise of Lady Khadijah", "is_holiday": False},
    {"month": 9, "day": 15, "title": "Birth of Imam Hasan ibn Ali", "is_holiday": False},
    {"month": 9, "day": 18, "title": "First Night of Qadr / Attack on Imam Ali", "is_holiday": False},
    {"month": 9, "day": 19, "title": "Wounding of Imam Ali in the mosque of Kufa", "is_holiday": False},
    {"month": 9, "day": 21, "title": "Martyrdom of Imam Ali ibn Abi Talib", "is_holiday": True},
    {"month": 9, "day": 23, "title": "Greatest estimated Night of Qadr", "is_holiday": False},

    # Shawwal (10)
    {"month": 10, "day": 1, "title": "Eid al-Fitr", "is_holiday": True},
    {"month": 10, "day": 8, "title": "Youm al-Hadm (Destruction of Jannat al-Baqi shrines)", "is_holiday": False},
    {"month": 10, "day": 25, "title": "Martyrdom of Imam Ja'far al-Sadiq", "is_holiday": False},

    # Dhu al-Qi'dah (11)
    {"month": 11, "day": 1, "title": "Birth of Sayyidah Fatimah Masumeh", "is_holiday": False},
    {"month": 11, "day": 11, "title": "Birth of Imam Ali al-Ridha", "is_holiday": False},
    {"month": 11, "day": 23, "title": "Martyrdom commemoration of Imam Ali al-Ridha", "is_holiday": False},
    {"month": 11, "day": 25, "title": "Dahw al-Ardh (Rolling of the Earth)", "is_holiday": False},
    {"month": 11, "day": 29, "title": "Martyrdom of Imam Muhammad al-Jawad", "is_holiday": False},

    # Dhu al-Hijjah (12)
    {"month": 12, "day": 1, "title": "Marriage of Imam Ali and Sayyidah Fatimah", "is_holiday": False},
    {"month": 12, "day": 7, "title": "Martyrdom of Imam Muhammad al-Baqir", "is_holiday": False},
    {"month": 12, "day": 8, "title": "Tarwiyya Day / Imam Hussain departs Mecca", "is_holiday": False},
    {"month": 12, "day": 9, "title": "Day of Arafah / Martyrdom of Muslim ibn Aqil", "is_holiday": False},
    {"month": 12, "day": 10, "title": "Eid al-Adha (Festival of Sacrifice)", "is_holiday": True},
    {"month": 12, "day": 15, "title": "Birth of Imam Ali al-Hadi", "is_holiday": False},
    {"month": 12, "day": 18, "title": "Eid al-Ghadir (Appointment of Imam Ali)", "is_holiday": True},
    {"month": 12, "day": 24, "title": "Day of Mubahala", "is_holiday": False},
    {"month": 12, "day": 25, "title": "Revelation of Surah Al-Insan (Hal Ata)", "is_holiday": False},
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