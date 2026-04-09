# Berlin Zoning Assistant — Sprint 3 Reference

> Drop this file into a new chat with the message:  
> *"This is my Sprint 3 reference doc. I want to continue working on the Berlin Zoning Assistant."*

---

## Project Overview

A Streamlit app that helps architects, developers, and property owners understand Berlin zoning regulations and building codes. Live demo is password-protected.

**Stack:** Python 3.11, LangGraph 1.0.10, LangChain, Anthropic Claude Sonnet 4.6, ChromaDB, voyage-law-2 embeddings, SQLite, Streamlit.

**Sprint 2 (old):** Single `create_react_agent` node. Monolithic `get_full_zoning_report` tool. No memory across sessions.

**Sprint 3 (current):** Explicit `StateGraph` with parallel tool nodes, HITL interrupts, SQLite memory, multi-LLM support, and a new Quick Report form tab.

---

## Folder Structure

```
berlin-zoning-assistant/
│
├── app.py                    ← 1-line entry point: from ui.app import main; main()
├── config.py                 ← Secrets, constants, model IDs, feature flags
├── requirements.txt
├── memory.db                 ← SQLite — auto-created at runtime
├── chroma_db/                ← ChromaDB vector store — auto-created at runtime
│
├── chain/                    ← All LangGraph logic (fully rewritten in Sprint 3)
│   ├── state.py              ← AgentState TypedDict + reducers
│   ├── graph.py              ← Graph assembly: nodes, edges, compile
│   ├── nodes.py              ← All node functions
│   ├── agent.py              ← Public API: run_agent(), run_form_agent(), get_graph()
│   ├── memory.py             ← SqliteSaver checkpointer + address_cache table
│   ├── llm.py                ← LLM factory: get_llm("anthropic" | "openai")
│   └── prompts.py            ← SYSTEM_PROMPTS, CLASSIFIER_SYSTEM, TOOLS list
│
├── tools/                    ← LangChain @tool functions — UNCHANGED from Sprint 2
│   ├── buildable_area.py     ← calculate_buildable_area (GRZ/GFZ, BauNVO §17-19)
│   ├── parking.py            ← calculate_parking_requirements (AV Stellplätze 2021)
│   ├── construction_cost.py  ← estimate_construction_cost, get_construction_price_index
│   ├── demographics.py       ← get_demographics, get_district_from_address
│   ├── fisbroker.py          ← lookup_zone_for_address (GDI Berlin APIs + Nominatim)
│   └── zoning_report.py      ← get_full_zoning_report — RETIRED, kept for reference only
│
├── rag/                      ← RAG pipeline — UNCHANGED from Sprint 2
│   ├── embeddings.py         ← get_or_create_vector_store() (@st.cache_resource)
│   ├── loader.py             ← PDF loading + chunking
│   └── retriever.py          ← retrieve_and_format() — classify, translate, retrieve
│
├── data/
│   ├── docs/                 ← Source PDFs (BauO, BauNVO, AV Stellplätze, etc.)
│   └── zoning_rules.py       ← ZONE_PARAMETERS, SETBACK_RULES, ZONE_TO_BUILDING_TYPE,
│                                INNER_CITY_DISTRICTS, SPECIAL_REQUIREMENTS, SETBACK_DEFAULT
│
└── ui/                       ← Streamlit UI
    ├── app.py                ← Two-tab layout (Chat + Quick Report) + handoff logic
    ├── chat.py               ← Chat rendering, input handling, interrupt/resume
    ├── sidebar.py            ← Language, LLM provider selector, cost tracker
    ├── components.py         ← render_chat_message(), render_technical_details() — UNCHANGED
    ├── cards.py              ← render_full_report() — UNCHANGED
    ├── strings.py            ← All UI strings (de/en) — UNCHANGED
    └── rate_limiter.py       ← check_rate_limit() — UNCHANGED
```

---

## Graph Architecture

