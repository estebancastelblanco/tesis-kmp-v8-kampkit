"""Phase 2 orchestrator — static impact analysis.

Combines tree-sitter parsing (always available) with Detekt metrics
(when Gradle ran successfully in Phase 1).
"""

from __future__ import annotations

from pathlib import Path

from ..contracts import ImpactGraph, ShadowManifest
from ..utils.log import get_logger
from .dependency_graph import DependencyGraph
from .expect_actual import ExpectActualResolver
from .kotlin_parser import parse_project
from .source_metrics import parse_detekt_xml, parse_kover_xml
from .symbol_table import SymbolTable

log = get_logger(__name__)


def run_static_analysis(manifest: ShadowManifest) -> ImpactGraph:
    """Execute Phase 2: parse Kotlin, build graph, propagate impact.

    If Detekt XML reports are available from Phase 1, per-file metrics
    are enriched with real cyclomatic complexity data.  Otherwise the
    lightweight heuristic is used.
    """
    before_dir = Path(manifest.before_dir)
    dep_group = manifest.version_change.dependency_group

    # Load Detekt findings if available from Phase 1
    detekt_findings: dict[str, list[dict]] | None = None
    if manifest.detekt_reports:
        detekt_findings = {}
        for subproject, xml_path in manifest.detekt_reports.items():
            parsed = parse_detekt_xml(Path(xml_path))
            detekt_findings.update(parsed)
        if detekt_findings:
            log.info(f"Loaded Detekt findings for {len(detekt_findings)} files")
        else:
            log.info("Detekt reports found but no findings extracted")
            detekt_findings = None

    # Load Kover coverage if available from Phase 1
    kover_coverage: dict[str, float] | None = None
    if manifest.kover_reports:
        kover_coverage = {}
        for subproject, xml_path in manifest.kover_reports.items():
            parsed = parse_kover_xml(Path(xml_path))
            kover_coverage.update(parsed)
        if kover_coverage:
            log.info(f"Loaded Kover coverage for {len(kover_coverage)} files")
        else:
            kover_coverage = None

    # Log compilation status of AFTER copy
    comp = manifest.compilation_after
    if comp.get("status") == "failure":
        log.warning(
            f"AFTER copy failed to compile ({len(comp.get('errors', []))} errors) "
            f"— dependency change introduces breaking changes"
        )

    log.info(f"Parsing Kotlin files in {before_dir}...")
    parse_results = parse_project(before_dir)
    log.info(f"Parsed {len(parse_results)} Kotlin files")

    # Build symbol table
    symbol_table = SymbolTable()
    symbol_table.build(parse_results)

    # Build expect/actual resolver
    ea_resolver = ExpectActualResolver()
    ea_resolver.build(parse_results)

    # Build dependency graph and find seeds
    graph = DependencyGraph()
    seeds = graph.build(parse_results, dep_group)

    if not seeds:
        log.warning(f"No files found importing '{dep_group}'")

    # BFS propagation (with optional Detekt/Kover data for enriched metrics)
    impacted = graph.propagate_impact(
        seeds, ea_resolver, str(before_dir),
        detekt_findings=detekt_findings,
        kover_coverage=kover_coverage,
    )

    result = ImpactGraph(
        dependency_group=dep_group,
        version_before=manifest.version_change.before,
        version_after=manifest.version_change.after,
        seed_files=[s for s in seeds],
        impacted_files=impacted,
        expect_actual_pairs=ea_resolver.pairs,
        total_project_files=len(parse_results),
        total_impacted=len(impacted),
    )

    log.info(
        f"[bold green]Phase 2 complete[/bold green]: "
        f"{result.total_impacted}/{result.total_project_files} files impacted "
        f"({len(seeds)} direct, {len(ea_resolver.pairs)} expect/actual pairs)"
    )
    return result
