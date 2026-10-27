# Contributing to multicz-go-deps-plugin

Thanks for taking the time to contribute. This document is the short version
of how to propose a change and what the project expects in return.

## Code of Conduct

Participation in this project is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md). By contributing you agree to abide by
its terms.

## Development setup

```bash
git clone https://github.com/goabonga/multicz-go-deps-plugin.git
cd multicz-go-deps-plugin
uv sync
uv run pre-commit install   # installs the pre-commit + commit-msg hooks
```

A `go` toolchain on `PATH` is required to run the test suite (it exercises
`go list -deps` against real fixture modules under `tests/`).

## Quality gates

Before pushing, make sure your code passes the same gates the `ci` workflow
runs:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pyright
uv run pytest
uv tool run multicz validate --strict
python scripts/add_license_header.py --path . --types py,yml,toml --check
```

These checks run in CI and gate the release, along with the security scans
(bandit, pip-audit, osv-scanner). Each CI job writes a summary of its result
on the run page.

## Branching and pull requests

1. Fork the repository and create a topic branch from `main`, or from the
   branch of the issue you work on (see [Branch names](#branch-names)).
2. Keep commits small, focused and atomic.
3. Open a pull request against `main`, or against the issue branch for a
   sub-issue. The CI workflow runs the full quality matrix on both.
4. Reviews target correctness, scope and adherence to the
   conventional-commits contract; please do not bundle unrelated changes.

### Branch names

A branch is named after the GitHub issue it addresses:

```
issue-<number>-<slug>
```

`<number>` is the issue number and `<slug>` a few lowercase words separated
by hyphens, for example `issue-12-strict-go-list`. Keep it free of `/`: Git
cannot hold `issue-12` and `issue-12/...` at the same time, and the
automation only recognises `issue-*` as a base branch.

| Work | Branch | Created from | Pull request into |
| --- | --- | --- | --- |
| An issue | `issue-<number>-<slug>` | `main` | `main` |
| A sub-issue of an issue | `issue-<number>-<slug>` (its own issue number) | the branch of the parent issue | the branch of the parent issue |

An issue split into sub-issues therefore gets one branch of its own, which
collects the pull requests of its sub-issues. Once they are all merged, the
issue branch is proposed to `main` in a single pull request. Dependabot
branches (`dependabot/...`) are created by Dependabot and need no naming.

`main` and the `issue-*` branches are protected by rulesets: signed commits,
linear history, rebase merges only, and the CI checks must pass.

### Merging

Adding the `auto-merge` label to a pull request, by someone with write
access, replays its commits GPG-signed onto its base branch once the
required checks passed, then fast-forwards that branch: `main`, or the issue
branch for a sub-issue. The history stays linear. The commits of a branch
pushed unsigned, such as by GitHub's "Update branch", are re-signed in place.

Dependabot pull requests are rewritten as Conventional Commits and signed.
Each one also gets an issue, assigned to the repository owner, which the
pull request closes when it is merged. If the pull request is closed
without a merge, the issue is closed as not planned.

## Commit messages

Commit messages MUST follow
[Conventional Commits](https://www.conventionalcommits.org/). They drive the
version bump and CHANGELOG computed by
[multicz](https://github.com/goabonga/multicz).

| Type | Effect on version | Use it for |
| --- | --- | --- |
| `feat` | minor | new capability |
| `fix` | patch | bug fix |
| `perf` | patch | performance improvement |
| `refactor`, `docs`, `test`, `chore`, `ci`, `build`, `style` | none | maintenance |
| `feat!` / `BREAKING CHANGE:` | major | incompatible change |

The subject is at most 72 characters, has no trailing period and a
lowercase first word after the colon: the signed merge refuses any other
subject, so the `commit-subject` pre-commit hook and the `commit-subjects`
CI job check it first.

Only commits that touch the tracked paths (`src/**`, `pyproject.toml`)
trigger a release. Do not append `Co-Authored-By` trailers.

## Releasing

Releases are automated: on every push to `main`, the `ci` workflow runs
`multicz bump` (signed commit + tag) and publishes to PyPI. Maintainers do
not bump versions or edit the changelog by hand. The `chore(release)` commit
pushed back by multicz does not start another run.

## Reporting bugs and asking for features

Please open a GitHub issue. For security-sensitive reports, follow
[SECURITY.md](SECURITY.md) instead of the public tracker.
