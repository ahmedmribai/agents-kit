"""agents_kit/webhook_rail.py — a payment webhook rail with explicit adapter contracts.

The handler verifies raw bytes, parses a provider payload, deduplicates, records, then fulfils.
Persistent atomicity and recovery are responsibilities of the caller's ledger/worker.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass
from typing import Callable, Protocol


class AlreadyHandled(Exception):
    """Raised by a Ledger when an event id has already been inserted."""


class Ledger(Protocol):
    """Persistent storage; record() must enforce event-ID uniqueness atomically."""

    def seen(self, event_id: str) -> bool: ...
    def record(self, event_id: str, amount: float, currency: str, live: bool) -> None:
        """Insert under a UNIQUE event_id constraint; raise AlreadyHandled on conflict."""
        ...


@dataclass(frozen=True)
class Event:
    """A normalized payment event."""

    id: str
    kind: str
    amount: float
    currency: str
    email: str
    live: bool
    reference: str
    raw: dict

    @property
    def is_refund(self) -> bool:
        return self.kind in ("order_refunded", "subscription_payment_refunded")


def verify(raw_body: bytes, signature: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 check over the exact raw request bytes."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body or b"", hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def _parse_test_mode(value) -> bool | None:
    """Parse an explicit provider test-mode flag; unknown/missing is not treated as live."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "t"):
            return True
        if normalized in ("0", "false", "no", "f"):
            return False
    return None


def parse(raw_body: bytes, event_name: str) -> Event | None:
    """Normalize a Lemon Squeezy payload; return None for malformed/ambiguous input.

    Adapt the provider-specific fields and signature verification for another processor.
    """
    try:
        payload = json.loads((raw_body or b"").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None

    data = payload.get("data")
    meta = payload.get("meta", {})
    if meta is None:
        meta = {}
    if not isinstance(data, dict) or not isinstance(meta, dict):
        return None
    attrs = data.get("attributes", {})
    custom = meta.get("custom_data", {})
    if attrs is None:
        attrs = {}
    if custom is None:
        custom = {}
    if not isinstance(attrs, dict) or not isinstance(custom, dict):
        return None

    test_mode = _parse_test_mode(attrs.get("test_mode"))
    if test_mode is None:
        return None

    kind = str(event_name or meta.get("event_name") or "").strip()
    payload_kind = str(meta.get("event_name") or "").strip()
    if not kind or (event_name and payload_kind and kind != payload_kind):
        return None

    resource_id = str(data.get("id") or "").strip()
    if not resource_id:
        return None

    # Lemon Squeezy's data.id identifies the underlying order/subscription resource,
    # not a unique webhook delivery. Keying retries by it would discard later events
    # (for example order_refunded after order_created) on the same resource. The
    # provider does not include a distinct delivery UUID in its documented payload,
    # so use a stable fingerprint of the event name and exact signed bytes.
    event_id = hashlib.sha256(kind.encode("utf-8") + b"\0" + (raw_body or b"")).hexdigest()

    # Refund events use the actual refunded amount, which can be partial, rather than
    # the original order or invoice total.
    is_refund = kind in ("order_refunded", "subscription_payment_refunded")
    total = attrs.get("refunded_amount") if is_refund else attrs.get("total")
    if total is None or isinstance(total, bool):
        return None
    try:
        amount = round(float(total) / 100.0, 2)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(amount) or amount < 0:
        return None

    currency_value = attrs.get("currency")
    if (not isinstance(currency_value, str) or len(currency_value) != 3
            or not currency_value.isascii() or not currency_value.isalpha()):
        return None

    return Event(
        id=event_id,
        kind=kind,
        amount=amount,
        currency=currency_value.upper(),
        email=str(attrs.get("user_email") or "").strip(),
        live=not test_mode,
        reference=str(custom.get("reference") or custom.get("venture_id") or "").strip(),
        raw=payload,
    )


def handle(raw_body: bytes, signature: str, event_name: str, secret: str,
           ledger: Ledger, fulfil: Callable[[Event], None]) -> tuple[int, dict]:
    """Verify → parse → dedupe → record → fulfil.

    The ledger's record() must atomically enforce event-ID uniqueness. The seen() check is
    only an optimization. A durable outbox/recovery worker is required to recover fulfilment
    after a crash between recording and completing the downstream action.
    """
    if not verify(raw_body, signature, secret):
        return 401, {"error": "bad signature"}

    event = parse(raw_body, event_name)
    if event is None:
        return 400, {"error": "unparseable"}

    if ledger.seen(event.id):
        return 200, {"status": "duplicate", "id": event.id}

    amount = -event.amount if event.is_refund else event.amount
    try:
        ledger.record(event.id, amount, event.currency, event.live)
    except AlreadyHandled:
        return 200, {"status": "duplicate", "id": event.id}

    try:
        fulfil(event)
    except Exception as exc:  # noqa: BLE001 — reported as pending; caller must recover durably
        return 200, {"status": "recorded", "fulfilment": f"pending: {str(exc)[:200]}"}

    return 200, {"status": "ok", "recorded": amount, "live": event.live}
