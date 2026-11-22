"""Adapters for the OpenAI Agents SDK.

The OpenAI SDK is optional and is imported only when building its guardrail object.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from agents_kit import gates


def evaluate_output(output: Any, checks: Sequence[Callable[[Any], bool]]) -> gates.GateResult:
    """Evaluate deterministic output checks with a fail-closed policy.

    Every check must pass. If any check raises, the aggregate verdict is UNKNOWN and
    remains blocked. The partial score is retained for diagnostics.
    """
    judges = [
        (lambda check=check: gates.Judgement(ok=bool(check(output))))
        for check in checks
    ]
    return gates.evaluate(judges, threshold=1.0, unknown_policy="block")


def build_output_guardrail(checks: Sequence[Callable[[Any], bool]]):
    """Build an OpenAI Agents SDK output guardrail from ordinary Python checks."""
    try:
        from agents import GuardrailFunctionOutput
        from agents.decorators import output_guardrail
    except ImportError as exc:
        raise RuntimeError(
            "Install the optional dependency with: pip install openai-agents"
        ) from exc

    @output_guardrail
    async def quality_guardrail(context, agent, output):
        result = evaluate_output(output, checks)
        return GuardrailFunctionOutput(
            output_info={
                "verdict": result.verdict.value,
                "score": result.score,
                "judged": result.judged,
                "errors": result.errors,
                "reasons": result.reasons,
            },
            tripwire_triggered=not result.allowed,
        )

    return quality_guardrail
