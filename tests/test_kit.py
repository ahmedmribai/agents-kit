"""Every claim the kit makes, as an executable test.

These are the regression tests for the production incidents the kit exists to prevent.
If you change a module, these must stay green.
"""

import hashlib
import hmac
import json
import math
import time

from agents_kit import attention, delivery, gates, staleness, webhook_rail
from agents_kit.integrations.openai_agents import evaluate_output

SECRET = "test-signing-secret"


def _signed(payload: dict) -> tuple[bytes, str]:
    raw = json.dumps(payload).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def _order(oid="ord_1", total=9899, test_mode=False, email="buyer@example.com", refunded_amount=None):
    return {"meta": {"custom_data": {"reference": "42"}},
            "data": {"id": oid, "attributes": {"total": total,
                                               "refunded_amount": total if refunded_amount is None else refunded_amount,
                                               "test_mode": test_mode, "user_email": email,
                                               "currency": "USD"}}}


class FakeLedger:
    def __init__(self):
        self.rows = {}

    def seen(self, event_id):
        return event_id in self.rows

    def record(self, event_id, amount, currency, live):
        # Simulate a database UNIQUE constraint: the insert is atomic.
        if event_id in self.rows:
            raise webhook_rail.AlreadyHandled(event_id)
        self.rows[event_id] = {"amount": amount, "currency": currency, "live": live}


# -- webhook rail -------------------------------------------------------------

def test_bad_signature_is_rejected():
    raw, _ = _signed(_order())
    status, _ = webhook_rail.handle(raw, "deadbeef", "order_created", SECRET,
                                    FakeLedger(), lambda e: None)
    assert status == 401


def test_empty_secret_never_passes():
    """An unset secret must not mean 'skip verification'."""
    raw, sig = _signed(_order())
    assert webhook_rail.verify(raw, sig, "") is False
    status, _ = webhook_rail.handle(raw, sig, "order_created", "", FakeLedger(), lambda e: None)
    assert status == 401


def test_good_signature_records_once():
    raw, sig = _signed(_order())
    ledger = FakeLedger()
    status, body = webhook_rail.handle(raw, sig, "order_created", SECRET, ledger, lambda e: None)
    assert status == 200 and body["recorded"] == 98.99
    event = webhook_rail.parse(raw, "order_created")
    assert event is not None and ledger.rows[event.id]["live"] is True


def test_retry_does_not_double_count():
    raw, sig = _signed(_order())
    ledger = FakeLedger()
    webhook_rail.handle(raw, sig, "order_created", SECRET, ledger, lambda e: None)
    status, body = webhook_rail.handle(raw, sig, "order_created", SECRET, ledger, lambda e: None)
    assert status == 200 and body["status"] == "duplicate"
    assert len(ledger.rows) == 1


def test_test_mode_is_not_live_revenue():
    """The rehearsal must never be reportable as income."""
    raw, sig = _signed(_order(test_mode=True))
    ledger = FakeLedger()
    webhook_rail.handle(raw, sig, "order_created", SECRET, ledger, lambda e: None)
    event = webhook_rail.parse(raw, "order_created")
    assert event is not None and ledger.rows[event.id]["live"] is False


def test_refund_books_negative():
    raw, sig = _signed(_order(oid="ord_r"))
    ledger = FakeLedger()
    webhook_rail.handle(raw, sig, "order_refunded", SECRET, ledger, lambda e: None)
    event = webhook_rail.parse(raw, "order_refunded")
    assert event is not None and ledger.rows[event.id]["amount"] == -98.99


def test_fulfilment_failure_still_records_the_sale():
    def boom(_event):
        raise RuntimeError("mail server down")

    raw, sig = _signed(_order())
    ledger = FakeLedger()
    status, body = webhook_rail.handle(raw, sig, "order_created", SECRET, ledger, boom)
    assert status == 200 and "pending" in body["fulfilment"]
    event = webhook_rail.parse(raw, "order_created")
    assert event is not None and ledger.rows[event.id]["amount"] == 98.99  # still recorded


def test_malformed_body_is_400_not_a_crash():
    sig = hmac.new(SECRET.encode(), b"not json", hashlib.sha256).hexdigest()
    status, _ = webhook_rail.handle(b"not json", sig, "order_created", SECRET,
                                    FakeLedger(), lambda e: None)
    assert status == 400


