COMPONENT_STRINGS = {
	"en": {
		# General
		"sources_page":				"Page",
		"tool_input":				"Input",
		"tool_output":				"Output",
		"no_tools":					"No tools were called for this response.",
		"thinking":					"Thinking...",
		# Welcome
		"welcome_title": 			"🏗️ Berlin Building & Zoning Assistant",
"welcome_text": (
			"Ask me anything about Berlin's zoning regulations, building codes, "
			"and planning requirements. I can also calculate buildable areas, "
			"parking requirements, construction costs, and look up demographics "
			"for any Berlin address.\n\n"
			"**Try asking:**\n"
			"- *What are the zoning rules and demographics for Kurfürstendamm 90?*\n"
			"- *What are the setback regulations for a WA zone?*\n"
			"- *Estimate construction costs for a 4-storey apartment building at Eulerstraße 6.*\n"
			"- *How many accessible car parking spaces are required for an office building under BauO Bln?*\n"
			"- *How many bike parking spaces are required for a new apartment building at Schwedter Straße 13, 10119?*"
		),
		# Parcel fields
		"parcel_area":				"Official Area",
		"parcel_id":				"Object ID",
		"parcel_aaa":				"AAA Description",
		"parcel_fsko":				"Parcel ID (full)",
		"parcel_zae":				"Parcel No. (numerator)",
		"parcel_nen":				"Parcel No. (denominator)",
		"parcel_gmk":				"Gemarkung key",
		"parcel_gemarkung":			"Gemarkung name",
		"parcel_flur":				"Flur number",
		"parcel_gdz":				"Municipality key",
		"parcel_gemeinde":			"Municipality",
		"parcel_created":			"Date of origin",
		"parcel_dst":				"Responsible authority",
		"parcel_beg":				"Lifetime interval (start)",
		"parcel_source":			"Source",
		# Tabs & expander
		"expander_label":			"🔍 Analysis",
		"tab_parcel":				"📍 Parcel Info",
		"tab_report":				"📐 Report",
		"tab_sources":				"📚 Sources",
		"tab_debug":				"🔧 Debug",
		"no_sources":				"No knowledge base sources matched this query.",
		"no_parcel":				"Parcel data not available for this address.",
		# Input validation & rate limiting
		"input_too_short":			"Message too short — please enter at least {min} characters.",
		"input_too_long":			"Message too long ({length}/{max} characters). Please shorten your input.",
		"rate_limit_exceeded":		"Rate limit reached ({limit} requests per {window}s). Please wait {wait}s before sending another message.",
		# RAG process tab
		"tab_rag":					"🔍 RAG Process",
		"rag_query":				"Query sent to vector store",
		"rag_retrieved":			"Retrieved chunks",
		"rag_context_size":			"Context injected",
		"rag_tokens_approx":		"≈ {tokens} tokens",
		"rag_score_label":			"Relevance score",
		"rag_score_note":			"Lower score = more similar (L2 distance). Scores below 0.8 are strong matches.",
		"rag_no_chunks":			"No chunks were retrieved for this query.",
		# Buildable area card
		"ba_title":					"#### 📐 Buildable Area",
		"ba_plot_area":				"Plot area",
		"ba_footprint":				"Max footprint (GRZ)",
		"ba_floor_area":			"Max floor area (GFZ)",
		"ba_floors":				"Typical floors",
		"ba_basement":				"Max basement",
		"ba_zone":					"Zone type",
		"ba_calc":					"Calculation",
		"ba_footprint_label":		"footprint",
		"ba_total_label":			"total floor area",
		# Parking card
		"park_title":				"#### 🚲 Parking Requirements",
		"park_units":				"Estimated units",
		"park_bike":				"Bike spaces",
		"park_cargo":				"Cargo bike spaces",
		"park_accessible":			"Accessible car spaces",
		"park_accessible_help":		"Mandatory spaces for disabled users (AV Stellplätze 2021, Anlage 1)",
		"park_step1":				"**Step 1 — Estimate units from floor area:**",
		"park_step1_note":			"⚠️ Standard assumption: **{size} m² per unit**. Ask to recalculate with a different unit size (e.g. 'use 65m² per unit').",
		"park_step2":				"**Step 2 — Apply bike parking ratios (AV Stellplätze 2021):**",
		"park_source":				"Source",
		"park_no_car_min":			"ℹ️ Berlin abolished the general car parking minimum (Stellplatzpflicht) in 2021 (§49 BauO Bln). No minimum number of general car spaces is legally required.",
		"park_regulation":			"Regulation",
		# Construction cost card
		"cost_title":				"#### 🏗️ Construction Cost Estimate",
		"cost_avg":					"Average",
		"cost_btype":				"Building type",
		"cost_area":				"Area",
		"cost_location":			"Location factor",
		"cost_rate":				"Rate",
		"cost_source":				"📊 **Data source:**",
		"cost_index":				"📈 **Price index:**",
		"cost_default_source":		"BKI Baukosten 2024, Berlin market",
		"cost_default_disclaimer":	"Estimate only. Excludes land and planning fees.",
		# Demographics card
		"demo_title":				"#### 👥 District Demographics",
		"demo_population":			"Population",
		"demo_age":					"Avg age",
		"demo_foreign":				"Foreign residents",
		"demo_apt_size":			"Avg apt size",
		"demo_rent":				"Avg rent",
		"demo_household":			"Dominant household",
		"demo_source":				"*Source: {src}, reference date: {ref}*",
	},
	"de": {
		# General
		"sources_page":				"Seite",
		"tool_input":				"Eingabe",
		"tool_output":				"Ergebnis",
		"no_tools":					"Für diese Antwort wurden keine Werkzeuge aufgerufen.",
		"thinking":					"Wird berechnet...",
		# Welcome
		"welcome_title":			"🏗️ Berliner Bebauungs- und Zonenassistent",
		"welcome_text": (
			"Stellen Sie mir Fragen zu Berliner Bebauungsplänen, Bauordnungen "
			"und Planungsanforderungen. Ich kann auch bebaubare Flächen, "
			"Stellplatzbedarfe, Baukosten berechnen und demografische Daten "
			"für jede Berliner Adresse abrufen.\n\n"
			"**Beispielanfragen:**\n"
			"- *Welche Bebauungsregeln und Demografiedaten gibt es für den Kurfürstendamm 90?*\n"
			"- *Welche Abstandsregeln gelten in einem WA-Gebiet?*\n"
			"- *Baukosten schätzen für ein 4-geschossiges Wohngebäude in der Eulerstraße 6.*\n"
			"- *Wie viele barrierefreie Kfz-Stellplätze sind für ein Bürogebäude nach BauO Bln erforderlich?*\n"
			"- *Wie viele Fahrradstellplätze sind für ein neues Wohngebäude in der Schwedter Straße 13, 10119 erforderlich?*"
		),
		# Parcel fields
		"parcel_area":				"Amtliche Fläche (m²)",
		"parcel_id":				"Objekt-Identifikator",
		"parcel_aaa":				"AAA-Beschreibung",
		"parcel_fsko":				"Flurstückskennzeichen",
		"parcel_zae":				"Flurstückskennzeichen (Zähler)",
		"parcel_nen":				"Flurstückskennzeichen (Nenner)",
		"parcel_gmk":				"Gemarkungsschlüssel",
		"parcel_gemarkung":			"Gemarkungsname",
		"parcel_flur":				"Flurnummer",
		"parcel_gdz":				"Gemeindekennzeichen",
		"parcel_gemeinde":			"Gemeindename",
		"parcel_created":			"Zeitpunkt der Entstehung",
		"parcel_dst":				"Zuständige Stelle",
		"parcel_beg":				"Lebenszeitintervall (Beginn)",
		"parcel_source":			"Quelle",
		# Tabs & expander
		"expander_label":			"🔍 Analyse",
		"tab_parcel":				"📍 Flurstück",
		"tab_report":				"📐 Bericht",
		"tab_sources":				"📚 Quellen",
		"tab_debug":				"🔧 Debug",
		"no_sources":				"Keine Quellen aus der Wissensdatenbank gefunden.",
		"no_parcel":				"Keine Flurstücksdaten für diese Adresse verfügbar.",
		# Input validation & rate limiting
		"input_too_short":			"Nachricht zu kurz — bitte mindestens {min} Zeichen eingeben.",
		"input_too_long":			"Nachricht zu lang ({length}/{max} Zeichen). Bitte kürzen Sie Ihre Eingabe.",
		"rate_limit_exceeded":		"Anfragelimit erreicht ({limit} Anfragen pro {window}s). Bitte warten Sie {wait}s.",
		# RAG process tab
		"tab_rag":					"🔍 RAG-Prozess",
		"rag_query":				"Anfrage an den Vektorspeicher",
		"rag_retrieved":			"Abgerufene Chunks",
		"rag_context_size":			"Injizierter Kontext",
		"rag_tokens_approx":		"≈ {tokens} Tokens",
		"rag_score_label":			"Relevanzbewertung",
		"rag_score_note":			"Niedrigerer Wert = ähnlicher (L2-Distanz). Werte unter 0,8 sind starke Treffer.",
		"rag_no_chunks":			"Für diese Anfrage wurden keine Chunks abgerufen.",
		# Buildable area card
		"ba_title":					"#### 📐 Bebaubare Fläche",
		"ba_plot_area":				"Grundstücksfläche",
		"ba_footprint":				"Max. Grundfläche (GRZ)",
		"ba_floor_area":			"Max. Geschossfläche (GFZ)",
		"ba_floors":				"Typische Geschosse",
		"ba_basement":				"Max. Kellergeschoss",
		"ba_zone":					"Gebietstyp",
		"ba_calc":					"Berechnung",
		"ba_footprint_label":		"Grundfläche",
		"ba_total_label":			"Gesamtgeschossfläche",
		# Parking card
		"park_title":				"#### 🚲 Stellplatzberechnung",
		"park_units":				"Geschätzte Einheiten",
		"park_bike":				"Fahrradabstellplätze",
		"park_cargo":				"Sonderfahrradstellplätze",
		"park_accessible":			"Barrierefreie Kfz-Stellplätze",
		"park_accessible_help":		"Pflichtstellplätze für Menschen mit Behinderung (AV Stellplätze 2021, Anlage 1)",
		"park_step1":				"**Schritt 1 — Wohneinheiten aus Geschossfläche:**",
		"park_step1_note":			"⚠️ Standardannahme: **{size} m² pro Einheit**. Neuberechnung mit anderer Einheitsgröße auf Anfrage.",
		"park_step2":				"**Schritt 2 — Fahrradstellplatzquoten anwenden (AV Stellplätze 2021):**",
		"park_source":				"Quelle",
		"park_no_car_min":			"ℹ️ Berlin hat die allgemeine Kfz-Stellplatzpflicht 2021 abgeschafft (§49 BauO Bln). Es gibt keine gesetzliche Mindestanzahl an allgemeinen Kfz-Stellplätzen.",
		"park_regulation":			"Vorschrift",
		# Construction cost card
		"cost_title":				"#### 🏗️ Baukostenschätzung",
		"cost_avg":					"Durchschnitt",
		"cost_btype":				"Gebäudetyp",
		"cost_area":				"Fläche",
		"cost_location":			"Lagefaktor",
		"cost_rate":				"Ansatz",
		"cost_source":				"📊 **Datenquelle:**",
		"cost_index":				"📈 **Preisindex:**",
		"cost_default_source":		"BKI Baukosten 2024, Berliner Markt",
		"cost_default_disclaimer":	"Nur Schätzwert. Ohne Grundstück und Planungskosten.",
		# Demographics card
		"demo_title":				"#### 👥 Bezirksdemografie",
		"demo_population":			"Bevölkerung",
		"demo_age":					"Ø Alter",
		"demo_foreign":				"Ausländeranteil",
		"demo_apt_size":			"Ø Wohnfläche",
		"demo_rent":				"Ø Miete",
		"demo_household":			"Haushaltstyp",
		"demo_source":				"*Quelle: {src}, Stichtag: {ref}*",
	},
}

