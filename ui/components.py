import json
import streamlit as st
from ui.strings import COMPONENT_STRINGS, TOOL_ERROR_STRINGS
from ui.cards import (
	_render_map_and_parcel_fields,
	_render_buildable_area_card,
	_render_parking_card,
	_render_construction_cost_card,
	_render_demographics_card,
)

# -----------------------
# Welcome + chat messages
# -----------------------

def render_welcome(language: str = "en"):
	s = COMPONENT_STRINGS[language]
	st.title(s["welcome_title"])
	st.markdown(s["welcome_text"])

def render_chat_message(role: str, content: str):
	with st.chat_message(role):
		st.markdown(content)


# ------------------
# Main details panel
# ------------------

def render_technical_details(
	tool_calls: list,
	source_chunks: list,
	token_usage: dict | None,
	language: str = "en",
	map_index: int = 0,
):
	"""
	Single ' Analysis' expander per assistant message, collapsed by default.

	Address lookup messages → 4 tabs: Parcel Info | Report | Sources | Debug
	All other messages      → 2 tabs:                        Sources | Debug
	"""
	s = COMPONENT_STRINGS[language]

	parsed = {tc["tool"]: _parse_tool_output(tc) for tc in tool_calls}
	zoning_report = parsed.get("get_full_zoning_report") or {}
	zoning_data = _extract_zoning_data(zoning_report)
	has_zoning = zoning_data is not None and zoning_report.get("status") == "complete"

	label = _build_expander_label(s, tool_calls, source_chunks)

	with st.expander(label, expanded=False):
		tabs = _create_tabs(s, has_zoning)

		if tabs.get("parcel"):
			with tabs["parcel"]:
				_render_map_and_parcel_fields(zoning_data, language, map_index)
		
		if tabs.get("report"):
			with tabs["report"]:
				_render_report_tab(zoning_report, language)
		
		with tabs["rag"]:
			_render_rag_process_tab(source_chunks, s)

		with tabs["sources"]:
			_render_sources_tab(source_chunks, s)
		
		with tabs["debug"]:
			_render_debug_tab(tool_calls, s)

# ----------------
# Internal helpers
# ----------------

def _parse_tool_output(tc: dict) -> dict | None:
	"""Parse a tool call's output into a dict, whether it's already a dict or a JSON string."""
	output = tc.get("output")
	if not output:
		return None
	if isinstance(output, dict):
		return output
	try:
		return json.loads(output)
	except Exception:
		return None

def _extract_zoning_data(zoning_report: dict) -> dict | None:
	"""Extract lat/lon and ALKIS props from a parsed zoning report dict."""
	lat = zoning_report.get("coordinates", {}).get("lat")
	lon = zoning_report.get("coordinates", {}).get("lon")
	if not lat or not lon:
		return None
	return {
		"lat": lat,
		"lon": lon,
		"address": zoning_report.get("address", ""),
		"alkis_props": zoning_report.get("alkis_props"),
	}

def _build_expander_label(s: dict, tool_calls: list, source_chunks: list) -> str:
	"""Build the expander button label e.g. '🔍 Analysis — 3 tools · 4 sources'."""
	parts = []
	if len(tool_calls):
		parts.append(f"{len(tool_calls)} tool{'s' if len(tool_calls) != 1 else ''}")
	if len(source_chunks):
		parts.append(f"{len(source_chunks)} source{'s' if len(source_chunks) != 1 else ''}")
	subtitle = "  ·  ".join(parts)
	return f"{s['expander_label']} - {subtitle}" if subtitle else s["expander_label"]

def _create_tabs(s: dict, has_zoning: bool) -> dict:
	"""Create the correct set of tabs and return them as a dict."""
	if has_zoning:
		parcel, report, rag, sources, debug = st.tabs([
			s["tab_parcel"],
			s["tab_report"],
			s["tab_rag"],
			s["tab_sources"],
			s["tab_debug"],
		])
		return {"parcel": parcel, "report": report, "rag": rag, "sources": sources, "debug": debug}
	else:
		rag, sources, debug = st.tabs([s["tab_rag"], s["tab_sources"], s["tab_debug"]])
		return {"parcel": None, "report": None, "rag": rag, "sources": sources, "debug": debug}

def _render_report_tab(zoning_report: dict, language: str):
	"""Render the four report cards if the zoning report completed successfully."""
	if zoning_report.get("status") != "complete":
		return
	_render_buildable_area_card(
		zoning_report.get("buildable_area", {}),
		zoning_report.get("plot", {}),
		language
	)
	_render_parking_card(zoning_report.get("parking", {}), language)
	_render_construction_cost_card(zoning_report.get("construction_cost", {}), language)
	_render_demographics_card(zoning_report.get("demographics"), language)

