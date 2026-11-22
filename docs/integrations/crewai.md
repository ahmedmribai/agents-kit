# CrewAI task guardrails

Agents Kit can provide deterministic checks for CrewAI task outputs using CrewAI's
function-based `guardrail` callback. CrewAI is an optional application dependency; the
adapter itself does not import CrewAI and the core package remains standard-library-only.

CrewAI documents function guardrails as callables that receive a `TaskOutput` and return
a `(bool, Any)` pair: success plus either the output or feedback for the agent.
See the [CrewAI task guardrails documentation](https://docs.crewai.com/en/concepts/tasks#task-guardrails).

## Install

```bash
python -m pip install agents-toolkit crewai
```

## Use the adapter

```python
from crewai import Agent, Crew, Task
from agents_kit.integrations.crewai import build_task_guardrail

def non_empty(result):
    return bool(str(getattr(result, "raw", result)).strip())

def within_limit(result):
    return len(str(getattr(result, "raw", result))) <= 4000

guardrail = build_task_guardrail([non_empty, within_limit])

writer = Agent(
    role="Technical writer",
    goal="Produce concise, useful technical explanations",
    backstory="You write clear technical documentation.",
)

task = Task(
    description="Explain why webhook handlers need idempotency.",
    expected_output="A concise explanation with one example.",
    agent=writer,
    guardrail=guardrail,
    guardrail_max_retries=2,
)

crew = Crew(agents=[writer], tasks=[task])
result = crew.kickoff()
print(result)
```

Every configured check must pass. If a validator raises or returns an invalid measurement,
the adapter returns failure feedback rather than treating missing evidence as success.
CrewAI controls retry behavior through `guardrail_max_retries`; choose a retry count
appropriate to your task and cost budget.

The included checks are illustrative. Replace them with deterministic checks for your
application's actual output contract. This is not a factuality guarantee.
