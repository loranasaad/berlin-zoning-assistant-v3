"""
chain/agent.py — Public API for the Berlin Zoning Assistant graph.

Functions:
  get_graph()          — @st.cache_resource singleton; call once to warm up.
  run_agent(...)       — Streaming chat invocation (sync generator).
  run_form_agent(...)  — Synchronous form invocation; returns final state dict.
"""

import logging
from typing import Generator

import streamlit as st
from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.types import Command

from config import DEFAULT_LLM_PROVIDER

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graph singleton
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_graph():
    """
    Build and compile the StateGraph exactly once per Streamlit server process.
    SqliteSaver uses check_same_thread=False for Streamlit's multi-threaded env.
    """
    from chain.graph import build_graph
    return build_graph()


# ---------------------------------------------------------------------------
# Chat mode streaming
# ---------------------------------------------------------------------------

def run_agent(
    user_input: str,
    config: dict,
    language: str = "de",
    llm_provider: str = DEFAULT_LLM_PROVIDER,
    resuming: bool = False,
) -> tuple[Generator, callable]:
    """
    Stream the agent response for chat mode.

    Returns:
      (stream_gen, get_state_fn)

      stream_gen   — yields text chunks from synthesize_response; pass to
                     st.write_stream().  Yields nothing if the graph is
                     interrupted before reaching synthesize_response.
      get_state_fn — call AFTER the stream is fully consumed to get interrupt
                     status, source_chunks, and accumulated token_usage.
    """
    graph = get_graph()

    if resuming:
        # Resume an interrupt() pause — pass user_input as the resume value.
        # interrupt() in resolve_address returns this value in-place (no re-run).
        input_val = Command(resume=user_input)
    else:
        input_val = {
            "messages":              [HumanMessage(content=user_input)],
            "mode":                  "chat",
            "language":              language,
            "llm_provider":          llm_provider,
            "cache_hit":             False,
            "awaiting_clarification": False,
            "tool_results":          {},
            "token_usage":           {},
            "source_chunks":         [],
        }

    def stream_gen() -> Generator:
        """Yield text chunks emitted by the synthesize_response node."""
        for chunk, metadata in graph.stream(
            input_val, config, stream_mode="messages"
        ):
            if (
                isinstance(chunk, AIMessageChunk)
                and metadata.get("langgraph_node") == "synthesize_response"
                and not getattr(chunk, "tool_calls", None)
            ):
                text = _extract_text(chunk.content)
                if text:
                    yield text

    def get_state_fn() -> dict:
        """Call after stream_gen is exhausted to get post-run state."""
        graph_state = graph.get_state(config)
        interrupted = bool(graph_state.next)

        interrupt_value = None
        if interrupted and graph_state.tasks and graph_state.tasks[0].interrupts:
            interrupt_value = graph_state.tasks[0].interrupts[0].value

        vals = graph_state.values
        return {
            "interrupted":     interrupted,
            "interrupt_value": interrupt_value,   # e.g. "postcode_needed: ..."
            "source_chunks":   vals.get("source_chunks", []),
            "token_usage":     vals.get("token_usage", {}),
            "tool_results":    vals.get("tool_results", {}),
        }

    return stream_gen(), get_state_fn


# ---------------------------------------------------------------------------
# Form mode (synchronous)
# ---------------------------------------------------------------------------

def run_form_agent(
    address: str,
    language: str = "de",
    llm_provider: str = DEFAULT_LLM_PROVIDER,
) -> dict:
    """
    Synchronous graph.invoke() for the Quick Report tab.
    Returns the final LangGraph state dict.
    """
    import uuid
    graph = get_graph()

    thread_id = str(uuid.uuid4())
    config    = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages":              [HumanMessage(content=f"Quick Report für Adresse: {address}")],
        "mode":                  "form",
        "language":              language,
        "llm_provider":          llm_provider,
        "address":               address,
        "cache_hit":             False,
        "awaiting_clarification": False,
        "tool_results":          {},
        "token_usage":           {},
        "source_chunks":         [],
    }

    return graph.invoke(initial_state, config)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _extract_text(content) -> str:
    """Handle both plain-string and block-list content formats."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""
