# Releasing Agents Kit

This project uses semantic versioning. The current release candidate is **1.0.2**, a patch
release for correctness, validation, documentation, and optional framework integrations.
The release process must not publish automatically from a branch push.

## Before creating a GitHub release

1. Merge the release-preparation PR.
2. Confirm the package version matches in all three places:
   - `pyproject.toml` — distribution metadata
   - `agents_kit/__init__.py` — `__version__`
   - `CITATION.cff` — citation version and release date
3. Confirm `CHANGELOG.md` has a dated section for the release.
4. Confirm CI, CodeQL, tests, example execution, wheel/sdist build, and `twine check` pass.
5. Review the built distributions and verify that the separate post-mortem text is not
   included in either artifact.
6. Create a GitHub release tagged `v1.0.2` from the merged release commit. Do not publish
   the release until the PyPI Trusted Publisher and environment protections below are ready.

## Configure PyPI Trusted Publishing once

On PyPI, open the `agents-toolkit` project settings and add a GitHub Actions Trusted Publisher
with these exact values:

- PyPI project: `agents-toolkit`
- Owner: `ahmedmribai`
- Repository: `agents-kit`
- Workflow filename: `release.yml`
- Environment: `pypi`

Then, in GitHub repository settings, create the `pypi` environment and require manual
approval before deployments. The publishing job has only `id-token: write`; it does not
use a long-lived PyPI API token. The trusted-publishing workflow builds and tests in a
separate, unprivileged job, transfers the exact verified artifacts, then publishes those
artifacts in the isolated OIDC-enabled job.

Official setup instructions:
- [PyPI: add a Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [PyPI: publish with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [PyPA publishing action](https://github.com/pypa/gh-action-pypi-publish)

## Publish and verify

Publishing is triggered only when a GitHub Release is marked **published**. The workflow:

- checks that the tag, package version, runtime `__version__`, and citation version match;
- installs test dependencies and runs the complete test suite;
- runs the basic example;
- builds wheel and source distributions;
- runs `twine check`;
- uploads those exact verified files through PyPI Trusted Publishing.

After the workflow succeeds, verify the version on
[PyPI](https://pypi.org/project/agents-toolkit/), install it into a clean Python 3.9 and
3.14 environment, and run:

```bash
python -c "import agents_kit; print(agents_kit.__version__)"
python -m pip show agents-toolkit
```

Do not reuse a version number once it has been uploaded. If an artifact is wrong, increment
the version and create a new release.
