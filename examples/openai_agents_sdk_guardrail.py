"""Optional OpenAI Agents SDK adapter example.

Install the optional integration dependencies:
    python -m pip install agents-toolkit openai-agents

Running an agent also requires the SDK's configured model provider and credentials.
The core Agents Kit package does not depend on the OpenAI SDK.
"""
from __future__ import annotations

from typing import Any

from agents_kit.integrations.openai_agents import build_output_guardrail


def non_empty_output(output: Any) -> bool:
    """Example check: reject an empty final answer."""
    return bool(str(output).strip())


def within_character_limit(output: Any, limit: int = 4000) -> bool:
    """Example check: enforce an application-specific output-size limit."""
    return len(str(output)) <= limit


if __name__ == "__main__":
    print("Import build_output_guardrail(checks) into an OpenAI Agents SDK application.")
    print("Example: build_output_guardrail([non_empty_output, within_character_limit])")
