# Changelog

All notable project changes are documented here.

## Unreleased

### Reliability and correctness
- Use a fingerprint of the event name and exact signed body bytes for Lemon Squeezy webhook retry deduplication instead of the underlying resource ID.
- Preserve distinct webhook events for the same order or subscription.
- Use the actual refunded amount for partial refunds.
- Reject malformed webhook structures, mismatched event names, missing test/live flags, invalid currency codes, and negative or non-finite amounts.
- Make the webhook ledger's atomic uniqueness requirement explicit and handle duplicate-insert races.
- Add an explicit fail-closed option for quality-gate UNKNOWN results; partial judge failures remain UNKNOWN.
- Reject invalid quality-gate thresholds and invalid judge return values.
- Validate staleness measurements and attention-arbitration configuration.
- Use monotonic time for arbitration urgency intervals.
- Restrict fulfilment links to public HTTPS URLs and reject credentials and local destinations.
- Document caller responsibilities for durable storage, distributed coordination, and recovery.

### Integrations and documentation
- Add a dependency-optional, unit-tested OpenAI Agents SDK output-guardrail adapter and example.
- Add production integration guidance, contributor/support/security policies, issue and PR templates, citation metadata, and this changelog.
- Clarify package metadata and Python agent-reliability positioning.

### CI and maintenance
- Add a Python 3.9–3.14 test matrix, example compile checks, and wheel/source-distribution validation.
- Add CodeQL analysis, weekly Dependabot update proposals, and an optional CI smoke test against the current OpenAI Agents SDK.
- Cancel superseded CI and CodeQL runs on the same ref.

- Add optional CrewAI task-guardrail and LangChain/LangGraph after-model middleware adapters with framework-specific integration guides.
- Add framework integration smoke testing for LangChain to CI.
