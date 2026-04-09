"""
data/construction_cost_data.py — Construction cost data for Berlin.

Edit this file to update figures when new statistics are published.

Sources:
  - BKI Baukosten Gebäude 2024 (Baukosten-Informationszentrum, Stuttgart)
    Kostenkennwerte KG 300+400, konventioneller Neubau, Nettobaukosten per m² BGF
  - Amt für Statistik Berlin-Brandenburg, M I 4 – vj (Januar 2026), CC BY 3.0 DE
  - Statistisches Bundesamt (Destatis), Pressemitteilung 09.01.2026
"""

DATA_SOURCE = "BKI Baukosten Gebäude 2024, angepasst auf Preisstand Berlin 2025"
DATA_REFERENCE_DATE = "2025 (Preisindex-Stand: November 2025)"


# ---------------------------------------------------------------------------
# Cost ranges per m² BGF (Bruttogrundfläche), net of VAT, Preisstand 2025
# To convert BGF → Wohnfläche (NF): multiply by ~1.25–1.35 (typically 1.30)
# ---------------------------------------------------------------------------

CONSTRUCTION_COSTS = {
    "einfamilienhaus": {
        "label": "Einfamilienhaus (freistehend)",
        "cost_min": 1900,
        "cost_max": 2800,
        "cost_avg": 2300,
        "unit": "m² BGF",
        "notes": (
            "Freistehend, konventioneller Neubau, einfache bis gehobene Ausstattung. "
            "Umrechnung auf Wohnfläche: Faktor ~1,30 (z.B. 2.300 €/m² BGF ≈ 3.000 €/m² WF)."
        ),
        "notes_en": (
            "Detached, conventional new build, basic to premium fit-out. "
            "To convert to living area (Wohnfläche): multiply by ~1.30 (e.g. €2,300/m² GFA ≈ €3,000/m² NFA)."
        ),
    },
    "doppelhaus_reihenhaus": {
        "label": "Doppelhaus / Reihenhaus",
        "cost_min": 1700,
        "cost_max": 2500,
        "cost_avg": 2100,
        "unit": "m² BGF",
        "notes": "Aneinandergebaut, inkl. Brandwand. Etwas günstiger als freistehendes EFH.",
        "notes_en": "Semi-detached or terraced house, incl. party wall. Slightly cheaper than detached.",
    },
    "mehrfamilienhaus_klein": {
        "label": "Mehrfamilienhaus (3–6 Wohneinheiten)",
        "cost_min": 1800,
        "cost_max": 2600,
        "cost_avg": 2200,
        "unit": "m² BGF",
        "notes": (
            "Kleines MFH, 2–4 Geschosse. Berliner Markt, konventioneller Bau. "
            "Entspricht ca. 2.900 €/m² Wohnfläche im Mittel."
        ),
        "notes_en": (
            "Small apartment building, 2–4 storeys, Berlin market, conventional construction. "
            "Approx. €2,900/m² net floor area on average."
        ),
    },
    "mehrfamilienhaus": {
        "label": "Mehrfamilienhaus (7–20 Wohneinheiten)",
        "cost_min": 1900,
        "cost_max": 2700,
        "cost_avg": 2300,
        "unit": "m² BGF",
        "notes": (
            "Typischer Berliner Neubau-Mietspiegel, 4–6 Geschosse, Blockrandbebauung. "
            "Entspricht ca. 3.000 €/m² Wohnfläche im Mittel."
        ),
        "notes_en": (
            "Typical Berlin new-build rental block, 4–6 storeys, perimeter block development. "
            "Approx. €3,000/m² net floor area on average."
        ),
    },
    "mehrfamilienhaus_gross": {
        "label": "Mehrfamilienhaus (>20 Wohneinheiten)",
        "cost_min": 2000,
        "cost_max": 2900,
        "cost_avg": 2400,
        "unit": "m² BGF",
        "notes": "Großes MFH oder Wohnanlage. Leichte Skaleneffekte bei Haustechnik.",
        "notes_en": "Large apartment building or residential complex. Slight economies of scale on building services.",
    },
    "buerogebaeude": {
        "label": "Bürogebäude",
        "cost_min": 1800,
        "cost_max": 3200,
        "cost_avg": 2400,
        "unit": "m² BGF",
        "notes": (
            "Einfaches Bürogebäude: ~1.800–2.300 €/m² BGF. "
            "Mittelwert inkl. moderner Haustechnik, 4–8 Geschosse. "
            "Gehobene Ausstattung bis 3.200 €/m² BGF."
        ),
        "notes_en": (
            "Basic office building: ~€1,800–2,300/m² GFA. "
            "Average includes modern building services, 4–8 storeys. "
            "Premium fit-out up to €3,200/m² GFA."
        ),
    },
    "gewerbe_halle": {
        "label": "Gewerbehalle / Lager (einfach)",
        "cost_min": 700,
        "cost_max": 1400,
        "cost_avg": 1000,
        "unit": "m² BGF",
        "notes": "Einfache Stahlhalle oder Massivbau, keine besonderen Anforderungen.",
        "notes_en": "Simple steel frame or masonry industrial hall, no special requirements.",
    },
    "gewerbe_mix": {
        "label": "Büro-Gewerbe-Mix",
        "cost_min": 1400,
        "cost_max": 2200,
        "cost_avg": 1800,
        "unit": "m² BGF",
        "notes": "Kombination aus Hallen- und Bürofläche, z.B. Handwerksbetrieb mit Büroteil.",
        "notes_en": "Mixed industrial and office space, e.g. a workshop with an attached office wing.",
    },
    "tiefgarage": {
        "label": "Tiefgarage (pro Stellplatz)",
        "cost_min": 20000,
        "cost_max": 35000,
        "cost_avg": 26000,
        "unit": "Stellplatz",
        "notes": (
            "Kosten je Stellplatz. Unteres Ende: 1 UG, gute Bodenverhältnisse. "
            "Oberes Ende: 2+ UG, Berliner Innenstadtlage, schwieriger Baugrund."
        ),
        "notes_en": (
            "Cost per parking space. Lower end: 1 basement level, good ground conditions. "
            "Upper end: 2+ levels, Berlin inner city, difficult subsoil."
        ),
    },
    "parkdeck": {
        "label": "Parkdeck (oberirdisch, pro Stellplatz)",
        "cost_min": 8000,
        "cost_max": 15000,
        "cost_avg": 11000,
        "unit": "Stellplatz",
        "notes": "Oberirdisches Parkdeck, Stahlbeton- oder Stahlbau.",
        "notes_en": "Above-ground parking deck, reinforced concrete or steel structure.",
    },
    "dachgeschossausbau": {
        "label": "Dachgeschossausbau",
        "cost_min": 1600,
        "cost_max": 3000,
        "cost_avg": 2200,
        "unit": "m² BGF",
        "notes": (
            "Ausbau zu Wohnraum inkl. Dämmung, Gauben, Treppe. "
            "Stark abhängig von Dachform und vorhandenem Zustand."
        ),
        "notes_en": (
            "Conversion to residential use incl. insulation, dormers, staircase. "
            "Highly dependent on roof shape and existing condition."
        ),
    },
    "sanierung_altbau": {
        "label": "Altbausanierung (Gründerzeit)",
        "cost_min": 1200,
        "cost_max": 3200,
        "cost_avg": 2000,
        "unit": "m² Wohnfläche",
        "notes": (
            "Berliner Gründerzeitaltbau (Baujahr ~1880–1930). "
            "Moderate Sanierung (Heizung, Bäder, Böden): ~1.200–1.800 €/m² WF. "
            "Umfassende Kernsanierung inkl. Fassade und Aufzug: ~2.400–3.200 €/m² WF."
        ),
        "notes_en": (
            "Berlin Gründerzeit old building (built ~1880–1930). "
            "Moderate refurbishment (heating, bathrooms, floors): ~€1,200–1,800/m² NFA. "
            "Full gut renovation incl. facade and lift: ~€2,400–3,200/m² NFA."
        ),
    },
}


