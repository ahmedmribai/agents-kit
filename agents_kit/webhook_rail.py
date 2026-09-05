"""agents_kit/webhook_rail.py — a payment webhook that cannot silently lose money.

Every failure mode here is one I hit in production, in the order I hit it.

    1. The webhook was registered against the WRONG SERVICE. It had never fired once.
    2. The signing secret was empty, so verification returned False and every call 401'd —
       money arrived at the processor, the app recorded nothing, the buyer got nothing.
    3. Retries double-counted, because "did we already handle this order?" was never asked.
    4. Test-mode orders booked as real income, so the dashboard showed revenue that did not
       exist and every downstream gate keyed off a lie.

The rail below is ~120 lines and closes all four. Copy it whole.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Callable, Protocol


class AlreadyHandled(Exception):
    """Raised by a Ledger when an event id has been seen before."""


class Ledger(Protocol):
    """Your storage. Two operations, both of which must be atomic."""

    def seen(self, event_id: str) -> bool: ...
    def record(self, event_id: str, amount: float, currency: str, live: bool) -> None: ...


@dataclass(frozen=True)
class Event:
    """A normalised payment event. `live` is the single most important field on it."""

    id: str
    kind: str
    amount: float
    currency: str
    email: str
    live: bool          # False for processor test-mode. NEVER book these as income.
    reference: str      # your own id (venture/product/customer) from checkout metadata
    raw: dict

    @property
    def is_refund(self) -> bool:
        return self.kind in ("order_refunded", "subscription_payment_refunded")


def verify(raw_body: bytes, signature: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 check over the RAW body.

    Three rules that are easy to get wrong:

    * Verify the raw bytes, not a re-serialised dict. `json.loads` then `json.dumps` will
      reorder keys and change whitespace, and the signature will never match again.
    * An empty secret returns False. It must never mean "skip the check" — an internet-facing
      revenue route that mints on an unverified call is a free-money endpoint for anyone who
      finds it.
    * Compare with `hmac.compare_digest`, not `==`, so the comparison does not leak the
      expected digest one byte at a time.
    """
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body or b"", hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def parse(raw_body: bytes, event_name: str) -> Event | None:
    """Normalise a Lemon Squeezy payload. Adapt `attributes` for another processor.

    Returns None rather than raising: a malformed body is a 400, not a 500, and it must not
    take down the listener that healthy retries depend on.
    """
    try:
        payload = json.loads((raw_body or b"").decode("utf-8", "replace"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    data = payload.get("data") or {}
    attrs = data.get("attributes") or {}
    meta = payload.get("meta") or {}
    custom = meta.get("custom_data") or {}

    total = attrs.get("total")
    try:
        amount = round(float(total) / 100.0, 2) if total is not None else 0.0
    except (TypeError, ValueError):
        amount = 0.0

    return Event(
        id=str(data.get("id") or attrs.get("identifier") or "").strip(),
        kind=(event_name or meta.get("event_name") or "").strip(),
        amount=amount,
        currency=str(attrs.get("currency") or "USD").upper(),
        email=str(attrs.get("user_email") or "").strip(),
        # Missing test_mode is treated as LIVE. A processor always sends it; a payload without
        # it is not a test order, and defaulting to "test" would hide real income.
        live=not _truthy(attrs.get("test_mode")),
        reference=str(custom.get("reference") or custom.get("venture_id") or "").strip(),
        raw=payload,
    )


def _truthy(value) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "t")


def handle(raw_body: bytes, signature: str, event_name: str, secret: str,
           ledger: Ledger, fulfil: Callable[[Event], None]) -> tuple[int, dict]:
    """The whole rail. Returns (http_status, body) — wire it straight into your handler.

    Order matters and is not negotiable:
      verify → parse → dedupe → record → fulfil

    Fulfilment runs LAST and its failure does not roll back the recording. A sale you recorded
    but failed to deliver is a support ticket; a sale you delivered but failed to record is a
    hole in your books that nothing will ever surface.
    """
    if not verify(raw_body, signature, secret):
        return 401, {"error": "bad signature"}

    event = parse(raw_body, event_name)
    if event is None or not event.id:
        return 400, {"error": "unparseable"}

    if ledger.seen(event.id):
        # 200, not 409: the processor is retrying and a non-2xx makes it retry harder.
        return 200, {"status": "duplicate", "id": event.id}

    amount = -event.amount if event.is_refund else event.amount
    ledger.record(event.id, amount, event.currency, event.live)

    try:
        fulfil(event)
    except Exception as exc:                                  # noqa: BLE001 — reported, not raised
        return 200, {"status": "recorded", "fulfilment": f"pending: {exc}"[:200]}

    return 200, {"status": "ok", "recorded": amount, "live": event.live}
