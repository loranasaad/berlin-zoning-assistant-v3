"""
tools/demographics.py — LangChain tool for Berlin district demographics.

Data is imported from data/berlin_districts.py — edit that file to update
figures when new statistics are published.
"""

import logging
from langchain_core.tools import tool
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

from data.berlin_districts import DISTRICT_DATA, DISTRICT_ALIASES, DATA_SOURCE, DATA_REFERENCE_DATE

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalise_district(name: str) -> str | None:
    """Resolve any district spelling / Ortsteil name to a canonical key."""
    name = name.lower().strip()
    if name in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[name]
    for alias, key in DISTRICT_ALIASES.items():
        if alias in name or name in alias:
            return key
    return None


def geocode_address(address: str) -> dict:
    try:
        geolocator = Nominatim(user_agent="berlin-zoning-assistant")
        location = geolocator.geocode(f"{address}, Berlin, Germany", timeout=10)
        if not location:
            return {"error": f"Address not found: {address}"}
        return {
            "lat": location.latitude,
            "lon": location.longitude,
            "display_name": location.address,
        }
    except GeocoderTimedOut:
        return {"error": "Geocoding service timed out. Please try again."}
    except GeocoderUnavailable:
        return {"error": "Geocoding service is unavailable."}
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        return {"error": f"Geocoding error: {str(e)}"}


def get_district_from_address(address: str) -> str | None:
    address_lower = address.lower()
    for alias, key in DISTRICT_ALIASES.items():
        if alias in address_lower:
            return key
    return None


# ── Tool ──────────────────────────────────────────────────────────────────────

@tool
def get_demographics(address: str) -> dict:
    """
    Get demographic and real estate data for a Berlin district.

    Returns population, average age, foreign residents percentage,
    average apartment size, average rent, dominant household types,
    and typical building types for the district containing the address.

    Args:
        address: A Berlin street address (e.g. "Kastanienallee 10, Prenzlauer Berg")
    """
    geo = geocode_address(address)
    if "error" in geo:
        return geo

    display_name = geo.get("display_name", "")
    district_key = (
        get_district_from_address(display_name)
        or get_district_from_address(address)
    )

    if not district_key:
        return {
            "error": (
                f"Could not determine district for '{address}'. "
                f"Geocoded as: {display_name}"
            ),
            "coordinates": {"lat": geo["lat"], "lon": geo["lon"]},
        }

    data = DISTRICT_DATA.get(district_key)
    if not data:
        return {
            "error": f"No data available for district '{district_key}'.",
            "coordinates": {"lat": geo["lat"], "lon": geo["lon"]},
        }

    return {
        "district":              district_key.title(),
        "coordinates":           {"lat": geo["lat"], "lon": geo["lon"]},
        "geocoded_address":      display_name,
        "population":            data["population"],
        "avg_age":               data["avg_age"],
        "foreign_residents_pct": data["foreign_residents_pct"],
        "avg_apartment_size_m2": data["avg_apartment_size_m2"],
        "avg_rent_per_m2":       data["avg_rent_per_m2"],
        "dominant_household":    data["dominant_household"],
        "typical_building_type": data["typical_building_type"],
        "data_source":           DATA_SOURCE,
        "reference_date":        DATA_REFERENCE_DATE,
    }