"""agents_kit/delivery.py — deliver what was paid for, exactly once, or tell somebody.

The three ways I have actually failed a paying customer:

  1. **Delivered nothing.** Revenue was recorded, no delivery step existed. The buyer paid and
     got silence. Nothing in the system knew anything was wrong, because the sale looked fine.

  2. **Delivered twice.** The processor retried the webhook and the buyer got two emails.
     Harmless here; if the deliverable had been a licence key or a credit top-up, it would not
     have been.

  3. **Delivered a link back to the sales page they had just bought from.** This one is my
     favourite, because it passed every test. The code collected "the venture's best URL", and
     the venture's best URL was its own landing page. To the buyer it reads exactly like a
     scam. It shipped because "a link was produced" was the success condition.

The rules encoded below:
  * Idempotent per (order, product) — a retry is a no-op, not a second delivery.
  * A deliverable must be *verified* to be a deliverable, not merely to exist.
  * NEVER fail silently. If delivery cannot happen, record it as PENDING and alert a human.
    A paid customer must never be left with nothing and no trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol


class Store(Protocol):
    def delivered(self, order_ref: str) -> bool: ...
    def mark_delivered(self, order_ref: str, to: str, links: list[str]) -> None: ...
    def mark_pending(self, order_ref: str, to: str, reason: str) -> None: ...


@dataclass(frozen=True)
class Result:
    status: str            # delivered | duplicate | pending
    links: list[str]
    reason: str = ""


def usable_links(candidates: Iterable[str], sales_pages: Iterable[str]) -> list[str]:
    """Filter candidate URLs down to ones a buyer can actually use.

    Rejects, in order of how badly each one burned me:
      * the sales page itself (and its directory/index twin)
      * `file://` and localhost paths, which resolve only on the machine that made them —
        these appear when a publisher silently falls back to a local "dry" mode
      * empties and duplicates, order preserved
    """
    blocked = set()
    for page in sales_pages:
        p = (page or "").strip()
        if not p:
            continue
        blocked.add(p)
        if p.endswith("/index.html"):
            blocked.add(p[: -len("index.html")])
        elif p.endswith("/"):
            blocked.add(p + "index.html")

    out, seen = [], set()
    for c in candidates:
        u = (c or "").strip()
        if not u or u in blocked or u in seen:
            continue
        if u.lower().startswith(("file://", "http://127.0.0.1", "http://localhost")):
            continue
        seen.add(u)
        out.append(u)
    return out


def deliver(order_ref: str, to: str, candidates: Iterable[str], sales_pages: Iterable[str],
            store: Store, send: Callable[[str, list[str]], bool]) -> Result:
    """Deliver once. Never raises.

    Note what happens when there is nothing good to send: it does NOT fall back to "send the
    least-bad link". It records PENDING so a human finishes the job. An honest pending beats a
    delivery the buyer will read as a scam — and unlike the scam, somebody finds out about it.
    """
    if store.delivered(order_ref):
        return Result("duplicate", [], "already delivered")

    if not to or "@" not in to:
        store.mark_pending(order_ref, to, "no buyer address")
        return Result("pending", [], "no buyer address")

    links = usable_links(candidates, sales_pages)
    if not links:
        store.mark_pending(order_ref, to, "no usable deliverable")
        return Result("pending", [], "no usable deliverable")

    try:
        ok = send(to, links)
    except Exception as exc:                                  # noqa: BLE001
        store.mark_pending(order_ref, to, f"send raised: {str(exc)[:120]}")
        return Result("pending", links, "send raised")

    if not ok:
        store.mark_pending(order_ref, to, "send rejected")
        return Result("pending", links, "send rejected")

    # Mark only AFTER a confirmed send, so a failure retries instead of being sealed as done.
    store.mark_delivered(order_ref, to, links)
    return Result("delivered", links)