def test_concurrent_duplicate_is_rejected_by_atomic_ledger_insert():
    """Two requests can both pass seen(); the unique insert must still deduplicate."""
    class RacingLedger(FakeLedger):
        def seen(self, event_id):
            return False  # Simulate both requests checking before either inserts.

    raw, sig = _signed(_order())
    ledger = RacingLedger()
    first, _ = webhook_rail.handle(raw, sig, "order_created", SECRET, ledger, lambda e: None)
    second, body = webhook_rail.handle(raw, sig, "order_created", SECRET, ledger, lambda e: None)
    assert first == second == 200
    assert body["status"] == "duplicate"
    assert len(ledger.rows) == 1


def test_same_resource_can_have_distinct_webhook_event_types():
    """An order-created event must not suppress a later refund for the same order."""
    payload = _order(oid="same-order", refunded_amount=2500)
    created_raw, created_sig = _signed(payload)
    refunded_raw, refunded_sig = _signed(payload)
    ledger = FakeLedger()

    webhook_rail.handle(created_raw, created_sig, "order_created", SECRET, ledger, lambda e: None)
    status, body = webhook_rail.handle(
        refunded_raw, refunded_sig, "order_refunded", SECRET, ledger, lambda e: None
    )

    assert status == 200 and body["status"] == "ok"
    assert len(ledger.rows) == 2
    assert sorted(row["amount"] for row in ledger.rows.values()) == [-25.0, 98.99]


def test_changed_payload_for_same_resource_is_a_distinct_event():
    first_raw, _ = _signed(_order(oid="subscription-1", total=1000))
    second_raw, _ = _signed(_order(oid="subscription-1", total=1200))
    first = webhook_rail.parse(first_raw, "subscription_updated")
    second = webhook_rail.parse(second_raw, "subscription_updated")
    assert first is not None and second is not None
    assert first.id != second.id


def test_webhook_header_and_payload_event_names_must_match():
    payload = _order()
    payload["meta"]["event_name"] = "order_created"
    raw, _ = _signed(payload)
    assert webhook_rail.parse(raw, "order_refunded") is None


def test_partial_refund_uses_refunded_amount_not_original_order_total():
    raw, sig = _signed(_order(oid="partial-refund", total=9899, refunded_amount=2500))
    ledger = FakeLedger()
    status, body = webhook_rail.handle(raw, sig, "order_refunded", SECRET, ledger, lambda e: None)
    event = webhook_rail.parse(raw, "order_refunded")
    assert status == 200 and body["recorded"] == -25.0
    assert event is not None and ledger.rows[event.id]["amount"] == -25.0


# -- gates --------------------------------------------------------------------

def _judge(ok=True, error=False):
    return lambda: gates.Judgement(ok=ok, error=error)


def test_gate_blocks_a_measured_low_score():
    r = gates.evaluate([_judge(ok=False)] * 4, threshold=0.5)
    assert r.verdict is gates.Verdict.BLOCK and r.allowed is False


def test_gate_passes_a_measured_high_score():
    r = gates.evaluate([_judge(ok=True)] * 4, threshold=0.5)
    assert r.verdict is gates.Verdict.PASS and r.allowed is True


def test_gate_returns_unknown_when_every_judge_errors():
    """THE regression: an LLM outage must not read as unanimous rejection."""
    r = gates.evaluate([_judge(error=True)] * 5, threshold=0.5)
    assert r.verdict is gates.Verdict.UNKNOWN
    assert r.allowed is True            # unknown passes through
    assert r.errors == 5 and r.judged == 0


def test_gate_unknown_when_a_judge_raises():
    def raising():
        raise TimeoutError("429 rate limited")

    r = gates.evaluate([raising] * 3, threshold=0.5)
    assert r.verdict is gates.Verdict.UNKNOWN and r.allowed is True


def test_partial_errors_keep_diagnostic_score_but_return_unknown():
    judges = [_judge(ok=True), _judge(ok=True), _judge(error=True)]
    allowed = gates.evaluate(judges, threshold=0.5, unknown_policy="allow")
    blocked = gates.evaluate(judges, threshold=0.5, unknown_policy="block")
    assert allowed.judged == 2 and allowed.errors == 1
    assert allowed.score == 1.0 and allowed.verdict is gates.Verdict.UNKNOWN
    assert allowed.allowed is True
    assert blocked.allowed is False


