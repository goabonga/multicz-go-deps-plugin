# Security Policy

## Supported versions

Security fixes are applied only to the latest released minor of
`multicz-go-deps-plugin`.

| Version | Supported |
| --- | --- |
| latest minor on PyPI | ✅ |
| Older minors or pre-releases | ❌ |

## Reporting a vulnerability

**Please do not open a public issue.** GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
is the preferred channel:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Fill in the form with the affected version, reproduction steps and
   suggested mitigation.

If you cannot use GitHub's form, email **goabonga@pm.me** with the same
information. PGP encryption is available on request.

You can expect:

- an acknowledgement within **3 business days**;
- a triage assessment (severity, scope, affected versions) within **10
  business days**;
- a fix or written mitigation plan before any public disclosure.

## Scope

The plugin's only sensitive surface is the subprocess call to `go list -deps`
(`src/multicz_go_deps/__init__.py`), run with a fixed argument list and no shell
against the host repository's own `go.mod` and source tree, with a package path
taken from the plugin configuration. A report showing that it can be made to run
anything else is in scope. Vulnerabilities in multicz itself or in a Go toolchain should be
reported there; for third-party dependencies of this package, please let us know
so the pinned ranges can be bumped.

## Disclosure process

Coordinated disclosure is the default. Once a fix is released:

1. A patched version is published to PyPI.
2. A GitHub Security Advisory is opened with a CVE when applicable.
3. The reporter is credited in the advisory unless they request anonymity.

Thanks for helping keep `multicz-go-deps-plugin` and its users safe.
