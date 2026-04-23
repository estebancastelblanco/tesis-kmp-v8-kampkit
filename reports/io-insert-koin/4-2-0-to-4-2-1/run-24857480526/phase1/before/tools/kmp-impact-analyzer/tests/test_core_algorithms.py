"""Tests for core algorithms: BFS propagation, Maven-to-Kotlin mapping,
expect/actual bridging, and screen mapping heuristics."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from kmp_impact_analyzer.contracts import (
    DeclarationKind,
    FileImpact,
    FileParseResult,
    ImpactRelation,
    KotlinDeclaration,
    SourceMetrics,
)
from kmp_impact_analyzer.phase2_static.dependency_graph import (
    DependencyGraph,
    _MAVEN_TO_KOTLIN,
    _maven_to_kotlin_prefixes,
)
from kmp_impact_analyzer.phase2_static.expect_actual import ExpectActualResolver
from kmp_impact_analyzer.phase4_consolidate.code_screen_mapper import CodeScreenMapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pr(path: str, pkg: str, imports: list[str], decls: list[KotlinDeclaration] | None = None, source_set: str = "common") -> FileParseResult:
    """Shorthand factory for FileParseResult."""
    return FileParseResult(
        file_path=path,
        package=pkg,
        imports=imports,
        declarations=decls or [],
        source_set=source_set,
    )


_STUB_METRICS = SourceMetrics()


def _run_propagation(parse_results: list[FileParseResult], dep_group: str) -> list[FileImpact]:
    """Build graph, find seeds, resolve expect/actual, propagate, and return impacts."""
    resolver = ExpectActualResolver()
    resolver.build(parse_results)

    graph = DependencyGraph()
    seeds = graph.build(parse_results, dep_group)

    with patch(
        "kmp_impact_analyzer.phase2_static.dependency_graph.compute_metrics",
        return_value=_STUB_METRICS,
    ):
        return graph.propagate_impact(seeds, resolver, "/project")


# ---------------------------------------------------------------------------
# 1. test_bfs_propagation_direct
# ---------------------------------------------------------------------------

def test_bfs_propagation_direct():
    """File A imports dependency X directly; file B imports from A.
    A should be DIRECT at distance 0, B should be TRANSITIVE at distance 1."""
    results = [
        _pr("A.kt", "com.app.core", ["io.ktor.client.HttpClient"]),
        _pr("B.kt", "com.app.ui", ["com.app.core.SomeClass"]),
    ]

    impacted = _run_propagation(results, "io.ktor")
    by_path = {fi.file_path: fi for fi in impacted}

    assert "A.kt" in by_path, "Seed file A must be in the impact set"
    assert by_path["A.kt"].relation == ImpactRelation.DIRECT
    assert by_path["A.kt"].distance == 0

    assert "B.kt" in by_path, "B imports from A and must be transitively impacted"
    assert by_path["B.kt"].relation == ImpactRelation.TRANSITIVE
    assert by_path["B.kt"].distance == 1


# ---------------------------------------------------------------------------
# 2. test_bfs_propagation_distance
# ---------------------------------------------------------------------------

def test_bfs_propagation_distance():
    """Chain A -> B -> C -> D (each imports the previous package).
    Distances should be 0, 1, 2, 3 respectively."""
    results = [
        _pr("A.kt", "com.l0", ["io.ktor.client.HttpClient"]),
        _pr("B.kt", "com.l1", ["com.l0.Foo"]),
        _pr("C.kt", "com.l2", ["com.l1.Bar"]),
        _pr("D.kt", "com.l3", ["com.l2.Baz"]),
    ]

    impacted = _run_propagation(results, "io.ktor")
    by_path = {fi.file_path: fi for fi in impacted}

    assert len(by_path) == 4, f"All four files should be impacted, got {set(by_path)}"

    assert by_path["A.kt"].distance == 0
    assert by_path["B.kt"].distance == 1
    assert by_path["C.kt"].distance == 2
    assert by_path["D.kt"].distance == 3

    # Only the seed should be DIRECT
    assert by_path["A.kt"].relation == ImpactRelation.DIRECT
    for name in ("B.kt", "C.kt", "D.kt"):
        assert by_path[name].relation == ImpactRelation.TRANSITIVE


# ---------------------------------------------------------------------------
# 3. test_maven_to_kotlin_mapping
# ---------------------------------------------------------------------------

def test_maven_to_kotlin_mapping():
    """When a file imports 'org.koin.core.module' and the dependency group is
    'io.insert-koin', the mapping must resolve the Koin Maven group to the
    'org.koin' Kotlin prefix so the file is detected as a seed."""
    # Verify the mapping table first
    assert "io.insert-koin" in _MAVEN_TO_KOTLIN
    assert "org.koin" in _MAVEN_TO_KOTLIN["io.insert-koin"]

    # Verify the function itself
    prefixes = _maven_to_kotlin_prefixes("io.insert-koin")
    assert "org.koin" in prefixes

    # End-to-end: the file should become a seed
    results = [
        _pr("KoinModule.kt", "com.app.di", ["org.koin.core.module.Module"]),
        _pr("Unrelated.kt", "com.app.util", ["kotlin.collections.List"]),
    ]

    graph = DependencyGraph()
    seeds = graph.build(results, "io.insert-koin")

    assert "KoinModule.kt" in seeds
    assert "Unrelated.kt" not in seeds


# ---------------------------------------------------------------------------
# 4. test_expect_actual_bridge
# ---------------------------------------------------------------------------

def test_expect_actual_bridge():
    """An expect declaration in commonMain and an actual in androidMain.
    When the expect file is a seed, the actual file must be reached via
    the expect/actual bridge (relation = EXPECT_ACTUAL)."""
    expect_decl = KotlinDeclaration(
        kind=DeclarationKind.CLASS,
        name="PlatformDb",
        fqcn="com.app.db.PlatformDb",
        is_expect=True,
        source_set="commonMain",
        file_path="commonMain/PlatformDb.kt",
    )
    actual_decl = KotlinDeclaration(
        kind=DeclarationKind.CLASS,
        name="PlatformDb",
        fqcn="com.app.db.PlatformDb",
        is_actual=True,
        source_set="androidMain",
        file_path="androidMain/PlatformDb.kt",
    )

    results = [
        _pr(
            "commonMain/PlatformDb.kt", "com.app.db",
            ["app.cash.sqldelight.db.SqlDriver"],
            decls=[expect_decl],
            source_set="commonMain",
        ),
        _pr(
            "androidMain/PlatformDb.kt", "com.app.db",
            [],
            decls=[actual_decl],
            source_set="androidMain",
        ),
    ]

    impacted = _run_propagation(results, "app.cash.sqldelight")
    by_path = {fi.file_path: fi for fi in impacted}

    assert "commonMain/PlatformDb.kt" in by_path, "Expect file must be a seed"
    assert by_path["commonMain/PlatformDb.kt"].relation == ImpactRelation.DIRECT

    assert "androidMain/PlatformDb.kt" in by_path, (
        "Actual file must be reached via expect/actual bridge"
    )
    assert by_path["androidMain/PlatformDb.kt"].relation == ImpactRelation.EXPECT_ACTUAL
    assert by_path["androidMain/PlatformDb.kt"].distance == 1


# ---------------------------------------------------------------------------
# 5. test_screen_mapping_composable
# ---------------------------------------------------------------------------

def test_screen_mapping_composable(tmp_path: Path):
    """A FileImpact whose declarations include a known @Composable function
    should produce a screen mapping with confidence 0.9."""
    # Write a minimal Kotlin file so _scan_navigation picks up the composable
    kt_file = tmp_path / "PeopleListScreen.kt"
    kt_file.write_text(
        "@Composable\n"
        "fun PeopleListScreen() {\n"
        "    // UI\n"
        "}\n"
    )

    fi = FileImpact(
        file_path=str(kt_file),
        relation=ImpactRelation.DIRECT,
        distance=0,
        declarations=["com.app.ui.PeopleListScreen"],
    )

    mapper = CodeScreenMapper(project_root=tmp_path)
    mappings = mapper.build([fi])

    screen_names = {m.screen_name for m in mappings}
    assert "PeopleListScreen" in screen_names

    match = next(m for m in mappings if m.screen_name == "PeopleListScreen")
    assert match.confidence == pytest.approx(0.9)
    assert match.method == "composable_declaration"


# ---------------------------------------------------------------------------
# 6. test_screen_mapping_viewmodel
# ---------------------------------------------------------------------------

def test_screen_mapping_viewmodel(tmp_path: Path):
    """A FileImpact whose declarations include a ViewModel class
    should produce a screen mapping with confidence 0.8."""
    kt_file = tmp_path / "PeopleListViewModel.kt"
    kt_file.write_text(
        "class PeopleListViewModel : ViewModel() {\n"
        "    // logic\n"
        "}\n"
    )

    fi = FileImpact(
        file_path=str(kt_file),
        relation=ImpactRelation.TRANSITIVE,
        distance=1,
        declarations=["com.app.vm.PeopleListViewModel"],
    )

    mapper = CodeScreenMapper(project_root=tmp_path)
    mappings = mapper.build([fi])

    screen_names = {m.screen_name for m in mappings}
    assert "PeopleList" in screen_names, (
        f"ViewModel should map to screen 'PeopleList', got {screen_names}"
    )

    match = next(m for m in mappings if m.screen_name == "PeopleList")
    assert match.confidence == pytest.approx(0.8)
    assert match.method == "viewmodel_association"
