"""
data/zoning_rules.py — Zoning rules and mappings for Berlin.

Edit this file to update rules when regulations change.

Sources:
  - BauO Bln (Berliner Bauordnung, post-7th amendment, January 2026)
  - BauNVO (Baunutzungsverordnung, July 2023)
"""

# ---------------------------------------------------------------------------
# Zone parameters — GRZ, GFZ, max floors per zone type (BauNVO §17)
# Edit when BauNVO is amended or a specific B-Plan overrides defaults.
# ---------------------------------------------------------------------------

ZONE_PARAMETERS = {
	"WS": {"grz": 0.2, "gfz": 0.4,  "max_floors": 2},
	"WR": {"grz": 0.4, "gfz": 1.2,  "max_floors": 4},
	"WA": {"grz": 0.4, "gfz": 1.2,  "max_floors": 4},
	"WB": {"grz": 0.6, "gfz": 1.6,  "max_floors": 6},
	"MD": {"grz": 0.6, "gfz": 1.2,  "max_floors": 3},
	"MI": {"grz": 0.6, "gfz": 1.2,  "max_floors": 5},
	"MU": {"grz": 0.8, "gfz": 3.0,  "max_floors": 7},
	"MK": {"grz": 1.0, "gfz": 3.0,  "max_floors": 10},
	"GE": {"grz": 0.8, "gfz": 2.4,  "max_floors": 6},
	"GI": {"grz": 0.8, "gfz": 2.4,  "max_floors": 6},
}

# ---------------------------------------------------------------------------
# Zone type -> building type mapping for construction cost estimation
# ---------------------------------------------------------------------------

ZONE_TO_BUILDING_TYPE = {
	"WS": "einfamilienhaus",
	"WR": "einfamilienhaus",
	"WA": "mehrfamilienhaus",
	"WB": "mehrfamilienhaus",
	"MD": "einfamilienhaus",
	"MI": "mehrfamilienhaus",
	"MU": "mehrfamilienhaus",        # Mixed-use urban block, closest to MFH
	"MK": "mehrfamilienhaus_gross",
	"GE": "gewerbe_mix",
	"GI": "gewerbe_halle",
}

# ---------------------------------------------------------------------------
# Districts treated as inner-city for construction cost location multiplier
# ---------------------------------------------------------------------------

INNER_CITY_DISTRICTS = {
	"mitte", "friedrichshain-kreuzberg", "pankow",
	"charlottenburg-wilmersdorf", "tempelhof-schöneberg", "neukölln"
}

# ---------------------------------------------------------------------------
# Setback rules per zone group (BauO Bln §6)
# Each entry has a "zones" set and a "rules" dict returned to the caller
# ---------------------------------------------------------------------------

SETBACK_RULES = [
	{
		"zones": {"MK", "MU", "MI", "WB"},
		"rules": {
			"min_setback_m": 0,
			"note": "Setbacks may be reduced or waived in dense inner-city zones (MK/MU/MI/WB). Check Bebauungsplan.",
			"standard_rule": "0.4 × wall height (H), min 3 m — may be reduced or waived by B-Plan (§6 Abs. 5 BauO Berlin).",
		},
	},
	{
		"zones": {"GE", "GI"},
		"rules": {
			"min_setback_m": 3.0,
			"note": "Industrial zone setbacks apply. Check fire protection distances.",
			"standard_rule": "0.2 × wall height (H), minimum 3 m (§6 Abs. 5 BauO Berlin).",
		},
	},
]

# Default setback rules for all other zones
SETBACK_DEFAULT = {
	"min_setback_m":  3.0,
	"standard_rule": "0.4 × wall height (H), minimum 3 m on all sides (§6 Abs. 5 BauO Berlin). "
					 "Exception: Gebäudeklassen 1+2 with ≤3 floors: flat 3 m regardless of height.",
}

# ---------------------------------------------------------------------------
# Special requirements
# Each rule has:
#   "condition": lambda zone, footprint_m2 -> bool
#   "text": the requirement string shown in the report
# ---------------------------------------------------------------------------

