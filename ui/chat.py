"""
ui/chat.py — Chat tab: rendering, input handling, HITL interrupt/resume.

Sprint 3 changes vs Sprint 2:
  - Uses graph-backed run_agent() with thread_id config (not create_react_agent).
  - Checks graph state after streaming for NodeInterrupt.
  - Shows clarification prompt when interrupted; sends resume on next message.
  - State update (address correction) is applied before resuming so resolve_address
    re-runs with the corrected address.
"""

import streamlit as st

from chain.agent import get_graph, run_agent
from config import (
    MIN_INPUT_LENGTH,
    MAX_INPUT_LENGTH,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)
from ui.rate_limiter import check_rate_limit
from ui.sidebar import update_cost_tracker
from ui.strings import COMPONENT_STRINGS
from ui.components import render_chat_message, render_technical_details, render_welcome


# ---------------------------------------------------------------------------
# HITL clarification prompts (inline — strings.py is unchanged)
# ---------------------------------------------------------------------------

_CLARIFICATION_PROMPTS = {
    "postcode_needed": {
        "de": "Bitte geben Sie die Postleitzahl an (z. B. 10115):",
        "en": "Please provide the postcode (e.g. 10115):",
    },
    "zone_not_found": {
        "de": "Bitte geben Sie den Gebietstyp manuell an (z. B. WA, MI, MK, GE):",
        "en": "Please provide the zone type manually (e.g. WA, MI, MK, GE):",
    },
    "plot_area_needed": {
        "de": "Bitte geben Sie die Grundstücksfläche in m² an:",
        "en": "Please provide the plot area in m²:",
    },
}

_DEFAULT_PROMPT = {
    "de": "Bitte geben Sie die fehlende Information an:",
    "en": "Please provide the missing information:",
}


