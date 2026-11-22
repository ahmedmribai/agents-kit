# Changelog

All notable project changes are documented here.

## Unreleased

- Add Python 3.9–3.13 CI coverage and distribution validation.
- Add contributor, support, security, and community guidance.
- Add runnable examples and production integration notes.
- Make webhook event-ID uniqueness an explicit atomic ledger contract and handle duplicate-insert races.
- Reject malformed webhook structures, non-finite amounts, and missing or unrecognized test-mode flags.
- Restrict delivery links to public HTTPS URLs and reject credentials, local destinations, and sales-page aliases.
- Clarify that durable recovery, distributed coordination, and downstream idempotency remain integration responsibilities.
- Expand regression coverage for malformed inputs and unsafe URLs.

- Deduplicate Lemon Squeezy retries using an event/body fingerprint rather than the resource ID, and preserve distinct events for the same order or subscription.
- Account for partial refunds using the provider's refunded amount and reject mismatched event-name headers.

- Add an explicit fail-closed option for quality-gate UNKNOWN results and handle invalid judge return values without crashing.

- Validate staleness measurements and attention-arbitration configuration, rejecting invalid counts, costs, weights, budgets, and duplicate bid names.

- Treat partial judge failures as UNKNOWN rather than passing on an incomplete score; expose the partial score for diagnostics.

- Add a dependency-optional OpenAI Agents SDK output-guardrail integration example and guide.
- Compile all package and example modules in CI, including optional integration examples.

- Add Python 3.14 to the supported test matrix and package classifiers; clarify PyPI discovery metadata.

- Package the OpenAI Agents SDK adapter as an optional integration with lazy imports and unit-tested gate mapping.
