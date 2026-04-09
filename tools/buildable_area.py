from langchain_core.tools import tool
from data.zoning_rules import ZONE_PARAMETERS

@tool
def calculate_buildable_area(plot_area_m2: float, zone_type: str) -> dict:
	"""
	Calculate the maximum buildable area for a plot in Berlin based on zone type.

	Returns:
	- max_footprint_m2: maximum ground floor area (GRZ × plot)
	- max_total_floor_area_m2: maximum total floor area across all floors (GFZ × plot)
	- max_basement_footprint_m2: basement can exceed GRZ by 0.2 (§19 BauNVO)
	- typical_floors: estimated number of floors (GFZ / GRZ)
	- grz: ground coverage ratio used
	- gfz: floor area ratio used
	- zone_type: zone type used in calculation

	Args:
		plot_area_m2: Total plot area in square metres
		zone_type: Berlin zone type code (e.g. WA, MI, MK, GE)
	"""
	zone = zone_type.upper().strip()

	if zone not in ZONE_PARAMETERS:
		available = ", ".join(ZONE_PARAMETERS.keys())
		return {
			"error":        f"Unknown zone type '{zone_type}'. Available types: {available}",
			"error_code":   "unknown_zone_type",
			"error_params": {"zone_type": zone_type, "available": available},
		}

	if plot_area_m2 <= 0:
		return {
			"error":      "Plot area must be greater than 0 m².",
			"error_code": "invalid_plot_area",
		}

	params = ZONE_PARAMETERS[zone]
	grz = params["grz"]
	gfz = params["gfz"]

	max_footprint = round(grz * plot_area_m2, 2)
	max_total_floor_area = round(gfz * plot_area_m2, 2)

	# §19 BauNVO: basement/underground parking can exceed GRZ by up to 0.2
	basement_grz = min(grz + 0.2, 1.0)
	max_basement_footprint = round(basement_grz * plot_area_m2, 2)

	# Typical floor count estimate
	typical_floors = round(gfz / grz) if grz > 0 else params["max_floors"]

	return {
		"zone_type": zone,
		"plot_area_m2": plot_area_m2,
		"grz": grz,
		"gfz": gfz,
		"max_footprint_m2": max_footprint,
		"max_total_floor_area_m2": max_total_floor_area,
		"max_basement_footprint_m2": max_basement_footprint,
		"typical_floors": typical_floors,
		"max_floors": params["max_floors"],
	}
