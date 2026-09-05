"""agents_kit/staleness.py — catch the machinery that runs and produces nothing.

This is the failure mode that hides best, because every signal you normally watch says fine.

For three weeks a discovery loop logged, every single tick:

    discovery scan ok :: candidates=17 recorded=0

Status `ok`. No exception, no error rate, no latency spike, uptime 100%, dashboards green.
It evaluated the same 17 candidates and recorded none of them, forever. Alongside it a
perception loop logged `new=0` for seven days and a falsification loop logged `refuted=0`
on every tick it had ever run.

Health checks answer "did it run?". Almost nothing answers "did running it change anything?" —
and for an autonomous system, a step that changes nothing is indistinguishable from a step
that never ran, except that it also burns your budget.

Track the OUTPUT DELTA, and alarm when it is zero N times running.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class _Track:
    zero_streak: int = 0
    last_output_at: float = 0.0
    total_ticks: int = 0
    total_output: float = 0.0


@dataclass
class StalenessMonitor:
    """Records per-task output volume and reports which tasks have gone inert.

    >>> m = StalenessMonitor(patience=3)
    >>> for _ in range(3): _ = m.record("discovery", produced=0)
    >>> m.stale()
    ['discovery']

    `produced` is whatever "this tick did something" means for the task: rows written, bytes
    published, decisions taken. It must be a count of NEW output — an idempotent upsert that
    rewrites the same 7 rows every tick produces 0, not 7. Getting this wrong is exactly how
    `found=7 stored=7` read as healthy for a month.
    """

    patience: int = 5
    _tracks: dict[str, _Track] = field(default_factory=dict)

    def record(self, task: str, produced: float) -> bool:
        """Log one tick. Returns True if `task` is now considered stale."""
        t = self._tracks.setdefault(task, _Track())
        t.total_ticks += 1
        if produced > 0:
            t.zero_streak = 0
            t.last_output_at = time.time()
            t.total_output += produced
        else:
            t.zero_streak += 1
        return t.zero_streak >= self.patience

    def stale(self) -> list[str]:
        """Every task whose last `patience` ticks all produced nothing."""
        return sorted(k for k, t in self._tracks.items() if t.zero_streak >= self.patience)

    def report(self) -> list[dict]:
        """Full picture, worst first — drop this straight into a daily brief."""
        rows = [
            {
                "task": k,
                "zero_streak": t.zero_streak,
                "ticks": t.total_ticks,
                "total_output": t.total_output,
                "idle_hours": round((time.time() - t.last_output_at) / 3600.0, 1)
                if t.last_output_at else None,
                "stale": t.zero_streak >= self.patience,
            }
            for k, t in self._tracks.items()
        ]
        return sorted(rows, key=lambda r: (-r["zero_streak"], r["task"]))
