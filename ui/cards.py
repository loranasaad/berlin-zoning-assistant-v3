import streamlit as st
from ui.strings import COMPONENT_STRINGS

# Parcel Info tab — map + cadastral fields

def _render_map_and_parcel_fields(zoning_data: dict, language: str, map_index: int = 0):
	s = COMPONENT_STRINGS[language]
	lat = zoning_data.get("lat")
	lon = zoning_data.get("lon")
	address = zoning_data.get("address", "")
	alkis_props = zoning_data.get("alkis_props")

	try:
		import folium
		from streamlit_folium import st_folium

		m = folium.Map(location=[lat, lon], zoom_start=17, tiles="OpenStreetMap")
		folium.Marker(
			location=[lat, lon],
			popup=folium.Popup(
				f"<b>{address}</b><br>"
				+ (f"Area: {int(alkis_props['afl'])} m²"
				if alkis_props and alkis_props.get("afl") else ""),
				max_width=250,
		),
		tooltip=address,
		icon=folium.Icon(color="red", icon="home", prefix="fa"),
		).add_to(m)
		st_folium(m, use_container_width=True, height=380, returned_objects=[], key=f"map_{lat}_{lon}_{map_index}")

	except ImportError:
		import pandas as pd
		st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=16)

	st.markdown("---")
	if not alkis_props:
		st.caption(s["no_parcel"])
		return
	
	fields = [
		(s["parcel_area"],      f"{int(alkis_props['afl']):,} m²" if alkis_props.get("afl") is not None else None),
		(s["parcel_id"],        alkis_props.get("uuid")),
		(s["parcel_aaa"],       alkis_props.get("bezeich")),
		(s["parcel_fsko"],      alkis_props.get("fsko")),
		(s["parcel_zae"],       str(alkis_props["zae"]) if alkis_props.get("zae") is not None else None),
		(s["parcel_nen"],       str(alkis_props["nen"]) if alkis_props.get("nen") is not None else None),
		(s["parcel_gmk"],       alkis_props.get("gmk")),
		(s["parcel_gemarkung"], alkis_props.get("namgmk")),
		(s["parcel_flur"],      str(alkis_props["fln"]) if alkis_props.get("fln") is not None else None),
		(s["parcel_gdz"],       alkis_props.get("gdz")),
		(s["parcel_gemeinde"],  alkis_props.get("namgem")),
		(s["parcel_created"],   str(alkis_props.get("zde", ""))[:10] if alkis_props.get("zde") else None),
		(s["parcel_dst"],       alkis_props.get("dst")),
		(s["parcel_beg"],       str(alkis_props.get("beg", ""))[:10] if alkis_props.get("beg") else None),
		(s["parcel_source"],    "ALKIS (GDI Berlin)"),
	]

	visible = [(label, value) for label, value in fields if value is not None]

	NUM_COLS = 3
	col_size = -(-len(visible) // NUM_COLS)
	chunks = [visible[i:i + col_size] for i in range(0, len(visible), col_size)]

	cols = st.columns([1] * len(chunks), gap="small")
	for col_idx, (col, chunk) in enumerate(zip(cols, chunks)):
		with col:
			border = "border-left: 1px solid #444; padding-left: 12px;" if col_idx > 0 else ""
			rows_html = "".join(
				f"<div style='display:flex; justify-content:space-between; align-items:baseline; "
				f"padding: 5px 0; border-bottom: 1px solid #2a2a2a;'>"
				f"<span style='color:#888; font-size:0.78rem; margin-right:12px; white-space:nowrap;'>{lbl}</span>"
				f"<span style='font-weight:600; font-size:0.85rem; text-align:right;'>{val}</span>"
				f"</div>"
				for lbl, val in chunk
			)
			st.markdown(
				f"<div style='{border}'>{rows_html}</div>",
				unsafe_allow_html=True,
			)

# Render cards

def _render_buildable_area_card(ba: dict, plot: dict, language: str):
	s = COMPONENT_STRINGS[language]
	st.markdown(s["ba_title"])
	c1, c2, c3 = st.columns(3)
	c1.metric(
		s["ba_plot_area"],
		f"{plot.get('area_m2', '—')} m²",
		help=plot.get("area_source", ""),
	)
	c2.metric(
		s["ba_footprint"],
		f"{ba.get('max_footprint_m2', '—')} m²",
		help=f"GRZ {ba.get('grz')} × plot area",
	)
	c3.metric(
		s["ba_floor_area"],
		f"{ba.get('max_total_floor_area_m2', '—')} m²",
		help=f"GFZ {ba.get('gfz')} × plot area",
	)
	c4, c5, c6 = st.columns(3)
	c4.metric(
		s["ba_floors"],
		ba.get("typical_floors", "—"),
		help=f"Max allowed: {ba.get('max_floors')}",
	)
	c5.metric(
		s["ba_basement"],
		f"{ba.get('max_basement_footprint_m2', '—')} m²",
		help="GRZ + 0.2 (§19 BauNVO)",
	)
	c6.metric(s["ba_zone"], ba.get("zone_type", "—"))
	st.caption(
		f"**{s['ba_calc']}:** "
		f"{plot.get('area_m2')} m² × GRZ {ba.get('grz')} = {ba.get('max_footprint_m2')} m² "
		f"{s['ba_footprint_label']} | "
		f"{plot.get('area_m2')} m² × GFZ {ba.get('gfz')} = {ba.get('max_total_floor_area_m2')} m² "
		f"{s['ba_total_label']}"
	)
	st.divider()

def _render_parking_card(p: dict, language: str):
	s = COMPONENT_STRINGS[language]
	st.markdown(s["park_title"])

	# Row 1 — headline numbers
	c1, c2, c3 = st.columns(3)
	c1.metric(s["park_units"], p.get("estimated_units", "—"))
	c2.metric(s["park_bike"],  p.get("required_bike_spaces", "—"))
	c3.metric(s["park_cargo"], p.get("cargo_bike_spaces", 0))

	# Row 2 — accessible car spaces (only shown when > 0)
	accessible = p.get("required_accessible_car_spaces", 0)
	if accessible:
		st.metric(s["park_accessible"], accessible,
				  help=s["park_accessible_help"])

	# Step 1: unit estimate
	st.markdown(s["park_step1"])
	st.code(p.get("units_calculation", "—"))
	st.caption(s["park_step1_note"].format(size=p.get("avg_unit_size_m2", 75)))

	# Step 2: bike ratio
	st.markdown(s["park_step2"])
	st.code(p.get("bike_formula", "—"))
	st.caption(f"📋 {s['park_source']}: {p.get('bike_source', 'AV Stellplätze 16.06.2021')}")

	# Car parking note
	st.info(s["park_no_car_min"])
	st.divider()

def _render_construction_cost_card(c: dict, language: str):
	if not c or "error" in c:
		return
	s = COMPONENT_STRINGS[language]
	st.markdown(s["cost_title"])
	c1, c2, c3 = st.columns(3)
	c1.metric("Min", f"€{c.get('total_cost_min_eur', 0):,.0f}")
	c2.metric(s["cost_avg"], f"€{c.get('total_cost_avg_eur', 0):,.0f}")
	c3.metric("Max", f"€{c.get('total_cost_max_eur', 0):,.0f}")
	unit = c.get("unit", "m²")
	area = c.get("total_area", c.get("total_area_m2", "—"))
	multiplier = c.get("location_multiplier", 1.0)
	cost_min = c.get("cost_per_unit_min_eur", "—")
	cost_avg = c.get("cost_per_unit_avg_eur", "—")
	cost_max = c.get("cost_per_unit_max_eur", "—")
	st.caption(
		f"**{s['cost_btype']}:** {c.get('building_type', '—')} | "
		f"**{s['cost_area']}:** {area} {unit} | "
		f"**{s['cost_location']}:** {multiplier}× | "
		f"**{s['cost_rate']}:** €{cost_min}–€{cost_avg}–€{cost_max} / {unit}"
	)
	notes = c.get("notes_en") or c.get("notes")
	if notes:
		st.caption(f"ℹ️ {notes}")
	st.caption(f"{s['cost_source']} {c.get('data_source', s['cost_default_source'])}")
	if c.get("price_index_ref"):
		st.caption(f"{s['cost_index']} {c['price_index_ref']}")
	st.warning(c.get("disclaimer_en") or c.get("disclaimer", s["cost_default_disclaimer"]))
	st.divider()

def _render_demographics_card(d: dict | None, language: str):
	if not d:
		return
	s = COMPONENT_STRINGS[language]
	st.markdown(s["demo_title"])
	c1, c2, c3 = st.columns(3)
	c1.metric(
		s["demo_population"],
		f"{d.get('population', '—'):,}" if isinstance(d.get("population"), int) else d.get("population", "—"),
	)
	c2.metric(s["demo_age"], d.get("avg_age", "—"))
	c3.metric(s["demo_foreign"], f"{d.get('foreign_residents_pct', '—')}%")
	c4, c5, c6 = st.columns(3)
	c4.metric(s["demo_apt_size"], f"{d.get('avg_apartment_size_m2', '—')} m²")
	c5.metric(s["demo_rent"],     f"€{d.get('avg_rent_per_m2', '—')}/m²")
	c6.metric(s["demo_household"], d.get("dominant_household", "—"))
	src = d.get("data_source", "")
	ref = d.get("reference_date", "")
	if src:
		st.caption(s["demo_source"].format(src=src, ref=ref))
	