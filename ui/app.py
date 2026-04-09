"""
ui/app.py — Main Streamlit application.

Sprint 3: two-tab layout (Chat + Quick Report), password gate,
vector store loading.
"""

import re
import uuid

import streamlit as st

from config import DEFAULT_LLM_PROVIDER, PASSWORD_PROTECTION_ENABLED, APP_PASSWORD, ENV_FILE_PRESENT
from ui.strings import COMPONENT_STRINGS
from rag.embeddings import get_or_create_vector_store
from ui.sidebar import render_sidebar
from ui.chat import render_chat_tab
from ui.cards import (
    _render_map_and_parcel_fields,
    _render_buildable_area_card,
    _render_parking_card,
    _render_construction_cost_card,
    _render_demographics_card,
)

st.set_page_config(
    page_title="Berlin Zoning Assistant",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Password gate
# ---------------------------------------------------------------------------

def _check_password() -> bool:
    if not PASSWORD_PROTECTION_ENABLED:
        return True
    if st.session_state.get("authenticated"):
        return True
    st.title("🏗️ Berliner Bebauungsassistent")
    pwd = st.text_input("Passwort", type="password")
    if st.button("Anmelden"):
        if pwd == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Falsches Passwort")
    return False


# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def load_vector_store():
    with st.spinner("Wissensdatenbank wird geladen... (erster Start: ~30 Sekunden)"):
        return get_or_create_vector_store()


# ---------------------------------------------------------------------------
# Session state bootstrap
# ---------------------------------------------------------------------------

def _init_session_state():
    defaults = {
        "thread_id":             str(uuid.uuid4()),
        "llm_provider":          DEFAULT_LLM_PROVIDER,
        "language":              "de",
        "awaiting_clarification": False,
        "clarification_type":    None,
        "authenticated":         False,
        "active_tab":            "chat",     # "chat" | "form" — owns tab selection
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ---------------------------------------------------------------------------
# Quick Report tab
# ---------------------------------------------------------------------------

def _render_quick_report_tab(language: str):
    """
    Form mode: validated address + postcode → synchronous graph.invoke()
    → render cards directly (no LLM synthesis step).
    """
    from chain.agent import run_form_agent

    is_de = language == "de"

    with st.form("quick_report_form"):
        street   = st.text_input(
            "Straße und Hausnummer" if is_de else "Street and house number",
            placeholder="Friedrichstraße 100",
        )
        postcode = st.text_input(
            "Postleitzahl (Pflicht — verhindert Mehrdeutigkeit)" if is_de
            else "Postcode (required — prevents ambiguity)",
            placeholder="10117",
        )
        submitted = st.form_submit_button(
            "Bericht erstellen" if is_de else "Generate report",
            use_container_width=True,
        )

    if not submitted:
        return

    # Berlin postcodes: 5 digits, start with 1
    if not re.match(r"^1\d{4}$", postcode.strip()):
        st.error(
            "Bitte eine gültige Berliner PLZ angeben (5 Ziffern, beginnt mit 1)."
            if is_de else
            "Please enter a valid Berlin postcode (5 digits, starting with 1)."
        )
        return

    address = f"{street.strip()}, {postcode.strip()} Berlin"

    with st.spinner("Analyse läuft…" if is_de else "Analysing…"):
        final_state = run_form_agent(
            address=address,
            language=language,
            llm_provider=st.session_state.llm_provider,
        )

    report = final_state.get("tool_results", {}).get("zoning_report", {})

    if report.get("status") == "error":
        error_type = report.get("error_type", "unknown")
        message    = report.get("message", "")
        _err_map = {
            "postcode_needed": (
                "Die Adresse existiert in mehreren Bezirken. Bitte PLZ angeben."
                if is_de else
                "Address exists in multiple districts. Please include the postcode."
            ),
            "zone_not_found": (
                "Gebietstyp konnte nicht ermittelt werden."
                if is_de else "Zone type could not be determined."
            ),
            "plot_area_needed": (
                "Grundstücksfläche nicht gefunden."
                if is_de else "Plot area could not be found."
            ),
        }
        st.error(_err_map.get(error_type, message or error_type))
        return

    # Render cards
    coords    = report.get("coordinates", {})
    lat, lon  = coords.get("lat"), coords.get("lon")
    if lat and lon:
        _render_map_and_parcel_fields(
            {
                "lat":        lat,
                "lon":        lon,
                "address":    report.get("address", address),
                "alkis_props": report.get("alkis_props"),
            },
            language,
            map_index=99,
        )

    _render_buildable_area_card(report.get("buildable_area", {}), report.get("plot", {}), language)
    _render_parking_card(report.get("parking", {}), language)
    _render_construction_cost_card(report.get("construction_cost", {}), language)
    _render_demographics_card(report.get("demographics"), language)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not _check_password():
        st.stop()

    _init_session_state()

    if not ENV_FILE_PRESENT:
        lang = st.session_state.get("language", "de")
        st.info(COMPONENT_STRINGS[lang]["no_env_banner"])

    settings = render_sidebar()
    st.session_state.language     = settings["language"]
    st.session_state.llm_provider = settings["llm_provider"]

    # Warm up vector store (cached after first call)
    vs = load_vector_store()

    # Set vector store on nodes module (needed by retrieve_rag)
    from chain.nodes import set_vector_store
    set_vector_store(vs)

    # Warm up graph singleton
    from chain.agent import get_graph
    get_graph()

    # Two-tab layout — active_tab in session_state owns the selection.
    lang = st.session_state.language

    col_chat, col_form = st.columns(2)
    if col_chat.button(
        "💬 Chat",
        use_container_width=True,
        type="primary" if st.session_state.active_tab == "chat" else "secondary",
        key="tab_btn_chat",
    ):
        st.session_state.active_tab = "chat"
        st.rerun()
    if col_form.button(
        "📋 Quick Report",
        use_container_width=True,
        type="primary" if st.session_state.active_tab == "form" else "secondary",
        key="tab_btn_form",
    ):
        st.session_state.active_tab = "form"
        st.rerun()

    st.divider()

    if st.session_state.active_tab == "form":
        _render_quick_report_tab(lang)
    else:
        render_chat_tab(lang)
