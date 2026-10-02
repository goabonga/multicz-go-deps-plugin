# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest import make_ctx

from multicz_go_deps import GoDepsPlugin


def test_plugin_name_matches_entry_point():
    assert GoDepsPlugin.name == "go-deps"


def test_affects_claims_component_via_internal_import(go_project: Path):
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {"api": "./cmd/api", "worker": "./cmd/worker"})

    assert plugin.affects(ctx, "api", ["internal/auth/auth.go"]) is True


def test_affects_does_not_claim_an_unrelated_internal_package(go_project: Path):
    """``internal/queue`` is only imported by ``worker`` - ``api`` must
    not be claimed for a change confined to it."""
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {"api": "./cmd/api", "worker": "./cmd/worker"})

    assert plugin.affects(ctx, "api", ["internal/queue/queue.go"]) is False
    assert plugin.affects(ctx, "worker", ["internal/queue/queue.go"]) is True


def test_affects_returns_false_for_unconfigured_component(go_project: Path):
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {"api": "./cmd/api"})

    assert plugin.affects(ctx, "worker", ["internal/queue/queue.go"]) is False


def test_affects_returns_false_with_no_packages_configured(go_project: Path):
    """An empty ``[plugins.go-deps]`` section (no ``packages`` key)
    must not crash - ``_packages`` falls back to ``{}``."""
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {})
    ctx.plugin_config = {}

    assert plugin.affects(ctx, "api", ["internal/auth/auth.go"]) is False


def test_affects_shared_dependency_claims_every_importer(go_project: Path):
    """Both ``api`` and ``worker`` importing the same package must both
    be claimed - ``affects`` is evaluated independently per component,
    so a shared dependency fans out rather than picking one owner."""
    shared = go_project / "internal" / "shared"
    shared.mkdir()
    (shared / "shared.go").write_text(
        'package shared\n\nfunc Name() string {\n\treturn "shared"\n}\n'
    )
    (go_project / "cmd" / "api" / "main.go").write_text(
        "package main\n\n"
        'import (\n\t"fmt"\n\n\t"example.com/svc/internal/auth"\n\t'
        '"example.com/svc/internal/shared"\n)\n\n'
        "func main() {\n\tfmt.Println(auth.Token(), shared.Name())\n}\n"
    )
    (go_project / "cmd" / "worker" / "main.go").write_text(
        "package main\n\n"
        'import (\n\t"fmt"\n\n\t"example.com/svc/internal/queue"\n\t'
        '"example.com/svc/internal/shared"\n)\n\n'
        "func main() {\n\tfmt.Println(queue.Name(), shared.Name())\n}\n"
    )
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {"api": "./cmd/api", "worker": "./cmd/worker"})

    assert plugin.affects(ctx, "api", ["internal/shared/shared.go"]) is True
    assert plugin.affects(ctx, "worker", ["internal/shared/shared.go"]) is True


def test_affects_accepts_a_list_of_packages_for_one_component(go_project: Path):
    """A component that ships more than one binary (a daemon plus a
    sidecar it spawns, say) declares every import path as a list - a
    change under any of their dependency graphs must claim it."""
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {"agent": ["./cmd/api", "./cmd/worker"]})

    assert plugin.affects(ctx, "agent", ["internal/auth/auth.go"]) is True
    assert plugin.affects(ctx, "agent", ["internal/queue/queue.go"]) is True


def test_affects_caches_go_list_per_repo_and_package(
    go_project: Path, monkeypatch: pytest.MonkeyPatch
):
    real_run = subprocess.run
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {"api": "./cmd/api"})

    plugin.affects(ctx, "api", ["internal/auth/auth.go"])
    plugin.affects(ctx, "api", ["internal/auth/auth.go"])

    assert len(calls) == 1


def test_affects_returns_false_when_go_binary_is_missing(
    go_project: Path, monkeypatch: pytest.MonkeyPatch
):
    def raise_missing(*args, **kwargs):
        raise FileNotFoundError("go not found")

    monkeypatch.setattr(subprocess, "run", raise_missing)
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {"api": "./cmd/api"})

    assert plugin.affects(ctx, "api", ["internal/auth/auth.go"]) is False


def test_affects_returns_false_when_go_list_fails(go_project: Path):
    """A package go can't resolve (typo, not built, …) must degrade to
    "no opinion" rather than raising."""
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {"bogus": "./cmd/does-not-exist"})

    assert plugin.affects(ctx, "bogus", ["internal/auth/auth.go"]) is False


def test_affects_returns_false_for_path_outside_the_dependency_graph(
    go_project: Path,
):
    (go_project / "README.md").write_text("not imported by anything\n")
    plugin = GoDepsPlugin()
    ctx = make_ctx(go_project, {"api": "./cmd/api"})

    assert plugin.affects(ctx, "api", ["README.md"]) is False
