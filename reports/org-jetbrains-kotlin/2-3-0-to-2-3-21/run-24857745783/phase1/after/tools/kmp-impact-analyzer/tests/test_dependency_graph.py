"""Tests for dependency graph and BFS propagation."""

from kmp_impact_analyzer.contracts import FileParseResult, ImpactRelation
from kmp_impact_analyzer.phase2_static.dependency_graph import DependencyGraph
from kmp_impact_analyzer.phase2_static.expect_actual import ExpectActualResolver


def _pr(path, pkg, imports, decls=None):
    return FileParseResult(
        file_path=path, package=pkg, imports=imports,
        declarations=decls or [],
    )


def test_finds_seeds():
    results = [
        _pr("A.kt", "com.app", ["io.ktor.client.HttpClient"]),
        _pr("B.kt", "com.app.ui", ["com.app.SomeClass"]),
    ]
    graph = DependencyGraph()
    seeds = graph.build(results, "io.ktor")
    assert "A.kt" in seeds
    assert "B.kt" not in seeds


def test_bfs_propagation():
    results = [
        _pr("A.kt", "com.app.net", ["io.ktor.client.HttpClient"]),
        _pr("B.kt", "com.app.repo", ["com.app.net.SomeClass"]),
        _pr("C.kt", "com.app.vm", ["com.app.repo.Repo"]),
        _pr("D.kt", "com.app.unrelated", ["kotlin.collections.List"]),
    ]
    resolver = ExpectActualResolver()
    resolver.build(results)

    graph = DependencyGraph()
    seeds = graph.build(results, "io.ktor")
    impacted = graph.propagate_impact(seeds, resolver, "/project")

    impacted_paths = {fi.file_path for fi in impacted}
    assert "A.kt" in impacted_paths
    # B imports from A's package, should be transitive
    assert "B.kt" in impacted_paths
    # D doesn't import anything related
    assert "D.kt" not in impacted_paths


def test_seed_is_direct():
    results = [
        _pr("A.kt", "com.app", ["io.ktor.client.HttpClient"]),
    ]
    resolver = ExpectActualResolver()
    resolver.build(results)

    graph = DependencyGraph()
    seeds = graph.build(results, "io.ktor")
    impacted = graph.propagate_impact(seeds, resolver, "/project")

    assert len(impacted) == 1
    assert impacted[0].relation == ImpactRelation.DIRECT
    assert impacted[0].distance == 0
