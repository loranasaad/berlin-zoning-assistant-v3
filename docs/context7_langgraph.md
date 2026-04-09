# LangGraph Documentation (via Context7)

Source: `/websites/langchain_oss_python_langgraph` — High reputation, 679 code snippets, Benchmark Score: 89.51
Retrieved: 2026-04-09

---

## Overview

LangGraph is a low-level orchestration framework for building, managing, and deploying long-running, stateful agents. Key capabilities: durable execution, human-in-the-loop (HITL) interrupts, comprehensive memory via checkpointers, and flexible streaming.

---

## State Management

### TypedDict + Annotated Reducers

```python
from langgraph.graph.message import add_messages
from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # appends, never overwrites
    extra_field: int

def node(state: State):
    new_message = AIMessage("Hello!")
    return {"messages": [new_message], "extra_field": 10}

graph = StateGraph(State).add_node(node).set_entry_point("node").compile()
```

- `add_messages` reducer: appends new messages and can update existing ones by message ID.
- `operator.add`: simpler reducer that always appends.
- Fields with no reducer: last-write-wins (only safe when a single node writes them).

### MessagesState shorthand

LangGraph provides a built-in `MessagesState` for common chat patterns — it has a single `messages` field with the `add_messages` reducer pre-wired.

---

## Graph Assembly

### Basic StateGraph pattern

```python
from langgraph.graph import StateGraph, START, END

builder = StateGraph(State)
builder.add_node("node_a", node_a_fn)
builder.add_node("node_b", node_b_fn)
builder.add_edge(START, "node_a")
builder.add_edge("node_a", "node_b")
builder.add_edge("node_b", END)
graph = builder.compile()
```

### Conditional edges

```python
def router(state: State) -> str:
    if state["condition"]:
        return "node_a"
    return "node_b"

builder.add_conditional_edges(
    "entry_node",
    router,
    {"node_a": "node_a", "node_b": "node_b"},
)
```

---

## Parallel Execution — Send / Map-Reduce

Use `Send` to fan out work to parallel nodes. Each `Send` creates an independent execution with its own state snapshot. A reducer-backed field safely merges concurrent writes.

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from typing_extensions import TypedDict, Annotated
import operator

class OverallState(TypedDict):
    topic: str
    subjects: list[str]
    jokes: Annotated[list[str], operator.add]   # reducer merges parallel writes
    best_selected_joke: str

def generate_topics(state: OverallState):
    return {"subjects": ["lions", "elephants", "penguins"]}

def generate_joke(state: OverallState):
    joke_map = {
        "lions":    "Why don't lions like fast food? Because they can't catch it!",
        "elephants": "Why don't elephants use computers? They're afraid of the mouse!",
        "penguins":  "Why don't penguins like talking to strangers? They find it hard to break the ice.",
    }
    return {"jokes": [joke_map[state["subject"]]]}

def continue_to_jokes(state: OverallState):
    # Fan-out: one Send per subject, all run in parallel
    return [Send("generate_joke", {"subject": s}) for s in state["subjects"]]

def best_joke(state: OverallState):
    return {"best_selected_joke": "penguins"}

builder = StateGraph(OverallState)
builder.add_node("generate_topics", generate_topics)
builder.add_node("generate_joke",   generate_joke)
builder.add_node("best_joke",       best_joke)
builder.add_edge(START, "generate_topics")
builder.add_conditional_edges("generate_topics", continue_to_jokes, ["generate_joke"])
builder.add_edge("generate_joke", "best_joke")
builder.add_edge("best_joke", END)
graph = builder.compile()
```

**Key rule:** declare all possible target node names in the list passed to `add_conditional_edges` when using `Send`.

---

## Checkpointing (Persistence)

### SqliteSaver

```python
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver(sqlite3.connect("my.db", check_same_thread=False))
graph = builder.compile(checkpointer=checkpointer)
```

- `check_same_thread=False` — required for multi-threaded environments (e.g. Streamlit).
- `thread_id` is your persistent cursor: reusing it resumes the same checkpoint; a new value starts a fresh thread.

```python
config = {"configurable": {"thread_id": "some-uuid"}}
graph.invoke({"messages": [HumanMessage(content="Hello")]}, config)
```

### InMemorySaver (testing / dev)

```python
from langgraph.checkpoint.memory import InMemorySaver
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
```

---

## Human-in-the-Loop (HITL) — Interrupts

### `interrupt()` function (preferred)

The node calls `interrupt(payload)`, which pauses execution. The payload surfaces to the caller. Resume by passing `Command(resume=value)`.

```python
from langgraph.types import interrupt, Command

