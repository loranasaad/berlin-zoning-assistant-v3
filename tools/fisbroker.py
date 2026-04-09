"""
Berlin zoning lookup via the Geoportal Berlin GDI WFS API.
Replaces the defunct FIS-Broker (fbinter.stadt-berlin.de, shut down Dec 2025).

Endpoints used:
  B-Plan:  https://gdi.berlin.de/services/wfs/bplan
  FNP:     https://gdi.berlin.de/services/wfs/fnp_2025
  ALKIS:   https://gdi.berlin.de/services/wfs/alkis_flurstuecke

Zone detection strategy:
  1. Query B-Plan inhalt field → extract BauNVO code directly (most precise)
  2. Query FNP nutzungsart field → map to approximate BauNVO code (fallback)
  3. Neither found → ask user for manual input

Plot area strategy:
  1. Parse street, house number, PLZ, district from Photon
  2. Query adressen_berlin WFS with str_name + hnr + plz → official Hauskoordinate
  3. Fallback: str_name + hnr + bez_name (handles PLZ mismatches)
  4. Fallback: str_name + hnr only (single result accepted)
  5. CONTAINS query on ALKIS parcel layer using the returned coordinate

CRS: EPSG:25833 (required by all GDI Berlin servers)
"""

import logging
import math
import requests
import re
from geopy.geocoders import Photon
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from data.zoning_rules import ZONE_KEYWORDS, FNP_ZONE_MAP

logger = logging.getLogger(__name__)


# Endpoints
BPLAN_WFS_URL  = "https://gdi.berlin.de/services/wfs/bplan"
BPLAN_TYPENAME = "bplan:b_bp_fs"

FNP_WFS_URL    = "https://gdi.berlin.de/services/wfs/fnp_2025"
FNP_TYPENAME   = "fnp_2025:fnp_2025_vektor"

ALKIS_WFS_URL    = "https://gdi.berlin.de/services/wfs/alkis_flurstuecke"
ALKIS_TYPENAME   = "alkis_flurstuecke:flurstuecke"

ADR_WFS_URL      = "https://gdi.berlin.de/services/wfs/adressen_berlin"
ADR_TYPENAME     = "adressen_berlin:adressen_berlin"


SEARCH_RADIUS_M = 50  # metres, used for B-Plan and FNP BBOX queries

def _parse_all_zones_from_inhalt(inhalt: str | None) -> list[str]:
	if not inhalt:
		return []
	text = inhalt.lower()
	return [code for keyword, code in ZONE_KEYWORDS if keyword in text]


def _parse_zone_from_fnp(nutzungsart: str | None) -> tuple[str, str] | None:
	"""Returns (BauNVO code, nutzungsart label) or None."""
	if not nutzungsart:
		return None
	text = nutzungsart.lower()
	for keyword, code, _ in FNP_ZONE_MAP:
		if keyword in text:
			return code, nutzungsart
	return None


# Coordinate conversion: WGS84 → EPSG:25833
def _wgs84_to_epsg25833(lat: float, lon: float) -> tuple[float, float]:
	try:
		from pyproj import Transformer
		t = Transformer.from_crs("EPSG:4326", "EPSG:25833", always_xy=True)
		return t.transform(lon, lat)
	except ImportError:
		pass

	a    = 6378137.0
	f    = 1 / 298.257222101
	e2   = 2 * f - f * f
	k0   = 0.9996
	lon0 = math.radians(15.0)
	lat_r, lon_r = math.radians(lat), math.radians(lon)
	N  = a / math.sqrt(1 - e2 * math.sin(lat_r) ** 2)
	T  = math.tan(lat_r) ** 2
	C  = e2 / (1 - e2) * math.cos(lat_r) ** 2
	A  = (lon_r - lon0) * math.cos(lat_r)
	e4, e6 = e2*e2, e2*e2*e2
	M = a * (
		(1 - e2/4 - 3*e4/64 - 5*e6/256) * lat_r
		- (3*e2/8 + 3*e4/32 + 45*e6/1024) * math.sin(2*lat_r)
		+ (15*e4/256 + 45*e6/1024) * math.sin(4*lat_r)
		- (35*e6/3072) * math.sin(6*lat_r)
	)
	easting = k0 * N * (
		A + (1 - T + C) * A**3/6
		+ (5 - 18*T + T*T + 72*C - 58*(e2/(1-e2))) * A**5/120
	) + 500000.0
	northing = k0 * (
		M + N * math.tan(lat_r) * (
			A**2/2
			+ (5 - T + 9*C + 4*C*C) * A**4/24
			+ (61 - 58*T + T*T + 600*C - 330*(e2/(1-e2))) * A**6/720
		)
	)
	return easting, northing


