"""Build import-based dependency graph and propagate impact via BFS."""

from __future__ import annotations

from collections import defaultdict, deque

from ..contracts import FileImpact, FileParseResult, ImpactRelation
from ..utils.log import get_logger
from .expect_actual import ExpectActualResolver
from .source_metrics import compute_metrics

log = get_logger(__name__)

# Maven group → Kotlin package prefixes (when they differ)
_MAVEN_TO_KOTLIN: dict[str, list[str]] = {
    "io.insert-koin": ["org.koin"],
    "app.cash.sqldelight": ["app.cash.sqldelight", "com.squareup.sqldelight"],
    "co.touchlab": ["co.touchlab"],
    "co.touchlab.skie": ["co.touchlab.skie"],
    "org.jetbrains.kotlin": ["kotlin", "org.jetbrains.kotlin"],
    "org.jetbrains.kotlinx": ["kotlinx"],
    "com.russhwolf": ["com.russhwolf"],
}


def _maven_to_kotlin_prefixes(dependency_group: str) -> list[str]:
    """Map a Maven group ID to its Kotlin import prefixes."""
    dep_clean = dependency_group.replace(":", ".")
    # Check exact match first, then prefix match
    if dep_clean in _MAVEN_TO_KOTLIN:
        return _MAVEN_TO_KOTLIN[dep_clean]
    for maven, prefixes in _MAVEN_TO_KOTLIN.items():
        if dep_clean.startswith(maven):
            return prefixes
    return [dep_clean]


class DependencyGraph:
    """Directed graph of file-level import dependencies with BFS impact propagation."""

    def __init__(self) -> None:
        # file → set of files it imports from
        self._imports_from: dict[str, set[str]] = defaultdict(set)
        # file → set of files that import from it (reverse edges)
        self._imported_by: dict[str, set[str]] = defaultdict(set)
        self._file_parse: dict[str, FileParseResult] = {}

    def build(
        self,
        parse_results: list[FileParseResult],
        dependency_group: str,
    ) -> list[str]:
        """Build the graph and return seed files (those importing the dependency)."""
        # Index all files by package
        package_to_files: dict[str, list[str]] = defaultdict(list)
        for pr in parse_results:
            self._file_parse[pr.file_path] = pr
            if pr.package:
                package_to_files[pr.package].append(pr.file_path)

        # Build import edges
        for pr in parse_results:
            for imp in pr.imports:
                # Resolve import to files by matching package prefixes
                resolved_files = self._resolve_import(imp, package_to_files)
                for target in resolved_files:
                    if target != pr.file_path:
                        self._imports_from[pr.file_path].add(target)
                        self._imported_by[target].add(pr.file_path)

        # Find seed files: those that directly import the dependency group
        dep_prefixes = _maven_to_kotlin_prefixes(dependency_group)
        seeds: list[str] = []
        for pr in parse_results:
            for imp in pr.imports:
                if any(imp.startswith(p) for p in dep_prefixes):
                    seeds.append(pr.file_path)
                    break

        log.info(
            f"Graph: {len(parse_results)} files, "
            f"{sum(len(v) for v in self._imports_from.values())} edges, "
            f"{len(seeds)} seeds"
        )
        return seeds

    def _resolve_import(
        self, import_str: str, package_to_files: dict[str, list[str]]
    ) -> list[str]:
        """Resolve an import string to file paths."""
        if import_str.endswith(".*"):
            pkg = import_str[:-2]
            return package_to_files.get(pkg, [])

        # Try exact package match, then parent package
        parts = import_str.rsplit(".", 1)
        if len(parts) == 2:
            pkg = parts[0]
            return package_to_files.get(pkg, [])
        return []

    def propagate_impact(
        self,
        seeds: list[str],
        resolver: ExpectActualResolver,
        project_root: str,
        *,
        detekt_findings: dict[str, list[dict]] | None = None,
        kover_coverage: dict[str, float] | None = None,
    ) -> list[FileImpact]:
        """BFS from seeds through reverse import edges and expect/actual bridges.

        When *detekt_findings* is provided, per-file metrics are enriched
        with real Detekt complexity data instead of the heuristic.
        """
        visited: dict[str, FileImpact] = {}
        queue: deque[tuple[str, int, ImpactRelation]] = deque()

        # Initialize seeds
        for s in seeds:
            if s not in visited:
                pr = self._file_parse.get(s)
                dep_imports = []
                if pr:
                    dep_imports = [
                        i for i in pr.imports
                        if any(
                            i.startswith(pfx)
                            for pfx in self._get_dep_prefixes(seeds)
                        )
                    ]
                impact = FileImpact(
                    file_path=s,
                    relation=ImpactRelation.DIRECT,
                    distance=0,
                    imports_from_dependency=dep_imports,
                    metrics=compute_metrics(s, detekt_findings, kover_coverage),
                    declarations=[d.fqcn for d in (pr.declarations if pr else [])],
                    source_set=pr.source_set if pr else "common",
                )
                visited[s] = impact
                queue.append((s, 0, ImpactRelation.DIRECT))

        while queue:
            current, dist, _relation = queue.popleft()

            # Propagate through reverse import edges
            for dependent in self._imported_by.get(current, set()):
                if dependent not in visited:
                    pr = self._file_parse.get(dependent)
                    impact = FileImpact(
                        file_path=dependent,
                        relation=ImpactRelation.TRANSITIVE,
                        distance=dist + 1,
                        metrics=compute_metrics(dependent, detekt_findings, kover_coverage),
                        declarations=[d.fqcn for d in (pr.declarations if pr else [])],
                        source_set=pr.source_set if pr else "common",
                    )
                    visited[dependent] = impact
                    queue.append((dependent, dist + 1, ImpactRelation.TRANSITIVE))

            # Propagate through expect/actual bridges
            for linked in resolver.get_linked_files(current):
                if linked not in visited:
                    pr = self._file_parse.get(linked)
                    impact = FileImpact(
                        file_path=linked,
                        relation=ImpactRelation.EXPECT_ACTUAL,
                        distance=dist + 1,
                        metrics=compute_metrics(linked, detekt_findings, kover_coverage),
                        declarations=[d.fqcn for d in (pr.declarations if pr else [])],
                        source_set=pr.source_set if pr else "common",
                    )
                    visited[linked] = impact
                    queue.append((linked, dist + 1, ImpactRelation.EXPECT_ACTUAL))

        return list(visited.values())

    def _get_dep_prefixes(self, seeds: list[str]) -> set[str]:
        """Extract common dependency prefixes from seed files' imports."""
        prefixes: set[str] = set()
        for s in seeds:
            pr = self._file_parse.get(s)
            if pr:
                for imp in pr.imports:
                    parts = imp.split(".")
                    if len(parts) >= 2:
                        prefixes.add(f"{parts[0]}.{parts[1]}")
        return prefixes
