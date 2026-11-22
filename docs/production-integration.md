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
- Persist enough state to recover fulfilment after a process crash. In particular, recording
  a payment and sending a fulfilment email are not one atomic operation. Use a transactional
  outbox or a durable pending-fulfilment worker; do not assume a webhook retry will recover
  a crash after the ledger write.
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

The delivery helper relies on the caller's store and send adapter. Make the store's
idempotency operations atomic and durable. A crash between sending and marking delivered
can still cause a duplicate send on retry; use a provider idempotency key or an outbox when
the downstream service supports it. Validate destination URLs and recipients according to
your application's threat model before sending.

## General rule

Treat these modules as tested building blocks. They do not replace an architecture review,
provider documentation, database constraints, incident response, or end-to-end testing in
your own deployment.
