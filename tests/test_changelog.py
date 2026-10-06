# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""``enrich_changelog`` names the imported Go packages behind a bump
that the component's ``paths`` did not explain."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from multicz.cli import app
from multicz.config import load_config
from typer.testing import CliRunner

from multicz_go_deps import GoDepsPlugin

CONFIG = """\
[project]
initial_version = "0.0.0"

[plugins.go-deps{section}]
packages = {{ api = "./cmd/api", worker = "./cmd/worker" }}

[components.api]
paths = ["cmd/api/**"]
bump_files = [{{ file = "cmd/api/VERSION", key = "regex:(.+)" }}]
changelog = "cmd/api/CHANGELOG.md"

[components.worker]
paths = ["cmd/worker/**"]
bump_files = [{{ file = "cmd/worker/VERSION", key = "regex:(.+)" }}]
changelog = "cmd/worker/CHANGELOG.md"
"""


def _reason(sha: str, *files: str) -> SimpleNamespace:
    return SimpleNamespace(sha=sha, files=files)


def _ctx(
    repo: Path, reasons: dict[str, list[SimpleNamespace]], section: str | None = None
):
    (repo / "multicz.toml").write_text(CONFIG.format(section=""))
    plugin_config: dict[str, object] = {
        "packages": {"api": "./cmd/api", "worker": "./cmd/worker"}
    }
    if section is not None:
        plugin_config["changelog_section"] = section
    return SimpleNamespace(
        config=load_config(repo / "multicz.toml"),
        repo=repo,
        plan=SimpleNamespace(
            bumps={
                name: SimpleNamespace(reasons=items) for name, items in reasons.items()
            }
        ),
        plugin_config=plugin_config,
    )


def test_import_only_bump_names_the_changed_package(go_project: Path):
    ctx = _ctx(go_project, {"api": [_reason("a" * 40, "internal/auth/auth.go")]})

    [entry] = GoDepsPlugin().enrich_changelog(ctx, "api")

    assert entry.section == "Dependencies"
    assert entry.component == "api"
    assert entry.lines == ("Import `internal/auth` changed (`aaaaaaa`)",)


def test_path_owned_commits_add_no_dependency_line(go_project: Path):
    ctx = _ctx(
        go_project,
        {"api": [_reason("b" * 40, "cmd/api/main.go", "internal/auth/auth.go")]},
    )

    assert GoDepsPlugin().enrich_changelog(ctx, "api") == []


def test_only_packages_imported_by_the_component_are_listed(go_project: Path):
    ctx = _ctx(
        go_project,
        {
            "api": [
                _reason(
                    "c" * 40,
                    "internal/queue/queue.go",
                    "internal/auth/auth.go",
                    "README.md",
                )
            ]
        },
    )

    [entry] = GoDepsPlugin().enrich_changelog(ctx, "api")

    assert entry.lines == ("Import `internal/auth` changed (`ccccccc`)",)


def test_section_title_is_configurable_and_can_be_disabled(go_project: Path):
    reasons = {"api": [_reason("d" * 40, "internal/auth/auth.go")]}

    [entry] = GoDepsPlugin().enrich_changelog(
        _ctx(go_project, reasons, "Go imports"), "api"
    )
    assert entry.section == "Go imports"
    assert GoDepsPlugin().enrich_changelog(_ctx(go_project, reasons, ""), "api") == []


@pytest.mark.parametrize("component", ["worker", "unknown"])
def test_components_without_an_import_bump_get_nothing(
    go_project: Path, component: str
):
    ctx = _ctx(go_project, {"api": [_reason("e" * 40, "internal/auth/auth.go")]})

    assert GoDepsPlugin().enrich_changelog(ctx, component) == []


def test_reasons_without_commit_files_are_skipped(go_project: Path):
    """Cascade reasons (``depends_on``, mirrors) carry no commit files."""
    cascade = SimpleNamespace(upstream="worker", upstream_kind="patch")
    ctx = _ctx(go_project, {"api": [cascade, _reason("f" * 40)]})

    assert GoDepsPlugin().enrich_changelog(ctx, "api") == []


def test_a_missing_go_toolchain_adds_nothing(
    go_project: Path, monkeypatch: pytest.MonkeyPatch
):
    ctx = _ctx(go_project, {"api": [_reason("a" * 40, "internal/auth/auth.go")]})

    def raise_missing(*args, **kwargs):
        raise FileNotFoundError("go")

    monkeypatch.setattr(subprocess, "run", raise_missing)

    assert GoDepsPlugin().enrich_changelog(ctx, "api") == []


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_bump_writes_the_dependency_line_into_the_changelog(
    go_project: Path, monkeypatch: pytest.MonkeyPatch
):
    (go_project / "multicz.toml").write_text(CONFIG.format(section=""))
    for name in ("api", "worker"):
        (go_project / "cmd" / name / "VERSION").write_text("0.0.0")
        (go_project / "cmd" / name / "CHANGELOG.md").write_text("# Changelog\n")
    _git(go_project, "init", "-q", "-b", "main")
    _git(go_project, "config", "user.email", "test@example.com")
    _git(go_project, "config", "user.name", "Test")
    _git(go_project, "add", "-A")
    _git(go_project, "commit", "-q", "-m", "chore: init")
    (go_project / "internal" / "auth" / "auth.go").write_text(
        'package auth\n\nfunc Token() string {\n\treturn "rotated"\n}\n'
    )
    _git(go_project, "commit", "-q", "-am", "fix(auth): rotate the token")
    monkeypatch.chdir(go_project)

    result = CliRunner().invoke(app, ["bump"])

    assert result.exit_code == 0, result.stdout
    changelog = (go_project / "cmd" / "api" / "CHANGELOG.md").read_text()
    assert "### Dependencies" in changelog
    assert "- Import `internal/auth` changed (`" in changelog
    assert (go_project / "cmd" / "worker" / "VERSION").read_text() == "0.0.0"
