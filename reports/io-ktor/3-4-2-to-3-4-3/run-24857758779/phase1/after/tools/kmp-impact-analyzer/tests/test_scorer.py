"""Tests for evaluation scorer."""

import tempfile
from pathlib import Path

import yaml

from kmp_impact_analyzer.contracts import (
    ConsolidatedResult,
    DynamicStatus,
    FileImpact,
    ImpactGraph,
    ImpactRelation,
    SourceMetrics,
    UIRegressions,
)
from kmp_impact_analyzer.evaluation.scorer import score


def _write_ground_truth(gt: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
    yaml.dump(gt, f)
    f.close()
    return f.name


def _make_consolidated(files, screens):
    impact_files = [
        FileImpact(
            file_path=f"/project/{f}",
            relation=ImpactRelation.DIRECT,
            metrics=SourceMetrics(rloc=10),
        )
        for f in files
    ]
    impact = ImpactGraph(
        dependency_group="io.ktor",
        version_before="1.0",
        version_after="2.0",
        impacted_files=impact_files,
        total_project_files=10,
        total_impacted=len(files),
    )
    return ConsolidatedResult(
        dependency_group="io.ktor",
        version_before="1.0",
        version_after="2.0",
        static_impact=impact,
        dynamic_regressions=UIRegressions(status=DynamicStatus.SKIPPED),
        impacted_screens=screens,
        total_impacted_files=len(files),
        total_impacted_screens=len(screens),
    )


def test_perfect_score():
    gt_path = _write_ground_truth({
        "impacted_files": ["A.kt", "B.kt"],
        "impacted_screens": ["Home"],
    })
    consolidated = _make_consolidated(["A.kt", "B.kt"], ["Home"])
    result = score(consolidated, gt_path)
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.f1 == 1.0


def test_partial_recall():
    gt_path = _write_ground_truth({
        "impacted_files": ["A.kt", "B.kt", "C.kt"],
        "impacted_screens": [],
    })
    consolidated = _make_consolidated(["A.kt", "B.kt"], [])
    result = score(consolidated, gt_path)
    assert result.precision == 1.0
    assert result.recall < 1.0
    assert len(result.false_negatives) == 1


def test_false_positives():
    gt_path = _write_ground_truth({
        "impacted_files": ["A.kt"],
        "impacted_screens": [],
    })
    consolidated = _make_consolidated(["A.kt", "B.kt"], [])
    result = score(consolidated, gt_path)
    assert result.recall == 1.0
    assert result.precision < 1.0
    assert "B.kt" in result.false_positives
