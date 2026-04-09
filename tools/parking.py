import math
from langchain_core.tools import tool
from data.zoning_rules import BIKE_PARKING_RATIOS, ACCESSIBLE_CAR_RATIOS


@tool
def calculate_parking_requirements(
	use_type: str,
	quantity: float,
	avg_unit_size_m2: float = 75,
) -> dict:
	"""
	Calculate mandatory bicycle parking (Fahrradabstellplätze) and accessible car spaces
	for a Berlin development, per AV Stellplätze (16.06.2021, ABl. S. 2326).

	IMPORTANT: Berlin abolished the general car parking minimum (Stellplatzpflicht) in the
	2021 BauO Bln reform (§49 BauO Bln, effective 01.07.2021). No minimum number of general
	car spaces is legally required. Only bicycle spaces and accessible car spaces for
	disabled users remain mandatory.

	Args:
		use_type: Type of use. Options: wohnen, sozialwohnungsbau, buero,
				  einzelhandel, gaststaette, hotel, gewerbe
		quantity: Depends on use_type:
				  - wohnen / sozialwohnungsbau → number of residential units
				  - buero / einzelhandel / gewerbe → floor area in m² (NUF)
				  - gaststaette → number of guest seats (Gastplätze)
				  - hotel → number of guest rooms (Gästezimmer)
		avg_unit_size_m2: Average unit size in m² (only used for wohnen / sozialwohnungsbau).
						  Determines the AV Stellplätze tier: ≤50 / ≤75 / ≤100 / >100 m².
						  Default: 75 m².
	"""
	use = use_type.lower().strip()

	if use not in BIKE_PARKING_RATIOS:
		available = ", ".join(BIKE_PARKING_RATIOS.keys())
		return {
			"error":        f"Unknown use type '{use_type}'. Available types: {available}",
			"error_code":   "unknown_use_type",
			"error_params": {"use_type": use_type, "available": available},
		}

	if quantity <= 0:
		return {
			"error":      "Quantity must be greater than 0.",
			"error_code": "invalid_quantity",
		}

	bike_cfg       = BIKE_PARKING_RATIOS[use]
	accessible_cfg = ACCESSIBLE_CAR_RATIOS.get(use, {})

	# ── Bike spaces (Anlage 2) ──────────────────────────────────────────────
	if use in ("wohnen", "sozialwohnungsbau"):
		# Tiered by average unit size
		bike_per_unit = next(
			spaces for threshold, spaces in bike_cfg["tiers"]
			if avg_unit_size_m2 <= threshold
		)
		bike_spaces  = max(2, round(bike_per_unit * quantity))
		bike_ratio   = float(bike_per_unit)
		tier_label   = next(t for t, _ in bike_cfg["tiers"] if avg_unit_size_m2 <= t)
		bike_formula = (
			f"{int(quantity)} units × {bike_per_unit} (unit size ≤{tier_label} m²) "
			f"= {bike_spaces} bike spaces"
		)
	elif use == "buero":
		# Two-tier: small vs large building (threshold is BGF, but we use NUF as proxy)
		ratio        = bike_cfg["ratio_large"] if quantity >= bike_cfg["area_threshold_m2"] else bike_cfg["ratio_small"]
		bike_spaces  = max(2, math.ceil(ratio * quantity))
		bike_ratio   = round(ratio, 5)
		tier_label   = "≥4,000 m² BGF" if quantity >= bike_cfg["area_threshold_m2"] else "<4,000 m² BGF"
		bike_formula = f"{int(quantity)} m² NUF × {bike_ratio} ({tier_label}) = {bike_spaces} bike spaces"
	else:
		ratio        = bike_cfg["ratio"]
		bike_spaces  = max(2, math.ceil(ratio * quantity))
		bike_ratio   = round(ratio, 5)
		bike_formula = f"{quantity:.0f} {bike_cfg['unit']} × {bike_ratio} = {bike_spaces} bike spaces"

	# Cargo bike spaces: from 20 standard spaces, 5% must be cargo-capable (§2.4h AV Stellplätze)
	cargo_spaces = math.floor(bike_spaces / 20) if bike_spaces >= 20 else 0

	# ── Accessible car spaces (Anlage 1) ───────────────────────────────────
	accessible_spaces  = 0
	accessible_formula = "Not required for this use type"
	if accessible_cfg.get("ratio", 0) > 0 and quantity >= accessible_cfg.get("min_quantity", 0):
		accessible_spaces  = max(accessible_cfg["min_spaces"], math.ceil(accessible_cfg["ratio"] * quantity))
		accessible_formula = (
			f"{quantity:.0f} × {accessible_cfg['ratio']:.5f} = {accessible_spaces} accessible space(s)"
		)

	return {
		"use_type": use_type,
		"quantity": quantity,
		"unit":     bike_cfg["unit"],
		# Bike (mandatory)
		"required_bike_spaces":	bike_spaces,
		"cargo_bike_spaces":	cargo_spaces,
		"bike_ratio_used":		bike_ratio,
		"bike_formula":			bike_formula,
		"bike_source":			bike_cfg["source"],
		"bike_note":			bike_cfg.get("note", ""),
		# Accessible car (mandatory, Anlage 1)
		"required_accessible_car_spaces":	accessible_spaces,
		"accessible_formula":				accessible_formula,
		"accessible_source":				accessible_cfg.get("source", "AV Stellplätze 2021, Anlage 1"),
		# General car (not required)
		"general_car_spaces_required": False,
		"car_parking_note": (
			"Berlin abolished the general car parking minimum (Stellplatzpflicht) "
			"in the 2021 BauO Bln reform (§49 BauO Bln, effective 01.07.2021). "
			"No minimum number of general car spaces is required by law."
		),
		"regulation":  "AV Stellplätze (16.06.2021, ABl. S. 2326), §49 BauO Bln",
		"valid_until": "30.06.2026",
	}