def _render_rag_process_tab(source_chunks: list, s: dict):
	"""
	Visualise the RAG retrieval pipeline as a step-by-step flow.
	Shows:
	  1. The embedding step (static — always the same process)
	  2. Each retrieved chunk with its relevance score as a colour-coded bar
	  3. Total context size injected into the prompt
	"""
	if not source_chunks:
		st.caption(s["rag_no_chunks"])
		return

	# Step 1: Embedding
	st.markdown("**1 · Embedding**")
	st.markdown(
		"<div style='background:#1e1e2e; border-left:3px solid #6c63ff; "
		"padding:8px 12px; border-radius:4px; font-size:0.85rem; color:#cdd6f4;'>"
		"Query → <code>text-embedding-3-small</code> → 1 536-dim vector"
		"</div>",
		unsafe_allow_html=True,
	)
	st.markdown("")

	# Step 2: Retrieval with score bars
	st.markdown(f"**2 · {s['rag_retrieved']} ({len(source_chunks)})**")

	for i, chunk in enumerate(source_chunks, 1):
		source = chunk.metadata.get("source", "Unknown")
		page   = chunk.metadata.get("page", "")
		score  = chunk.metadata.get("retrieval_score")  # float or None

		page_info = f" — p.{page + 1}" if page != "" else ""
		label = f"{i}. {source}{page_info}"

		if score is not None:
			# L2 (Euclidean) distance: 0 = identical, 2 = maximum distance.
			# Map 0–2 range to 0–100% bar width.
			bar_pct = max(0, min(100, round((2.0 - score) / 2.0 * 100)))

			# Colour thresholds for L2 distance
			if score < 0.8:
				colour = "#a6e3a1"   # green
			elif score < 1.2:
				colour = "#f9e2af"   # amber
			else:
				colour = "#f38ba8"   # red

			st.markdown(
				f"<div style='margin:6px 0;'>"
				f"<div style='display:flex; justify-content:space-between; "
				f"font-size:0.82rem; margin-bottom:3px;'>"
				f"<span>{label}</span>"
				f"<span style='color:{colour}; font-weight:600;'>{s['rag_score_label']}: {score:.3f}</span>"
				f"</div>"
				f"<div style='background:#313244; border-radius:4px; height:8px;'>"
				f"<div style='background:{colour}; width:{bar_pct}%; height:8px; border-radius:4px;'></div>"
				f"</div>"
				f"</div>",
				unsafe_allow_html=True,
			)
		else:
			st.markdown(f"- {label}")

	st.caption(s["rag_score_note"])
	st.markdown("")

	# Step 3: Context size
	st.markdown(f"**3 · {s['rag_context_size']}**")
	total_chars  = sum(len(c.page_content) for c in source_chunks)
	approx_tokens = total_chars // 4
	st.markdown(
		f"<div style='background:#1e1e2e; border-left:3px solid #a6e3a1; "
		f"padding:8px 12px; border-radius:4px; font-size:0.85rem; color:#cdd6f4;'>"
		f"{len(source_chunks)} chunks · {total_chars:,} chars · "
		f"{s['rag_tokens_approx'].format(tokens=f'{approx_tokens:,}')} injected into system prompt"
		f"</div>",
		unsafe_allow_html=True,
	)

def _render_sources_tab(source_chunks: list, s: dict):
	"""Render the list of RAG source chunks."""
	if not source_chunks:
		st.caption(s["no_sources"])
		return
	for i, chunk in enumerate(source_chunks, 1):
		source = chunk.metadata.get("source", "Unknown")
		page = chunk.metadata.get("page", "")
		page_info = f" — {s['sources_page']} {page + 1}" if page != "" else ""
		with st.expander(f"{i}. {source}{page_info}"):
			st.caption(chunk.page_content)

def _translate_tool_error(output: dict, language: str) -> str:
	"""
	Translate a tool error dict into a localised string for display.
	Uses error_code + error_params if present, falls back to the raw error string.
	"""
	error_code = output.get("error_code")
	if error_code:
		template = TOOL_ERROR_STRINGS.get(language, TOOL_ERROR_STRINGS["en"]).get(error_code)
		if template:
			params = output.get("error_params", {})
			return template.format(**params)
	return output.get("error", str(output))

def _render_debug_tab(tool_calls: list, s: dict, language: str = "en"):
	"""Render the debug view showing raw tool inputs and outputs."""
	if not tool_calls:
		st.caption(s["no_tools"])
		return
	for i, tc in enumerate(tool_calls, 1):
		st.markdown(f"**{i}. `{tc['tool']}`**")
		col1, col2 = st.columns(2)
		with col1:
			st.markdown(f"*{s['tool_input']}:*")
			st.json(tc["input"])
		with col2:
			st.markdown(f"*{s['tool_output']}:*")
			output = tc["output"]
			parsed_output = output if isinstance(output, dict) else _parse_tool_output(tc)
			if parsed_output and "error_code" in parsed_output:
				st.error(_translate_tool_error(parsed_output, language))
			elif isinstance(output, dict):
				st.json(output)
			else:
				try:
					st.json(json.loads(output))
				except Exception:
					st.code(str(output))
		if i < len(tool_calls):
			st.divider()
