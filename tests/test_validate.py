# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_ctx
from multicz.plugins import Severity

from multicz_go_deps import GoDepsPlugin

PACKAGES = {"api": "./cmd/api", "worker": "./cmd/worker"}


@pytest.fixture
def broken_api(go_project: Path) -> Path:
    """``cmd/api`` imports a package that does not exist, so ``go list``
    cannot load its graph; ``cmd/worker`` still loads."""
    main = go_project / "cmd" / "api" / "main.go"
    main.write_text(main.read_text().replace("internal/auth", "internal/missing"))
    return go_project


def test_validate_is_silent_when_every_graph_loads(go_project: Path):
    assert GoDepsPlugin().validate(make_ctx(go_project, PACKAGES)) == []


def test_a_graph_that_cannot_load_is_a_warning(broken_api: Path):
    [violation] = GoDepsPlugin().validate(make_ctx(broken_api, PACKAGES))
    assert violation.severity == Severity.warning
    assert (violation.component, violation.plugin) == ("api", "go-deps")
    assert violation.message.startswith("go list -deps ./cmd/api failed")
    assert "internal/missing" in violation.message
    assert "go: downloading" not in violation.message


def test_a_missing_go_toolchain_is_reported(
    go_project: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PATH", "")
    violations = GoDepsPlugin().validate(make_ctx(go_project, PACKAGES))
    assert [v.component for v in violations] == ["api", "worker"]
    assert all("go list -deps" in v.message for v in violations)


def test_affects_still_degrades_to_no_opinion(broken_api: Path):
    ctx = make_ctx(broken_api, PACKAGES)
    plugin = GoDepsPlugin()
    assert plugin.validate(ctx)
    assert plugin.affects(ctx, "api", ["internal/auth/auth.go"]) is False
