"""Agents Kit — the parts of an autonomous agent that fail silently, and how to build them so
they don't.

Every module here was extracted from a running system after the corresponding failure had
already cost me weeks. Each one is standalone: copy the file, it has no dependencies beyond
the standard library.

    webhook_rail  a payment rail that cannot silently lose money
    gates         quality gates that fail OPEN on "couldn't measure", CLOSED on "measured bad"
    staleness     catch loops that run forever and produce nothing
    attention     budget arbitration that proves nothing starves
    delivery      idempotent fulfilment that never drops a paid order
"""

__version__ = "1.0.1"
