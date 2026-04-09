"""
chain/nodes.py — All LangGraph node functions for the Berlin Zoning Assistant.

Sections:
  1. Imports and extractors
  2. route_query, retrieve_rag
  3. check_address_cache, resolve_address
  4. run_buildable_area, run_parking, run_construction_cost, run_demographics
  5. merge_results, synthesize_response
"""

# ===========================================================================
# 1. IMPORTS AND EXTRACTORS
# ===========================================================================

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.errors import NodeInterrupt
from langgraph.types import interrupt
from trustcall import create_extractor

from chain.state import AgentState
from chain.llm import get_llm
from chain.memory import cache_lookup, cache_save
from chain.prompts import SYSTEM_PROMPTS, CLASSIFIER_SYSTEM, TOOLS
from config import DEFAULT_LLM_PROVIDER
from data.zoning_rules import ZONE_PARAMETERS, ZONE_TO_BUILDING_TYPE, INNER_CITY_DISTRICTS
from tools.buildable_area import calculate_buildable_area
from tools.parking import calculate_parking_requirements
from tools.construction_cost import estimate_construction_cost, get_construction_price_index
from tools.demographics import get_demographics
from tools.fisbroker import lookup_zone_for_address

logger = logging.getLogger(__name__)

# Vector store reference — set once by agent.get_graph() before the graph runs.
# Kept here (not in agent.py) to avoid a circular import.
_vector_store = None

def set_vector_store(vs) -> None:
    global _vector_store
    _vector_store = vs


# --- Pydantic schemas for trustcall extractors ---

class QueryClassification(BaseModel):
    """Classify the user query and extract relevant parameters for routing."""

    query_type: Literal["regulation", "address", "direct"] = Field(
        description=(
            "regulation = BauNVO/law/setback/zone-definition question requiring document search. "
            "address = query about a specific Berlin property address. "
            "direct = calculation or general question answerable by tools without an address."
        )
    )
    tools_needed: list[str] = Field(
        default_factory=list,
        description=(
            "For address queries: which tools to run. "
            "Options: buildable_area, parking, construction_cost, demographics. "
            "Leave empty for regulation and direct queries."
        ),
    )
    address: str | None = Field(
        default=None,
        description="The street address mentioned by the user, if any. Include postcode if provided.",
    )


# --- Extractor caches (one instance per LLM provider) ---

_classifier_cache: dict[str, Any] = {}


def _get_classifier(provider: str):
    if provider not in _classifier_cache:
        _classifier_cache[provider] = create_extractor(
            get_llm(provider),
            tools=[QueryClassification],
            tool_choice="QueryClassification",
        )
    return _classifier_cache[provider]


# Tool dispatcher for synthesize_response "direct" mode
_TOOL_MAP: dict[str, Any] = {
    "calculate_buildable_area":        calculate_buildable_area,
    "calculate_parking_requirements":  calculate_parking_requirements,
    "estimate_construction_cost":      estimate_construction_cost,
    "get_construction_price_index":    get_construction_price_index,
    "get_demographics":                get_demographics,
}


def _execute_tool(name: str, args: dict) -> Any:
    tool = _TOOL_MAP.get(name)
    if not tool:
        return {"error": f"Unknown tool: {name}"}
    return tool.invoke(args)


def _is_inner_city(address: str) -> bool:
    address_lower = address.lower()
    return any(d in address_lower for d in INNER_CITY_DISTRICTS)


def _extract_usage(response) -> dict:
    usage = getattr(response, "usage_metadata", None) or {}
    return {
        "input_tokens":  usage.get("input_tokens",  0),
        "output_tokens": usage.get("output_tokens", 0),
    }


# ===========================================================================
# 2. ROUTE_QUERY AND RETRIEVE_RAG
# ===========================================================================

