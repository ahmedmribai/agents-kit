# Security Policy

## Supported versions

Security fixes are currently accepted for the latest published version of Agents Kit.
The project is maintained on a best-effort basis; no response-time or remediation-time
guarantee is offered.

## Reporting a vulnerability

Please do not disclose exploitable vulnerabilities in a public GitHub issue.

If GitHub's private vulnerability reporting is enabled for this repository, use the
**Report a vulnerability** option on the repository's Security tab. Otherwise, contact
the maintainer through the contact method listed on the maintainer's public GitHub profile
and ask for a private reporting channel before sending technical details. You may also email
**hello@get-agents-kit.com** with the subject **[Security] Agents Kit**; this address is
published in the package metadata. Do not attach secrets or live customer data.

Do not include real credentials, payment details, customer information, or other sensitive
production data. Use synthetic examples.

Please allow reasonable time for investigation and a fix before publicly disclosing an
unresolved vulnerability. Acknowledgement and remediation timelines are best-effort.

## Scope and deployment responsibilities

Agents Kit provides small building blocks; it is not a hosted payment service or a complete
production infrastructure. Integrators remain responsible for secure secret storage,
database transactions, access controls, webhook endpoint configuration, monitoring, and
provider-specific verification requirements.

A report about a vulnerability in a third-party service should be sent to that service's
maintainers as well.
