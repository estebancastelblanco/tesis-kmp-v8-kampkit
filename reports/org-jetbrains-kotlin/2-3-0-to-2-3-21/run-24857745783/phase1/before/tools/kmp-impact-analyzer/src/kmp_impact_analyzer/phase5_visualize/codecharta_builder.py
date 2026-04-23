"""Phase 5 — Generate CodeCharta .cc.json visualization file."""

from __future__ import annotations

import json
from pathlib import Path

from ..contracts import (
    CCAttribute,
    CCProject,
    ConsolidatedResult,
    ImpactRelation,
)
from ..utils.log import get_logger
from .tree_builder import build_tree

log = get_logger(__name__)

_SKIPPED_PARTS = {
    '.git',
    '.gradle',
    '.idea',
    '.venv',
    '.venv-subagent',
    'build',
    'generated',
    'node_modules',
    'evidence',
}

_ATTRIBUTE_TYPES = {
    "nodes": {
        "rloc": "absolute",
        "mcc": "absolute",
        "impacted": "absolute",
        "impact_direct": "absolute",
        "impact_transitive": "absolute",
        "screen_impacted": "absolute",
        "screen_names": "absolute",
    }
}


def _make_relative_path(file_path: str, project_root: str) -> str:
    """Convert absolute path to project-relative."""
    try:
        return str(Path(file_path).relative_to(project_root))
    except ValueError:
        # If not relative, just use the filename
        return Path(file_path).name


def _collect_source_files(project_root: str) -> list[str]:
    """Collect Kotlin source files from a project, skipping build/generated/embedded-output folders."""
    root = Path(project_root)
    files: list[str] = []
    for kt_file in sorted(root.rglob("*.kt")):
        parts = set(kt_file.parts)
        if parts & _SKIPPED_PARTS:
            continue
        files.append(str(kt_file))
    return files


def _build_impacted_lookups(
    consolidated: ConsolidatedResult,
    before_root: str,
) -> tuple[dict[str, ImpactRelation], dict[str, int]]:
    """Build relpath lookups for impacted relation and impacted screen count."""
    relations: dict[str, ImpactRelation] = {}
    screen_counts: dict[str, int] = {}

    for fi in consolidated.static_impact.impacted_files:
        rel = _make_relative_path(fi.file_path, before_root)
        relations[rel] = fi.relation

    for entry in consolidated.trace:
        rel = _make_relative_path(entry.file_path, before_root)
        screen_counts[rel] = len(entry.screens)

    return relations, screen_counts


def _build_project_from_paths(
    project_root: str,
    project_name: str,
    impacted_relations: dict[str, ImpactRelation] | None = None,
    screen_counts: dict[str, int] | None = None,
) -> CCProject:
    """Build a CodeCharta project for all Kotlin files in a project path."""
    impacted_relations = impacted_relations or {}
    screen_counts = screen_counts or {}

    file_attrs: dict[str, CCAttribute] = {}
    for abs_path in _collect_source_files(project_root):
        rel_path = _make_relative_path(abs_path, project_root)
        relation = impacted_relations.get(rel_path)
        screen_count = screen_counts.get(rel_path, 0)

        from ..phase2_static.source_metrics import compute_metrics
        metrics = compute_metrics(abs_path)

        file_attrs[rel_path] = CCAttribute(
            rloc=metrics.rloc,
            mcc=metrics.mcc,
            impacted=1 if relation is not None else 0,
            impact_direct=1 if relation == ImpactRelation.DIRECT else 0,
            impact_transitive=1 if relation in (ImpactRelation.TRANSITIVE, ImpactRelation.EXPECT_ACTUAL) else 0,
            screen_impacted=1 if screen_count > 0 else 0,
            screen_names=screen_count,
        )

    root_node = build_tree(file_attrs, project_name)
    return CCProject(
        project_name=project_name,
        api_version="1.3",
        nodes=[root_node],
        attribute_types=_ATTRIBUTE_TYPES,
    )


def build_codecharta(
    consolidated: ConsolidatedResult,
    project_root: str,
    project_name: str = "",
) -> CCProject:
    """Build an enriched CodeCharta project from consolidated results (single map)."""
    if not project_name:
        project_name = consolidated.dependency_group.replace(".", "_")

    relations, screen_counts = _build_impacted_lookups(consolidated, project_root)
    project = _build_project_from_paths(
        project_root=project_root,
        project_name=project_name,
        impacted_relations=relations,
        screen_counts=screen_counts,
    )
    log.info(
        f"[bold green]Phase 5 complete[/bold green]: "
        f"CodeCharta project with {len(_collect_source_files(project_root))} files"
    )
    return project


def build_codecharta_delta(
    consolidated: ConsolidatedResult,
    before_root: str,
    after_root: str,
    project_name: str = "",
) -> tuple[CCProject, CCProject]:
    """Build BEFORE and AFTER CodeCharta projects for Delta mode."""
    if not project_name:
        project_name = consolidated.dependency_group.replace(".", "_")

    relations, screen_counts = _build_impacted_lookups(consolidated, before_root)

    before_project = _build_project_from_paths(
        project_root=before_root,
        project_name=f"{project_name}_before",
    )
    after_project = _build_project_from_paths(
        project_root=after_root,
        project_name=f"{project_name}_after",
        impacted_relations=relations,
        screen_counts=screen_counts,
    )
    return before_project, after_project


def save_codecharta(project: CCProject, output_path: str | Path) -> Path:
    """Save CodeCharta project as .cc.json file."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    data = project.model_dump()
    # CodeCharta expects camelCase at top-level.
    data = {
        "projectName": data.get("project_name", ""),
        "apiVersion": data.get("api_version", "1.3"),
        "nodes": data.get("nodes", []),
        "attributeTypes": data.get("attribute_types", {}),
    }
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Saved CodeCharta → {p}")
    return p
