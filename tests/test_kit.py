"""Every claim the kit makes, as an executable test.

These are the regression tests for the production incidents the kit exists to prevent.
If you change a module, these must stay green.
"""

import hashlib
import hmac
import json
import time

from agents_kit import attention, delivery, gates, staleness, webhook_rail

SECRET = "test-signing-secret"


def _signed(payload: dict) -> tuple[bytes, str]:
    raw = json.dumps(payload).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def _order(oid="ord_1", total=9899, test_mode=False, email="buyer@example.com"):
    return {"meta": {"custom_data": {"reference": "42"}},
            "data": {"id": oid, "attributes": {"total": total, "test_mode": test_mode,
                                               "user_email": email, "currency": "USD"}}}


class FakeLedger:
    def __init__(self):
        self.rows = {}

    def seen(self, event_id):
        return event_id in self.rows

    def record(self, event_id, amount, currency, live):
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
    assert ledger.rows["ord_1"]["live"] is True


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
    assert ledger.rows["ord_1"]["live"] is False


def test_refund_books_negative():
    raw, sig = _signed(_order(oid="ord_r"))
    ledger = FakeLedger()
    webhook_rail.handle(raw, sig, "order_refunded", SECRET, ledger, lambda e: None)
    assert ledger.rows["ord_r"]["amount"] == -98.99


def test_fulfilment_failure_still_records_the_sale():
    def boom(_event):
        raise RuntimeError("mail server down")

    raw, sig = _signed(_order())
    ledger = FakeLedger()
    status, body = webhook_rail.handle(raw, sig, "order_created", SECRET, ledger, boom)
    assert status == 200 and "pending" in body["fulfilment"]
    assert ledger.rows["ord_1"]["amount"] == 98.99      # the money is still on the books


def test_malformed_body_is_400_not_a_crash():
    sig = hmac.new(SECRET.encode(), b"not json", hashlib.sha256).hexdigest()
    status, _ = webhook_rail.handle(b"not json", sig, "order_created", SECRET,
                                    FakeLedger(), lambda e: None)
    assert status == 400


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


def test_partial_errors_still_score_on_what_was_measured():
    r = gates.evaluate([_judge(ok=True), _judge(ok=True), _judge(error=True)], threshold=0.5)
    assert r.judged == 2 and r.errors == 1
    assert r.score == 1.0 and r.verdict is gates.Verdict.PASS


def test_measure_only_mode_never_blocks():
    r = gates.evaluate([_judge(ok=False)] * 4, threshold=0.5, enabled=False)
    assert r.verdict is gates.Verdict.PASS and r.score == 0.0


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