def test_measure_only_mode_never_blocks():
    r = gates.evaluate([_judge(ok=False)] * 4, threshold=0.5, enabled=False)
    assert r.verdict is gates.Verdict.PASS and r.score == 0.0



def test_gate_unknown_can_be_configured_to_fail_closed():
    result = gates.evaluate([_judge(error=True)] * 2, unknown_policy="block")
    assert result.verdict is gates.Verdict.UNKNOWN
    assert result.allowed is False


def test_measure_only_mode_never_blocks_even_when_every_judge_fails():
    result = gates.evaluate([_judge(error=True)], enabled=False, unknown_policy="block")
    assert result.verdict is gates.Verdict.PASS
    assert result.allowed is True


def test_invalid_judge_result_is_recorded_as_measurement_error():
    result = gates.evaluate([lambda: None], unknown_policy="block")
    assert result.verdict is gates.Verdict.UNKNOWN
    assert result.errors == 1
    assert result.allowed is False


def test_invalid_unknown_policy_fails_closed():
    result = gates.evaluate([_judge(error=True)], unknown_policy="permit")
    assert result.verdict is gates.Verdict.UNKNOWN
    assert result.allowed is False



def test_openai_agents_adapter_passes_when_all_output_checks_pass():
    result = evaluate_output("A valid answer.", [lambda output: bool(output), lambda output: len(output) < 100])
    assert result.verdict is gates.Verdict.PASS
    assert result.allowed is True


def test_openai_agents_adapter_blocks_when_a_check_fails():
    result = evaluate_output("x", [lambda output: len(output) > 10])
    assert result.verdict is gates.Verdict.BLOCK
    assert result.allowed is False


def test_openai_agents_adapter_fails_closed_when_a_check_raises():
    def unavailable(output):
        raise TimeoutError("validator unavailable")

    result = evaluate_output("answer", [lambda output: True, unavailable])
    assert result.verdict is gates.Verdict.UNKNOWN
    assert result.allowed is False


def test_openai_agents_adapter_fails_closed_without_checks():
    result = evaluate_output("answer", [])
    assert result.verdict is gates.Verdict.UNKNOWN
    assert result.allowed is False



def test_gate_rejects_invalid_threshold_configuration():
    for threshold in (-0.1, 1.1, float("nan"), True):
        try:
            gates.evaluate([_judge(ok=True)], threshold=threshold)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid threshold was accepted")


# -- staleness ----------------------------------------------------------------

def test_zero_output_streak_is_detected():
    m = staleness.StalenessMonitor(patience=3)
    for _ in range(2):
        assert m.record("discovery", produced=0) is False
    assert m.record("discovery", produced=0) is True
    assert m.stale() == ["discovery"]


def test_output_resets_the_streak():
    m = staleness.StalenessMonitor(patience=2)
    m.record("perception", 0)
    m.record("perception", 5)
    assert m.stale() == []


def test_productive_task_never_flagged():
    m = staleness.StalenessMonitor(patience=2)
    for _ in range(10):
        m.record("publisher", produced=3)
    assert m.stale() == [] and m.report()[0]["total_output"] == 30


def test_report_ranks_worst_first():
    m = staleness.StalenessMonitor(patience=2)
    for _ in range(4):
        m.record("dead", 0)
    m.record("alive", 1)
    assert m.report()[0]["task"] == "dead" and m.report()[0]["stale"] is True



def test_staleness_rejects_invalid_patience_and_output_counts():
    for patience in (0, -1, True):
        try:
            staleness.StalenessMonitor(patience=patience)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid patience was accepted")

    monitor = staleness.StalenessMonitor()
    for produced in (-1, float("nan"), float("inf"), True):
        try:
            monitor.record("worker", produced)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid output measurement was accepted")


# -- attention ----------------------------------------------------------------

def test_expensive_bid_is_reported_as_starving():
    """THE regression: a bid that can never win must be visible, not silently dead."""
    a = attention.Arbiter(budget=3.0)
    bids = [attention.Bid("cheap", lambda: 1, cost=0.3),
            attention.Bid("expensive", lambda: 1, cost=5.0)]
    for _ in range(5):
        a.run(bids)
    assert "expensive" in a.starving()


