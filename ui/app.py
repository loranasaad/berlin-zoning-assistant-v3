"""
ui/app.py — Main Streamlit application.

Sprint 3: two-tab layout (Chat + Quick Report), password gate,
vector store loading, and "Continue in Chat" handoff from form to chat.
"""

import json
import re
import uuid

import streamlit as st

from config import _get_secret, DEFAULT_LLM_PROVIDER
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
    if st.session_state.get("authenticated"):
        return True
    st.title("🏗️ Berliner Bebauungsassistent")
    pwd = st.text_input("Passwort", type="password")
    if st.button("Anmelden"):
        if pwd == _get_secret("APP_PASSWORD"):
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
        "pending_tab":           None,       # "chat" | "form" | None
        "main_tab_selector":     "💬 Chat",  # drives the segmented_control widget
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
    "Continue in Chat →" seeds a new thread so follow-up questions work.
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

    # Handoff button
    btn_label = "→ Im Chat fortsetzen" if is_de else "→ Continue in Chat"
    if st.button(btn_label, use_container_width=True, key="handoff_btn"):
        _handoff_to_chat(report, address, final_state.get("_thread_id"))


# ---------------------------------------------------------------------------
# Chat handoff
# ---------------------------------------------------------------------------

def _handoff_to_chat(report: dict, address: str, form_thread_id: str | None):
    """
    Seed a new chat thread with the Quick Report results so the user can ask
    follow-up questions without re-running tools.
    Pattern: edit-state-human-feedback.ipynb (LangChain Academy).
    """
    from chain.agent import get_graph
    from langchain_core.messages import HumanMessage, AIMessage

    new_thread_id = str(uuid.uuid4())
    config        = {"configurable": {"thread_id": new_thread_id}}
    graph         = get_graph()

    summary = json.dumps(report, indent=2, ensure_ascii=False)
    graph.update_state(config, {
        "messages": [
            HumanMessage(content=f"Quick Report für Adresse: {address}"),
            AIMessage(content=f"Quick Report abgeschlossen.\n\n```json\n{summary}\n```"),
        ],
        "mode":         "chat",
        "language":     st.session_state.language,
        "llm_provider": st.session_state.llm_provider,
        "tool_results": {"zoning_report": report},
        "cache_hit":    True,
    })

    # Switch to Chat tab
    st.session_state.pending_tab           = "chat"
    st.session_state.thread_id             = new_thread_id
    st.session_state.awaiting_clarification = False
    st.session_state.clarification_type    = None
    st.session_state.chat_history = [
        {"role": "user",      "content": f"Quick Report für Adresse: {address}"},
        {"role": "assistant", "content": "Quick Report abgeschlossen. Sie können jetzt Folgefragen stellen."},
    ]
    st.session_state.chat_metadata = [{"tool_calls": [], "sources": [], "token_usage": {}}]
    st.rerun()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if not _check_password():
        st.stop()

    _init_session_state()
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

    # Two-tab layout — uses segmented_control so the active tab can be switched
    # programmatically (e.g. "Continue in Chat" handoff from Quick Report).
    lang = st.session_state.language

    _TAB_CHAT = "💬 Chat"
    _TAB_FORM = "📋 Quick Report"
    _TAB_KEY  = "main_tab_selector"

    # Honour a pending programmatic switch (set by _handoff_to_chat)
    if st.session_state.get("pending_tab") == "chat":
        st.session_state[_TAB_KEY] = _TAB_CHAT
        st.session_state.pending_tab = None
    elif st.session_state.get("pending_tab") == "form":
        st.session_state[_TAB_KEY] = _TAB_FORM
        st.session_state.pending_tab = None

    selected_tab = st.segmented_control(
        "Navigation",
        options=[_TAB_CHAT, _TAB_FORM],
        key=_TAB_KEY,
        label_visibility="collapsed",
    )

    if selected_tab == _TAB_FORM:
        _render_quick_report_tab(lang)
    else:
        render_chat_tab(lang)
