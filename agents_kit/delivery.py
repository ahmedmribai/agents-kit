"""agents_kit/delivery.py — deliver verified HTTPS artefacts and expose failure states.

This helper provides sequential idempotency. A production Store and downstream sender must
supply durable, atomic coordination for concurrent workers and ambiguous network outcomes.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol
from urllib.parse import unquote, urlsplit


class Store(Protocol):
    def delivered(self, order_ref: str) -> bool: ...
    def mark_delivered(self, order_ref: str, to: str, links: list[str]) -> None: ...
    def mark_pending(self, order_ref: str, to: str, reason: str) -> None: ...


@dataclass(frozen=True)
class Result:
    status: str            # delivered | duplicate | pending
    links: list[str]
    reason: str = ""


def _url_identity(value: str) -> tuple[str, str] | None:
    """Return a comparable host/path key for an HTTP(S) URL, or None if malformed."""
    try:
        parts = urlsplit(value.strip())
        scheme = parts.scheme.lower()
        host = (parts.hostname or "").lower().rstrip(".")
        if scheme not in ("http", "https") or not host:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        port = parts.port
        if (scheme == "https" and port not in (None, 443)) or (scheme == "http" and port not in (None, 80)):
            return None
    except (ValueError, TypeError):
        return None

    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid")):
        return None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return None

    path = unquote(parts.path or "/")
    if path.endswith("/index.html"):
        path = path[:-len("index.html")]
    path = path.rstrip("/") or "/"
    return host, path


def usable_links(candidates: Iterable[str], sales_pages: Iterable[str]) -> list[str]:
    """Keep unique public HTTPS links, excluding sales pages and their index aliases.

    This validates URL shape, not the safety or availability of the destination's content.
    """
    blocked = {
        identity for page in sales_pages
        if page and (identity := _url_identity(page)) is not None
    }

    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = (candidate or "").strip()
        if not url or url in seen:
            continue
        try:
            parts = urlsplit(url)
        except ValueError:
            continue
        if parts.scheme.lower() != "https":
            continue
        identity = _url_identity(url)
        if identity is None or identity in blocked:
            continue
        seen.add(url)
        out.append(url)
    return out


def deliver(order_ref: str, to: str, candidates: Iterable[str], sales_pages: Iterable[str],
            store: Store, send: Callable[[str, list[str]], bool]) -> Result:
    """Attempt delivery once in this process and return an explicit outcome.

    Store operations are allowed to raise: persistence failures must not be disguised as a
    successful or durable pending result. The delivered() check is not a distributed lock.
    """
    if store.delivered(order_ref):
        return Result("duplicate", [], "already delivered")

    if not to or "@" not in to:
        store.mark_pending(order_ref, to, "no buyer address")
        return Result("pending", [], "no buyer address")

    links = usable_links(candidates, sales_pages)
    if not links:
        store.mark_pending(order_ref, to, "no usable HTTPS deliverable")
        return Result("pending", [], "no usable HTTPS deliverable")

    try:
        ok = send(to, links)
    except Exception as exc:  # noqa: BLE001
        store.mark_pending(order_ref, to, f"send raised: {str(exc)[:120]}")
        return Result("pending", links, "send raised")

    if not ok:
        store.mark_pending(order_ref, to, "send rejected")
        return Result("pending", links, "send rejected")

    # Mark only after confirmed send. Provider idempotency is still needed for ambiguous
    # timeouts/crashes between the provider accepting the send and this write succeeding.
    store.mark_delivered(order_ref, to, links)
    return Result("delivered", links)
