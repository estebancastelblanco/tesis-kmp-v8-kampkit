"""Phase 4 — Consolidate static and dynamic analysis results."""

from __future__ import annotations

from pathlib import Path

from ..contracts import (
    ConsolidatedResult,
    DynamicStatus,
    ImpactGraph,
    ImpactRelation,
    TraceEntry,
    UIRegressions,
)
from ..utils.log import get_logger
from .code_screen_mapper import CodeScreenMapper

log = get_logger(__name__)


def run_consolidation(
    impact_graph: ImpactGraph,
    ui_regressions: UIRegressions,
    project_root: str,
) -> ConsolidatedResult:
    """Merge static impact graph with dynamic UI regressions."""
    # Build code → screen mappings
    mapper = CodeScreenMapper(Path(project_root))
    screen_mappings = mapper.build(impact_graph.impacted_files)

    # Build file → screens lookup
    file_to_screens: dict[str, list[str]] = {}
    for mapping in screen_mappings:
        for f in mapping.mapped_files:
            file_to_screens.setdefault(f, []).append(mapping.screen_name)

    # Build trace entries
    trace: list[TraceEntry] = []
    all_impacted_screens: set[str] = set()

    for fi in impact_graph.impacted_files:
        screens = file_to_screens.get(fi.file_path, [])
        all_impacted_screens.update(screens)
        trace.append(
            TraceEntry(
                file_path=fi.file_path,
                relation=fi.relation,
                distance=fi.distance,
                screens=screens,
                metrics=fi.metrics,
            )
        )

    # Add dynamically-detected screens
    if ui_regressions.status == DynamicStatus.COMPLETED:
        for diff in ui_regressions.diffs:
            all_impacted_screens.add(diff.screen_name)

    result = ConsolidatedResult(
        dependency_group=impact_graph.dependency_group,
        version_before=impact_graph.version_before,
        version_after=impact_graph.version_after,
        static_impact=impact_graph,
        dynamic_regressions=ui_regressions,
        screen_mappings=screen_mappings,
        trace=trace,
        impacted_screens=sorted(all_impacted_screens),
        total_impacted_files=impact_graph.total_impacted,
        total_impacted_screens=len(all_impacted_screens),
    )

    log.info(
        f"[bold green]Phase 4 complete[/bold green]: "
        f"{result.total_impacted_files} files, "
        f"{result.total_impacted_screens} screens"
    )
    return result
