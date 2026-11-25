# Community-reported downstream adaptation: guard-sdk

**Status checked: 25 November 2026**

This page records an early, publicly reported interoperability experiment. It is not a certification or a claim of production deployment.

## What was reported

In [CrewAI issue #5888](https://github.com/crewAIInc/crewAI/issues/5888#issuecomment-7152730542), the maintainer of [DSHCorrectover/guard-sdk](https://github.com/DSHCorrectover/guard-sdk) reported installing Agents Kit from the `main` branch in a clean virtual environment and checking two gate outcomes:

- two successful judgements produced `verdict=pass` and `allowed=true`;
- a judge fault with `unknown_policy="block"` produced `verdict=unknown` and `allowed=false`.

The downstream project's public [v0.2.0 commit](https://github.com/DSHCorrectover/guard-sdk/commit/4c333668d14803f09782a4357927af01e4f89611) explicitly credits Agents Kit's gate semantics and records a separate JavaScript implementation with three decision-model additions: `reason_class`, `expires_at`, and `supersedes`. Its commit message reports 35 passing assertions.

## What this does and does not establish

This is a useful external usage report and a public downstream adaptation. It is stronger than an expression of interest, but its scope should not be overstated:

- `guard-sdk` is an independently implemented JavaScript project; it does not depend on or embed Agents Kit.
- The report is from the downstream maintainer. Agents Kit has not independently run the downstream test suite or established a successful CI run for that commit.
- This is not evidence of production deployment, customer usage, or a verified CrewAI pre-tool lifecycle integration.
- The implementation does not establish that a signed decision receipt proves a tool was authorized or executed. A verifier must independently trust the signing key, and invocation-specific evidence must be bound to a host-supplied invocation identifier.

## Review note

A source review of downstream commit `4c333668` found an expiry-validation edge case in `ruleExpired()`: when `expires_at` is supplied but cannot be parsed, `Date.parse()` returns `NaN`; `Number.isFinite(NaN)` is false, so the function returns `false` and treats the rule as not expired. A matching allow rule with a malformed expiry can therefore remain active. This needs fail-closed validation, including care not to fall through to a built-in permissive default.

This is a source-level review finding, not a claim that Agents Kit ran or penetration-tested the downstream package. See the [exact implementation at the reviewed commit](https://github.com/DSHCorrectover/guard-sdk/blob/4c333668d14803f09782a4357927af01e4f89611/src/index.mjs).

## Agents Kit boundaries

Agents Kit continues to provide decision primitives, not an identity provider or complete policy engine. Applications supply their identity evidence and policy and enforce the result immediately before a side effect. The existing [CrewAI guide](../integrations/crewai.md) documents task-output guardrails; a pre-tool wrapper is a separate application-owned pattern tracked in [Agents Kit issue #10](https://github.com/ahmedmribai/agents-kit/issues/10).
