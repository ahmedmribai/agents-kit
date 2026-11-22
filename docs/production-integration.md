# Production integration boundaries

Agents Kit contains small primitives, not turnkey production infrastructure. The caller
owns persistence, transaction boundaries, authentication, monitoring, retry policy, and
provider-specific behavior. Read this page before wiring a module into a live system.

## Webhook rail

- Verify the exact raw request bytes using the payment provider's documented signature format.
- Use a persistent ledger with a database-level UNIQUE constraint on the provider event ID.
  The adapter's `record()` operation must atomically insert the event and raise
  `AlreadyHandled` when that unique constraint rejects a duplicate. The earlier `seen()`
  call is only an optimization and is not a concurrency guarantee.
- The parser requires an explicit, recognized `test_mode` flag. Unknown or missing values
  are rejected rather than silently classified as live revenue. Adapt this contract to the
  exact provider payload before integration.
- Persist enough state to recover fulfilment after a process crash. Recording a payment and
  sending a fulfilment email are not one atomic operation. Use a transactional outbox or a
  durable pending-fulfilment worker; do not assume a webhook retry will recover a crash after
  the ledger write.
- Confirm the provider's event types, refund semantics, currency units, and test/live flags.
  Adapt `parse()` for your provider and reject event types your application does not handle.
- Use integer minor units or a decimal money type in your own ledger when exact monetary
  arithmetic matters. The example API normalizes amounts to floats for convenience.
- Return provider-appropriate responses and monitor failed/pending fulfilments.

## Quality gates

`Verdict.UNKNOWN` is allowed by default in this module. That is a deliberate availability
policy for workflows where a failed judge should not masquerade as a negative judgement.
It is not universally safe. For authorization, security checks, payments, compliance, or
irreversible actions, explicitly enforce a fail-closed policy in the calling application.

## Staleness monitor

The included monitor stores state in memory. It resets when the process restarts and does not
coordinate across workers. Persist counters or export output-delta metrics if you need durable
or distributed monitoring. Define "new output" carefully: rewriting the same records is not
new output.

## Attention arbiter

The arbiter is a local heuristic, not a formal fairness scheduler. Its starvation report
identifies bids that have never won, but it does not guarantee every bid will eventually run.
Use `feasible()` during configuration and add a hard reservation, aging, or weighted-fair
policy if every task must receive a guaranteed share of compute.

## Delivery

The helper accepts only public HTTPS URLs, rejects URL credentials and non-public IP
addresses, and filters the configured sales page and its `index.html`/trailing-slash alias.
This is URL-shape validation, not a reputation check or proof that the destination content is
safe. Validate content and ownership in your application before sending links to customers.

The current API's `delivered()` check is not an atomic distributed claim. Concurrent workers
can both send before either records delivery. Use a database-backed claim/lease or serialize
attempts per order. A timeout or process crash after a provider accepts a message but before
`mark_delivered()` can also cause a duplicate on retry; use a downstream idempotency key or
transactional outbox where supported. Storage errors intentionally propagate instead of being
reported as a durable pending result.

## General rule

Treat these modules as tested building blocks. They do not replace an architecture review,
provider documentation, database constraints, incident response, or end-to-end testing in
your own deployment.
