"""Pipeline orchestrator — runs all 5 phases sequentially."""

from __future__ import annotations

from pathlib import Path

from .config import AnalysisConfig
from .utils.json_io import save_json
from .utils.log import get_logger

log = get_logger(__name__)


def run_pipeline(config: AnalysisConfig) -> None:
    """Execute the full 5-phase impact analysis pipeline."""
    output = Path(config.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # Phase 1 — Shadow Build
    log.info("[bold]Phase 1: Shadow Build[/bold]")
    from .phase1_shadow.shadow import run_shadow

    manifest = run_shadow(config)
    save_json(manifest, output / "phase1" / "manifest.json")

    # Phase 2 — Static Analysis
    log.info("[bold]Phase 2: Static Analysis[/bold]")
    from .phase2_static.analyzer import run_static_analysis

    impact_graph = run_static_analysis(manifest)
    save_json(impact_graph, output / "phase2" / "impact_graph.json")

    # Phase 3 — Dynamic Analysis
    log.info("[bold]Phase 3: Dynamic Analysis[/bold]")
    from .phase3_dynamic.droidbot_runner import run_dynamic_analysis

    ui_regressions = run_dynamic_analysis(config)
    save_json(ui_regressions, output / "phase3" / "ui_regressions.json")

    # Phase 4 — Consolidation
    log.info("[bold]Phase 4: Consolidation[/bold]")
    from .phase4_consolidate.consolidator import run_consolidation

    consolidated = run_consolidation(
        impact_graph, ui_regressions, manifest.before_dir
    )
    save_json(consolidated, output / "phase4" / "consolidated.json")

    # Phase 5 — Visualization
    log.info("[bold]Phase 5: CodeCharta Visualization[/bold]")
    from .phase5_visualize.codecharta_builder import (
        build_codecharta,
        build_codecharta_delta,
        save_codecharta,
    )

    # Single enriched map (backward compatibility)
    cc_project = build_codecharta(consolidated, manifest.before_dir)
    save_codecharta(cc_project, output / "phase5" / "impact.cc.json")

    # Delta-ready maps: BEFORE baseline and AFTER enriched impact
    before_cc, after_cc = build_codecharta_delta(
        consolidated,
        before_root=manifest.before_dir,
        after_root=manifest.after_dir,
    )
    save_codecharta(before_cc, output / "phase5" / "before.cc.json")
    save_codecharta(after_cc, output / "phase5" / "after.cc.json")

    # Thesis-friendly HTML report + CI summary bundle
    from .reporting.report_site import generate_report_site

    generate_report_site(consolidated, manifest, output)

    # Summary
    log.info("")
    log.info("[bold green]Pipeline complete![/bold green]")
    log.info(f"  Impacted files:   {consolidated.total_impacted_files}")
    log.info(f"  Impacted screens: {consolidated.total_impacted_screens}")
    log.info(f"  Output directory:  {output.resolve()}")
