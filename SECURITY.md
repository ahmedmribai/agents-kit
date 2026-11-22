# Security Policy

## Supported versions

Security fixes are currently accepted for the latest published version of Agents Kit.
The project is maintained on a best-effort basis; no response-time or remediation-time
guarantee is offered.

## Reporting a vulnerability

Please do not disclose exploitable vulnerabilities in a public GitHub issue.

Email **hello@get-agents-kit.com** with:

- A concise description of the vulnerability.
- The affected module, version, and relevant configuration.
- Reproduction steps or a minimal proof of concept.
- The potential impact and any suggested mitigation.

Do not include real credentials, payment details, customer information, or other sensitive
production data. Use synthetic examples.

You should receive an acknowledgement when the report is reviewed. Please allow reasonable
time for investigation and a fix before publicly disclosing the issue.

## Scope and deployment responsibilities

Agents Kit provides small building blocks; it is not a hosted payment service or a complete
production infrastructure. Integrators remain responsible for secure secret storage,
database transactions, access controls, webhook endpoint configuration, monitoring, and
provider-specific verification requirements.

A report about a vulnerability in a third-party service should be sent to that service's
maintainers as well.
