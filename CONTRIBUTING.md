# Contributing

Thank you for considering a contribution to Agents Kit. The project is a small,
dependency-free Python toolkit for making autonomous-agent workflows more reliable.

## Before you start

- Read the [README](README.md) to understand the five modules and their intended scope.
- Search existing issues and pull requests before opening a new one.
- For substantial changes, open an issue first so we can agree on the problem and approach.
- Keep runtime code compatible with Python 3.9 and newer.
- Keep the core package free of third-party runtime dependencies.

## Development setup

Use a virtual environment and install the project with its test extra:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

## Tests

Run the complete test suite before submitting a change:

```bash
python -m pytest tests/ -q
```

Add regression tests for bug fixes. Tests should be deterministic, should not require
network access, and should not depend on real payment providers, credentials, or external
services.

## Pull requests

A useful pull request should:

1. Explain the failure mode or user problem being addressed.
2. Describe the behavior before and after the change.
3. Include focused tests, including relevant edge cases.
4. Update documentation and examples when public behavior changes.
5. Keep changes focused; avoid unrelated refactors.
6. Never include secrets, customer data, production payloads, or private incident details.

The GitHub Actions test matrix must pass before a change is merged.

## Design principles

- Prefer the Python standard library for runtime functionality.
- Make failure states explicit; do not silently convert errors into success.
- Preserve idempotency and safe retry behavior.
- Avoid claiming guarantees that depend on a caller's database, transaction model,
  payment provider, or deployment environment.
- Keep public APIs small and document important assumptions.

## Security issues

Do not report exploitable vulnerabilities in public issues. Follow the private reporting
instructions in [SECURITY.md](SECURITY.md).

By participating, you agree to communicate respectfully and constructively. Contributions
are reviewed on their technical merits and fit with the project's scope.