```
START
  └─► route_query
        ├─ "regulation" ──► retrieve_rag ──► synthesize_response ──► END
        │
        ├─ "address" ───► check_address_cache
        │                       ├─ cache hit ──────────────────────────────────► merge_results
        │                       └─ cache miss ──► resolve_address               │
        │                                            ├─ error (form mode) ──────► merge_results
        │                                            ├─ HITL interrupt ──────────► [paused]
        │                                            │    └─ resume ──► resolve_address (retry)
        │                                            └─ success
        │                                                 └─ Send × tools_needed (parallel)
        │                                                       ├─ run_buildable_area ─────────┐
        │                                                       ├─ run_parking ────────────────┤
        │                                                       ├─ run_construction_cost ──────┤
        │                                                       └─ run_demographics ───────────┘
        │                                                                                       │
        │                                                                                       ▼
        │                                                                               merge_results
        │                                                                                ├─ form ──► END
        │                                                                                └─ chat ──► synthesize_response ──► END
        │
        └─ "direct" ────► synthesize_response ──► END
                          (LLM uses bind_tools, one-shot tool call)
```

### Node summary

| Node | What it does |
|---|---|
| `route_query` | LLM classifier (CLASSIFIER_SYSTEM, max_tokens=5). Sets `query_type`, `tools_needed`, `address`. Form mode skips this. |
| `retrieve_rag` | Calls `retriever.retrieve_and_format()`. Populates `rag_context` + `source_chunks`. |
| `check_address_cache` | SQLite lookup. Exact match → fuzzy 35-char prefix → ambiguous check. Cache hit loads full `tool_results`. |
| `resolve_address` | Nominatim geocode + GDI Berlin FIS-Broker. 1 retry on transient failure. Computes `estimated_floor_area = GFZ × plot_area` before fan-out. |
| `run_buildable_area` | Calls `calculate_buildable_area`. Reads `resolved_zone` + `resolved_plot_area` from state. |
| `run_parking` | Calls `calculate_parking_requirements`. Uses `estimated_floor_area / avg_unit_size_m2` for unit estimate. |
| `run_construction_cost` | Calls `estimate_construction_cost`. Uses `ZONE_TO_BUILDING_TYPE` + `INNER_CITY_DISTRICTS` lookup. |
| `run_demographics` | Calls `get_demographics`. Errors are swallowed (non-critical). |
| `merge_results` | Assembles full `zoning_report` dict (matching `cards.py` schema). Saves to address cache if not a cache hit. |
| `synthesize_response` | LLM call. Injects RAG context or tool results JSON into system prompt. Direct queries: `bind_tools` + one-shot execution. |

---

## AgentState

```python
class AgentState(TypedDict):
    messages:              Annotated[list[BaseMessage], add_messages]
    language:              str           # "de" | "en"
    llm_provider:          str           # "anthropic" | "openai"
    mode:                  str           # "chat" | "form"
    query_type:            str           # "regulation" | "address" | "direct"
    tools_needed:          list[str]     # parallel nodes to spawn
    rag_context:           str
    source_chunks:         list
    address:               str | None
    canonical_address:     str | None    # Nominatim display_name
    geocode_result:        dict | None
    resolved_zone:         str | None    # e.g. "WA", "MI", "GE"
    resolved_plot_area:    float | None
    estimated_floor_area:  float | None  # GFZ × plot_area, set in resolve_address
    cache_hit:             bool
    awaiting_clarification: bool
    clarification_type:    str | None    # "postcode_needed"|"zone_not_found"|"plot_area_needed"
    tool_results:          Annotated[dict, _merge_dicts]   # parallel merge reducer
    token_usage:           Annotated[dict, _add_tokens]    # accumulating reducer
```

---

## Key Design Decisions