def route_query(state: AgentState) -> dict:
    """
    Classify the user query into regulation / address / direct.
    Form mode bypasses LLM classification entirely — address and all 4 tools
    are always needed.
    """
    if state.get("mode") == "form":
        return {
            "query_type":   "address",
            "tools_needed": ["buildable_area", "parking", "construction_cost", "demographics"],
        }

    provider     = state.get("llm_provider", DEFAULT_LLM_PROVIDER)
    last_message = state["messages"][-1].content
    classifier   = _get_classifier(provider)

    result         = classifier.invoke({
        "messages": [
            SystemMessage(content=CLASSIFIER_SYSTEM),
            HumanMessage(content=last_message),
        ]
    })
    classification: QueryClassification = result["responses"][0]

    # Always run all four tools for address queries — UI renders all four sections
    # and partial results leave construction_cost/demographics cards empty.
    if classification.query_type == "address":
        tools_needed = ["buildable_area", "parking", "construction_cost", "demographics"]
    else:
        tools_needed = classification.tools_needed

    return {
        "query_type":   classification.query_type,
        "tools_needed": tools_needed,
        "address":      classification.address,
    }


def retrieve_rag(state: AgentState) -> dict:
    """
    Run the RAG retrieval pipeline for regulation queries.
    Uses the module-level _vector_store set by agent.get_graph().
    """
    from rag.retriever import retrieve_and_format

    last_message = state["messages"][-1].content
    language     = state.get("language", "de")

    context, chunks, usage = retrieve_and_format(
        query=last_message,
        vector_store=_vector_store,
        language=language,
    )

    return {
        "rag_context":   context,
        "source_chunks": chunks,
        "token_usage":   {
            "input_tokens":  usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
        },
    }


# ===========================================================================
# 3. CHECK_ADDRESS_CACHE AND RESOLVE_ADDRESS
# ===========================================================================

def check_address_cache(state: AgentState) -> dict:
    """
    SQLite address cache lookup.
    Exact normalised match → 35-char fuzzy prefix → ambiguous check.
    Cache hit loads the full zoning_report and resolved fields into state.
    """
    address = state.get("address")
    if not address:
        return {"cache_hit": False}

    cached = cache_lookup(address)
    if not cached:
        return {"cache_hit": False}

    logger.info(f"Address cache hit for: {address[:60]}")
    return {
        "cache_hit":        True,
        "tool_results":     {"zoning_report": cached},
        "canonical_address": cached.get("address"),
        "resolved_zone":    cached.get("zone", {}).get("type"),
        "resolved_plot_area": cached.get("plot", {}).get("area_m2"),
    }


