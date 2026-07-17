"""Great-circle bearing from a location to the Kaaba (Mecca)."""

import math

KAABA_LAT = 21.4225
KAABA_LNG = 39.8262


def bearing_to_kaaba(lat: float, lng: float) -> float:
    """Returns compass bearing in degrees (0-360, 0=North) from (lat,lng) to Kaaba."""
    lat1 = math.radians(lat)
    lat2 = math.radians(KAABA_LAT)
    dlng = math.radians(KAABA_LNG - lng)

    x = math.sin(dlng) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlng)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def distance_km(lat: float, lng: float) -> float:
    R = 6371.0
    lat1, lat2 = math.radians(lat), math.radians(KAABA_LAT)
    dlat = math.radians(KAABA_LAT - lat)
    dlng = math.radians(KAABA_LNG - lng)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
