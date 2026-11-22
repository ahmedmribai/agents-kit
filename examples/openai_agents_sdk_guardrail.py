"""Optional OpenAI Agents SDK adapter for Agents Kit quality gates.

Install the optional integration dependencies:
    python -m pip install agents-toolkit openai-agents

This file demonstrates wiring only; running a model also requires the SDK's configured
model provider and credentials. The core Agents Kit package does not depend on that SDK.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from agents_kit import gates


def build_output_guardrail(checks: Sequence[Callable[[Any], bool]]):
    """Build an OpenAI Agents SDK output guardrail from ordinary Python checks.

    Any failed check blocks because threshold=1.0. Any check that raises makes the
    aggregate verdict UNKNOWN; unknown_policy="block" therefore fails closed.
    """
    try:
        from agents import GuardrailFunctionOutput
        from agents.decorators import output_guardrail
    except ImportError as exc:
        raise RuntimeError(
            "Install the optional dependency with: pip install openai-agents"
        ) from exc

    @output_guardrail
    async def quality_guardrail(context, agent, output):
        judges = [
            (lambda check=check: gates.Judgement(ok=bool(check(output))))
            for check in checks
        ]
        result = gates.evaluate(
            judges,
            threshold=1.0,
            unknown_policy="block",
        )
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


def non_empty_output(output: Any) -> bool:
    """Example check: reject an empty final answer."""
    return bool(str(output).strip())


def within_character_limit(output: Any, limit: int = 4000) -> bool:
    """Example check: enforce an application-specific output-size limit."""
    return len(str(output)) <= limit


if __name__ == "__main__":
    print("Import build_output_guardrail(checks) into an OpenAI Agents SDK application.")
    print("Example: build_output_guardrail([non_empty_output, within_character_limit])")