# Geocoding
def _geocode(address: str) -> dict:
	"""
	Geocode a Berlin address via Photon (OpenStreetMap).

	Ambiguity detection — runs when the user did NOT include a postcode:
	  Photon is asked for up to 5 candidate results. If multiple type="house"
	  hits are returned for the same street + house number but with different
	  postcodes, the address is ambiguous (street exists in several districts).
	  In that case we return immediately with an "ambiguous" signal so the
	  caller can ask the user to supply a postcode before doing any WFS work.

	  This is more reliable than the downstream ALKIS ambiguity check because
	  Photon/OSM has comprehensive Berlin address coverage, whereas the ALKIS
	  WFS may store duplicate streets under different spelling variants (ß vs ss)
	  that cause the CQL filter to miss one of the entries.
	"""
	geolocator = Photon(user_agent="berlin_zoning_assistant_v2")
	try:
		user_provided_plz = bool(re.search(r"\b\d{5}\b", address))

		# Fetch up to 5 candidates so we can detect same-name streets in
		# different districts. exactly_one=False is required; limit is a
		# Photon-specific kwarg passed through geopy.
		results = geolocator.geocode(
			address + ", Berlin, Germany",
			exactly_one=False,
			timeout=10,
			limit=5,
		) or []

		if not results:
			return {"error": f"Address not found: '{address}'. Please check the address and try again."}

		# Filter to precise house-level hits only.
		house_hits = [r for r in results if r.raw.get("properties", {}).get("type") == "house"]

		# Sort: prefer results with a clean housenumber (e.g. "5", "5a") over
		# ranges (e.g. "5-7") or missing numbers. Named POIs like "Dermazentrum
		# Berlin" can match type="house" but have range housenumbers that break
		# downstream parsing — they should never be the top pick.
		def _hnr_score(r):
			hn = str(r.raw.get("properties", {}).get("housenumber", ""))
			return 0 if re.match(r"^\d+[a-zA-Z]?$", hn) else 1
		house_hits.sort(key=_hnr_score)

		if not house_hits:
			# Photon returned results but none at house level — likely a street
			# name spelling issue (space in name, wrong umlaut, etc.).
			return {
				"error": (
					f"Could not find a precise match for '{address}'. "
					"Please check the street name spelling — avoid spaces within "
					"the name (e.g. use 'Eulerstraße 12' or 'Eulerstrasse 12', "
					"not 'Euler strasse 12')."
				)
			}

		# --- Ambiguity check (only when the user did not supply a postcode) ---
		if not user_provided_plz and len(house_hits) > 1:
			# Group by (street_name, house_number) — normalise ß↔ss so
			# "Bergmannstraße" and "Bergmannstrasse" are treated as the same street.
			def _norm(s: str) -> str:
				return s.lower().replace("ß", "ss")

			# Collect unique postcodes for candidates that share the same
			# normalised street + house number as the top hit.
			top_props  = house_hits[0].raw.get("properties", {})
			top_street = _norm(top_props.get("street", ""))
			top_hnr    = str(top_props.get("housenumber", ""))

			matching = [
				r for r in house_hits
				if _norm(r.raw.get("properties", {}).get("street", "")) == top_street
				and str(r.raw.get("properties", {}).get("housenumber", "")) == top_hnr
			]

			unique_plz = sorted({
				r.raw.get("properties", {}).get("postcode", "")
				for r in matching
				if r.raw.get("properties", {}).get("postcode", "")
			})

			if len(unique_plz) > 1:
				# Multiple distinct postcodes → genuinely ambiguous street.
				street_display = top_props.get("street", address)
				hnr_display    = top_hnr
				candidates = [
					{
						"plz":      r.raw["properties"].get("postcode", ""),
						"district": r.raw["properties"].get("district", ""),
						"display":  (
							f"{r.raw['properties'].get('housenumber','')} "
							f"{r.raw['properties'].get('street','')}, "
							f"{r.raw['properties'].get('postcode','')} Berlin"
						).strip(),
						"lat": r.latitude,
						"lon": r.longitude,
						"raw": r.raw,
					}
					for r in matching
				]
				logger.warning(
					f"Geocode ambiguity: '{street_display} {hnr_display}' "
					f"found in postcodes {unique_plz}"
				)
				return {
					"ambiguous":  True,
					"street":     street_display,
					"hnr":        hnr_display,
					"plz_list":   unique_plz,
					"candidates": candidates,
				}
		# --- End ambiguity check ---

		# Single unambiguous result — use the top hit.
		loc   = house_hits[0]
		props = loc.raw.get("properties", {})
		housenumber  = props.get("housenumber", "")
		street       = props.get("street", "")
		postcode     = props.get("postcode", "")
		display_name = f"{housenumber} {street}, {postcode} Berlin".strip(", ")

		return {
			"lat":          loc.latitude,
			"lon":          loc.longitude,
			"display_name": display_name,
			"raw":          loc.raw,
		}
	except GeocoderTimedOut:
		logger.warning(f"Geocoding timed out for address: {address}")
		return {"error": "Geocoding service timed out. Please try again."}
	except GeocoderUnavailable:
		logger.error("Geocoding service unavailable")
		return {"error": "Geocoding service is currently unavailable. Please try again later."}
	except Exception as e:
		logger.error(f"Geocoding error for '{address}': {e}")
		return {"error": f"Geocoding error: {str(e)}"}




