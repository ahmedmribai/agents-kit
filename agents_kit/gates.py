"""agents_kit/gates.py — distinguish a measured failure from a failed measurement.

A gate may block on evidence. A judge outage is UNKNOWN, not a negative judgement.
Callers choose whether UNKNOWN is allowed or blocked; security-sensitive workflows
should use unknown_policy="block".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Callable, Sequence


class Verdict(str, Enum):
    PASS = "pass"
    BLOCK = "block"
    UNKNOWN = "unknown"


@dataclass
class Judgement:
    """One judge's answer. error=True means the judge never produced a verdict."""

    ok: bool = False
    error: bool = False


@dataclass
class GateResult:
    verdict: Verdict
    score: float
    threshold: float
    judged: int
    errors: int
    reasons: list[str] = field(default_factory=list)
    unknown_policy: str = "allow"

    @property
    def allowed(self) -> bool:
        """Return the decision after applying the caller's UNKNOWN policy."""
        return self.verdict is Verdict.PASS or (
            self.verdict is Verdict.UNKNOWN and self.unknown_policy == "allow"
        )


def evaluate(judges: Sequence[Callable[[], Judgement]], threshold: float = 0.5,
             enabled: bool = True, unknown_policy: str = "allow") -> GateResult:
    """Run every judge and return an explicit verdict.

    unknown_policy is "allow" (the backwards-compatible default) or "block".
    Use "block" for authorization, security, payments, compliance, and irreversible
    actions. enabled=False is measure-only mode and never blocks.
    """
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError("threshold must be a finite number between 0 and 1")
    if not math.isfinite(float(threshold)) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be a finite number between 0 and 1")

    policy_valid = unknown_policy in ("allow", "block")
    policy = unknown_policy if policy_valid else "block"
    judged = errors = passed = 0
    reasons: list[str] = []
    if not policy_valid:
        reasons.append("invalid unknown_policy; UNKNOWN will fail closed")

    for judge in judges:
        try:
            result = judge()
        except Exception as exc:  # noqa: BLE001
            errors += 1
            reasons.append(f"judge raised: {str(exc)[:80]}")
            continue
        if not isinstance(result, Judgement):
            errors += 1
            reasons.append("judge returned an invalid result")
            continue
        if result.error:
            errors += 1
            reasons.append("judge could not run")
            continue
        judged += 1
        passed += 1 if bool(result.ok) else 0

    if judged == 0:
        if not enabled:
            return GateResult(Verdict.PASS, 0.0, threshold, 0, errors,
                              reasons + ["gate in measure-only mode"], policy)
        return GateResult(Verdict.UNKNOWN, 0.0, threshold, 0, errors,
                          reasons or ["no judge produced a verdict"], policy)

    score = round(passed / judged, 4)
    if not enabled:
        return GateResult(Verdict.PASS, score, threshold, judged, errors,
                          reasons + ["gate in measure-only mode"], policy)
    if errors:
        # A partial score is useful telemetry, but it is not complete evidence.
        return GateResult(Verdict.UNKNOWN, score, threshold, judged, errors, reasons, policy)
    verdict = Verdict.PASS if score >= threshold else Verdict.BLOCK
    return GateResult(verdict, score, threshold, judged, errors, reasons, policy)
