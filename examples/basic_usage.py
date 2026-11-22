"""Small, dependency-free examples for the public Agents Kit API.

Run with: python examples/basic_usage.py
These examples are in-memory demonstrations, not production storage adapters.
"""
from agents_kit import attention, delivery, gates, staleness


def demonstrate_gates():
    result = gates.evaluate([
        lambda: gates.Judgement(ok=True),
        lambda: gates.Judgement(ok=True),
        lambda: gates.Judgement(ok=False),
    ], threshold=0.66)
    print("gate:", result.verdict.value, "score=", result.score)


def demonstrate_staleness():
    monitor = staleness.StalenessMonitor(patience=3)
    for produced in (4, 0, 0, 0):
        monitor.record("catalog_sync", produced)
    print("stale tasks:", monitor.stale())


def demonstrate_attention():
    arbiter = attention.Arbiter(budget=2.0)
    bids = [
        attention.Bid("summarize", lambda: "summary ready", value=0.8, cost=1.0),
        attention.Bid("deep_review", lambda: "review ready", value=0.9, info=0.9, cost=1.0),
        attention.Bid("expensive_simulation", lambda: "simulation ready", cost=3.0),
    ]
    print("attention:", arbiter.run(bids))


class DemoStore:
    def __init__(self):
        self.done = {}
        self.pending = {}

    def delivered(self, order_ref):
        return order_ref in self.done

    def mark_delivered(self, order_ref, to, links):
        self.done[order_ref] = (to, links)

    def mark_pending(self, order_ref, to, reason):
        self.pending[order_ref] = (to, reason)


def demonstrate_delivery():
    store = DemoStore()
    result = delivery.deliver(
        "demo-order-1",
        "buyer@example.test",
        ["https://downloads.example.com/guide.pdf"],
        ["https://shop.example.com/product"],
        store,
        lambda recipient, links: True,  # Replace with your mail/provider adapter.
    )
    print("delivery:", result.status, result.links)


if __name__ == "__main__":
    demonstrate_gates()
    demonstrate_staleness()
    demonstrate_attention()
    demonstrate_delivery()
