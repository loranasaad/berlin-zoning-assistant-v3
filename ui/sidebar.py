"""
ui/sidebar.py — Sidebar: language selector, LLM provider selector, cost tracker.

Sprint 3 additions:
  - LLM provider radio button (OpenAI / Anthropic).
  - Changing provider resets thread_id so a fresh conversation starts on the
    new model (checkpointer threads are model-specific by convention).
"""

import uuid
import streamlit as st

from config import LANGUAGES, DEFAULT_LANGUAGE, LLM_PROVIDERS, DEFAULT_LLM_PROVIDER, TOKEN_COSTS
from ui.strings import SIDEBAR_STRINGS


def render_sidebar() -> dict:
    with st.sidebar:
        _init_session_state()
        s = SIDEBAR_STRINGS[st.session_state.language]
        s = _render_settings(s)
        st.divider()
        _render_cost_tracker(s)
        st.divider()
        _render_clear_chat(s)
        st.divider()
        _render_about(s)
    return {
        "language":     st.session_state.language,
        "llm_provider": st.session_state.llm_provider,
    }


def _init_session_state():
    defaults = {
        "total_input_tokens":  0,
        "total_output_tokens": 0,
        "total_cost_usd":      0.0,
        "chat_history":        [],
        "chat_metadata":       [],
        "language":            DEFAULT_LANGUAGE,
        "llm_provider":        DEFAULT_LLM_PROVIDER,
        "thread_id":           str(uuid.uuid4()),
        "awaiting_clarification": False,
        "clarification_type":  None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_settings(s: dict) -> dict:
    """Render language + LLM provider selectors. Returns refreshed strings after language change."""
    st.header(s["settings_header"])

    # Language selector
    selected_lang_label = st.selectbox(
        s["language_label"],
        options=list(LANGUAGES.keys()),
        index=list(LANGUAGES.values()).index(st.session_state.language),
    )
    st.session_state.language = LANGUAGES[selected_lang_label]
    s = SIDEBAR_STRINGS[st.session_state.language]

    # LLM provider selector
    provider_label = (
        "KI-Modell" if st.session_state.language == "de" else "AI Model"
    )
    provider_options = list(LLM_PROVIDERS.keys())
    current_provider_label = next(
        (k for k, v in LLM_PROVIDERS.items() if v == st.session_state.llm_provider),
        provider_options[0],
    )
    selected_provider_label = st.radio(
        provider_label,
        options=provider_options,
        index=provider_options.index(current_provider_label),
    )
    new_provider = LLM_PROVIDERS[selected_provider_label]

    # Reset thread_id when provider changes so the new model starts fresh
    if new_provider != st.session_state.llm_provider:
        st.session_state.llm_provider    = new_provider
        st.session_state.thread_id       = str(uuid.uuid4())
        st.session_state.chat_history    = []
        st.session_state.chat_metadata   = []
        st.session_state.awaiting_clarification = False
        st.session_state.clarification_type     = None
        st.rerun()

    return s


def _render_cost_tracker(s: dict):
    st.header(s["cost_header"])
    col1, col2 = st.columns(2)
    with col1:
        st.metric(s["tokens_input"],  f"{st.session_state.total_input_tokens:,}")
        st.metric(s["tokens_output"], f"{st.session_state.total_output_tokens:,}")
    with col2:
        total = st.session_state.total_input_tokens + st.session_state.total_output_tokens
        st.metric(s["tokens_total"], f"{total:,}")
        st.metric(s["cost_label"],   f"${st.session_state.total_cost_usd:.4f}")
    if st.button(s["cost_reset"], use_container_width=True):
        st.session_state.total_input_tokens  = 0
        st.session_state.total_output_tokens = 0
        st.session_state.total_cost_usd      = 0.0
        st.rerun()


def _render_clear_chat(s: dict):
    if st.button(s["clear_chat"], use_container_width=True):
        st.session_state.chat_history    = []
        st.session_state.chat_metadata   = []
        st.session_state.thread_id       = str(uuid.uuid4())
        st.session_state.awaiting_clarification = False
        st.session_state.clarification_type     = None
        st.rerun()


def _render_about(s: dict):
    st.header(s["about_header"])
    st.markdown(s["about_text"])


def update_cost_tracker(token_usage: dict):
    """Add token counts from one exchange to the running session totals."""
    if not token_usage:
        return
    st.session_state.total_input_tokens  += token_usage.get("input_tokens",  0)
    st.session_state.total_output_tokens += token_usage.get("output_tokens", 0)
    input_cost  = (token_usage.get("input_tokens",  0) / 1000) * TOKEN_COSTS["input"]
    output_cost = (token_usage.get("output_tokens", 0) / 1000) * TOKEN_COSTS["output"]
    st.session_state.total_cost_usd += input_cost + output_cost
