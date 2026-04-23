"""Tests for thesis-friendly HTML report generation."""

from pathlib import Path

from kmp_impact_analyzer.contracts import (
    ConsolidatedResult,
    DynamicStatus,
    FileImpact,
    ImpactGraph,
    ImpactRelation,
    ShadowManifest,
    SourceMetrics,
    TraceEntry,
    UIRegressions,
    VersionChange,
)
from kmp_impact_analyzer.reporting.report_site import generate_report_site


def _make_consolidated() -> ConsolidatedResult:
    impact = ImpactGraph(
        dependency_group="io.ktor",
        version_before="2.3.8",
        version_after="2.3.11",
        seed_files=["/project/src/com/app/Net.kt"],
        impacted_files=[
            FileImpact(
                file_path="/project/src/com/app/Net.kt",
                relation=ImpactRelation.DIRECT,
                distance=0,
                declarations=["com.app.NetClient"],
                source_set="common",
                metrics=SourceMetrics(rloc=40, functions=3, mcc=5),
            ),
            FileImpact(
                file_path="/project/src/com/app/HomeScreen.kt",
                relation=ImpactRelation.TRANSITIVE,
                distance=1,
                declarations=["com.app.HomeScreen"],
                source_set="android",
                metrics=SourceMetrics(rloc=30, functions=2, mcc=3),
            ),
        ],
        total_project_files=8,
        total_impacted=2,
    )
    return ConsolidatedResult(
        dependency_group="io.ktor",
        version_before="2.3.8",
        version_after="2.3.11",
        static_impact=impact,
        dynamic_regressions=UIRegressions(status=DynamicStatus.BLOCKED, blocked_reason="No emulator"),
        impacted_screens=["Home"],
        trace=[
            TraceEntry(file_path="/project/src/com/app/Net.kt", relation=ImpactRelation.DIRECT, screens=["Home"]),
            TraceEntry(file_path="/project/src/com/app/HomeScreen.kt", relation=ImpactRelation.TRANSITIVE),
        ],
        total_impacted_files=2,
        total_impacted_screens=1,
    )


def test_generate_report_site_creates_html_and_summary(tmp_path: Path):
    consolidated = _make_consolidated()
    manifest = ShadowManifest(
        before_dir="/project/before",
        after_dir="/project/after",
        version_change=VersionChange(
            dependency_group="io.ktor",
            version_key="ktor",
            before="2.3.8",
            after="2.3.11",
        ),
        init_script_injected=True,
    )

    (tmp_path / "phase4").mkdir()
    (tmp_path / "phase4" / "consolidated.json").write_text("{}", encoding="utf-8")
    (tmp_path / "phase5").mkdir()
    (tmp_path / "phase5" / "impact.cc.json").write_text("{}", encoding="utf-8")

    outputs = generate_report_site(consolidated, manifest, tmp_path)

    html_text = outputs["html"].read_text(encoding="utf-8")
    summary_text = outputs["summary_md"].read_text(encoding="utf-8")

    assert outputs["html"].exists()
    assert outputs["summary_json"].exists()
    assert "Reporte de Análisis de Impacto" in html_text
    assert "Shadow Build" in html_text
    assert "Grafo de Propagación" in html_text
    assert "Trazabilidad" in html_text
    assert "CodeCharta" in html_text
    assert "LOW" in summary_text or "MEDIUM" in summary_text or "HIGH" in summary_text
    assert "io.ktor" in summary_text
    assert "targeted regression checks pass" in summary_text or "Proceed cautiously" in summary_text or "basic validation" in summary_text