SPECIAL_REQUIREMENTS = [
	{
		# §8 Abs. 1 BauO Berlin: applies to roofs with pitch ≤10° AND total roof area > 100m².
		# We approximate using footprint as a proxy for roof area (flat/near-flat roofs),
		# and note the pitch condition in the text since we can't compute it from zone data.
		"condition": lambda zone, footprint_m2: footprint_m2 > 100,
		"text": "Green roof (Dachbegrünung) required for flat roofs (pitch ≤10°) with total roof area > 100 m² (§8 Abs. 1 BauO Berlin). Exceptions apply where another permitted use of the roof surface is required.",
	},
	{
		# This rule does not exist in BauNVO or BauO Berlin as a general statutory requirement.
		# It may appear in specific Bebauungspläne but cannot be stated as a universal rule.
		# Replaced with the actual §8 Abs. 1 requirement for unpaved/vegetated open areas.
		"condition": lambda zone, footprint_m2: zone in {"WA", "MI", "MU", "WB"},
		"text": "Unpaved open areas on the plot must be kept or made water-permeable and must be greened or planted, as far as no other permitted use requires otherwise (§8 Abs. 1 BauO Berlin).",
	},
	{
		# 8 Abs. 2 BauO Berlin only requires a playground for buildings with MORE THAN SIX residential units.
		"condition": lambda zone, footprint_m2: zone in {"WS", "WR", "WA", "WB", "MD", "MI", "MU", "MK"},
		"text": "Children's playground required when constructing buildings with more than six residential units (notwendiger Kinderspielplatz). Min. 4 m² usable play area per dwelling, min. 50 m² total. For >75 units: must also be suitable for older children (§8 Abs. 2 BauO Berlin).",
	},
]

# ---------------------------------------------------------------------------
# Parking ratios per AV Stellplätze (16.06.2021, ABl. S. 2326)
# Edit when a new AV Stellplätze is published (current version expires 30.06.2026).
# ---------------------------------------------------------------------------

# AV Stellplätze 16.06.2021 (ABl. S. 2326), Anlage 2 — Mandatory bike parking
# Valid from 01.07.2021 until 30.06.2026.
BIKE_PARKING_RATIOS = {
	"wohnen": {
		# Tiered by unit size (m² Wohnfläche)
		"tiers": [(50, 1), (75, 2), (100, 3), (float("inf"), 4)],
		"unit": "je Wohneinheit",
		"source": "AV Stellplätze 16.06.2021, Anlage 2 Nr. 1a",
		"note": "≤50m²→1, ≤75m²→2, ≤100m²→3, >100m²→4 Abstellplätze je Wohneinheit",
	},
	"sozialwohnungsbau": {
		"tiers": [(50, 1), (75, 2), (100, 3), (float("inf"), 4)],
		"unit": "je Wohneinheit",
		"source": "AV Stellplätze 16.06.2021, Anlage 2 Nr. 1a",
		"note": "Same tiers as standard residential",
	},
	"buero": {
		"ratio_small": 1 / 80,    # < 4 000 m² BGF: 1 per 80 m² NUF
		"ratio_large": 1 / 200,   # ≥ 4 000 m² BGF: 1 per 200 m² NUF
		"area_threshold_m2": 4000,
		"unit": "je m² Nutzungsfläche",
		"source": "AV Stellplätze 16.06.2021, Anlage 2 Nr. 2",
		"note": "1 per 80 m² NUF (<4,000 m² BGF) or 1 per 200 m² NUF (≥4,000 m² BGF)",
	},
	"einzelhandel": {
		"ratio": 1 / 75,
		"unit": "je m² Nutzungsfläche",
		"source": "AV Stellplätze 16.06.2021, Anlage 2 Nr. 3a",
		"note": "Neighbourhood/specialist retail: 1 per 75 m². Large-format retail: 1 per 100 m²",
	},
	"gaststaette": {
		"ratio": 1 / 10,
		"unit": "je Gastplatz (Sitz- und Stehplätze)",
		"source": "AV Stellplätze 16.06.2021, Anlage 2 Nr. 8",
		"note": "1 per 10 guest seats (seated + standing)",
	},
	"hotel": {
		"ratio": 1 / 20,
		"unit": "je Gästezimmer",
		"source": "AV Stellplätze 16.06.2021, Anlage 2 Nr. 9",
		"note": "1 per 20 guest rooms",
	},
	"gewerbe": {
		"ratio": 1 / 200,
		"unit": "je m² Nutzungsfläche",
		"source": "AV Stellplätze 16.06.2021, Anlage 2 Nr. 18",
		"note": "Handwerk/Industrie: 1 per 200 m² NUF",
	},
}

