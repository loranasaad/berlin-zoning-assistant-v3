"""
data/berlin_districts.py — Static reference data for Berlin's 12 Bezirke.

To update this file, consult:
  - Population / avg_age / foreign_residents_pct:
      Amt für Statistik Berlin-Brandenburg, Einwohnerregisterstatistik (CC-BY)
      https://www.statistik-berlin-brandenburg.de/kommunalstatistik/einwohnerbestand-berlin
      Published biannually (30 June, 31 December). Latest: 30.06.2025 / 31.12.2025.

  - avg_apartment_size_m2 / avg_rent_per_m2:
      IBB Wohnungsmarktbericht (annual, published by Investitionsbank Berlin)
      https://www.ibb.de/de/wohnungsmarktbericht

  - dominant_household / typical_building_type:
      Qualitative estimates from Amt für Statistik census microdata.

Notes:
  - foreign_residents_pct = Ausländeranteil (non-German passport holders only).
    Migrationshintergrund (incl. naturalised Germans) is considerably higher.
  - Berlin-wide: population 3,913,644 | avg age 42.9 | foreign 24.9% (31.12.2025)
  - Last updated: March 2026 (data reference: 31.12.2024 / 30.06.2025)
"""

# ── District statistics ────────────────────────────────────────────────────────

DISTRICT_DATA: dict[str, dict] = {
    "mitte": {
        "population":            397_000,   # 31.12.2024
        "avg_age":               39.5,
        "foreign_residents_pct": 37.0,      # 30.06.2025 (highest in Berlin)
        "avg_apartment_size_m2": 63,
        "avg_rent_per_m2":       18.5,
        "dominant_household":    "Singles and couples",
        "typical_building_type": "Gründerzeit historic buildings, new construction",
    },
    "friedrichshain-kreuzberg": {
        "population":            291_000,
        "avg_age":               37.5,      # youngest district
        "foreign_residents_pct": 28.0,
        "avg_apartment_size_m2": 65,
        "avg_rent_per_m2":       17.8,
        "dominant_household":    "Singles, shared flats, young families",
        "typical_building_type": "Historic buildings, loft conversions",
    },
    "pankow": {
        "population":            427_276,   # 31.12.2024 — largest district
        "avg_age":               40.8,
        "foreign_residents_pct": 14.0,
        "avg_apartment_size_m2": 72,
        "avg_rent_per_m2":       15.2,
        "dominant_household":    "Families, young parents",
        "typical_building_type": "Historic buildings, single-family homes, new construction",
    },
    "charlottenburg-wilmersdorf": {
        "population":            345_000,
        "avg_age":               45.2,      # 2nd highest avg age (31.12.2025)
        "foreign_residents_pct": 26.9,      # 30.06.2025 (down 0.3pp)
        "avg_apartment_size_m2": 78,
        "avg_rent_per_m2":       18.0,
        "dominant_household":    "Couples, older residents, expats",
        "typical_building_type": "Gründerzeit historic buildings, upscale new construction",
    },
    "spandau": {
        "population":            259_300,   # 31.12.2024 — smallest district
        "avg_age":               44.5,
        "foreign_residents_pct": 18.5,
        "avg_apartment_size_m2": 74,
        "avg_rent_per_m2":       12.5,
        "dominant_household":    "Families",
        "typical_building_type": "Single-family homes, prefab housing, new construction",
    },
    "steglitz-zehlendorf": {
        "population":            311_000,
        "avg_age":               46.6,      # highest avg age in Berlin (31.12.2025)
        "foreign_residents_pct": 15.0,
        "avg_apartment_size_m2": 82,
        "avg_rent_per_m2":       14.8,
        "dominant_household":    "Families, upper-income households",
        "typical_building_type": "Single-family homes, villas, upscale historic buildings",
    },
    "tempelhof-schöneberg": {
        "population":            355_000,
        "avg_age":               42.1,
        "foreign_residents_pct": 21.6,
        "avg_apartment_size_m2": 68,
        "avg_rent_per_m2":       15.5,
        "dominant_household":    "Singles, couples, diverse population",
        "typical_building_type": "Historic buildings, post-war construction",
    },
    "neukölln": {
        "population":            332_000,
        "avg_age":               38.5,
        "foreign_residents_pct": 33.0,      # Migrationshintergrund 52.2% (30.06.2025)
        "avg_apartment_size_m2": 62,
        "avg_rent_per_m2":       14.2,
        "dominant_household":    "Singles, families, diverse population",
        "typical_building_type": "Historic buildings, post-war construction",
    },
    "treptow-köpenick": {
        "population":            278_000,
        "avg_age":               46.5,
        "foreign_residents_pct": 16.9,      # lowest foreign % (30.06.2024)
        "avg_apartment_size_m2": 76,
        "avg_rent_per_m2":       13.0,
        "dominant_household":    "Families, older residents",
        "typical_building_type": "Single-family homes, prefab housing, new construction",
    },
    "marzahn-hellersdorf": {
        "population":            272_000,
        "avg_age":               45.0,
        "foreign_residents_pct": 14.5,      # foreign growth +6.3% in 2024
        "avg_apartment_size_m2": 65,
        "avg_rent_per_m2":       11.5,
        "dominant_household":    "Families, older residents",
        "typical_building_type": "Prefab housing (Plattenbau), new construction",
    },
    "lichtenberg": {
        "population":            293_000,
        "avg_age":               43.5,
        "foreign_residents_pct": 19.5,
        "avg_apartment_size_m2": 64,
        "avg_rent_per_m2":       12.8,
        "dominant_household":    "Families, singles",
        "typical_building_type": "Prefab housing, historic buildings, new construction",
    },
    "reinickendorf": {
        "population":            274_000,
        "avg_age":               44.8,
        "foreign_residents_pct": 23.8,      # biggest foreign growth 2024 (+10.3%)
        "avg_apartment_size_m2": 71,
        "avg_rent_per_m2":       13.2,
        "dominant_household":    "Families",
        "typical_building_type": "Single-family homes, new construction, prefab housing",
    },
}

