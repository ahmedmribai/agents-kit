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
