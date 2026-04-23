"""Tests for CodeCharta builder."""

from kmp_impact_analyzer.contracts import (
    CCAttribute,
    ConsolidatedResult,
    DynamicStatus,
    FileImpact,
    ImpactGraph,
    ImpactRelation,
    SourceMetrics,
    TraceEntry,
    UIRegressions,
)
from kmp_impact_analyzer.phase5_visualize.codecharta_builder import build_codecharta


def _make_consolidated():
    impact = ImpactGraph(
        dependency_group="io.ktor",
        version_before="2.3.8",
        version_after="2.3.11",
        seed_files=["src/com/app/Net.kt"],
        impacted_files=[
            FileImpact(
                file_path="/project/src/com/app/Net.kt",
                relation=ImpactRelation.DIRECT,
                distance=0,
                metrics=SourceMetrics(rloc=50, functions=3, mcc=5),
            ),
            FileImpact(
                file_path="/project/src/com/app/Repo.kt",
                relation=ImpactRelation.TRANSITIVE,
                distance=1,
                metrics=SourceMetrics(rloc=30, functions=2, mcc=3),
            ),
        ],
        total_project_files=10,
        total_impacted=2,
    )
    return ConsolidatedResult(
        dependency_group="io.ktor",
        version_before="2.3.8",
        version_after="2.3.11",
        static_impact=impact,
        dynamic_regressions=UIRegressions(status=DynamicStatus.SKIPPED),
        trace=[
            TraceEntry(file_path="/project/src/com/app/Net.kt", relation=ImpactRelation.DIRECT, screens=["Home"]),
            TraceEntry(file_path="/project/src/com/app/Repo.kt", relation=ImpactRelation.TRANSITIVE),
        ],
        total_impacted_files=2,
        total_impacted_screens=1,
    )


def test_builds_hierarchical_tree():
    consolidated = _make_consolidated()
    project = build_codecharta(consolidated, "/project", "test_project")

    assert project.project_name == "test_project"
    assert project.api_version == "1.3"
    assert len(project.nodes) == 1

    root = project.nodes[0]
    assert root.type == "Folder"
    assert root.name == "test_project"


def test_includes_attribute_types():
    consolidated = _make_consolidated()
    project = build_codecharta(consolidated, "/project")
    assert "nodes" in project.attribute_types
    assert "rloc" in project.attribute_types["nodes"]