# ---------------------------------------------------------------------------
# Location multipliers — Berlin districts
# innenstadt: Mitte, Prenzlauer Berg, Kreuzberg, Friedrichshain, Schöneberg
# stadtrand:  Spandau, Marzahn-Hellersdorf, Reinickendorf (outer areas)
# standard:   All other districts (default)
# ---------------------------------------------------------------------------

LOCATION_MULTIPLIERS = {
    "innenstadt": 1.10,
    "stadtrand":  0.95,
    "standard":   1.00,
}


# ---------------------------------------------------------------------------
# Official price index data
# Source: Amt für Statistik Berlin-Brandenburg, M I 4 – vj (Januar 2026)
#         Statistisches Bundesamt (Destatis), Pressemitteilung 09.01.2026
# Basis: Basisjahr 2021 = 100
# ---------------------------------------------------------------------------

PRICE_INDEX_DATA = {
    "berlin_wohngebaeude_2025": {
        "description": "Baupreisindex Wohngebäude Neubau, Berlin, 2025",
        "source": "Amt für Statistik Berlin-Brandenburg, M I 4 – vj (Januar 2026)",
        "quarterly_yoy": {
            "Februar 2025":  "+3,6 %",
            "Mai 2025":      "+4,0 %",
            "August 2025":   "+3,9 %",
            "November 2025": "+4,1 %",
        },
        "annual_average_2025": "+3,9 %",
        "vs_national": "Berlin liegt ca. 0,9 Prozentpunkte über dem Bundesdurchschnitt",
    },
    "national_wohngebaeude_2025": {
        "description": "Baupreisindex Wohngebäude Neubau, Deutschland gesamt, 2025",
        "source": "Statistisches Bundesamt (Destatis), Pressemitteilung 09.01.2026",
        "quarterly_yoy": {
            "Februar 2025":  "+3,2 %",
            "Mai 2025":      "+3,2 %",
            "August 2025":   "+3,1 %",
            "November 2025": "+3,2 %",
        },
        "annual_average_2025": "~3,2 %",
    },
    "national_buerogebaeude_nov2025": {
        "description": "Baupreisindex Bürogebäude Neubau, Deutschland, November 2025",
        "source": "Destatis, Pressemitteilung 09.01.2026",
        "yoy_change": "+3,5 %",
    },
    "national_gewerbe_nov2025": {
        "description": "Baupreisindex gewerbliche Betriebsgebäude, Deutschland, November 2025",
        "source": "Destatis, Pressemitteilung 09.01.2026",
        "yoy_change": "+3,3 %",
    },
    "berlin_rohbau_nov2025": {
        "description": "Rohbauarbeiten Wohngebäude, Berlin, November 2025",
        "source": "Amt für Statistik Berlin-Brandenburg, M I 4 – vj (Januar 2026)",
        "yoy_change": "+2,6 %",
        "breakdown": {
            "Betonarbeiten":               "+0,9 %",
            "Mauerarbeiten":               "+0,7 %",
            "Zimmer- und Holzbauarbeiten": "+7,2 %",
            "Dachdeckungsarbeiten":        "+5,5 %",
        },
    },
    "berlin_ausbau_nov2025": {
        "description": "Ausbauarbeiten Wohngebäude, Berlin, November 2025",
        "source": "Amt für Statistik Berlin-Brandenburg, M I 4 – vj (Januar 2026)",
        "yoy_change": "+5,1 %",
        "breakdown": {
            "Gas-/Wasser-/Entwässerungsanlagen (innerhalb Gebäude)": "+10,9 %",
            "Betonwerksteinarbeiten":                                 "+8,6 %",
            "Ramm-/Rüttel-/Pressarbeiten":                           "-0,9 %",
        },
    },
    "historical_national": {
        "description": "Historische Baupreissteigerungen Deutschland, Wohngebäude Neubau",
        "source": "Destatis, eigene Zusammenstellung",
        "annual_changes": {
            "2021": "+9,0 %",
            "2022": "+17,0 %",
            "2023": "+6,0 %",
            "2024": "+3,1 %",
            "2025": "+3,2 %",
        },
        "note": "Langfristiges Mittel (vor 2020): ca. 2 % pro Jahr",
    },
}