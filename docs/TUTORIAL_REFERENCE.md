# Tutorial Reference — Berlin Zoning Assistant Sprint 3

> This file maps every Sprint 3 implementation requirement to the exact
> LangChain Academy tutorial pattern it should follow.
> Place this file alongside SPRINT3_REFERENCE.md in the project root and
> give Claude Code this instruction:
> "Follow TUTORIAL_REFERENCE.md for coding style and patterns on every file you write."

---

## 1. AgentState — state-reducers.ipynb

Use `TypedDict` with `Annotated` for all fields that need merge behaviour.
Never overwrite — always reduce.

```python
# PATTERN from state-reducers.ipynb
import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

# Custom reducer for safe dict merging (parallel tool results)
def _merge_dicts(left: dict | None, right: dict | None) -> dict:
    if not left:
        left = {}
    if not right:
        right = {}
    return {**left, **right}

# Custom reducer for accumulating token counts
def _add_tokens(left: dict | None, right: dict | None) -> dict:
    if not left:
        left = {}
    if not right:
        right = {}
    return {k: left.get(k, 0) + right.get(k, 0) for k in set(left) | set(right)}

class AgentState(TypedDict):
    # add_messages reducer: appends, never overwrites
    messages:   Annotated[list[AnyMessage], add_messages]
    # _merge_dicts reducer: parallel nodes safely merge their results
    tool_results: Annotated[dict, _merge_dicts]
    # _add_tokens reducer: accumulates across all nodes
    token_usage:  Annotated[dict, _add_tokens]
    # Plain fields (last-write wins — only one node writes these)
    language:              str
    llm_provider:          str
    mode:                  str
    query_type:            str
    tools_needed:          list[str]
    rag_context:           str
    source_chunks:         list
    address:               str | None
    canonical_address:     str | None
    geocode_result:        dict | None
    resolved_zone:         str | None
    resolved_plot_area:    float | None
    estimated_floor_area:  float | None
    cache_hit:             bool
    awaiting_clarification: bool
    clarification_type:    str | None
```

---

## 2. SqliteSaver Checkpointer — chatbot-external-memory.ipynb

Use a file-path connection (not `:memory:`) so state survives process restarts.
Pass `check_same_thread=False` — required for Streamlit's multi-threaded environment.

```python
# PATTERN from chatbot-external-memory.ipynb
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from config import SQLITE_MEMORY_PATH   # "./memory.db"

def get_checkpointer() -> SqliteSaver:
    conn = sqlite3.connect(SQLITE_MEMORY_PATH, check_same_thread=False)
    return SqliteSaver(conn)
```

Thread IDs are passed per invocation — the checkpointer uses them as keys:
```python
config = {"configurable": {"thread_id": "some-uuid"}}
graph.invoke({"messages": [HumanMessage(content=user_input)]}, config)
```

---

## 3. Parallel Tool Fan-out with Send — map-reduce.ipynb

`Send` dispatches independent tasks in parallel. Each parallel node writes
into a reducer-backed field so concurrent writes are safe.

```python
# PATTERN from map-reduce.ipynb
from langgraph.types import Send

# The conditional edge that fans out
def fan_out_tools(state: AgentState):
    # Each Send creates an independent parallel execution
    return [Send(f"run_{tool}", state) for tool in state["tools_needed"]]

# Each parallel node writes ONLY its own key into tool_results
# The _merge_dicts reducer merges all parallel writes safely
def run_buildable_area(state: AgentState):
    result = calculate_buildable_area(...)
    return {"tool_results": {"buildable_area": result}}

def run_parking(state: AgentState):
    result = calculate_parking_requirements(...)
    return {"tool_results": {"parking": result}}

# Graph wiring — parallel nodes converge at merge_results
graph.add_conditional_edges("resolve_address", fan_out_tools,
                            ["run_buildable_area", "run_parking",
                             "run_construction_cost", "run_demographics"])
graph.add_edge("run_buildable_area", "merge_results")
graph.add_edge("run_parking",        "merge_results")
graph.add_edge("run_construction_cost", "merge_results")
graph.add_edge("run_demographics",   "merge_results")
```

---

## 4. HITL Dynamic Interrupts — dynamic-breakpoints.ipynb

Use `NodeInterrupt` (raised inside a node) for dynamic interrupts that depend
on runtime conditions. Only interrupt in chat mode — form mode returns an
error dict instead.

```python
# PATTERN from dynamic-breakpoints.ipynb
from langgraph.errors import NodeInterrupt

def resolve_address(state: AgentState):
    # ... geocoding logic ...

    if postcode_missing:
        if state["mode"] == "form":
            # Form mode: no interrupt, return error in state
            return {"tool_results": {"error": "postcode_needed"}}
        else:
            # Chat mode: interrupt and wait for user input
            raise NodeInterrupt("postcode_needed: Please provide the postcode for the address.")

    if zone_not_found:
        if state["mode"] == "form":
            return {"tool_results": {"error": "zone_not_found"}}
        else:
            raise NodeInterrupt("zone_not_found: Could not determine zoning for this address.")
```