# Address parsing helpers
def _parse_address_components(raw: dict) -> dict:
	props = raw.get("properties", {})
	housenumber = props.get("housenumber", "")
	# Photon housenumber may be "12" or "12a" — split numeric and suffix
	m = re.match(r"^(\d+)([a-zA-Z]?)$", str(housenumber))
	hnr        = int(m.group(1)) if m else None
	hnr_zusatz = m.group(2) or None if m else None

	# Photon district field contains Ortsteil (e.g. "Gesundbrunnen"), not Bezirk.
	# We check against known Bezirke so bez_name is only set when it matches.
	BEZIRKE = {
		"mitte", "friedrichshain-kreuzberg", "pankow", "charlottenburg-wilmersdorf",
		"spandau", "steglitz-zehlendorf", "tempelhof-schöneberg", "neukölln",
		"treptow-köpenick", "marzahn-hellersdorf", "lichtenberg", "reinickendorf",
	}
	district = props.get("district", "")
	bez_name = district if district.lower() in BEZIRKE else None

	return {
		"street":     props.get("street"),
		"hnr":        hnr,
		"hnr_zusatz": hnr_zusatz,
		"plz":        props.get("postcode"),
		"bez_name":   bez_name,
	}

# Official address point lookup
def _lookup_hauskoordinate(raw: dict, original_address: str = "") -> tuple[float, float] | None:
	"""
	Look up the official Hauskoordinate for an address using the GDI Berlin
	adressen_berlin WFS. These coordinates are placed by the surveying offices
	directly on the plot — not interpolated on the street.

	Lookup chain:
	  0. Upfront ambiguity check — if no PLZ in original query and street+hnr
		 returns multiple results, return ambiguous error with postcode hints.
	  1. str_name + hnr + plz — primary strategy (Photon always supplies PLZ).
		 Fallback 2: if nothing found, retry with ß↔ss normalized street name.
	  2. str_name + plz only (no hnr) — accepts if exactly one result.
		 Covers new buildings or recently renumbered plots not yet in ALKIS.

	Returns (lon, lat) in WGS84, {"ambiguous": True, ...} dict, or None.
	"""
	parsed = _parse_address_components(raw)
	street = parsed["street"]
	hnr    = parsed["hnr"]

	if not street or hnr is None:
		logger.warning(f"Could not extract street/hnr from Photon raw: {raw.get('properties', {})}")
		return None

	def _adr_query(cql: str) -> list:
		params = {
			"SERVICE":      "WFS",
			"VERSION":      "2.0.0",
			"REQUEST":      "GetFeature",
			"TYPENAMES":    ADR_TYPENAME,
			"CQL_FILTER":   cql,
			"SRSNAME":      "EPSG:4326",
			"outputFormat": "application/json",
			"count":        "3",
		}
		try:
			resp = requests.get(ADR_WFS_URL, params=params, timeout=15)
			resp.raise_for_status()
			return resp.json().get("features", [])
		except Exception as ex:
			logger.warning(f"adressen_berlin query failed: {ex}")
			return []

	base_cql = f"str_name = '{street}' AND hnr = {hnr}"
	if parsed["hnr_zusatz"]:
		base_cql += f" AND hnr_zusatz = '{parsed['hnr_zusatz']}'"

	# Ambiguity check.
	# Photon always supplies a PLZ (the one it picked), so without this check
	# Strategy 1 would silently resolve to the wrong address when the street
	# exists in multiple Berlin districts (e.g. Bergmannstraße 5).
	# We only run this when the user did NOT provide a PLZ in their original query.
	user_provided_plz = bool(re.search(r"\b\d{5}\b", original_address))
	if not user_provided_plz:
		# Query with normalized street name (ß↔ss) so ambiguity is detected regardless of which spelling the user typed.
		street_alt = (
			street.replace("ß", "ss") if "ß" in street
			else street.replace("ss", "ß") if "ss" in street.lower()
			else None
		)
		base_cql_alt = (
			f"str_name = '{street_alt}' AND hnr = {hnr}" if street_alt else None
		)
		all_features = _adr_query(base_cql)
		if street_alt and base_cql_alt:
			alt_features = _adr_query(base_cql_alt)
			# Combine results from both spellings, deduplicate by feature id
			existing_ids = {f.get("id") for f in all_features}
			all_features += [f for f in alt_features if f.get("id") not in existing_ids]

		if len(all_features) == 1:
			# Exactly one ALKIS record for this street+hnr — use it directly.
			# We do NOT need Photon's PLZ here: there is no ambiguity, and
			# Photon may have picked the wrong PLZ (e.g. for a street that exists
			# in one ALKIS district but was geocoded to a different one).
			coords = all_features[0]["geometry"]["coordinates"]
			logger.info(f"Hauskoordinate found via no-PLZ single-result: {coords}")
			return coords[0], coords[1]

		elif len(all_features) > 1:
			unique_plz = {f["properties"].get("plz", "") for f in all_features}
			unique_bez = {f["properties"].get("bez_name", "") for f in all_features}
			# Only flag as ambiguous if results span multiple districts
			# or multiple postcodes. Multiple results within the same PLZ+district
			# are just house number variants (e.g. 91, 91A, 91B) — not a true
			# ambiguity, so we fall through to Strategy 1 as normal.
			if len(unique_plz) > 1 or len(unique_bez) > 1:
				districts = list(unique_bez)
				plz_list  = list(unique_plz)
				logger.warning(f"Upfront ambiguity: '{street} {hnr}' in {districts}")
				return {
					"ambiguous": True,
					"districts": districts,
					"plz_list":  plz_list,
					"street":    street,
					"hnr":       hnr,
				}
			logger.info(f"Multiple results for '{street} {hnr}' but same PLZ/district — house number variants, proceeding normally")

	# Strategy 1: street + hnr + plz (Photon always provides plz)
	if parsed["plz"]:
		features = _adr_query(f"{base_cql} AND plz = '{parsed['plz']}'")
		if len(features) == 1:
			coords = features[0]["geometry"]["coordinates"]
			logger.info(f"Hauskoordinate found via PLZ: {coords}")
			return coords[0], coords[1]

		# Fallback 2 — normalize ß ↔ ss and retry.
		# Photon normalises to ß (e.g. "Eulerstraße") but ALKIS may store
		# "Eulerstrasse" or vice versa, causing the CQL filter to return nothing.
		street_alt = (
			street.replace("ß", "ss") if "ß" in street
			else street.replace("ss", "ß") if "ss" in street.lower()
			else None
		)
		if street_alt and street_alt != street:
			base_cql_alt = f"str_name = '{street_alt}' AND hnr = {hnr}"
			if parsed["hnr_zusatz"]:
				base_cql_alt += f" AND hnr_zusatz = '{parsed['hnr_zusatz']}'"
			features = _adr_query(f"{base_cql_alt} AND plz = '{parsed['plz']}'")
			if len(features) == 1:
				coords = features[0]["geometry"]["coordinates"]
				logger.info(f"Hauskoordinate found via PLZ + normalized street name (ß↔ss): {coords}")
				return coords[0], coords[1]

	# Fallback 1 — street + plz only (no house number).
	# Useful when the house number is not yet registered in ALKIS
	# (new buildings, recently renumbered plots, etc.).
	# Only accepted if exactly one result is returned — avoids guessing.
	if parsed["plz"]:
		features = _adr_query(f"str_name = '{street}' AND plz = '{parsed['plz']}'")
		if len(features) == 1:
			coords = features[0]["geometry"]["coordinates"]
			logger.info(f"Hauskoordinate found via street + PLZ only (no hnr): {coords}")
			return coords[0], coords[1]

	logger.info(f"No Hauskoordinate found for '{street} {hnr}'")
	return None


