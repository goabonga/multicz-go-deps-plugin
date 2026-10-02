# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

GO_MOD = "module example.com/svc\n\ngo 1.22\n"

API_MAIN = """\
package main

import (
\t"fmt"

\t"example.com/svc/internal/auth"
)

func main() {
\tfmt.Println(auth.Token())
}
"""

WORKER_MAIN = """\
package main

import (
\t"fmt"

\t"example.com/svc/internal/queue"
)

func main() {
\tfmt.Println(queue.Name())
}
"""

AUTH_GO = 'package auth\n\nfunc Token() string {\n\treturn "token"\n}\n'
QUEUE_GO = 'package queue\n\nfunc Name() string {\n\treturn "queue"\n}\n'


@pytest.fixture
def go_project(tmp_path: Path) -> Path:
    """A minimal real Go module: ``cmd/api`` imports ``internal/auth``,
    ``cmd/worker`` imports ``internal/queue`` - no shared dependency."""
    (tmp_path / "go.mod").write_text(GO_MOD)
    (tmp_path / "cmd" / "api").mkdir(parents=True)
    (tmp_path / "cmd" / "api" / "main.go").write_text(API_MAIN)
    (tmp_path / "cmd" / "worker").mkdir(parents=True)
    (tmp_path / "cmd" / "worker" / "main.go").write_text(WORKER_MAIN)
    (tmp_path / "internal" / "auth").mkdir(parents=True)
    (tmp_path / "internal" / "auth" / "auth.go").write_text(AUTH_GO)
    (tmp_path / "internal" / "queue").mkdir(parents=True)
    (tmp_path / "internal" / "queue" / "queue.go").write_text(QUEUE_GO)
    return tmp_path


def make_ctx(repo: Path, packages: dict[str, str]) -> SimpleNamespace:
    """A stand-in :class:`~multicz.plugins.OwnershipContext` - only
    ``repo`` and ``plugin_config`` are ever read by the plugin."""
    return SimpleNamespace(
        config=None,
        repo=repo,
        plugin_config={"packages": packages},
    )