SIDEBAR_STRINGS = {
	"en": {
		"settings_header":			"⚙️ Settings",
		"language_label":			"Language",
		"model_label":				"AI Model",
		"cost_header":				"💰 Session Cost",
		"tokens_input":				"Input tokens",
		"tokens_output":			"Output tokens",
		"tokens_total":				"Total tokens",
		"cost_label":				"Estimated cost",
		"cost_reset":				"Reset counter",
		"about_header":				"ℹ️ About",
		"about_text": (
			"This tool helps architects, developers, and property owners "
			"navigate Berlin's zoning regulations and building codes.\n\n"
			"**Regulatory sources:**\n"
			"- BauNVO (Baunutzungsverordnung, July 2023)\n"
			"- BauO Bln (Berliner Bauordnung, post-7th amendment, January 2026)\n"
			"- AV Stellplätze (16. Juni 2021, ABl. S. 2326) — mandatory bicycle parking\n"
			"  and accessible car spaces per §49 BauO Bln (valid until 30.06.2026)\n\n"
			"**Geodata & cadastre:**\n"
			"- GDI Berlin WFS API — B-Plan, FNP 2025\n"
			"- ALKIS (Amtliches Liegenschaftskatasterinformationssystem)\n"
			"- Adressen Berlin WFS (GDI Berlin) — official Hauskoordinaten\n"
			"- Nominatim / OpenStreetMap (geocoding, address parsing)\n\n"
			"**Construction costs & statistics:**\n"
			"- Construction cost ranges based on BKI Baukosten Gebäude 2024 (reference values)\n"
			"- Amt für Statistik Berlin-Brandenburg (price index, Jan 2026)\n"
			"- Destatis / Statistisches Bundesamt (national index)\n\n"
			"⚠️ For informational purposes only. Always verify with official authorities."
		),
		"clear_chat":				"🗑️ Clear chat",
	},
	"de": {
		"settings_header":			"⚙️ Einstellungen",
		"language_label":			"Sprache",
		"model_label":				"KI-Modell",
		"cost_header":				"💰 Sitzungskosten",
		"tokens_input":				"Eingabe-Tokens",
		"tokens_output":			"Ausgabe-Tokens",
		"tokens_total":				"Tokens gesamt",
		"cost_label":				"Geschätzte Kosten",
		"cost_reset":				"Zurücksetzen",
		"about_header":				"ℹ️ Über",
		"about_text": (
			"Dieses Tool hilft Architekten, Entwicklern und Eigentümern, "
			"die Berliner Bebauungsvorschriften und Bauordnung zu verstehen.\n\n"
			"**Rechtsquellen:**\n"
			"- BauNVO (Baunutzungsverordnung, Juli 2023)\n"
			"- BauO Bln (Berliner Bauordnung, nach 7. Änderung, Januar 2026)\n"
			"- AV Stellplätze (16. Juni 2021, ABl. S. 2326) — Pflicht-Fahrradabstellplätze\n"
			"  und barrierefreie Kfz-Stellplätze gem. §49 BauO Bln (gültig bis 30.06.2026)\n\n"
			"**Geodaten & Kataster:**\n"
			"- GDI Berlin WFS API — B-Plan, FNP 2025\n"
			"- ALKIS (Amtliches Liegenschaftskatasterinformationssystem)\n"
			"- Adressen Berlin WFS (GDI Berlin) — amtliche Hauskoordinaten\n"
			"- Nominatim / OpenStreetMap (Geokodierung, Adressanalyse)\n\n"
			"**Baukosten & Statistik:**\n"
			"- Baukostenkennwerte auf Basis BKI Baukosten Gebäude 2024 (Richtwerte)\n"
			"- Amt für Statistik Berlin-Brandenburg (Preisindex, Jan 2026)\n"
			"- Destatis / Statistisches Bundesamt (Bundesindex)\n\n"
			"⚠️ Nur zur Information. Immer mit den zuständigen Behörden prüfen."
		),
		"clear_chat":				"🗑️ Chat leeren",
	},
}