# Parcel area lookup
def _query_plot_area_at_point(cx: float, cy: float) -> dict | None:
	"""CONTAINS query on ALKIS parcel layer at a given EPSG:25833 point."""
	params = {
		"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
		"TYPENAMES": ALKIS_TYPENAME,
		"CQL_FILTER": f"CONTAINS(geom, POINT({cx:.3f} {cy:.3f}))",
		"SRSNAME": "EPSG:25833",
		"outputFormat": "application/json",
		"count": "1",
	}
	try:
		resp = requests.get(ALKIS_WFS_URL, params=params, timeout=15)
		resp.raise_for_status()
		features = resp.json().get("features", [])
		if features:
			return features[0]["properties"]
	except Exception as e:
		logger.warning(f"ALKIS CONTAINS query failed: {e}")
	return None


def _query_plot_area(raw: dict, original_address: str = "") -> dict | None | dict:
	"""
	Look up the ALKIS parcel for an address using the official Hauskoordinate.

	Queries the adressen_berlin WFS for the official address point (placed by
	the surveying office on the plot), then runs a CONTAINS query on the ALKIS
	parcel layer. This is reliable for all plot types including empty land.

	Returns:
	  - ALKIS properties dict on success
	  - {"ambiguous": True, ...} if street exists in multiple districts
	  - None if address not found
	"""
	hko = _lookup_hauskoordinate(raw, original_address)
	if not hko:
		return None
	if isinstance(hko, dict):
		return hko  # ambiguous signal — pass through to caller

	lon, lat = hko
	easting, northing = _wgs84_to_epsg25833(lat, lon)
	return _query_plot_area_at_point(easting, northing)


