# LangChain / LangGraph output middleware

Agents Kit can run deterministic quality checks after a LangChain agent's model response.
The optional adapter uses LangChain's `after_model` middleware hook and leaves tool-call
messages untouched. On a failed or blocked UNKNOWN result, it adds a deterministic rejection
message and jumps to the graph's end node.

See the official [custom middleware guide](https://docs.langchain.com/oss/python/langchain/middleware/custom)
for hook lifecycle and the `after_model` / `hook_config` APIs.

## Install

```bash
python -m pip install agents-toolkit langchain
```

## Use

```python
from langchain.agents import create_agent
from agents_kit.integrations.langchain import build_output_gate_middleware

def non_empty(text):
    return bool(text.strip())

def within_limit(text):
    return len(text) <= 4000

gate = build_output_gate_middleware(
    [non_empty, within_limit],
    unknown_policy="block",
)

agent = create_agent(
    model="your-provider:your-model",
    tools=[],
    middleware=[gate],
)

result = agent.invoke({"messages": [{"role": "user", "content": "Explain idempotency."}]})
print(result["messages"][-1].content)
```

## Scope and safety

This is a final-text output gate. It does not authorize tools, validate tool arguments, or
prevent side effects that occurred before the final response. Use tool-level or pre-execution
authorization for those controls. The adapter blocks UNKNOWN by default; setting
`unknown_policy="allow"` restores pass-through behavior for unavailable validators.

The example checks are illustrative and do not establish factual correctness. Use
application-specific deterministic validators and test the behavior against your pinned
LangChain version.