def resolve_address(state: AgentState) -> dict:
    """
    Geocode the address and look up its BauNVO zone and plot area via GDI Berlin APIs.

    Uses interrupt() (not NodeInterrupt) so the node pauses in-place and the
    user's response is returned directly — no re-run from scratch on resume.

    Flow:
      1. lookup_zone_for_address — Photon geocode + B-Plan/FNP WFS + ALKIS parcel.
      2. interrupt() (chat) or return error dict (form) for:
           postcode_needed   — address is genuinely ambiguous across multiple districts.
           address_not_found — typo or made-up address; user can supply corrected address.
           zone_not_found    — geocode OK but zone could not be determined automatically.
           plot_area_needed  — ALKIS parcel not found; user must supply m² manually.
      3. Compute estimated_floor_area = GFZ × plot_area (needed by all parallel nodes).

    1 retry on transient network failure.
    """
    address = state.get("address") or ""
    mode    = state.get("mode", "chat")

    # --- Step 1: geocode + zone lookup (1 retry on transient failure) ---
    zone_result: dict | None = None
    for attempt in range(2):
        try:
            zone_result = lookup_zone_for_address(address)
            break
        except Exception as exc:
            if attempt == 0:
                logger.warning(f"resolve_address attempt 1 failed ({exc}), retrying…")
                continue
            logger.error(f"resolve_address failed after 2 attempts: {exc}")
            if mode == "form":
                return {"tool_results": {"error": "resolve_failed", "message": str(exc)}}
            raise NodeInterrupt(f"resolve_failed: {exc}") from exc

    # --- Step 2: handle error responses from the geocoder ---
    if "error" in zone_result:
        err_msg = zone_result["error"]

        # Ambiguous address — street exists in multiple districts with different postcodes.
        # The error message from lookup_zone_for_address already contains specific candidates.
        if any(kw in err_msg for kw in ("multiple", "postcodes", "ambiguous")):
            if mode == "form":
                return {"tool_results": {"error": "postcode_needed", "message": err_msg}}
            user_reply = interrupt(f"postcode_needed: {err_msg}")
            user_reply = user_reply.strip()
            # User may reply with just a postcode ("13357") or a full corrected address
            if re.search(r"\b1\d{4}\b", user_reply) and "," not in user_reply:
                address = f"{address.split(',')[0].strip()}, {user_reply}"
            else:
                address = user_reply
            zone_result = lookup_zone_for_address(address)
            if "error" in zone_result:
                if mode == "form":
                    return {"tool_results": {"error": "resolve_failed", "message": zone_result["error"]}}
                raise NodeInterrupt(f"resolve_failed: {zone_result['error']}")

        else:
            # Address genuinely not found (typo, made-up, outside Berlin, etc.).
            # Give the user a chance to correct the address instead of failing immediately.
            if mode == "form":
                return {"tool_results": {"error": "resolve_failed", "message": err_msg}}
            user_reply = interrupt(
                f"address_not_found: I couldn't find '{address}' in Berlin. "
                "Please check the spelling and enter the corrected address."
            )
            address = user_reply.strip()
            zone_result = lookup_zone_for_address(address)
            if "error" in zone_result:
                raise NodeInterrupt(
                    f"resolve_failed: I still couldn't find '{address}'. "
                    "Please start a new query with the correct address."
                )

    # Zone could not be determined from B-Plan or FNP.
    # This also happens when Photon geocoded a typo/made-up address to the wrong location.
    # Show the user what address was actually found and let them correct it OR supply a zone.
    if zone_result.get("needs_user_input"):
        display_name = zone_result.get("display_name", address)
        if mode == "form":
            return {"tool_results": {"error": "zone_not_found"}}

        user_reply = interrupt(
            f"zone_not_found: I found your address as '{display_name}' in the GDI Berlin "
            f"database, but the zone type (Bebauungsplan / FNP) could not be determined.\n\n"
            f"• If this address is correct, please provide the zone type manually "
            f"(e.g. WA, MI, MK, GE).\n"
            f"• If the address is wrong (e.g. a typo), please type the correct full address."
        )
        user_reply = user_reply.strip()

        # Zone code: 2–4 uppercase letters, optionally followed by a single digit (e.g. WA, MI2)
        if re.match(r'^[A-Za-z]{1,4}\d?$', user_reply) and len(user_reply) <= 5:
            zone_type    = user_reply.upper()
            plot_area_m2 = zone_result.get("plot_area_m2")
            gfz          = ZONE_PARAMETERS.get(zone_type, {}).get("gfz", 1.2)
            est_floor    = round(gfz * float(plot_area_m2 or 0), 2)
            logger.info(f"resolve_address: manual zone '{zone_type}' for '{display_name}'")
            return {
                "canonical_address":    display_name,
                "geocode_result":       zone_result,
                "resolved_zone":        zone_type,
                "resolved_plot_area":   float(plot_area_m2 or 0),
                "estimated_floor_area": est_floor,
                "awaiting_clarification": False,
                "clarification_type":   None,
            }
        else:
            # Corrected address — re-geocode once
            address     = user_reply
            zone_result = lookup_zone_for_address(address)
            if "error" in zone_result:
                raise NodeInterrupt(
                    f"resolve_failed: Could not geocode '{address}': {zone_result['error']}"
                )
            if zone_result.get("needs_user_input"):
                raise NodeInterrupt(
                    f"resolve_failed: Still could not determine the zone type for "
                    f"'{zone_result.get('display_name', address)}'. Please start a new query."
                )

    zone_type    = zone_result["zone_type"]
    plot_area_m2 = zone_result.get("plot_area_m2")

    # Plot area missing from ALKIS
    if not plot_area_m2:
        if mode == "form":
            return {"tool_results": {"error": "plot_area_needed"}}
        user_reply = interrupt(
            "plot_area_needed: The official plot area could not be found in the ALKIS cadastre. "
            "Please provide the plot area in m²."
        )
        try:
            plot_area_m2 = float(user_reply.strip().replace(",", "."))
        except ValueError:
            raise NodeInterrupt(
                "resolve_failed: Could not parse the plot area. "
                "Please start a new query and enter the plot area as a number (e.g. 850)."
            )

    # --- Step 3: pre-compute estimated_floor_area before fan-out ---
    gfz                  = ZONE_PARAMETERS.get(zone_type, {}).get("gfz", 1.2)
    estimated_floor_area = round(gfz * float(plot_area_m2), 2)

    logger.info(
        f"resolve_address OK: zone={zone_type}, plot={plot_area_m2}m², "
        f"est_floor={estimated_floor_area}m², address='{zone_result.get('display_name', '')}'"
    )

    return {
        "canonical_address":   zone_result["display_name"],
        "geocode_result":      zone_result,
        "resolved_zone":       zone_type,
        "resolved_plot_area":  float(plot_area_m2),
        "estimated_floor_area": estimated_floor_area,
        "awaiting_clarification": False,
        "clarification_type":   None,
    }