def init_chat_state():
    defaults = {
        "chat_history":          [],    # [{role, content}, ...] for display
        "chat_metadata":         [],    # [{tool_calls, sources, token_usage}, ...] per assistant turn
        "awaiting_clarification": False,
        "clarification_type":    None,  # "postcode_needed" | "zone_not_found" | "plot_area_needed"
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def render_chat_tab(language: str):
    init_chat_state()
    # Container created before chat_input so new messages render above the sticky input bar
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            render_welcome(language)
        else:
            _render_chat_history(language)
    _handle_user_input(language, chat_container)


# ---------------------------------------------------------------------------
# History rendering
# ---------------------------------------------------------------------------

def _render_chat_history(language: str):
    meta_index = 0
    for msg in st.session_state.chat_history:
        render_chat_message(msg["role"], msg["content"])
        if msg["role"] == "assistant" and meta_index < len(st.session_state.chat_metadata):
            meta = st.session_state.chat_metadata[meta_index]
            render_technical_details(
                tool_calls=meta.get("tool_calls", []),
                source_chunks=meta.get("sources", []),
                token_usage=meta.get("token_usage"),
                language=language,
                map_index=meta_index,
                zoning_report=meta.get("zoning_report"),
            )
            meta_index += 1


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

def _handle_user_input(language: str, chat_container=None):
    s = COMPONENT_STRINGS[language]

    # Clarification prompt — shown when graph is waiting for HITL input
    if st.session_state.awaiting_clarification:
        ctype  = st.session_state.clarification_type or ""
        prompt = (
            _CLARIFICATION_PROMPTS
            .get(ctype, _DEFAULT_PROMPT)
            .get(language, _CLARIFICATION_PROMPTS.get(ctype, _DEFAULT_PROMPT)["en"])
        )
        st.info(prompt)

    placeholder = (
        "Frage zur Berliner Bebauungsordnung stellen..."
        if language == "de"
        else "Ask about Berlin zoning regulations..."
    )
    user_input = st.chat_input(placeholder)

    if not user_input:
        return

    # Validate
    stripped = user_input.strip()
    if not stripped:
        return
    if len(stripped) < MIN_INPUT_LENGTH:
        st.error(s["input_too_short"].format(min=MIN_INPUT_LENGTH))
        return
    if len(user_input) > MAX_INPUT_LENGTH:
        st.error(s["input_too_long"].format(length=len(user_input), max=MAX_INPUT_LENGTH))
        return

    # Rate limit
    allowed, wait_seconds = check_rate_limit()
    if not allowed:
        st.error(s["rate_limit_exceeded"].format(
            limit=RATE_LIMIT_REQUESTS,
            window=RATE_LIMIT_WINDOW_SECONDS,
            wait=wait_seconds,
        ))
        return

    resuming = st.session_state.awaiting_clarification
    config   = {"configurable": {"thread_id": st.session_state.thread_id}}

    # Apply state corrections before resuming
    if resuming:
        _apply_clarification(user_input, config)

    # Use the pre-created container so new messages render above the sticky input bar
    out = chat_container if chat_container is not None else st.container()

    # Show user message
    with out:
        render_chat_message("user", user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # Stream response
    with st.spinner(s["thinking"]):
        stream_gen, get_state_fn = run_agent(
            user_input=user_input,
            config=config,
            language=language,
            llm_provider=st.session_state.llm_provider,
            resuming=resuming,
        )

    with out:
        with st.chat_message("assistant"):
            # Reserve a slot BEFORE the stream so we can write the interrupt message
            # into the same bubble instead of creating a second empty+error pair.
            _interrupt_slot = st.empty()
            streamed_text = st.write_stream(stream_gen)

    state_result = get_state_fn()

    # Interrupt detected — graph is waiting for clarification
    if state_result["interrupted"]:
        interrupt_value = state_result["interrupt_value"] or ""
        ctype = interrupt_value.split(":")[0].strip() if ":" in interrupt_value else ""
        message = interrupt_value.split(":", 1)[1].strip() if ":" in interrupt_value else interrupt_value

        # Only recoverable interrupts keep awaiting_clarification=True.
        # resolve_failed (address not found) is terminal — next message starts fresh.
        recoverable = ctype in ("postcode_needed", "zone_not_found", "plot_area_needed")
        st.session_state.awaiting_clarification = recoverable
        st.session_state.clarification_type     = ctype if recoverable else None

        # Write interrupt message into the existing bubble (no second bubble)
        if not streamed_text:
            _interrupt_slot.markdown(message)
            st.session_state.chat_history.append({"role": "assistant", "content": message})
            st.session_state.chat_metadata.append({"tool_calls": [], "sources": [], "token_usage": {}, "zoning_report": None})

    else:
        # Normal completion
        st.session_state.awaiting_clarification = False
        st.session_state.clarification_type     = None

        if streamed_text:
            zoning_report = state_result.get("tool_results", {}).get("zoning_report")
            with out:
                render_technical_details(
                    tool_calls=[],
                    source_chunks=state_result.get("source_chunks", []),
                    token_usage=state_result.get("token_usage"),
                    language=language,
                    map_index=len(st.session_state.chat_metadata),
                    zoning_report=zoning_report,
                )
            st.session_state.chat_history.append({"role": "assistant", "content": streamed_text})
            st.session_state.chat_metadata.append({
                "tool_calls":    [],
                "sources":       state_result.get("source_chunks", []),
                "token_usage":   state_result.get("token_usage", {}),
                "zoning_report": zoning_report,
            })
            update_cost_tracker(state_result.get("token_usage", {}))


# ---------------------------------------------------------------------------
# HITL state correction
# ---------------------------------------------------------------------------

def _apply_clarification(user_input: str, config: dict):
    """
    Before resuming from a NodeInterrupt, update the relevant state field so
    resolve_address re-runs with corrected data.

    postcode_needed  → append postcode to existing address
    plot_area_needed → set resolved_plot_area (skip re-geocoding)
    zone_not_found   → set resolved_zone (skip re-geocoding)
    """
    ctype = st.session_state.clarification_type or ""
    graph = get_graph()

    try:
        if ctype == "postcode_needed":
            current = graph.get_state(config).values.get("address", "")
            # If user typed a full address keep it; otherwise append the postcode
            new_address = (
                user_input.strip()
                if "," in user_input
                else f"{current}, {user_input.strip()}"
            )
            graph.update_state(config, {"address": new_address})

        elif ctype == "plot_area_needed":
            try:
                plot_area = float(user_input.strip().replace(",", "."))
                graph.update_state(config, {"resolved_plot_area": plot_area})
            except ValueError:
                pass  # leave state as-is; resolve_address will interrupt again

        elif ctype == "zone_not_found":
            graph.update_state(config, {"resolved_zone": user_input.strip().upper()})

    except Exception as exc:
        # Non-fatal — resume will still happen, may interrupt again
        import logging
        logging.getLogger(__name__).warning(f"_apply_clarification failed: {exc}")