def approval_node(state: State):
    # Pause and surface a prompt to the caller
    approved = interrupt("Do you approve this action?")
    # Execution resumes here when Command(resume=value) is passed
    return {"approved": approved}
```

### Full interrupt / resume cycle

```python
import sqlite3
from typing import TypedDict
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

class FormState(TypedDict):
    age: int | None

def get_age_node(state: FormState):
    prompt = "What is your age?"
    while True:
        answer = interrupt(prompt)           # pauses; payload in result["__interrupt__"]
        if isinstance(answer, int) and answer > 0:
            return {"age": answer}
        prompt = f"'{answer}' is not a valid age. Please enter a positive number."

builder = StateGraph(FormState)
builder.add_node("collect_age", get_age_node)
builder.add_edge(START, "collect_age")
builder.add_edge("collect_age", END)

checkpointer = SqliteSaver(sqlite3.connect("forms.db"))
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "form-1"}}

# First invoke — graph pauses at interrupt()
first = graph.invoke({"age": None}, config=config)
print(first["__interrupt__"])          # surfaces the prompt

# Resume with invalid data — node re-prompts
retry = graph.invoke(Command(resume="thirty"), config=config)
print(retry["__interrupt__"])

# Resume with valid data — loop exits, state updated
final = graph.invoke(Command(resume=30), config=config)
print(final["age"])                    # 30
```

### Inspect interrupt state

```python
graph_state = graph.get_state(config)

# Is the graph interrupted?
interrupted = bool(graph_state.next)

# What is it waiting on?
interrupt_value = graph_state.tasks[0].interrupts[0].value  # if interrupted

# Inject corrected state before resuming
graph.update_state(config, {"address": "Friedrichstraße 1, 10117 Berlin"})

# Resume (streams from interrupted node)
for chunk in graph.stream(None, config, stream_mode="values"):
    ...
```

---

## Streaming

### `stream_mode="messages"` — token-by-token LLM output

Returns `(message_chunk, metadata)` tuples (or `StreamPart` dicts with `version="v2"`).

```python
# Sync — filter by node name
for chunk in graph.stream(
    {"topic": "ice cream"},
    stream_mode="messages",
    version="v2",
):
    if chunk["type"] == "messages":
        message_chunk, metadata = chunk["data"]
        if message_chunk.content and metadata["langgraph_node"] == "some_node_name":
            print(message_chunk.content, end="", flush=True)
```

```python
# Async — filter by tag
async for chunk in graph.astream(
    {"topic": "cats"},
    stream_mode="messages",
    version="v2",
):
    if chunk["type"] == "messages":
        msg, metadata = chunk["data"]
        if metadata["tags"] == ["joke"]:
            print(msg.content, end="|", flush=True)
```

### `stream_mode="values"` — full state after each step

```python
for event in graph.stream(
    {"messages": [HumanMessage(content=user_input)]},
    config,
    stream_mode="values",
):
    last_message = event["messages"][-1]
```

### `stream_mode="updates"` — state delta per node

```python
for update in graph.stream(inputs, config, stream_mode="updates"):
    node_name = list(update.keys())[0]
    node_output = update[node_name]
```

### Streaming + HITL interrupts together

```python
async for chunk in graph.astream(
    initial_input,
    stream_mode=["messages", "updates"],
    subgraphs=True,
    config=config,
    version="v2",
):
    if chunk["type"] == "messages":
        msg, _ = chunk["data"]
        if isinstance(msg, AIMessageChunk) and msg.content:
            print(msg.content, end="", flush=True)

    elif chunk["type"] == "updates":
        if "__interrupt__" in chunk["data"]:
            interrupt_info = chunk["data"]["__interrupt__"][0].value
            user_response  = get_user_input(interrupt_info)
            initial_input  = Command(resume=user_response)
            break
```

**Notes:**
- `subgraphs=True` — required for interrupt detection inside subgraphs.
- `version="v2"` — unified `StreamPart` dict format; omit for legacy tuple format.
- Interrupt payloads also surface in `chunk["interrupts"]` on `values` stream parts.

---

## API Reference Summary

Full API reference: https://langchain-ai.github.io/langgraph/reference/
Conceptual guides: https://langchain-ai.github.io/langgraph/concepts/
How-to guides: https://langchain-ai.github.io/langgraph/how-tos/
