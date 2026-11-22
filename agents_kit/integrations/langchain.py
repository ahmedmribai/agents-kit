"""LangChain/LangGraph agent middleware adapter.

LangChain is optional. Imports are lazy and occur only when the middleware factory is used.
"""
from __future__ import annotations

from typing import Any, Callable, Sequence

from agents_kit.integrations.openai_agents import evaluate_output


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def build_output_gate_middleware(
    checks: Sequence[Callable[[Any], bool]],
    *,
    unknown_policy: str = "block",
    blocked_message: str = "The response could not pass the configured quality checks.",
):
    """Create LangChain agent after-model middleware that gates final text responses.

    Tool-call messages are left untouched. A failed or UNKNOWN final response is followed
    by a deterministic blocked message and the graph jumps to its end node. This is an
    output-quality gate, not a substitute for tool authorization or pre-execution checks.
    """
    if unknown_policy not in ("allow", "block"):
        raise ValueError("unknown_policy must be 'allow' or 'block'")

    try:
        from langchain.agents.middleware import after_model, hook_config
        from langchain.messages import AIMessage
    except ImportError as exc:
        raise RuntimeError(
            "Install the optional dependency with: pip install langchain"
        ) from exc

    @after_model
    @hook_config(can_jump_to=["end"])
    def agents_kit_output_gate(state, runtime):
        messages = state.get("messages", [])
        if not messages:
            return None
        last = messages[-1]
        # Tool calls are part of the agent loop; validate only a final assistant message.
        if getattr(last, "tool_calls", None):
            return None
        result = evaluate_output(_message_text(last), checks)
        if result.allowed:
            return None
        if result.verdict.value == "unknown" and unknown_policy == "allow":
            return None
        return {
            "messages": [AIMessage(content=blocked_message)],
            "jump_to": "end",
        }

    return agents_kit_output_gate
