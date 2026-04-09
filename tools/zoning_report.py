import logging
from langchain_core.tools import tool
from tools.fisbroker import lookup_zone_for_address
from tools.buildable_area import calculate_buildable_area
from tools.parking import calculate_parking_requirements
from tools.construction_cost import estimate_construction_cost
from tools.demographics import get_demographics, get_district_from_address
from data.zoning_rules import (
	ZONE_TO_BUILDING_TYPE,
	INNER_CITY_DISTRICTS,
	SETBACK_RULES,
	SETBACK_DEFAULT,
	SPECIAL_REQUIREMENTS,
)

logger = logging.getLogger(__name__)

@tool
def get_full_zoning_report(
	address: str,
	plot_area_m2: float = 0,
	avg_unit_size_m2: float = 75,
) -> dict:
	"""
	Generate a complete zoning and development report for a Berlin address.

	Automatically looks up zone type AND plot area from official Berlin data sources
	(GDI Berlin WFS APIs). No need to provide plot_area_m2 — it is fetched automatically
	from the ALKIS cadastre system. Only provide plot_area_m2 if you want to override
	the automatic value.

	Args:
		address: Berlin street address (e.g. "Friedrichstraße 100, Mitte")
		plot_area_m2: Optional override for plot area in m². Leave as 0 to auto-fetch from ALKIS.
		avg_unit_size_m2: Average residential unit size used to estimate number of units
		                  (default 75m²). Override if user specifies a different unit size,
		                  e.g. 65 for smaller apartments or 100 for larger ones.
	"""
	# Step 1: Look up zone type and plot area via GDI Berlin APIs
	geo = lookup_zone_for_address(address)
	if "error" in geo:
		return {"error": geo["error"]}

	base = {
		"address": address,
		"geocoded_as": geo.get("display_name"),
		"coordinates": {"lat": geo.get("lat"), "lon": geo.get("lon")},
		"alkis_props": geo.get("alkis_props"),
	}

	# Step 2: Resolve plot area
	auto_plot_area = geo.get("plot_area_m2")
	if plot_area_m2 > 0:
		resolved_plot_area = plot_area_m2
		area_source = "user-provided"
	elif auto_plot_area:
		resolved_plot_area = float(auto_plot_area)
		area_source = geo.get("plot_area_source", "ALKIS (GDI Berlin)")
	else:
		return {
			**base,
			"status": "needs_input",
			"zone_type": geo.get("zone_type"),
			"message": (
				"Zone type was found but the plot area could not be determined automatically. "
				"Please provide the plot area in m²."
			),
		}

	# Step 3: Zone type check
	if geo.get("needs_user_input") or not geo.get("zone_type"):
		return {
			**base,
			"status": "needs_input",
			"plot_area_m2": resolved_plot_area,
			"plot_area_source": area_source,
			"message": (
				f"Plot area: {resolved_plot_area} m² (from {area_source}). "
				f"However, the zone type could not be determined automatically for this address. "
				f"This is likely a §34 BauGB area (no formal Bebauungsplan). "
				f"Please provide the zone type (e.g. WA, MI, MK, GE)."
			),
		}

	zone = geo["zone_type"].upper()

	# Step 4: Buildable area — delegate entirely to calculate_buildable_area
	buildable = calculate_buildable_area.invoke({
		"plot_area_m2": resolved_plot_area,
		"zone_type": zone,
	})
	if "error" in buildable:
		return {**base, "status": "needs_input", "message": buildable["error"]}

	max_total_floor_area = buildable["max_total_floor_area_m2"]

	# Step 5: Setback rules
	setback = _get_setback_rules(zone)

	# Step 6: Parking — delegate to calculate_parking_requirements (residential default)
	units_estimate = max(1, round(max_total_floor_area / avg_unit_size_m2))
	parking = calculate_parking_requirements.invoke({
		"use_type":			"wohnen",
		"quantity":			units_estimate,
		"avg_unit_size_m2":	avg_unit_size_m2,
	})

	# Step 7: Construction cost — delegate to estimate_construction_cost
	building_type = ZONE_TO_BUILDING_TYPE.get(zone, "mehrfamilienhaus")
	display_name = geo.get("display_name", address)
	district_key = get_district_from_address(display_name) or get_district_from_address(address)
	location_type = "innenstadt" if district_key in INNER_CITY_DISTRICTS else "standard"

	cost = estimate_construction_cost.invoke({
		"building_type": building_type,
		"total_area_m2": max_total_floor_area,
		"location_type": location_type,
	})

	# Step 8: Demographics — delegate to get_demographics
	demographics = get_demographics.invoke({"address": address})
	if "error" in demographics:
		logger.warning(f"Demographics unavailable: {demographics['error']}")
		demographics = None

	# Step 9: Special requirements
	special = _get_special_requirements(zone, buildable["max_footprint_m2"])

	return {
		**base,
		"status": "complete",
		"zone": {
			"type": zone,
			"source": geo.get("zone_source"),
			"plan_name": geo.get("plan_name"),
			"plan_inhalt": geo.get("plan_inhalt"),
			"all_zone_types": geo.get("all_zone_types", []),
			"note": geo.get("note"),
		},
		"plot": {
			"area_m2": resolved_plot_area,
			"area_source": area_source,
		},
		"buildable_area": buildable,
		"setbacks": setback,
		"parking": {
			"assumed_use_type":              "wohnen (residential)",
			"estimated_units":               units_estimate,
			"avg_unit_size_m2":              avg_unit_size_m2,
			"units_calculation":             f"{max_total_floor_area} m² ÷ {avg_unit_size_m2} m²/unit = {units_estimate} units",
			"required_bike_spaces":          parking.get("required_bike_spaces"),
			"cargo_bike_spaces":             parking.get("cargo_bike_spaces"),
			"required_accessible_car_spaces": parking.get("required_accessible_car_spaces"),
			"general_car_spaces_required":   False,
			"bike_formula":                  parking.get("bike_formula"),
			"bike_source":                   parking.get("bike_source"),
			"car_parking_note":              parking.get("car_parking_note"),
			"regulation":                    parking.get("regulation"),
			"note": "Unit count assumes standard avg unit size — ask to recalculate with a different size.",
		},
		"construction_cost": cost,
		"special_requirements": special,
		"demographics": demographics,
	}


def _get_setback_rules(zone: str) -> dict:
	"""Look up setback rules for a zone type from SETBACK_RULES data."""
	for rule in SETBACK_RULES:
		if zone in rule["zones"]:
			return rule["rules"]
	return SETBACK_DEFAULT


def _get_special_requirements(zone: str, footprint_m2: float) -> list:
	"""Evaluate all special requirements against the given zone and footprint."""
	return [
		rule["text"]
		for rule in SPECIAL_REQUIREMENTS
		if rule["condition"](zone, footprint_m2)
	]