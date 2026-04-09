"""
tools/construction_cost.py — LangChain tools for Berlin construction cost estimation.

Data is imported from data/construction_cost_data.py — edit that file to update
figures when new statistics or price indices are published.
"""

from langchain_core.tools import tool

from data.construction_cost_data import (
	CONSTRUCTION_COSTS,
	LOCATION_MULTIPLIERS,
	PRICE_INDEX_DATA,
	DATA_SOURCE,
	DATA_REFERENCE_DATE,
)


@tool
def estimate_construction_cost(
	building_type: str,
	total_area_m2: float,
	location_type: str = "standard",
) -> dict:
	"""
	Estimate construction costs for a Berlin building project.

	Returns min/avg/max cost estimates based on building type and location.
	Costs are based on BKI Baukosten 2024 adjusted for the Berlin market (Preisstand 2025).

	Args:
		building_type: Type of building. Options:
			einfamilienhaus, doppelhaus_reihenhaus,
			mehrfamilienhaus_klein, mehrfamilienhaus, mehrfamilienhaus_gross,
			buerogebaeude, gewerbe_halle, gewerbe_mix,
			tiefgarage, parkdeck, dachgeschossausbau, sanierung_altbau
		total_area_m2: Total floor area in m² BGF (or number of parking spaces for
			tiefgarage / parkdeck)
		location_type: Location factor. Options: innenstadt, stadtrand, standard
	"""
	btype = building_type.lower().strip()

	if btype not in CONSTRUCTION_COSTS:
		available = ", ".join(CONSTRUCTION_COSTS.keys())
		return {
			"error":        f"Unknown building type '{building_type}'. Available types: {available}",
			"error_code":   "unknown_building_type",
			"error_params": {"building_type": building_type, "available": available},
		}

	if total_area_m2 <= 0:
		return {
		"error":      "Area must be greater than 0 m².",
		"error_code": "invalid_area",
	}

	location = location_type.lower().strip()
	if location not in LOCATION_MULTIPLIERS:
		location = "standard"

	multiplier = LOCATION_MULTIPLIERS[location]
	costs = CONSTRUCTION_COSTS[btype]

	cost_min = round(costs["cost_min"] * multiplier)
	cost_avg = round(costs["cost_avg"] * multiplier)
	cost_max = round(costs["cost_max"] * multiplier)

	return {
		"building_type":          costs["label"],
		"total_area":             total_area_m2,
		"unit":                   costs["unit"],
		"location_type":          location_type,
		"location_multiplier":    multiplier,
		"cost_per_unit_min_eur":  cost_min,
		"cost_per_unit_avg_eur":  cost_avg,
		"cost_per_unit_max_eur":  cost_max,
		"total_cost_min_eur":     round(cost_min * total_area_m2),
		"total_cost_avg_eur":     round(cost_avg * total_area_m2),
		"total_cost_max_eur":     round(cost_max * total_area_m2),
		"notes":                  costs["notes"],
		"notes_en":               costs.get("notes_en", costs["notes"]),
		"data_source":            DATA_SOURCE,
		"price_index_ref": (
			"Berliner Baupreisindex Wohngebäude 2025: Ø +3,9 % ggü. 2024 "
			"(Amt für Statistik Berlin-Brandenburg, M I 4 – vj, Januar 2026)"
		),
		"disclaimer": (
			"Richtwerte auf Basis BGF (Bruttogrundfläche), netto ohne MwSt. "
			"Nicht enthalten: Grundstück, Außenanlagen, Baunebenkosten (~15–20 % Aufschlag). "
			"Exakte Kosten abhängig von Baugrund, Ausstattung und Ausführungsqualität."
		),
		"disclaimer_en": (
			"Indicative figures based on GFA (gross floor area), net of VAT. "
			"Excludes: land, external works, and ancillary costs (~15–20% surcharge). "
			"Exact costs depend on subsoil conditions, fit-out standard, and construction quality."
		),
	}


@tool
def get_construction_price_index(category: str = "berlin_wohngebaeude_2025") -> dict:
	"""
	Return official construction price index data for Berlin and Germany.

	Provides quarterly year-on-year changes from official statistics, useful for
	contextualising cost estimates and explaining price trends to clients.

	Args:
		category: Which index to return. Options:
			berlin_wohngebaeude_2025       — Berlin residential new build 2025 (quarterly)
			national_wohngebaeude_2025     — Germany residential new build 2025
			national_buerogebaeude_nov2025 — Germany office new build Nov 2025
			national_gewerbe_nov2025       — Germany commercial new build Nov 2025
			berlin_rohbau_nov2025          — Berlin shell construction breakdown Nov 2025
			berlin_ausbau_nov2025          — Berlin finishing works breakdown Nov 2025
			historical_national            — Historical annual changes 2021–2025
	"""
	key = category.lower().strip()
	if key not in PRICE_INDEX_DATA:
		available = ", ".join(PRICE_INDEX_DATA.keys())
		return {
			"error":        f"Unknown category '{category}'. Available categories: {available}",
			"error_code":   "unknown_price_index_category",
			"error_params": {"category": category, "available": available},
		}
	return PRICE_INDEX_DATA[key]