RETRIEVER_STRINGS = {
	"en": {
		"no_results":   "No relevant documents found.",
		"unknown_src":  "Unknown source",
		"page_label":   "Page",
		"source_label": "Source",
	},
	"de": {
		"no_results":   "Keine relevanten Dokumente gefunden.",
		"unknown_src":  "Unbekannte Quelle",
		"page_label":   "Seite",
		"source_label": "Quelle",
	},
}

TOOL_ERROR_STRINGS = {
	"en": {
		"unknown_zone_type":              "Unknown zone type '{zone_type}'. Available types: {available}",
		"invalid_plot_area":              "Plot area must be greater than 0 m².",
		"unknown_use_type":               "Unknown use type '{use_type}'. Available types: {available}",
		"invalid_quantity":               "Quantity must be greater than 0.",
		"unknown_building_type":          "Unknown building type '{building_type}'. Available types: {available}",
		"invalid_area":                   "Area must be greater than 0 m².",
		"unknown_price_index_category":   "Unknown category '{category}'. Available categories: {available}",
	},
	"de": {
		"unknown_zone_type":              "Unbekannter Gebietstyp '{zone_type}'. Verfügbare Typen: {available}",
		"invalid_plot_area":              "Grundstücksfläche muss größer als 0 m² sein.",
		"unknown_use_type":               "Unbekannte Nutzungsart '{use_type}'. Verfügbare Typen: {available}",
		"invalid_quantity":               "Mengenangabe muss größer als 0 sein.",
		"unknown_building_type":          "Unbekannter Gebäudetyp '{building_type}'. Verfügbare Typen: {available}",
		"invalid_area":                   "Fläche muss größer als 0 m² sein.",
		"unknown_price_index_category":   "Unbekannte Kategorie '{category}'. Verfügbare Kategorien: {available}",
	},
}