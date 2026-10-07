# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""multicz-go-deps-plugin - claim a Go component by its
compiler-verified import graph instead of a hand-maintained ``paths``
glob.

A Go binary's real dependency graph is whatever ``go list -deps``
says it is. A ``multicz.toml`` ``paths`` glob is whatever someone
remembered to write down. The two drift apart the moment a package
gains a new ``internal/`` import and nobody updates the glob - the
component silently stops seeing changes that should have bumped it.

This package implements :meth:`multicz.plugins.Plugin.affects` - the
one hook that runs *before* path matching has necessarily failed - to
give a component a second chance: if the plain-glob match misses a
changed file, ask the Go compiler's own import graph whether the
file's directory is actually a dependency of that component's binary.

It never *replaces* ``paths``; it only widens what counts as "yes,
this touches me" past what the globs already caught.

It also implements :meth:`multicz.plugins.Plugin.enrich_changelog`: a
release that exists only because an imported package changed gets a
``Dependencies`` line naming that package, next to multicz's own
``Track ...`` cascade lines.

``affects`` answers "no opinion" when ``go list`` fails, so a broken
module (a corrupted ``go.sum``, a package that no longer builds) would
silently stop claiming changes. :meth:`multicz.plugins.Plugin.validate`
reports that failure in ``multicz validate`` as a warning, which
``multicz validate --strict`` turns into a failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from multicz.config import ComponentMatcher
from multicz.plugins import BasePlugin, ChangelogEntry, Severity, Violation

if TYPE_CHECKING:
    from multicz.plugins import OwnershipContext, PluginContext

DEFAULT_CHANGELOG_SECTION = "Dependencies"

__version__ = "0.3.0"

__all__ = ["GoDepsPlugin"]


class GoDepsPlugin(BasePlugin):
    """Plugin entry point registered under ``multicz.plugins``."""

    # ``name`` is required. It must match the entry-point key declared
    # in pyproject.toml AND the ``[plugins.<name>]`` section in the
    # consumer's multicz.toml.
    name = "go-deps"

    def __init__(self) -> None:
        # One ``go list`` call per (repo, package) for the lifetime of
        # this plugin instance - ``affects`` is called once per
        # component by ``changed`` and once per (component, commit) by
        # the planner, and the import graph doesn't change mid-run.
        self._go_list_cache: dict[
            tuple[Path, tuple[str, ...]], tuple[frozenset[Path], str | None]
        ] = {}

    def _packages(
        self, ctx: OwnershipContext | PluginContext
    ) -> dict[str, tuple[str, ...]]:
        """``{component: (go-package-import-path, ...)}`` from
        ``[plugins.go-deps.packages]``. A component missing from this
        map has nothing for this plugin to say about it.

        A component that ships more than one binary (e.g. a daemon
        plus a sidecar it spawns) declares a list of import paths
        instead of a single string - both forms are accepted."""
        raw: dict[str, str | list[str]] = ctx.plugin_config.get("packages", {})
        return {
            name: (value,) if isinstance(value, str) else tuple(value)
            for name, value in raw.items()
        }

    def _go_list(
        self, ctx: OwnershipContext | PluginContext, packages: tuple[str, ...]
    ) -> tuple[frozenset[Path], str | None]:
        """Resolved, absolute directories of every package in
        ``packages`` (including themselves), and why ``go list`` failed
        when it did - in which case the directories are empty, so a
        broken toolchain degrades to "no opinion" rather than crashing
        the bump."""
        key = (ctx.repo, packages)
        cached = self._go_list_cache.get(key)
        if cached is not None:
            return cached
        try:
            result = subprocess.run(
                ["go", "list", "-deps", "-f", "{{.Dir}}", *packages],
                cwd=ctx.repo,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            outcome: tuple[frozenset[Path], str | None] = (frozenset(), str(exc))
        else:
            if result.returncode == 0:
                outcome = (
                    frozenset(
                        Path(line).resolve()
                        for line in result.stdout.splitlines()
                        if line.strip()
                    ),
                    None,
                )
            else:
                # Progress lines ("go: downloading ...") say nothing about
                # the failure.
                lines = [
                    line.strip()
                    for line in result.stderr.splitlines()
                    if line.strip() and not line.startswith("go: downloading ")
                ]
                reason = "; ".join(lines) or f"exit status {result.returncode}"
                outcome = (frozenset(), reason)
        self._go_list_cache[key] = outcome
        return outcome

    def _dep_dirs(
        self, ctx: OwnershipContext | PluginContext, packages: tuple[str, ...]
    ) -> frozenset[Path]:
        return self._go_list(ctx, packages)[0]

    def _failures(
        self, ctx: OwnershipContext | PluginContext, severity: Severity
    ) -> list[Violation]:
        """One violation per component whose packages ``go list`` cannot load."""
        violations: list[Violation] = []
        for component, packages in sorted(self._packages(ctx).items()):
            _, error = self._go_list(ctx, packages)
            if error is not None:
                violations.append(
                    Violation(
                        severity,
                        f"go list -deps {' '.join(packages)} failed, so changes to "
                        f"its imports cannot be attributed: {error}",
                        component=component,
                        plugin=self.name,
                    )
                )
        return violations

    def validate(self, ctx: OwnershipContext) -> list[Violation]:
        """Report every component whose import graph cannot be loaded,
        as a warning (failing ``multicz validate --strict``)."""
        return self._failures(ctx, Severity.warning)

    def affects(self, ctx: OwnershipContext, component: str, paths: list[str]) -> bool:
        packages = self._packages(ctx).get(component)
        if packages is None:
            return False
        dep_dirs = self._dep_dirs(ctx, packages)
        if not dep_dirs:
            return False
        return any((ctx.repo / path).resolve().parent in dep_dirs for path in paths)

    def enrich_changelog(
        self, ctx: PluginContext, component: str
    ) -> list[ChangelogEntry]:
        """Name the imported packages behind a bump the paths did not explain.

        For each commit the plan attributes to ``component`` without any
        of its files matching the component's ``paths``, list the changed
        directories that are Go dependencies of its binaries, e.g.
        ``Import `internal/transport` changed (`7cf9773`)``. The section
        title comes from ``[plugins.go-deps] changelog_section`` (default
        ``Dependencies``, merged with multicz's cascade lines); an empty
        title disables the section.
        """
        section = ctx.plugin_config.get("changelog_section", DEFAULT_CHANGELOG_SECTION)
        packages = self._packages(ctx).get(component)
        bump = ctx.plan.bumps.get(component) if ctx.plan is not None else None
        if not section or packages is None or bump is None:
            return []
        dep_dirs = self._dep_dirs(ctx, packages)
        if not dep_dirs:
            return []
        matcher = ComponentMatcher(ctx.config.components)
        lines: list[str] = []
        for reason in bump.reasons:
            files: tuple[str, ...] = getattr(reason, "files", ())
            sha: str | None = getattr(reason, "sha", None)
            if not files or not sha:
                continue
            # A commit the paths already own explains itself in the
            # regular changelog sections.
            if any(component in matcher.match_all(path) for path in files):
                continue
            imported = sorted(
                {
                    Path(path).parent.as_posix()
                    for path in files
                    if (ctx.repo / path).resolve().parent in dep_dirs
                }
            )
            if imported:
                names = ", ".join(f"`{name}`" for name in imported)
                lines.append(f"Import {names} changed (`{sha[:7]}`)")
        if not lines:
            return []
        return [
            ChangelogEntry(section=section, component=component, lines=tuple(lines))
        ]
