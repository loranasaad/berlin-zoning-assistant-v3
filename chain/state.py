"""
chain/state.py — AgentState TypedDict + custom reducers.

Pattern: state-reducers.ipynb (LangChain Academy)
"""

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


def _merge_dicts(left: dict | None, right: dict | None) -> dict:
    """Safe merge for parallel tool writes. Last write wins per key."""
    return {**(left or {}), **(right or {})}


def _add_tokens(left: dict | None, right: dict | None) -> dict:
    """Accumulate token counts across all nodes."""
    left  = left  or {}
    right = right or {}
    return {k: left.get(k, 0) + right.get(k, 0) for k in set(left) | set(right)}


class AgentState(TypedDict):
    # Reducers — never overwritten, always merged/appended
    messages:    Annotated[list[AnyMessage], add_messages]
    tool_results: Annotated[dict, _merge_dicts]
    token_usage:  Annotated[dict, _add_tokens]

    # Plain fields — last-write-wins (only one node writes each)
    language:               str
    llm_provider:           str
    mode:                   str           # "chat" | "form"
    query_type:             str           # "regulation" | "address" | "direct"
    tools_needed:           list[str]
    rag_context:            str
    source_chunks:          list
    address:                str | None
    canonical_address:      str | None
    geocode_result:         dict | None
    resolved_zone:          str | None
    resolved_plot_area:     float | None
    estimated_floor_area:   float | None
    cache_hit:              bool
    awaiting_clarification: bool
    clarification_type:     str | None    # "postcode_needed"|"zone_not_found"|"plot_area_needed"
