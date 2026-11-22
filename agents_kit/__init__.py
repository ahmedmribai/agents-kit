"""Agents Kit — the parts of an autonomous agent that fail silently, and how to build them so
they don't.

Every module here was extracted from a running system after the corresponding failure had
already cost me weeks. Each one is standalone: copy the file, it has no dependencies beyond
the standard library.

    webhook_rail  signed webhook verification, deduplication, and ledger contracts
    gates         quality gates with explicit UNKNOWN allow/block policy
    staleness     detect repeated work that produces no new output
    attention     budget arbitration with starvation visibility
    delivery      idempotent fulfilment with explicit pending outcomes
"""

__version__ = "1.1.0"
