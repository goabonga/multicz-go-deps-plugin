# multicz-go-deps-plugin

[![CI](https://github.com/goabonga/multicz-go-deps-plugin/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/goabonga/multicz-go-deps-plugin/actions/workflows/ci.yml)
[![Codecov](https://img.shields.io/codecov/c/github/goabonga/multicz-go-deps-plugin?logo=codecov)](https://codecov.io/gh/goabonga/multicz-go-deps-plugin)
[![PyPI](https://img.shields.io/pypi/v/multicz-go-deps-plugin.svg)](https://pypi.org/project/multicz-go-deps-plugin/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/goabonga/multicz-go-deps-plugin/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

A [multicz](https://github.com/goabonga/multicz) plugin that claims a Go
component by its **compiler-verified import graph** (`go list -deps`)
instead of a hand-maintained `paths` glob.

## The problem

A Go monorepo's `multicz.toml` typically declares each binary's own
`cmd/` directory:

```toml
[components.api]
paths = ["cmd/api/**"]

[components.worker]
paths = ["cmd/worker/**"]
```

That's the realistic state most configs end up in: `cmd/` is easy to
remember, `internal/` is not. A change to `internal/auth/auth.go` -
which `cmd/api/main.go` imports - doesn't match `cmd/api/**`, so plain
path matching says `api` is unaffected. It's wrong: `go build
./cmd/api` picks up that file every time, and the drift only gets
worse as the import graph grows.

## The fix

This plugin implements multicz's `Plugin.affects` hook - consulted
**only as a fallback**, once plain `paths` matching has already failed
to attribute a changed file to a component:

```toml
[plugins.go-deps]
[plugins.go-deps.packages]
api    = "./cmd/api"
worker = "./cmd/worker"
# A component that ships more than one binary (a daemon plus a
# sidecar it spawns, say) lists every import path instead:
agent  = ["./cmd/agent", "./cmd/agent-sidecar"]
```

When consulted, it resolves `go list -deps -f '{{.Dir}}' ./cmd/api`
(all of a component's configured packages in one call), gets back
every directory they actually import (including `internal/auth`), and
checks whether the changed path lives under one of them.

## Install

```bash
pip install multicz-go-deps-plugin
```

Then declare `[plugins.go-deps]` in your `multicz.toml` (see above) and
confirm:

```
$ multicz plugins
┃ Plugin  ┃ Status ┃ Module         ┃ Config section
│ go-deps │ active │ multicz_go_deps │ [plugins.go-deps] packages={…}
```

If you see `go-deps: inactive`, you forgot to declare the section. A
component missing from `[plugins.go-deps.packages]` gets no second
look from this plugin - plain `paths` matching is all it has.

## Behaviour notes

- **`affects` is a fallback, not a replacement.** It's only ever
  consulted once `paths` matching has already missed - a change inside
  a component's own `paths` never reaches the plugin at all.
- **One `go list` call per (repo, package) per run.** Resolved
  dependency directories are cached on the plugin instance for the
  lifetime of the process.
- **A broken toolchain degrades to "no opinion".** If `go` isn't on
  `PATH`, or the package doesn't build, the plugin returns `False` -
  the bump still proceeds on whatever `paths` alone could determine.
- **A shared dependency fans out to every importer.** `affects` is
  evaluated independently per component by multicz - a change to a
  package imported by both `cmd/api` and `cmd/worker` claims both.
  This is unaffected by `overlap_policy`, which only governs plain
  `paths` matching.
- **The changelog names the package behind an import-only bump.** When
  a component is bumped by a commit none of whose files match its
  `paths`, the plugin adds a line such as
  ``Import `internal/transport` changed (`7cf9773`)`` to the
  component's changelog, under `Dependencies` next to multicz's own
  `Track ...` cascade lines. Set `changelog_section` in
  `[plugins.go-deps]` to use another heading, or to `""` to turn it off.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for environment management
- A `go` toolchain on `PATH` at the time `multicz changed`/`plan`/`bump`
  runs (not required to install or import this package)

## Getting started (development)

```bash
git clone https://github.com/goabonga/multicz-go-deps-plugin.git
cd multicz-go-deps-plugin
uv sync
uv run pre-commit install
uv run ruff check src tests
uv run mypy src
uv run pytest
```

## Versioning and release

Versions are bumped from
[Conventional Commits](https://www.conventionalcommits.org/) by
[multicz](https://github.com/goabonga/multicz) (dogfooding its own
tool). On every push to `main`, CI computes the bump, writes the
changelog, tags, and publishes to PyPI. Maintainers do not bump
versions or edit the changelog by hand.

## Contributing

See [CONTRIBUTING.md](https://github.com/goabonga/multicz-go-deps-plugin/blob/main/CONTRIBUTING.md)
for the workflow, the commit-message convention, and the test/lint
expectations. By participating you agree to the
[Code of Conduct](https://github.com/goabonga/multicz-go-deps-plugin/blob/main/CODE_OF_CONDUCT.md).

Security issues: please follow the disclosure process in
[SECURITY.md](https://github.com/goabonga/multicz-go-deps-plugin/blob/main/SECURITY.md).

## License

Distributed under the [MIT License](https://github.com/goabonga/multicz-go-deps-plugin/blob/main/LICENSE).
