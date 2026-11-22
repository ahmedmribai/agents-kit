# OpenAI Agents SDK integration

Agents Kit's quality-gate module can be connected to the OpenAI Agents SDK without adding
an OpenAI SDK dependency to the core package.

The SDK exposes input/output guardrails and lifecycle hooks. An output guardrail receives
the final agent output and can raise a tripwire to reject it. See the
[official guardrails guide](https://openai.github.io/openai-agents-python/guardrails/)
and [lifecycle hooks reference](https://openai.github.io/openai-agents-python/ref/lifecycle/).

## Install

```bash
python -m pip install agents-toolkit openai-agents
```

## Attach an Agents Kit quality gate

The optional adapter at [agents_kit/integrations/openai_agents.py](../../agents_kit/integrations/openai_agents.py)
provides a small factory. It converts ordinary Python checks into Agents Kit Judgements and
maps the GateResult to the SDK's GuardrailFunctionOutput. The SDK is imported lazily, so
importing the integration module does not require the optional dependency.

```python
from agents import Agent, Runner
from examples.openai_agents_sdk_guardrail import (
    build_output_guardrail,
    non_empty_output,
    within_character_limit,
)

quality_guardrail = build_output_guardrail([
    non_empty_output,
    within_character_limit,
])

agent = Agent(
    name="Support assistant",
    instructions="Answer the user's question clearly and concisely.",
    output_guardrails=[quality_guardrail],
)

result = Runner.run_sync(agent, "How do I reset my password?")
print(result.final_output)
```

The adapter uses a threshold of 1.0, so every configured check must pass. If a check raises,
the overall result is UNKNOWN and the adapter blocks it using `unknown_policy="block"`.
This avoids silently treating an unavailable check as a successful quality measurement.

## Important execution boundary

OpenAI Agents SDK output guardrails run after the final agent output has been produced.
They do not prevent earlier model calls or tool side effects. If a check must prevent a
dangerous tool invocation, attach a suitable input tool guardrail to that function tool
instead. Agent-level input/output guardrails do not automatically cover every handoff or
every tool call; follow the SDK's documented workflow boundaries.

The sample checks are intentionally simple. Replace them with domain-specific deterministic
checks. Do not treat a character-count or non-empty check as a substitute for factual,
security, authorization, or policy validation.

## Keep the core dependency-free

Only the integration application needs `openai-agents`. Agents Kit's core package remains
standard-library-only. This guide is a supported integration pattern, not a claim that the
SDK itself is maintained by the Agents Kit project.