# AV Stellplätze 16.06.2021, Anlage 1 — Accessible car spaces (disabled users)
# These are the ONLY mandatory car spaces in Berlin since the 2021 BauO Bln reform
# abolished the general Stellplatzpflicht for cars (§49 BauO Bln, effective 01.07.2021).
ACCESSIBLE_CAR_RATIOS = {
	"buero":             {"ratio": 1 / 3000, "min_quantity": 0,    "min_spaces": 1, "source": "AV Stellplätze 2021, Anlage 1 Nr. 1"},
	"hotel":             {"ratio": 2 / 200,  "min_quantity": 60,   "min_spaces": 1, "source": "AV Stellplätze 2021, Anlage 1 Nr. 9",  "note": "Min 1 from 60 beds"},
	"gaststaette":       {"ratio": 1 / 300,  "min_quantity": 50,   "min_spaces": 1, "source": "AV Stellplätze 2021, Anlage 1 Nr. 10", "note": "Min 1 from 50 guest seats"},
	"einzelhandel":      {"ratio": 1 / 2500, "min_quantity": 1000, "min_spaces": 1, "source": "AV Stellplätze 2021, Anlage 1 Nr. 11"},
	"wohnen":            {"ratio": 0, "min_quantity": 0, "min_spaces": 0, "source": "n/a", "note": "Not required for residential"},
	"sozialwohnungsbau": {"ratio": 0, "min_quantity": 0, "min_spaces": 0, "source": "n/a", "note": "Not required for residential"},
	"gewerbe":           {"ratio": 0, "min_quantity": 0, "min_spaces": 0, "source": "n/a", "note": "Not required unless publicly accessible (§50 BauO Bln)"},
}

# ---------------------------------------------------------------------------
# B-Plan: German zone name → BauNVO code (used by fisbroker.py)
# Source: BauNVO zone type names as they appear in GDI Berlin B-Plan inhalt field
# ---------------------------------------------------------------------------
 
ZONE_KEYWORDS: list[tuple[str, str]] = [
	("reines wohngebiet",		"WR"),
	("allgemeines wohngebiet",	"WA"),
	("besonderes wohngebiet",	"WB"),
	("urbanes gebiet",			"MU"),
	("dorfgebiet",				"MD"),
	("mischgebiet",				"MI"),
	("kerngebiet",				"MK"),
	("gewerbegebiet",			"GE"),
	("industriegebiet",			"GI"),
	("sondergebiet",			"SO"),
	("gemeinbedarfsfläche",		"GEMB"),
	("grünfläche",				"GRF"),
]
 
# ---------------------------------------------------------------------------
# FNP: nutzungsart → approximate BauNVO code (used by fisbroker.py)
# Source: GDI Berlin FNP 2025 nutzungsart field values
# ---------------------------------------------------------------------------
 
FNP_ZONE_MAP: list[tuple[str, str, str]] = [
	# (keyword in nutzungsart, BauNVO code, full name)
	("kerngebiet",				"MK",	"Kerngebiet"),
	("gemischte baufläche",		"MI",	"Mischgebiet (approx.)"),
	("gewerbliche baufläche",	"GE",	"Gewerbegebiet (approx.)"),
	("industriebaufläche",		"GI",	"Industriegebiet (approx.)"),
	("sonderbaufläche",			"SO",	"Sondergebiet (approx.)"),
	("wohnbaufläche",			"WA",	"Allgemeines Wohngebiet (approx.)"),
	("gemeinbedarfsfläche",		"GEMB",	"Gemeinbedarfsfläche (approx.)"),
	("grünfläche",				"GRF",	"Grünfläche (approx.)"),
	("verkehrsfläche",			"VF",	"Verkehrsfläche"),
]