# ===========================================================================
# 4. PARALLEL TOOL NODES
# ===========================================================================

def run_buildable_area(state: AgentState) -> dict:
    """Calculate GRZ/GFZ buildable area. Reads resolved_zone + resolved_plot_area from state."""
    zone_type    = state.get("resolved_zone", "WA")
    plot_area_m2 = state.get("resolved_plot_area", 0.0)

    result = calculate_buildable_area.invoke({
        "plot_area_m2": plot_area_m2,
        "zone_type":    zone_type,
    })
    return {"tool_results": {"buildable_area": result}}


def run_parking(state: AgentState) -> dict:
    """
    Estimate residential units from estimated_floor_area / avg_unit_size_m2,
    then calculate mandatory bike and accessible car spaces.
    Augments the tool result with UI-expected fields (estimated_units, units_calculation).
    """
    estimated_floor_area = state.get("estimated_floor_area", 0.0)
    avg_unit_size_m2     = 75.0   # AV Stellplätze default tier

    estimated_units = max(1, round(estimated_floor_area / avg_unit_size_m2))

    result = calculate_parking_requirements.invoke({
        "use_type":         "wohnen",
        "quantity":         float(estimated_units),
        "avg_unit_size_m2": avg_unit_size_m2,
    })

    # Merge UI-expected fields that the tool does not return on its own
    result = dict(result)
    result["estimated_units"]   = estimated_units
    result["avg_unit_size_m2"]  = avg_unit_size_m2
    result["units_calculation"] = (
        f"{estimated_floor_area:.0f} m² ÷ {avg_unit_size_m2:.0f} m²/unit "
        f"= {estimated_units} units (estimate)"
    )

    return {"tool_results": {"parking": result}}


def run_construction_cost(state: AgentState) -> dict:
    """
    Estimate construction cost.
    Building type is derived from ZONE_TO_BUILDING_TYPE.
    Location (innenstadt vs standard) is inferred from the canonical address.
    """
    zone_type            = state.get("resolved_zone", "WA")
    estimated_floor_area = state.get("estimated_floor_area", 0.0)
    canonical_address    = state.get("canonical_address", "")

    building_type = ZONE_TO_BUILDING_TYPE.get(zone_type, "mehrfamilienhaus")
    location_type = "innenstadt" if _is_inner_city(canonical_address) else "standard"

    result = estimate_construction_cost.invoke({
        "building_type": building_type,
        "total_area_m2": estimated_floor_area,
        "location_type": location_type,
    })
    return {"tool_results": {"construction_cost": result}}


def run_demographics(state: AgentState) -> dict:
    """
    Fetch district demographics. Errors are swallowed — demographics are non-critical.
    Returns None in tool_results["demographics"] on any failure.
    """
    address = state.get("canonical_address") or state.get("address", "")
    try:
        result = get_demographics.invoke({"address": address})
        if "error" in result:
            logger.warning(f"Demographics returned error (swallowed): {result['error']}")
            return {"tool_results": {"demographics": None}}
        return {"tool_results": {"demographics": result}}
    except Exception as exc:
        logger.warning(f"run_demographics swallowed exception: {exc}")
        return {"tool_results": {"demographics": None}}


# ===========================================================================
# 5. MERGE_RESULTS AND SYNTHESIZE_RESPONSE
# ===========================================================================

