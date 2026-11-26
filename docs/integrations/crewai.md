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

## Pre-tool authorization is a separate concern

This guide covers **task-output guardrails**: checks that run on a task's produced output.
They are not a pre-dispatch tool authorization hook and do not prevent a tool from being
called in the first place.

For a pre-tool decision, the application must own the authorization policy and identity
source, wrap the side-effecting operation, and call
`agents_kit.gates.evaluate(..., unknown_policy="block")` immediately before dispatch.
The wrapper must invoke the underlying tool only when the result is allowed, and must
fail closed on UNKNOWN, evaluator errors, and invalid results.

Agents Kit does not claim that CrewAI exposes a native universal pre-tool hook. A narrowly
scoped, offline application-owned example with a side-effect counter is being coordinated in
[issue #10](https://github.com/ahmedmribai/agents-kit/issues/10). Any CrewAI-specific
lifecycle integration must be separately verified against an exact CrewAI version.

## Pre-dispatch enforcement: coverage and trust boundaries

A task-output guardrail is not a pre-tool authorization control. An application-owned wrapper
can enforce a gate only for calls that actually pass through that wrapper. Do not infer that
wrapping one tool or testing one invocation path protects every way an agent can reach a tool.

For any application-owned pre-dispatch example:

- enumerate the dispatch entry points the application exposes and route each through the
  same gate; test each path with a side-effect counter;
- evaluate the exact arguments that will be dispatched, and reject any post-decision
  mutation or re-use of a decision for a different invocation;
- record the decision before dispatch in a host-owned store, bound to a unique call ID,
  run/agent identity, tool, canonical argument hash, policy version, verdict, and reason;
- keep the authoritative writer and any signing key outside the agent's write/access domain;
  a log line or an in-memory test double is not proof of tamper-resistant production storage.

CrewAI PR [#7372](https://github.com/crewAIInc/crewAI/pull/7372) describes three previously
missed tool-dispatch paths in Flow `ToolAction.run`, the OpenAI Agents adapter, and the
LangGraph adapter. That PR is not treated here as merged or released. Verify exact framework
versions and execution paths rather than claiming universal hook coverage.

### Distributed budgets and uncertain dispatch outcomes

Agents Kit does not provide a distributed budget ledger or reservation service. If an
application enforces a hard shared budget, reservation must be atomic in durable state outside
the worker/agent's write domain. A concurrency test must race two workers against the authoritative reservation store
for the last unit and prove exactly one reserves it and exactly one reaches dispatch. The
reservation/spend record should bind the run, agent, tool, canonical argument hash, approving
principal, policy ID/version, and unique call ID. A worker-owned counter is not an authoritative
reservation store. A HALF-OPEN circuit-breaker probe is also a dispatch and must pass the same
pre-dispatch authorization and reservation checks.

A dispatch timeout is an unknown outcome, not permission to retry. Keep the reservation
associated with the original call until a run coordinator reconciles the provider using the
original request ID. Lease expiry is a liveness signal, not a release decision. If the outcome
is still unknown at the deadline, pause the run and notify the owner with the request ID and
last confirmed state; stopping the run must not release the reservation or authorize a second
dispatch. Test this by killing the worker after dispatch, advancing beyond the deadline, and
asserting zero redispatches and exactly one notification.
