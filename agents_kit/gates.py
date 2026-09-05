"""agents_kit/gates.py — quality gates that fail OPEN on "couldn't measure" and CLOSED on "measured bad".

The bug this exists to prevent cost me weeks of a pipeline that looked healthy and shipped
nothing.

A gate scored products with an LLM panel. Its judge looked like this:

    try:
        verdict = llm.judge(...)
        return {"success": verdict["success"], "reuse": verdict["reuse"]}
    except Exception:
        return {"success": False, "reuse": False}      # <-- the bug

That `except` conflates two completely different facts: "the user said no" and "I could not
ask the user". When the LLM pool started returning 429s, every judgement became a rejection,
the score pinned to 0.0, the threshold was 0.5, and the gate blocked every launch — forever.
The logs showed a busy, green system. 47 blocks, 3 passes, and nobody could see why.

Worse, it was self-sealing: no launch → no page → no traffic → no real usage data → the gate
fell back to the broken proxy → no launch.

The rule: a gate may only block on evidence. Absence of evidence is UNKNOWN, and UNKNOWN
must pass through while being loudly recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence


class Verdict(str, Enum):
    PASS = "pass"        # measured, and good enough
    BLOCK = "block"      # measured, and not good enough
    UNKNOWN = "unknown"  # could not measure — passes through, but says so


@dataclass
class Judgement:
    """One judge's answer. `error=True` means the judge never ran."""

    ok: bool = False
    error: bool = False


@dataclass
class GateResult:
    verdict: Verdict
    score: float
    threshold: float
    judged: int              # how many judgements actually happened
    errors: int              # how many failed to run
    reasons: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        """UNKNOWN is allowed. This is the whole point of the module."""
        return self.verdict in (Verdict.PASS, Verdict.UNKNOWN)


def evaluate(judges: Sequence[Callable[[], Judgement]], threshold: float = 0.5,
             enabled: bool = True) -> GateResult:
    """Run every judge, then decide. Never raises.

    `enabled=False` gives you measure-only mode: the score is still computed and returned, but
    the verdict is always PASS. Run a new gate this way for a week before you let it block —
    you want to know what it *would* have done while it can't hurt you.
    """
    judged = errors = passed = 0
    reasons: list[str] = []

    for judge in judges:
        try:
            j = judge()
        except Exception as exc:                              # noqa: BLE001
            errors += 1
            reasons.append(f"judge raised: {str(exc)[:80]}")
            continue
        if j.error:
            errors += 1
            reasons.append("judge could not run")
            continue
        judged += 1
        passed += 1 if j.ok else 0

    if judged == 0:
        # Nothing was actually measured. Do NOT score this 0.0 and block on it.
        return GateResult(Verdict.UNKNOWN, 0.0, threshold, 0, errors,
                          reasons or ["no judge produced a verdict"])

    score = round(passed / judged, 4)
    if not enabled:
        return GateResult(Verdict.PASS, score, threshold, judged, errors,
                          ["gate in measure-only mode"])
    verdict = Verdict.PASS if score >= threshold else Verdict.BLOCK
    return GateResult(verdict, score, threshold, judged, errors, reasons)