After streaming, `ui/chat.py` checks whether the graph is paused:
```python
# PATTERN: check if interrupted after streaming
graph_state = graph.get_state(config)
if graph_state.next:                              # non-empty = interrupted
    interrupt_value = graph_state.tasks[0].interrupts[0].value
    # Show clarification UI to user
```

Resume after user provides input:
```python
# PATTERN from dynamic-breakpoints.ipynb — resume by streaming with None input
for event in graph.stream(None, config, stream_mode="values"):
    ...
```

---

## 5. Resuming After Interrupt — edit-state-human-feedback.ipynb

When the user provides clarification, update state and resume:

```python
# PATTERN from edit-state-human-feedback.ipynb

# Option A: inject user reply directly and resume
graph.update_state(config, {"address": user_clarification})
for event in graph.stream(None, config, stream_mode="values"):
    ...

# Option B: resume via Command (used in agent.py run_agent())
from langgraph.types import Command
graph.invoke(Command(resume=user_input), config)
```

---

## 6. Graph Compilation — standard pattern across all notebooks

Always compile with the checkpointer. The graph singleton is cached with
`@st.cache_resource` so it is built once per Streamlit server process.

```python
# PATTERN — consistent across all tutorial notebooks
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

def get_graph():
    builder = StateGraph(AgentState)

    # Add all nodes
    builder.add_node("route_query",         route_query)
    builder.add_node("retrieve_rag",        retrieve_rag)
    builder.add_node("check_address_cache", check_address_cache)
    builder.add_node("resolve_address",     resolve_address)
    builder.add_node("run_buildable_area",  run_buildable_area)
    builder.add_node("run_parking",         run_parking)
    builder.add_node("run_construction_cost", run_construction_cost)
    builder.add_node("run_demographics",    run_demographics)
    builder.add_node("merge_results",       merge_results)
    builder.add_node("synthesize_response", synthesize_response)

    # Edges (see graph.py for full routing logic)
    builder.add_edge(START, "route_query")
    # ... conditional edges per SPRINT3_REFERENCE.md graph diagram ...

    checkpointer = get_checkpointer()
    return builder.compile(checkpointer=checkpointer)
```

---

## 7. Streaming to Streamlit — streaming-interruption.ipynb

Use `stream_mode="values"` for full state snapshots, or `stream_mode="updates"`
for delta-only updates. For token streaming use `astream_events`.

```python
# PATTERN from streaming-interruption.ipynb

# Standard values streaming (used in run_agent)
for event in graph.stream(
    {"messages": [HumanMessage(content=user_input)]},
    config,
    stream_mode="values"
):
    last_message = event["messages"][-1]

# Token-level streaming for chat UI
async for event in graph.astream_events(input_dict, config, version="v2"):
    if event["event"] == "on_chat_model_stream" \
    and event["metadata"].get("langgraph_node") == "synthesize_response":
        chunk = event["data"]["chunk"].content
        # yield chunk to Streamlit
```

---

## 8. LLM Factory — consistent with all notebooks

All tutorial notebooks use `ChatOpenAI` from `langchain_openai`.
The factory pattern wraps provider selection so nodes never import LLMs directly.

```python
# chain/llm.py
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENAI_MODEL_ID

def get_llm(provider: str = "openai"):
    if provider == "openai":
        return ChatOpenAI(
            model=OPENAI_MODEL_ID,       # "gpt-5.2"
            openai_api_key=OPENAI_API_KEY,
            temperature=0,
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model="claude-sonnet-4-6",
            anthropic_api_key=ANTHROPIC_API_KEY,
            temperature=0,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
```

---

## 9. Trustcall — memoryschema_profile.ipynb + memoryschema_collection.ipynb + memory_agent.ipynb

Trustcall is a structured extraction library that wraps an LLM and a Pydantic
schema. It has two advantages over plain `model.with_structured_output()`:

1. **It reliably extracts partial data** — if the user only provides a street
   name but no postcode, it fills what it can and leaves the rest `None`.
2. **It can UPDATE existing structured data** using `PatchDoc` — it surgically
   patches a JSON doc instead of re-extracting everything from scratch.

### Where to use trustcall in this project

**`route_query` node** — extract `query_type`, `tools_needed`, and `address`
from the user message in one structured call. More reliable than a free-text
classifier with `max_tokens=5`.