# B-Plan lookup
def _query_bplan(easting: float, northing: float) -> dict | None:
	r = SEARCH_RADIUS_M
	params = {
		"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
		"TYPENAMES": BPLAN_TYPENAME,
		"BBOX": f"{easting-r},{northing-r},{easting+r},{northing+r}",
		"SRSNAME": "EPSG:25833",
		"outputFormat": "application/json",
		"count": "1",
	}
	try:
		resp = requests.get(BPLAN_WFS_URL, params=params, timeout=15)
		resp.raise_for_status()
		features = resp.json().get("features", [])
		return features[0]["properties"] if features else None
	except Exception as e:
		logger.warning(f"B-Plan WFS query failed: {e}")
	return None


# FNP lookup
def _query_fnp(easting: float, northing: float) -> dict | None:
	r = SEARCH_RADIUS_M
	params = {
		"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
		"TYPENAMES": FNP_TYPENAME,
		"BBOX": f"{easting-r},{northing-r},{easting+r},{northing+r}",
		"SRSNAME": "EPSG:25833",
		"outputFormat": "application/json",
		"count": "1",
	}
	try:
		resp = requests.get(FNP_WFS_URL, params=params, timeout=15)
		resp.raise_for_status()
		features = resp.json().get("features", [])
		return features[0]["properties"] if features else None
	except Exception as e:
		logger.warning(f"FNP WFS query failed: {e}")
	return None


