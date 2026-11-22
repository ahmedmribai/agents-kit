"""Security and malformed-input regression tests for public helpers."""
import hashlib
import hmac
import json

from agents_kit import delivery, webhook_rail

SECRET = "test-signing-secret"


def _signed(payload):
    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, signature


def _payload():
    return {
        "meta": {"event_name": "order_created", "custom_data": {"reference": "42"}},
        "data": {
            "id": "evt_1",
            "attributes": {
                "total": 2500,
                "test_mode": False,
                "currency": "USD",
                "user_email": "buyer@example.com",
            },
        },
    }


def test_webhook_rejects_missing_test_mode_instead_of_assuming_live():
    payload = _payload()
    del payload["data"]["attributes"]["test_mode"]
    raw, signature = _signed(payload)
    status, body = webhook_rail.handle(
        raw, signature, "order_created", SECRET,
        type("Ledger", (), {"seen": lambda self, event_id: False,
                            "record": lambda self, *args: None})(),
        lambda event: None,
    )
    assert status == 400
    assert body == {"error": "unparseable"}


def test_webhook_rejects_malformed_nested_objects():
    for key, value in (("data", "not-an-object"), ("meta", [])):
        payload = _payload()
        payload[key] = value
        raw, signature = _signed(payload)
        assert webhook_rail.parse(raw, "order_created") is None


def test_webhook_rejects_non_finite_amounts():
    for amount in (float("nan"), float("inf"), float("-inf")):
        payload = _payload()
        payload["data"]["attributes"]["total"] = amount
        raw, signature = _signed(payload)
        assert webhook_rail.parse(raw, "order_created") is None


def test_webhook_accepts_explicit_test_mode_and_marks_event_not_live():
    raw, signature = _signed(_payload())
    event = webhook_rail.parse(raw, "order_created")
    assert event is not None
    assert event.live is True

    payload = _payload()
    payload["data"]["attributes"]["test_mode"] = "true"
    raw, signature = _signed(payload)
    event = webhook_rail.parse(raw, "order_created")
    assert event is not None
    assert event.live is False



def test_webhook_rejects_missing_or_invalid_currency_codes():
    for currency in (None, "", "US", "USDD", "USD!"):
        payload = _payload()
        if currency is None:
            del payload["data"]["attributes"]["currency"]
        else:
            payload["data"]["attributes"]["currency"] = currency
        raw, _ = _signed(payload)
        assert webhook_rail.parse(raw, "order_created") is None


def test_webhook_rejects_negative_payment_and_refund_amounts():
    payload = _payload()
    payload["data"]["attributes"]["total"] = -1
    raw, _ = _signed(payload)
    assert webhook_rail.parse(raw, "order_created") is None

    payload = _payload()
    payload["meta"]["event_name"] = "order_refunded"
    payload["data"]["attributes"]["refunded_amount"] = -1
    raw, _ = _signed(payload)
    assert webhook_rail.parse(raw, "order_refunded") is None


def test_delivery_rejects_non_https_local_and_credential_urls():
    candidates = [
        "https://cdn.example.com/guide.pdf",
        "http://cdn.example.com/insecure.pdf",
        "file:///tmp/guide.pdf",
        "javascript:alert(1)",
        "https://localhost/guide.pdf",
        "https://127.0.0.1/guide.pdf",
        "https://user:password@cdn.example.com/guide.pdf",
        "https://cdn.example.com:8443/guide.pdf",
    ]
    assert delivery.usable_links(candidates, []) == ["https://cdn.example.com/guide.pdf"]


def test_delivery_blocks_sales_page_aliases_across_scheme_and_query():
    candidates = [
        "https://shop.example.com/sale?campaign=1",
        "https://shop.example.com/sale/index.html",
        "https://cdn.example.com/download/guide.pdf",
    ]
    sales_pages = ["http://shop.example.com/sale/"]
    assert delivery.usable_links(candidates, sales_pages) == [
        "https://cdn.example.com/download/guide.pdf"
    ]