# ── Name aliases ───────────────────────────────────────────────────────────────
# Maps various spellings / Ortsteil names → canonical district key above.

DISTRICT_ALIASES: dict[str, str] = {
    "mitte":                      "mitte",
    "friedrichshain":             "friedrichshain-kreuzberg",
    "kreuzberg":                  "friedrichshain-kreuzberg",
    "friedrichshain-kreuzberg":   "friedrichshain-kreuzberg",
    "pankow":                     "pankow",
    "prenzlauer berg":            "pankow",
    "weißensee":                  "pankow",
    "charlottenburg":             "charlottenburg-wilmersdorf",
    "wilmersdorf":                "charlottenburg-wilmersdorf",
    "charlottenburg-wilmersdorf": "charlottenburg-wilmersdorf",
    "spandau":                    "spandau",
    "steglitz":                   "steglitz-zehlendorf",
    "zehlendorf":                 "steglitz-zehlendorf",
    "steglitz-zehlendorf":        "steglitz-zehlendorf",
    "tempelhof":                  "tempelhof-schöneberg",
    "schöneberg":                 "tempelhof-schöneberg",
    "tempelhof-schöneberg":       "tempelhof-schöneberg",
    "neukölln":                   "neukölln",
    "treptow":                    "treptow-köpenick",
    "köpenick":                   "treptow-köpenick",
    "treptow-köpenick":           "treptow-köpenick",
    "marzahn":                    "marzahn-hellersdorf",
    "hellersdorf":                "marzahn-hellersdorf",
    "marzahn-hellersdorf":        "marzahn-hellersdorf",
    "lichtenberg":                "lichtenberg",
    "reinickendorf":              "reinickendorf",
}

# ── Metadata ───────────────────────────────────────────────────────────────────

DATA_SOURCE = (
    "Amt für Statistik Berlin-Brandenburg, Einwohnerregisterstatistik "
    "31.12.2024 / 30.06.2025 (CC-BY); "
    "IBB Wohnungsmarktbericht 2023; Guthmann Immobilien Berlin 2024"
)

DATA_REFERENCE_DATE = "31.12.2024"