# Public API
def lookup_zone_for_address(address: str) -> dict:
	"""
	Look up BauNVO zone type and official plot area for a Berlin address.

	Returns a dict with:
	  zone_type        — BauNVO code (e.g. WA, MK) or None
	  zone_source      — "B-Plan", "FNP (approximate)", or "not found"
	  fnp_nutzungsart  — raw FNP land use label if used as fallback
	  plot_area_m2     — official parcel area in m² or None
	  needs_user_input — True if zone could not be determined automatically
	  note             — human-readable explanation for the agent
	"""
	geo = _geocode(address)
	if "error" in geo:
		return {"error": geo["error"]}

	# Ambiguous address detected at geocoding stage — street exists in multiple
	# districts. Ask the user to re-submit with a postcode before doing any WFS work.
	if geo.get("ambiguous"):
		street   = geo.get("street", "")
		hnr      = geo.get("hnr", "")
		plz_list = geo.get("plz_list", [])
		examples = [
			c.get("display", f"{street} {hnr}, {c['plz']} Berlin")
			for c in geo.get("candidates", [])
		]
		example_str = " or ".join(f"'{e}'" for e in examples) if examples else (
			f"'{street} {hnr}, {plz_list[0]} Berlin'" if plz_list else f"'{street} {hnr}, 10115 Berlin'"
		)
		return {
			"error": (
				f"'{street} {hnr}' exists in multiple Berlin districts "
				f"(postcodes: {', '.join(plz_list)}). "
				f"Please include the postcode to identify the correct address — "
				f"e.g. {example_str}."
			)
		}

	lat, lon = geo["lat"], geo["lon"]
	easting, northing = _wgs84_to_epsg25833(lat, lon)

	alkis_result = _query_plot_area(geo['raw'], address)

	# Second-line ambiguity guard — catches cases where Photon returned only one
	# result (so the geocode-level check above didn't fire) but the adressen_berlin
	# WFS found multiple records with different postcodes for the same street+hnr.
	if isinstance(alkis_result, dict) and alkis_result.get("ambiguous"):
		districts = alkis_result.get("districts", [])
		plz_list  = alkis_result.get("plz_list", [])
		street    = alkis_result.get("street", "")
		hnr       = alkis_result.get("hnr", "")
		plz_hint  = f" (postcodes: {', '.join(sorted(plz_list))})" if plz_list else ""
		return {
			"error": (
				f"'{street} {hnr}' exists in multiple Berlin districts"
				f"{plz_hint}. "
				f"Please include the postcode to identify the correct address, "
				f"e.g. '{street} {hnr}, {sorted(plz_list)[0] if plz_list else '10115'}'."
			)
		}

	alkis_props  = alkis_result
	plot_area_m2 = int(alkis_props["afl"]) if alkis_props and alkis_props.get("afl") is not None else None
	plot_source  = "ALKIS (GDI Berlin)" if plot_area_m2 else "not found"
	area_note = (
		f"\nPlot area: {plot_area_m2} m² (from ALKIS)."
		if plot_area_m2 else
		"\nPlot area: not found automatically — please provide manually."
	)

	# Strategy 1: B-Plan with inhalt field
	bplan_props = _query_bplan(easting, northing)
	if bplan_props:
		inhalt    = bplan_props.get("inhalt")
		plan_name = bplan_props.get("planname", "")
		all_zones = _parse_all_zones_from_inhalt(inhalt)
		zone_type = all_zones[0] if all_zones else None

		if zone_type:
			multi_note = (
				f" (plan also contains: {', '.join(all_zones[1:])})"
				if len(all_zones) > 1 else ""
			)
			return {
				"lat": lat, "lon": lon,
				"display_name": geo["display_name"],
				"zone_type": zone_type,
				"all_zone_types": all_zones,
				"zone_source": f"B-Plan {plan_name} (GDI Berlin)",
				"fnp_nutzungsart": None,
				"plan_name": plan_name,
				"plan_inhalt": inhalt,
				"plot_area_m2": plot_area_m2,
				"plot_area_source": plot_source,
			"alkis_props": alkis_props,
				"needs_user_input": False,
				"note": (
					f"Zone '{zone_type}' found in B-Plan {plan_name}"
					f"{multi_note}.{area_note}"
				),
			}

		# B-Plan exists but inhalt is null → try FNP before asking user
		fnp_props  = _query_fnp(easting, northing)
		fnp_result = _parse_zone_from_fnp(
			fnp_props.get("nutzungsart") if fnp_props else None
		)

		if fnp_result:
			fnp_code, fnp_label = fnp_result
			return {
				"lat": lat, "lon": lon,
				"display_name": geo["display_name"],
				"zone_type": fnp_code,
				"all_zone_types": [fnp_code],
				"zone_source": "FNP 2025 (approximate)",
				"fnp_nutzungsart": fnp_label,
				"plan_name": plan_name,
				"plan_inhalt": None,
				"plot_area_m2": plot_area_m2,
				"plot_area_source": plot_source,
			"alkis_props": alkis_props,
				"needs_user_input": False,
				"note": (
					f"B-Plan {plan_name} was found but its zone type is not "
					f"available in the GDI Berlin database. "
					f"I used the city-wide land use plan (FNP 2025) as a fallback: "
					f"'{fnp_label}' → approximate BauNVO code: {fnp_code}. "
					f"Please note this is an approximation — verify if needed."
					f"{area_note}"
				),
			}

		# B-Plan found, inhalt null, FNP also didn't help → ask user
		return {
			"lat": lat, "lon": lon,
			"display_name": geo["display_name"],
			"zone_type": None, "all_zone_types": [],
			"zone_source": "not found",
			"fnp_nutzungsart": None,
			"plan_name": plan_name, "plan_inhalt": None,
			"plot_area_m2": plot_area_m2, "plot_area_source": plot_source,
			"alkis_props": alkis_props,
			"needs_user_input": True,
			"note": (
				f"I'm sorry — B-Plan {plan_name} was found for this address "
				"but the zone type is not available in the GDI Berlin database, "
				"and the city-wide land use plan (FNP) did not return usable data either. "
				"Could you please specify the zone type manually? "
				"(e.g. WA, MI, MK, GE)"
			),
		}

	# Strategy 2: No B-Plan → try FNP directly
	fnp_props  = _query_fnp(easting, northing)
	fnp_result = _parse_zone_from_fnp(
		fnp_props.get("nutzungsart") if fnp_props else None
	)

	if fnp_result:
		fnp_code, fnp_label = fnp_result
		return {
			"lat": lat, "lon": lon,
			"display_name": geo["display_name"],
			"zone_type": fnp_code,
			"all_zone_types": [fnp_code],
			"zone_source": "FNP 2025 (approximate)",
			"fnp_nutzungsart": fnp_label,
			"plan_name": None, "plan_inhalt": None,
			"plot_area_m2": plot_area_m2, "plot_area_source": plot_source,
			"alkis_props": alkis_props,
			"needs_user_input": False,
			"note": (
				"No Bebauungsplan (B-Plan) was found for this address — "
				"this may be a §34 BauGB area. "
				f"I used the city-wide land use plan (FNP 2025) as a fallback: "
				f"'{fnp_label}' → approximate BauNVO code: {fnp_code}. "
				"Please note this is an approximation — verify if needed."
				f"{area_note}"
			),
		}

	# Strategy 3: Nothing found → ask user
	return {
		"lat": lat, "lon": lon,
		"display_name": geo["display_name"],
		"zone_type": None, "all_zone_types": [],
		"zone_source": "not found",
		"fnp_nutzungsart": None,
		"plan_name": None, "plan_inhalt": None,
		"plot_area_m2": plot_area_m2, "plot_area_source": plot_source,
			"alkis_props": alkis_props,
		"needs_user_input": True,
		"note": (
			"I'm sorry — I could not find the zone type for this address "
			"in the GDI Berlin database. Neither a Bebauungsplan nor the "
			"city-wide land use plan (FNP 2025) returned usable data. "
			"Could you please specify the zone type manually? "
			"(e.g. WA, MI, MK, GE)"
		),
	}