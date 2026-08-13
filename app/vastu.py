# vastu.py
"""
Vastu Shastra guidance module.

Vastu Shastra is the traditional Indian system of architecture and design.
This module provides daily guidance based on:
- Cardinal directions and their energies
- Time of day (sunrise/sunset based)
- Day of the week
- User's home orientation

The guidance is informational and for educational purposes only.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import math

from . import prayer_times_accurate as _pta

# Vastu directions and their properties
DIRECTIONS = {
    "north": {
        "name": "North",
        "english": "North",
        "symbol": "N",
        "degrees": 0,
        "element": "Water",
        "governing_deity": "Kubera",
        "beneficial_activities": ["Study", "Meditation", "Wealth accumulation"],
        "avoid_activities": ["Heavy cooking", "Storing weapons"],
        "color": "#1a8c8c",
        "opposite": "south"
    },
    "northeast": {
        "name": "Northeast",
        "english": "Northeast",
        "symbol": "NE",
        "degrees": 45,
        "element": "Water",
        "governing_deity": "Ishana (Shiva)",
        "beneficial_activities": ["Prayer", "Meditation", "Study"],
        "avoid_activities": ["Sleeping", "Toilet construction"],
        "color": "#4a8c8c",
        "opposite": "southwest"
    },
    "east": {
        "name": "East",
        "english": "East",
        "symbol": "E",
        "degrees": 90,
        "element": "Fire",
        "governing_deity": "Indra",
        "beneficial_activities": ["Morning prayers", "Starting new projects", "Sunrise viewing"],
        "avoid_activities": ["Heavy eating", "Sleeping"],
        "color": "#e67e22",
        "opposite": "west"
    },
    "southeast": {
        "name": "Southeast",
        "english": "Southeast",
        "symbol": "SE",
        "degrees": 135,
        "element": "Fire",
        "governing_deity": "Agni",
        "beneficial_activities": ["Cooking", "Eating", "Electrical work"],
        "avoid_activities": ["Study", "Meditation", "Sleeping"],
        "color": "#d35400",
        "opposite": "northwest"
    },
    "south": {
        "name": "South",
        "english": "South",
        "symbol": "S",
        "degrees": 180,
        "element": "Air",
        "governing_deity": "Yama",
        "beneficial_activities": ["Physical labor", "Gardening", "Storage"],
        "avoid_activities": ["Sleeping with head south", "Study"],
        "color": "#c0392b",
        "opposite": "north"
    },
    "southwest": {
        "name": "Southwest",
        "english": "Southwest",
        "symbol": "SW",
        "degrees": 225,
        "element": "Earth",
        "governing_deity": "Nirriti",
        "beneficial_activities": ["Sleeping", "Meditation", "Rest"],
        "avoid_activities": ["Cooking", "Study"],
        "color": "#8e44ad",
        "opposite": "northeast"
    },
    "west": {
        "name": "West",
        "english": "West",
        "symbol": "W",
        "degrees": 270,
        "element": "Air",
        "governing_deity": "Varuna",
        "beneficial_activities": ["Creative work", "Evening prayers", "Dining"],
        "avoid_activities": ["Important meetings", "Financial decisions"],
        "color": "#2980b9",
        "opposite": "east"
    },
    "northwest": {
        "name": "Northwest",
        "english": "Northwest",
        "symbol": "NW",
        "degrees": 315,
        "element": "Air",
        "governing_deity": "Vayu",
        "beneficial_activities": ["Socializing", "Meetings", "Communication"],
        "avoid_activities": ["Resting", "Study"],
        "color": "#3498db",
        "opposite": "southeast"
    }
}

# Center/Brahmasthan
CENTER = {
    "name": "Brahmasthan",
    "english": "Center",
    "symbol": "C",
    "element": "Space",
    "governing_deity": "Brahma",
    "beneficial_activities": ["Open space", "Lighting", "Air circulation"],
    "avoid_activities": ["Heavy furniture", "Construction", "Walls"],
    "color": "#f1c40f"
}

DAY_ENERGIES = {
    0: {"day": "Monday", "ruling_planet": "Moon", "direction": "Northwest", "energy": "Cooling, Emotional"},
    1: {"day": "Tuesday", "ruling_planet": "Mars", "direction": "South", "energy": "Fiery, Energetic"},
    2: {"day": "Wednesday", "ruling_planet": "Mercury", "direction": "Northeast", "energy": "Intellectual, Quick"},
    3: {"day": "Thursday", "ruling_planet": "Jupiter", "direction": "East", "energy": "Expansive, Wise"},
    4: {"day": "Friday", "ruling_planet": "Venus", "direction": "Southeast", "energy": "Creative, Harmonious"},
    5: {"day": "Saturday", "ruling_planet": "Saturn", "direction": "West", "energy": "Structured, Slow"},
    6: {"day": "Sunday", "ruling_planet": "Sun", "direction": "East", "energy": "Active, Authoritative"}
}

VASTU_PURUSHA_DIRECTIONS = {
    "head": "Northeast",
    "feet": "Southwest",
    "right_hand": "Southeast",
    "left_hand": "Northwest"
}

@dataclass
class VastuDayInfo:
    """Container for daily Vastu information."""
    date: date
    weekday: str
    ruling_planet: str
    energy_type: str
    agni_direction: str  # Fire energy
    vayu_direction: str   # Air energy
    prithvi_direction: str # Earth energy
    best_direction: str
    best_activity: str
    avoid_direction: str
    avoid_activity: str
    tips: List[str]
    directional_colors: Dict[str, str]
    # For different types of activities
    sleeping_direction: str
    working_direction: str
    eating_direction: str
    study_direction: str

@dataclass
class VastuPropertyInfo:
    """Information about a property from a Vastu perspective."""
    orientation: float
    main_direction: str
    vastu_purusha_position: Dict[str, str]
    strengths: List[str]
    weaknesses: List[str]
    remedies: List[str]

class VastuCalculator:
    """Main Vastu calculation engine."""
    
    def __init__(self, lat: float, lng: float, tz_offset: float):
        self.lat = lat
        self.lng = lng
        self.tz_offset = tz_offset
        self._sunrise_cache = {}
        self._sunset_cache = {}
    
    def _get_sunrise_sunset(self, d: date) -> Tuple[datetime, datetime]:
        """Get sunrise and sunset times for a given date."""
        cache_key = d.isoformat()
        if cache_key in self._sunrise_cache:
            return self._sunrise_cache[cache_key], self._sunset_cache[cache_key]
        
        jd = _pta.julian_day(d)
        dec, eqt = _pta.sun_position(jd)
        noon_utc = 12.0 - self.lng / 15.0 - eqt
        
        sunrise_utc = _pta.time_for_angle(
            jd, self.lat, self.lng, _pta.SUNSET_ANGLE, True, eqt, noon_utc
        )
        sunset_utc = _pta.time_for_angle(
            jd, self.lat, self.lng, _pta.SUNSET_ANGLE, False, eqt, noon_utc
        )
        
        # Convert to datetime
        sunrise_dt = datetime(d.year, d.month, d.day) + timedelta(hours=sunrise_utc + self.tz_offset)
        sunset_dt = datetime(d.year, d.month, d.day) + timedelta(hours=sunset_utc + self.tz_offset)
        
        self._sunrise_cache[cache_key] = sunrise_dt
        self._sunset_cache[cache_key] = sunset_dt
        
        return sunrise_dt, sunset_dt
    
    def _get_direction_from_degrees(self, degrees: float) -> str:
        """Convert degrees to the nearest cardinal/intercardinal direction."""
        degrees = degrees % 360
        direction_ranges = {
            "north": (337.5, 360, 0, 22.5),
            "northeast": (22.5, 67.5),
            "east": (67.5, 112.5),
            "southeast": (112.5, 157.5),
            "south": (157.5, 202.5),
            "southwest": (202.5, 247.5),
            "west": (247.5, 292.5),
            "northwest": (292.5, 337.5)
        }
        
        for direction, ranges in direction_ranges.items():
            if len(ranges) == 2:
                if ranges[0] <= degrees < ranges[1]:
                    return direction
            else:
                if (ranges[0] <= degrees <= 360) or (0 <= degrees < ranges[1]):
                    return direction
        return "north"  # fallback
    
    def calculate_daily(self, d: date, home_orientation: Optional[float] = None) -> VastuDayInfo:
        """Calculate daily Vastu guidance."""
        
        # Get sunrise/sunset
        sunrise, sunset = self._get_sunrise_sunset(d)
        day_length = sunset - sunrise
        
        # Weekday energy
        weekday_info = DAY_ENERGIES[d.weekday()]
        
        # Calculate directional energies based on sunrise/sunset
        # Agni (Fire) - Southeast, strongest at noon
        # Vayu (Air) - Northwest, strongest in the evening
        # Prithvi (Earth) - Southwest, strongest at midnight
        
        noon = sunrise + day_length / 2
        evening = sunset - timedelta(minutes=30)
        
        # Determine which directions are active based on time of day
        current_time = datetime.now()
        time_of_day = (current_time - sunrise).total_seconds() / day_length.total_seconds()
        
        if 0 <= time_of_day < 0.25:
            agni = "Southeast (Agni) - Morning fire"
            vayu = "Northwest (Vayu) - Gentle morning breeze"
            prithvi = "Southwest (Prithvi) - Morning grounding"
        elif 0.25 <= time_of_day < 0.5:
            agni = "Southeast (Agni) - Growing fire"
            vayu = "Northwest (Vayu) - Midday air"
            prithvi = "Southwest (Prithvi) - Midday grounding"
        elif 0.5 <= time_of_day < 0.75:
            agni = "Southeast (Agni) - Setting fire"
            vayu = "Northwest (Vayu) - Evening air"
            prithvi = "Southwest (Prithvi) - Evening grounding"
        else:
            agni = "Southeast (Agni) - Night fire"
            vayu = "Northwest (Vayu) - Night air"
            prithvi = "Southwest (Prithvi) - Night grounding"
        
        # Determine best and worst directions
        day_direction = weekday_info["direction"].lower()
        day_energy = weekday_info["energy"].lower()
        
        # Get direction info
        best_dir = self._get_best_direction(day_direction, home_orientation)
        avoid_dir = self._get_avoid_direction(day_direction, home_orientation)
        
        # Determine activities
        best_activity = self._get_best_activity(day_direction)
        avoid_activity = self._get_avoid_activity(day_direction)
        
        # Sleep, work, eat, study directions
        sleeping_dir = self._get_sleeping_direction(d)
        working_dir = self._get_working_direction(d)
        eating_dir = self._get_eating_direction(d)
        study_dir = self._get_study_direction(d)
        
        # Generate tips
        tips = self._generate_tips(d, weekday_info, best_dir, avoid_dir, home_orientation)
        
        # Directional colors
        directional_colors = {
            "north": DIRECTIONS["north"]["color"],
            "northeast": DIRECTIONS["northeast"]["color"],
            "east": DIRECTIONS["east"]["color"],
            "southeast": DIRECTIONS["southeast"]["color"],
            "south": DIRECTIONS["south"]["color"],
            "southwest": DIRECTIONS["southwest"]["color"],
            "west": DIRECTIONS["west"]["color"],
            "northwest": DIRECTIONS["northwest"]["color"]
        }
        
        return VastuDayInfo(
            date=d,
            weekday=weekday_info["day"],
            ruling_planet=weekday_info["ruling_planet"],
            energy_type=weekday_info["energy"],
            agni_direction=agni,
            vayu_direction=vayu,
            prithvi_direction=prithvi,
            best_direction=best_dir,
            best_activity=best_activity,
            avoid_direction=avoid_dir,
            avoid_activity=avoid_activity,
            tips=tips,
            directional_colors=directional_colors,
            sleeping_direction=sleeping_dir,
            working_direction=working_dir,
            eating_direction=eating_dir,
            study_direction=study_dir
        )
    
    def _get_best_direction(self, day_direction: str, home_orientation: Optional[float]) -> str:
        """Get the best direction for today."""
        # Map day direction to best direction
        direction_map = {
            "northwest": "Northeast",
            "south": "East",
            "northeast": "East",
            "east": "Northeast",
            "southeast": "North",
            "west": "Northeast",
            "north": "East"
        }
        best = direction_map.get(day_direction, "East")
        
        # If home orientation is provided, consider it
        if home_orientation is not None:
            home_dir = self._get_direction_from_degrees(home_orientation)
            if home_dir == best:
                # If best direction aligns with home orientation, reinforce it
                return f"{best} (aligned with your home)"
            else:
                return f"{best} (your home faces {home_dir})"
        return best
    
    def _get_avoid_direction(self, day_direction: str, home_orientation: Optional[float]) -> str:
        """Get the direction to avoid today."""
        direction_map = {
            "northwest": "Southeast",
            "south": "North",
            "northeast": "Southwest",
            "east": "South",
            "southeast": "Northwest",
            "west": "South",
            "north": "Southwest"
        }
        avoid = direction_map.get(day_direction, "South")
        return avoid
    
    def _get_best_activity(self, day_direction: str) -> str:
        """Get the best activity based on direction."""
        activity_map = {
            "north": "Financial planning, investments",
            "northeast": "Study, meditation, planning",
            "east": "Starting new projects, morning prayers",
            "southeast": "Cooking, electrical work, creative projects",
            "south": "Physical labor, gardening",
            "southwest": "Rest, meditation",
            "west": "Creative work, dining",
            "northwest": "Meetings, socializing, communication"
        }
        return activity_map.get(day_direction, "General activities")
    
    def _get_avoid_activity(self, day_direction: str) -> str:
        """Get the activity to avoid based on direction."""
        avoid_map = {
            "north": "Heavy meals, arguments",
            "northeast": "Sleeping, toilet use",
            "east": "Heavy eating, sleeping",
            "southeast": "Study, meditation",
            "south": "Important decisions, negotiations",
            "southwest": "Cooking, study",
            "west": "Financial decisions, important meetings",
            "northwest": "Rest, study"
        }
        return avoid_map.get(day_direction, "Avoid stressful activities")
    
    def _get_sleeping_direction(self, d: date) -> str:
        """Get the best direction to sleep based on Vastu."""
        # Head direction should be South or East
        weekday = d.weekday()
        if weekday in [0, 3, 4]:  # Monday, Thursday, Friday
            return "South (head facing South)"
        elif weekday in [1, 5]:  # Tuesday, Saturday
            return "East (head facing East)"
        else:  # Wednesday, Sunday
            return "South (head facing South)"
    
    def _get_working_direction(self, d: date) -> str:
        """Get the best direction to work based on Vastu."""
        weekday = d.weekday()
        if weekday in [0, 4]:  # Monday, Friday
            return "East (face East while working)"
        elif weekday in [2, 3]:  # Wednesday, Thursday
            return "North (face North while working)"
        else:  # Tuesday, Saturday, Sunday
            return "East (face East while working)"
    
    def _get_eating_direction(self, d: date) -> str:
        """Get the best direction to eat based on Vastu."""
        weekday = d.weekday()
        if weekday in [0, 1, 2]:  # Monday, Tuesday, Wednesday
            return "East (face East while eating)"
        else:  # Thursday, Friday, Saturday, Sunday
            return "North (face North while eating)"
    
    def _get_study_direction(self, d: date) -> str:
        """Get the best direction to study based on Vastu."""
        return "Northeast (face Northeast while studying)"
    
    def _generate_tips(self, d: date, weekday_info: Dict, best_dir: str, avoid_dir: str, home_orientation: Optional[float]) -> List[str]:
        """Generate Vastu tips for the day."""
        tips = [
            f"Today is {weekday_info['day']}, ruled by {weekday_info['ruling_planet']}. Focus on {weekday_info['energy']} energy.",
            f"Best direction: {best_dir}",
            f"Avoid direction: {avoid_dir}",
            f"Sleep with your head facing {self._get_sleeping_direction(d)}.",
            f"Face {self._get_working_direction(d)} while working.",
            f"Face {self._get_eating_direction(d)} while eating.",
        ]
        
        # Add home-specific tips
        if home_orientation is not None:
            home_dir = self._get_direction_from_degrees(home_orientation)
            if home_dir == "northeast":
                tips.append("Your home faces Northeast (Ishana) - Excellent for spiritual growth!")
            elif home_dir == "southeast":
                tips.append("Your home faces Southeast (Agni) - Good for business and cooking.")
            elif home_dir == "southwest":
                tips.append("Your home faces Southwest (Nirriti) - Good for rest and relaxation.")
            elif home_dir == "northwest":
                tips.append("Your home faces Northwest (Vayu) - Good for social activities.")
        
        # Add seasonal tips
        month = d.month
        if month in [12, 1, 2]:
            tips.append("Winter season: Focus on the Southeast (Agni) zone for warmth.")
        elif month in [3, 4, 5]:
            tips.append("Spring season: Focus on the Northeast (Ishana) zone for renewal.")
        elif month in [6, 7, 8]:
            tips.append("Summer season: Focus on the Northwest (Vayu) zone for cooling.")
        else:  # Fall
            tips.append("Fall season: Focus on the Southwest (Nirriti) zone for grounding.")
        
        return tips
    
    def analyze_property(self, orientation: float, entrance: str, has_toilet_northeast: bool = False) -> VastuPropertyInfo:
        """Analyze a property from a Vastu perspective."""
        main_direction = self._get_direction_from_degrees(orientation)
        
        # Determine strengths and weaknesses
        strengths = []
        weaknesses = []
        remedies = []
        
        # Main orientation analysis
        if main_direction in ["north", "east"]:
            strengths.append("Property faces an auspicious direction")
            strengths.append("Good for prosperity and health")
        elif main_direction in ["south", "west"]:
            weaknesses.append("Property faces a direction that may need remedies")
            remedies.append("Install a Vastu mirror or yantra facing the entrance")
            remedies.append("Keep the entrance well-lit and clean")
        
        # Entrance analysis
        if entrance in ["northeast", "east"]:
            strengths.append("Entrance is in an auspicious location")
        elif entrance in ["south", "southwest"]:
            weaknesses.append("Entrance in an inauspicious location")
            remedies.append("Place a threshold or step at the entrance")
            remedies.append("Keep a fountain or water feature near the entrance")
        
        # Toilet position
        if has_toilet_northeast:
            weaknesses.append("Toilet in Northeast is highly inauspicious")
            remedies.append("Use the toilet only when necessary")
            remedies.append("Keep the toilet door closed at all times")
            remedies.append("Place a pyramid or crystal in the toilet")
        
        # Vastu Purusha position
        vastu_purusha = {
            "head": VASTU_PURUSHA_DIRECTIONS["head"],
            "feet": VASTU_PURUSHA_DIRECTIONS["feet"],
            "right_hand": VASTU_PURUSHA_DIRECTIONS["right_hand"],
            "left_hand": VASTU_PURUSHA_DIRECTIONS["left_hand"]
        }
        
        return VastuPropertyInfo(
            orientation=orientation,
            main_direction=main_direction,
            vastu_purusha_position=vastu_purusha,
            strengths=strengths,
            weaknesses=weaknesses,
            remedies=remedies
        )

def get_vastu_for_day(d: date, lat: float, lng: float, tz_offset: float, home_orientation: Optional[float] = None) -> VastuDayInfo:
    """Convenience function to get daily Vastu guidance."""
    calculator = VastuCalculator(lat, lng, tz_offset)
    return calculator.calculate_daily(d, home_orientation)

def analyze_property(orientation: float, entrance: str, has_toilet_northeast: bool = False) -> VastuPropertyInfo:
    """Convenience function to analyze a property."""
    calculator = VastuCalculator(0, 0, 0)  # Location not needed for property analysis
    return calculator.analyze_property(orientation, entrance, has_toilet_northeast)
