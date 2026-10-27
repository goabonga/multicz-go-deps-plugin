<h1 align="center">
  <img src="https://github.com/goabonga/multicz/raw/main/docs/multicz.svg" alt="multicz" width="120" /><br/>
  multicz-go-deps-plugin
</h1>

<p align="center">
  <em>Claim Go components by their import graph in multicz.</em>
</p>

<p align="center">
  <a href="https://github.com/goabonga/multicz-go-deps-plugin/actions/workflows/ci.yml"><img src="https://github.com/goabonga/multicz-go-deps-plugin/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"/></a>
  <a href="https://codecov.io/gh/goabonga/multicz-go-deps-plugin"><img src="https://img.shields.io/codecov/c/github/goabonga/multicz-go-deps-plugin?logo=codecov" alt="Codecov"/></a>
  <a href="https://pypi.org/project/multicz-go-deps-plugin/"><img src="https://img.shields.io/pypi/v/multicz-go-deps-plugin.svg" alt="PyPI"/></a>
  <a href="https://github.com/goabonga/multicz-go-deps-plugin/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"/></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python"/></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"/></a>
</p>

A [multicz](https://github.com/goabonga/multicz) plugin that claims a Go
component by its **compiler-verified import graph** (`go list -deps`)
instead of a hand-maintained `paths` glob.

## Requirements

- Python 3.12+
- [multicz](https://github.com/goabonga/multicz) 1.8+
- A `go` toolchain on `PATH` at the time `multicz validate`/`changed`/`plan`/`bump`
  runs (not required to install or import this package)

## Installation

```bash
pip install multicz-go-deps-plugin
```

Or, with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install multicz --with multicz-go-deps-plugin
```

## Usage

Declare `[plugins.go-deps]` in your `multicz.toml` (see below) and confirm:

```
$ multicz plugins
┃ Plugin  ┃ Status ┃ Module         ┃ Config section
│ go-deps │ active │ multicz_go_deps │ [plugins.go-deps] packages={…}
```

If you see `go-deps: inactive`, you forgot to declare the section. A
component missing from `[plugins.go-deps.packages]` gets no second
look from this plugin - plain `paths` matching is all it has.

### The problem

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

### The fix

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

### Behaviour notes

- **`affects` is a fallback, not a replacement.** It's only ever
  consulted once `paths` matching has already missed - a change inside
  a component's own `paths` never reaches the plugin at all.
- **One `go list` call per (repo, package) per run.** Resolved
  dependency directories are cached on the plugin instance for the
  lifetime of the process.
- **A broken toolchain degrades to "no opinion", and says so.** If `go`
  isn't on `PATH`, or a package doesn't load (it doesn't build, a
  `go.sum` checksum is wrong), `affects` returns `False` - the bump
  still proceeds on whatever `paths` alone could determine. `multicz
  validate` reports it as a `plugin:go-deps` warning naming the
  component and `go`'s own error, so `multicz validate --strict` in CI
  fails instead of releasing without the component.
- **`strict = true` makes that failure an error.** With it in
  `[plugins.go-deps]`, plain `multicz validate` fails too, and
  `multicz bump` aborts before writing anything:

  ```toml
  [plugins.go-deps]
  strict = true
  ```
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

## Development

```bash
git clone https://github.com/goabonga/multicz-go-deps-plugin.git
cd multicz-go-deps-plugin
uv sync

# Quality gates (mirrored in CI).
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pyright
uv run pytest

# Install the pre-commit + commit-msg hooks.
uv run pre-commit install
```

A `go` toolchain on `PATH` is required to run the test suite.

## Versioning and release

Versions are bumped from
[Conventional Commits](https://www.conventionalcommits.org/) by
[multicz](https://github.com/goabonga/multicz) (dogfooding its own
tool). On every push to `main`, CI computes the bump, writes the
changelog, tags, and publishes to PyPI.

```bash
# Preview the next release against the current branch.
uv run multicz status
```

## Contributing

See [CONTRIBUTING.md](https://github.com/goabonga/multicz-go-deps-plugin/blob/main/CONTRIBUTING.md)
for the workflow, the branch and commit-message conventions, and the
test/lint expectations. By participating you agree to the
[Code of Conduct](https://github.com/goabonga/multicz-go-deps-plugin/blob/main/CODE_OF_CONDUCT.md).

Security issues: please follow the disclosure process in
[SECURITY.md](https://github.com/goabonga/multicz-go-deps-plugin/blob/main/SECURITY.md).

## License

Distributed under the
[MIT License](https://github.com/goabonga/multicz-go-deps-plugin/blob/main/LICENSE).