```python
# chain/nodes.py — route_query node
from pydantic import BaseModel, Field
from trustcall import create_extractor
from typing import Literal

class QueryClassification(BaseModel):
    query_type: Literal["regulation", "address", "direct"] = Field(
        description="Type of query: regulation=BauNVO/law question, address=specific property, direct=general"
    )
    tools_needed: list[str] = Field(
        default_factory=list,
        description="Which tools to run: buildable_area, parking, construction_cost, demographics"
    )
    address: str | None = Field(
        default=None,
        description="The street address mentioned by the user, if any"
    )

# Build the extractor once (module level, not inside the node)
_classifier = create_extractor(
    get_llm(),
    tools=[QueryClassification],
    tool_choice="QueryClassification",
)

def route_query(state: AgentState) -> dict:
    last_message = state["messages"][-1].content
    result = _classifier.invoke({
        "messages": [
            SystemMessage(content=CLASSIFIER_SYSTEM),
            HumanMessage(content=last_message),
        ]
    })
    classification: QueryClassification = result["responses"][0]
    return {
        "query_type":   classification.query_type,
        "tools_needed": classification.tools_needed,
        "address":      classification.address,
    }
```

**`resolve_address` node** — extract structured address components from the
raw address string before geocoding. Handles partial input gracefully.

```python
# chain/nodes.py — inside resolve_address
from pydantic import BaseModel, Field

class AddressComponents(BaseModel):
    street:   str | None = Field(default=None, description="Street name and number")
    postcode: str | None = Field(default=None, description="5-digit Berlin postcode")
    district: str | None = Field(default=None, description="Berlin district/Bezirk")

_address_extractor = create_extractor(
    get_llm(),
    tools=[AddressComponents],
    tool_choice="AddressComponents",
)

def resolve_address(state: AgentState) -> dict:
    raw_address = state["address"]

    # Use trustcall to parse the raw string into components
    result = _address_extractor.invoke({
        "messages": [HumanMessage(content=f"Extract address components from: {raw_address}")]
    })
    components: AddressComponents = result["responses"][0]

    # Interrupt if postcode is missing (chat mode only)
    if not components.postcode:
        if state["mode"] == "form":
            return {"tool_results": {"error": "postcode_needed"}}
        else:
            raise NodeInterrupt("postcode_needed: Please provide the postcode.")

    # ... proceed with geocoding using components ...
```

**Updating the address cache** — when a record already exists and new data
comes in, use trustcall's `existing` parameter with `PatchDoc` to update only
the changed fields instead of overwriting the whole record.

```python
# PATTERN from memoryschema_collection.ipynb — updating existing structured data
tool_name = "ZoningReport"
existing = [(record_id, tool_name, existing_record)] if existing_record else None

result = trustcall_extractor.invoke(
    {"messages": [HumanMessage(content=new_data_str)]},
    {"existing": existing}   # trustcall will PatchDoc or Insert as needed
)
updated_report = result["responses"][0]
```

### The three trustcall outputs to know

```python
result = trustcall_extractor.invoke({...})

result["responses"]          # list of Pydantic model instances — the extracted data
result["messages"]           # the raw tool call messages from the LLM
result["response_metadata"]  # metadata: which tool was called (PatchDoc vs Insert)
```

### Install

```
pip install trustcall
```

---

## Notebook → Sprint 3 Feature Map (quick reference)

| Feature | Tutorial file |
|---|---|
| TypedDict state + Annotated reducers | `state-reducers.ipynb` |
| add_messages reducer | `state-reducers.ipynb` |
| SqliteSaver checkpointer | `chatbot-external-memory.ipynb` |
| thread_id config pattern | `chatbot-external-memory.ipynb` |
| Send fan-out (parallel nodes) | `map-reduce.ipynb` |
| operator.add / custom merge reducers | `map-reduce.ipynb`, `state-reducers.ipynb` |
| NodeInterrupt (dynamic HITL) | `dynamic-breakpoints.ipynb` |
| graph.get_state + .next check | `dynamic-breakpoints.ipynb` |
| graph.update_state + resume | `edit-state-human-feedback.ipynb` |
| graph.stream(None, config) resume | `breakpoints.ipynb`, `dynamic-breakpoints.ipynb` |
| stream_mode="values" | `streaming-interruption.ipynb` |
| astream_events token streaming | `streaming-interruption.ipynb` |
| graph.compile(checkpointer=) | `chatbot-external-memory.ipynb` |
| Structured extraction (route_query) | `memoryschema_profile.ipynb` |
| Partial extraction (address parsing) | `memoryschema_profile.ipynb` |
| Update existing structured data | `memoryschema_collection.ipynb` |
| create_extractor + tool_choice | `memory_agent.ipynb` |
| result["responses"] / PatchDoc | `memoryschema_collection.ipynb`, `memory_agent.ipynb` |
