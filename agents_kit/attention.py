"""agents_kit/attention.py — spend a tick's compute on what is worth doing, and prove nothing starves.

An agent with more things to do than budget needs an arbiter. Mine scored bids as

    score = (0.4*value + 0.4*info + 0.2*urgency) / cost

and spent greedily under a per-tick budget. Reasonable. It also silently disabled a third of
the system for months.

The 13 registered bids cost 6.5 units in total. The budget was 3.0. Because greedy-by-ratio
picks cheap work first, the three most expensive bids — the deep reasoning, the simulation,
the dreaming, i.e. the entire reason the system was interesting — won **0 of 81** consecutive
arbitrations. Not "rarely": never. No flag said so, no log said so; the one number that
disabled them was a tunable nobody thought of as a switch.

Two defences, both here:
  * `starving()` names any bid that has never won. Alarm on it.
  * urgency rises the longer a bid goes unchosen, so an expensive bid eventually outbids
    cheap ones instead of losing on ratio forever.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Bid:
    """One candidate action competing for this tick."""

    name: str
    run: object                    # callable, invoked if chosen
    value: float = 0.5             # expected payoff, 0..1
    info: float = 0.5              # expected information gain, 0..1
    cost: float = 1.0              # budget units consumed if it runs
    stale_after_s: float = 7 * 86400   # urgency saturates at 1.0 after this long unchosen


@dataclass
class Arbiter:
    budget: float = 5.0
    w_value: float = 0.4
    w_info: float = 0.4
    w_urgency: float = 0.2
    min_score: float = 0.05
    _last_run: dict[str, float] = field(default_factory=dict)
    _wins: dict[str, int] = field(default_factory=dict)
    _seen: set[str] = field(default_factory=set)

    def urgency(self, bid: Bid) -> float:
        last = self._last_run.get(bid.name)
        if last is None:
            return 1.0                      # never run ⇒ maximally urgent
        return min(1.0, (time.time() - last) / max(1.0, bid.stale_after_s))

    def score(self, bid: Bid) -> float:
        raw = (self.w_value * bid.value + self.w_info * bid.info
               + self.w_urgency * self.urgency(bid))
        return raw / max(0.01, bid.cost)

    def choose(self, bids: list[Bid]) -> list[Bid]:
        """Greedy under budget. Pure — does not run anything."""
        for b in bids:
            self._seen.add(b.name)
        ranked = sorted(bids, key=self.score, reverse=True)
        chosen, spent = [], 0.0
        for bid in ranked:
            if self.score(bid) < self.min_score:
                continue
            if spent + bid.cost > self.budget:
                continue
            chosen.append(bid)
            spent += bid.cost
        return chosen

    def run(self, bids: list[Bid]) -> dict:
        chosen = self.choose(bids)
        results = {}
        for bid in chosen:
            self._last_run[bid.name] = time.time()
            self._wins[bid.name] = self._wins.get(bid.name, 0) + 1
            try:
                results[bid.name] = bid.run() if callable(bid.run) else None
            except Exception as exc:                          # noqa: BLE001
                results[bid.name] = f"error: {str(exc)[:120]}"
        return {"chosen": [b.name for b in chosen], "results": results,
                "starving": self.starving()}

    def starving(self) -> list[str]:
        """Bids that have competed but NEVER won. If this is non-empty, either raise the
        budget or delete the bid — do not leave it registered and dead."""
        return sorted(n for n in self._seen if not self._wins.get(n))

    def feasible(self, bids: list[Bid]) -> dict:
        """Sanity check to run at startup, not in production. Compares the budget against what
        the registered bids actually cost, and warns when the most expensive can never fit."""
        total = sum(b.cost for b in bids)
        unaffordable = sorted(b.name for b in bids if b.cost > self.budget)
        return {"budget": self.budget, "total_cost": round(total, 2),
                "coverage": round(self.budget / total, 2) if total else 1.0,
                "never_affordable": unaffordable}
