"""
chain/graph.py — StateGraph assembly: nodes, edges, compile.

Pattern: consistent across all LangChain Academy notebooks.
The compiled graph is exposed via chain/agent.py (get_graph), not imported directly.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from chain.state import AgentState
from chain.memory import get_checkpointer
from chain.nodes import (
    route_query,
    retrieve_rag,
    check_address_cache,
    resolve_address,
    run_buildable_area,
    run_parking,
    run_construction_cost,
    run_demographics,
    merge_results,
    synthesize_response,
)


# ---------------------------------------------------------------------------
# Routing functions (conditional edges)
# ---------------------------------------------------------------------------

def _route_query(state: AgentState) -> str:
    qt = state.get("query_type", "direct")
    if qt == "regulation":
        return "retrieve_rag"
    if qt == "address":
        return "check_address_cache"
    return "synthesize_response"


def _route_cache(state: AgentState) -> str:
    return "merge_results" if state.get("cache_hit") else "resolve_address"


def _fan_out_tools(state: AgentState):
    """
    Send fan-out from resolve_address → parallel tool nodes.
    Pattern: map-reduce.ipynb (LangChain Academy).

    If resolve_address returned a form-mode error dict, route directly to
    merge_results (which will produce an error zoning_report) instead of
    spawning tool nodes that would have no resolved zone/area to work with.
    """
    if state.get("tool_results", {}).get("error"):
        return [Send("merge_results", state)]
    return [Send(f"run_{tool}", state) for tool in state.get("tools_needed", [])]


def _route_merge(state: AgentState) -> str:
    return END if state.get("mode") == "form" else "synthesize_response"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph():
    builder = StateGraph(AgentState)

    # Nodes
    builder.add_node("route_query",           route_query)
    builder.add_node("retrieve_rag",          retrieve_rag)
    builder.add_node("check_address_cache",   check_address_cache)
    builder.add_node("resolve_address",       resolve_address)
    builder.add_node("run_buildable_area",    run_buildable_area)
    builder.add_node("run_parking",           run_parking)
    builder.add_node("run_construction_cost", run_construction_cost)
    builder.add_node("run_demographics",      run_demographics)
    builder.add_node("merge_results",         merge_results)
    builder.add_node("synthesize_response",   synthesize_response)

    # Entry
    builder.add_edge(START, "route_query")

    # route_query → one of three paths
    builder.add_conditional_edges(
        "route_query",
        _route_query,
        {
            "retrieve_rag":        "retrieve_rag",
            "check_address_cache": "check_address_cache",
            "synthesize_response": "synthesize_response",
        },
    )

    # RAG path
    builder.add_edge("retrieve_rag", "synthesize_response")

    # Address path: cache check
    builder.add_conditional_edges(
        "check_address_cache",
        _route_cache,
        {
            "merge_results":  "merge_results",
            "resolve_address": "resolve_address",
        },
    )

    # Address path: parallel tool fan-out
    builder.add_conditional_edges(
        "resolve_address",
        _fan_out_tools,
        [
            "run_buildable_area",
            "run_parking",
            "run_construction_cost",
            "run_demographics",
            "merge_results",    # error path (form mode)
        ],
    )

    # Parallel tool nodes → merge_results
    builder.add_edge("run_buildable_area",    "merge_results")
    builder.add_edge("run_parking",           "merge_results")
    builder.add_edge("run_construction_cost", "merge_results")
    builder.add_edge("run_demographics",      "merge_results")

    # merge_results → form ends here, chat continues to synthesis
    builder.add_conditional_edges(
        "merge_results",
        _route_merge,
        {
            "synthesize_response": "synthesize_response",
            END: END,
        },
    )

    # synthesis always ends
    builder.add_edge("synthesize_response", END)

    checkpointer = get_checkpointer()
    return builder.compile(checkpointer=checkpointer)
