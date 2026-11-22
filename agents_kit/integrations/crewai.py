"""CrewAI task-guardrail adapter.

CrewAI is optional. This adapter returns the (success, feedback) tuple expected by
CrewAI function-based task guardrails without importing CrewAI in the core package.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from agents_kit.integrations.openai_agents import evaluate_output


def build_task_guardrail(
    checks: Sequence[Callable[[Any], bool]],
    *,
    unknown_feedback: str = "Output validation could not be completed.",
):
    """Return a CrewAI-compatible function guardrail.

    The returned callable accepts a TaskOutput-like object and returns (bool, feedback).
    All configured checks must pass. Missing/failed checks block and return feedback.
    """
    def guardrail(task_output: Any) -> tuple[bool, Any]:
        result = evaluate_output(task_output, checks)
        if result.allowed:
            return True, task_output
        if result.verdict.value == "unknown":
            return False, unknown_feedback
        reasons = "; ".join(result.reasons) or "One or more output checks failed."
        return False, reasons

    return guardrail