def test_feasibility_check_flags_an_unaffordable_bid():
    a = attention.Arbiter(budget=3.0)
    bids = [attention.Bid("a", lambda: 1, cost=1.0), attention.Bid("b", lambda: 1, cost=4.0)]
    f = a.feasible(bids)
    assert f["never_affordable"] == ["b"] and f["total_cost"] == 5.0


def test_budget_is_respected():
    a = attention.Arbiter(budget=1.0)
    bids = [attention.Bid("b%d" % i, lambda: 1, cost=0.4) for i in range(5)]
    assert len(a.choose(bids)) == 2


def test_urgency_lets_a_neglected_bid_eventually_win():
    a = attention.Arbiter(budget=1.0)
    fresh = attention.Bid("fresh", lambda: 1, cost=0.5, value=0.9, info=0.9)
    neglected = attention.Bid("neglected", lambda: 1, cost=0.5, value=0.1, info=0.1)
    a._last_run["fresh"] = time.time()          # just ran
    # neglected has never run, so its urgency is 1.0
    assert "neglected" in [b.name for b in a.choose([fresh, neglected])]


def test_a_raising_bid_does_not_kill_the_tick():
    def boom():
        raise ValueError("nope")

    a = attention.Arbiter(budget=5.0)
    out = a.run([attention.Bid("bad", boom, cost=1.0),
                 attention.Bid("good", lambda: "ok", cost=1.0)])
    assert out["results"]["good"] == "ok" and "error" in out["results"]["bad"]



def test_arbiter_rejects_invalid_costs_weights_and_duplicate_names():
    for kwargs in ({"cost": -1}, {"cost": float("nan")}, {"value": 2}, {"stale_after_s": 0}):
        try:
            attention.Bid("invalid", lambda: None, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid bid configuration was accepted")

    try:
        attention.Arbiter(budget=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative budget was accepted")

    arbiter = attention.Arbiter()
    duplicate_bids = [
        attention.Bid("same", lambda: None),
        attention.Bid("same", lambda: None),
    ]
    try:
        arbiter.choose(duplicate_bids)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate bid names were accepted")


# -- delivery -----------------------------------------------------------------

class FakeStore:
    def __init__(self):
        self.done, self.pending = {}, {}

    def delivered(self, ref):
        return ref in self.done

    def mark_delivered(self, ref, to, links):
        self.done[ref] = (to, links)

    def mark_pending(self, ref, to, reason):
        self.pending[ref] = (to, reason)


def test_sales_page_is_never_delivered():
    """THE regression: the buyer must not be emailed the page they just bought from."""
    links = delivery.usable_links(
        ["https://x.com/product/guide.pdf", "https://x.com/sale/index.html"],
        ["https://x.com/sale/index.html"])
    assert links == ["https://x.com/product/guide.pdf"]


def test_sales_page_directory_twin_is_also_blocked():
    assert delivery.usable_links(["https://x.com/sale/"], ["https://x.com/sale/index.html"]) == []


def test_local_paths_are_never_delivered():
    assert delivery.usable_links(["file:///C:/Users/me/out.html"], []) == []
    assert delivery.usable_links(["http://127.0.0.1:8765/x"], []) == []


def test_no_usable_link_records_pending_rather_than_sending_junk():
    store = FakeStore()
    sent = []

    def send(to, links):
        sent.append(links)
        return True

    r = delivery.deliver("ord_1", "b@example.com", ["https://x.com/sale/"],
                         ["https://x.com/sale/"], store, send)
    assert r.status == "pending" and not sent
    assert "ord_1" in store.pending


def test_happy_path_delivers_and_is_idempotent():
    store, sent = FakeStore(), []

    def send(to, links):
        sent.append(links)
        return True

    args = ("ord_2", "b@example.com", ["https://x.com/guide.pdf"], ["https://x.com/sale/"])
    assert delivery.deliver(*args, store, send).status == "delivered"
    assert delivery.deliver(*args, store, send).status == "duplicate"
    assert len(sent) == 1


def test_failed_send_is_pending_and_retryable():
    store = FakeStore()
    r = delivery.deliver("ord_3", "b@example.com", ["https://x.com/g.pdf"], [],
                         store, lambda to, links: False)
    assert r.status == "pending" and not store.delivered("ord_3")   # retryable, not sealed