def merge_results(state: AgentState) -> dict:
    """
    Assemble the full zoning_report dict from parallel tool_results.
    Schema matches what ui/cards.py and ui/components.py expect:
      { status, address, coordinates, alkis_props, plot, zone,
        buildable_area, parking, construction_cost, demographics }
    Saves to the address cache when this is not a cache hit.

    Special cases handled first:
      - Cache hit: zoning_report already in tool_results — return early.
      - Form-mode error from resolve_address: produce error zoning_report.
    """
    tool_results   = state.get("tool_results", {})
    geocode_result = state.get("geocode_result") or {}

    # Cache hit — zoning_report already assembled by check_address_cache
    if state.get("cache_hit") and "zoning_report" in tool_results:
        return {}   # no state change needed

    # Form-mode error from resolve_address (chat mode uses NodeInterrupt instead)
    if "error" in tool_results and "zoning_report" not in tool_results:
        return {
            "tool_results": {
                "zoning_report": {
                    "status":     "error",
                    "error_type": tool_results["error"],
                    "message":    tool_results.get("message", ""),
                }
            }
        }

    ba_result   = tool_results.get("buildable_area", {})
    park_result = tool_results.get("parking", {})
    cost_result = tool_results.get("construction_cost", {})
    demo_result = tool_results.get("demographics")

    zoning_report = {
        "status":  "complete",
        "address": state.get("canonical_address") or state.get("address", ""),
        "coordinates": {
            "lat": geocode_result.get("lat"),
            "lon": geocode_result.get("lon"),
        },
        "alkis_props": geocode_result.get("alkis_props"),
        "plot": {
            "area_m2":     state.get("resolved_plot_area"),
            "area_source": geocode_result.get("plot_area_source", "ALKIS (GDI Berlin)"),
        },
        "zone": {
            "type":            state.get("resolved_zone"),
            "source":          geocode_result.get("zone_source", ""),
            "fnp_nutzungsart": geocode_result.get("fnp_nutzungsart"),
        },
        "buildable_area":    ba_result,
        "parking":           park_result,
        "construction_cost": cost_result,
        "demographics":      demo_result,
    }

    # Persist to address cache (skip if this was already a cache hit)
    canonical = state.get("canonical_address")
    if canonical and not state.get("cache_hit"):
        cache_save(canonical, zoning_report)

    return {"tool_results": {"zoning_report": zoning_report}}


def synthesize_response(state: AgentState) -> dict:
    """
    Generate the final LLM response.

    query_type == "regulation":
        Inject RAG context into system prompt and call LLM.
    query_type == "address":
        Inject zoning_report JSON into system prompt and call LLM.
    query_type == "direct":
        bind_tools + one-shot tool call: LLM may call one tool, we execute it,
        then LLM produces the final answer.
    """
    provider   = state.get("llm_provider", DEFAULT_LLM_PROVIDER)
    language   = state.get("language", "de")
    query_type = state.get("query_type", "direct")
    llm        = get_llm(provider)

    base_prompt = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["de"])

    # --- regulation: inject RAG context ---
    if query_type == "regulation":
        context        = state.get("rag_context", "")
        system_content = base_prompt.replace("{context}", context)
        messages       = [SystemMessage(content=system_content)] + list(state["messages"])
        response       = llm.invoke(messages)

    # --- address: inject tool results JSON ---
    elif query_type == "address":
        zoning_report  = state.get("tool_results", {}).get("zoning_report", {})
        context        = (
            "Tool results (JSON — use these figures, do not recalculate):\n"
            + json.dumps(zoning_report, indent=2, ensure_ascii=False)
        )
        system_content = base_prompt.replace("{context}", context)
        messages       = [SystemMessage(content=system_content)] + list(state["messages"])
        response       = llm.invoke(messages)

    # --- direct: bind_tools, one-shot execution ---
    else:
        llm_with_tools = llm.bind_tools(TOOLS)
        system_content = base_prompt.replace("{context}", "")
        messages       = [SystemMessage(content=system_content)] + list(state["messages"])
        response       = llm_with_tools.invoke(messages)

        if response.tool_calls:
            tool_messages = []
            for tc in response.tool_calls:
                tool_result = _execute_tool(tc["name"], tc["args"])
                tool_messages.append(ToolMessage(
                    content=json.dumps(tool_result, ensure_ascii=False),
                    tool_call_id=tc["id"],
                ))
            final_messages = messages + [response] + tool_messages
            response = llm.invoke(final_messages)

    return {
        "messages":    [response],
        "token_usage": _extract_usage(response),
    }