### Memory
- **Two layers in one SQLite file** (`memory.db`): `SqliteSaver` checkpointer tables (managed by LangGraph) + custom `address_cache` table (managed by `chain/memory.py`).
- **Checkpointer** = conversation persistence across sessions, keyed by `thread_id`.
- **Address cache** = skip all API calls on repeat queries. Canonical key = Nominatim `display_name`. Lookup: exact normalised match → 35-char fuzzy prefix → ambiguous detection.
- `thread_id` lives in `st.session_state`. Changing LLM provider resets `thread_id`.

### Parallel tool execution
- `resolve_address` computes `estimated_floor_area = GFZ × plot_area` and stores it in state **before** the Send fan-out. This makes all 4 tool nodes truly independent — no node waits for another.
- `tool_results` uses `_merge_dicts` reducer so parallel writes are safely merged.
- `[Send(f"run_{t}", state) for t in tools_needed]` fans out; all converge at `merge_results`.

### HITL (Human-in-the-Loop)
- Uses `interrupt()` from `langgraph.types` — **chat mode only**.
- Form mode returns an error dict in `tool_results` instead of interrupting.
- Three clarification types: `postcode_needed` | `zone_not_found` | `plot_area_needed`.
- After streaming, `chat.py` checks `graph.get_state(config).next` — if non-empty, interrupted. Interrupt message is in `state.tasks[0].interrupts[0].value`.
- Next user message: `run_agent(user_input, resuming=True)` → `Command(resume=user_input)`.
- `st.session_state.awaiting_clarification` tracks whether we're in HITL state.

### Form mode (Quick Report tab)
- Requires postcode (validated as `^1\d{4}$` — Berlin postcodes) to prevent ambiguity.
- Calls `run_form_agent()` — synchronous `graph.invoke()`, returns final state dict.
- Skips `synthesize_response` entirely. UI renders `cards.py` components directly from `tool_results["zoning_report"]`.
- "Continue in Chat →" handoff: creates new `thread_id`, seeds checkpointer via `graph.update_state()` with the report already in state so follow-up questions work without re-running tools.

### Multi-LLM
- `get_llm(provider)` in `chain/llm.py` returns `ChatAnthropic` or `ChatOpenAI`.
- Sidebar radio button selects provider. Stored in `st.session_state.llm_provider`.

### LangSmith
- Auto-configured in `config.py` if `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` are set.
- Sets `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` env vars at import time.

### Graph singleton
- `get_graph()` in `agent.py` is `@st.cache_resource` — built once, shared across all Streamlit sessions. The `SqliteSaver` connection uses `check_same_thread=False` for Streamlit's multi-threaded environment.

### Entry point
- Root `app.py` is a one-liner: `from ui.app import main; main()`.
- All real logic is in `ui/app.py`. Run with `streamlit run app.py`.

### Unchanged from Sprint 2
- All `tools/` files (pure Python `@tool` functions).
- All `rag/` files.
- `data/zoning_rules.py`.
- `ui/components.py`, `ui/cards.py`, `ui/strings.py`, `ui/rate_limiter.py`.
- `tools/zoning_report.py` exists but is no longer called by the graph (retired).

---

## Config additions (Sprint 3)

```python
OPENAI_API_KEY    = _get_secret("OPENAI_API_KEY")
OPENAI_MODEL_ID   = "gpt-4o-mini"
SQLITE_MEMORY_PATH = "./memory.db"
LLM_PROVIDERS = {
    "Anthropic (Claude)":   "anthropic",
    "OpenAI (GPT-4o mini)": "openai",
}
DEFAULT_LLM_PROVIDER = "anthropic"
# LangSmith auto-configured at import if env vars are set
```

## New dependencies (Sprint 3)

```
langchain-openai>=0.3.0
openai>=1.0.0
langsmith>=0.2.0
```

---

## What is NOT done yet

- No unit tests.
- `retrieve_and_format()` in `rag/retriever.py` still does its own classification step (cheap, 5 tokens) even though `route_query` already classified — minor redundancy, not worth fixing now.
- OpenAI streaming token counting may differ slightly from Anthropic (different `usage_metadata` field names) — worth testing.
