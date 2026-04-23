# Architecture Notes

## Goal

Provide a reproducible, modular pipeline for the **first thesis phase**: detect the code impact of a dependency version change in a KMP repository and export traceable artifacts that can later support analysis and visualization.

## Design principles

- **Phase isolation:** each pipeline phase produces a concrete output artifact.
- **Typed contracts:** inter-phase data is exchanged through Pydantic models in `contracts.py`.
- **GitHub readiness:** CI should be able to detect dependency bumps and run the same CLI pipeline used locally.
- **Scope discipline:** evaluation helpers remain available, but the repository is not extended with new metrics in this phase.

## Modules

### `config.py`
Centralizes execution parameters from CLI or YAML.

### `pipeline.py`
Orchestrates the five analysis phases in order and writes outputs into `output/phaseX/`.

### `phase1_shadow/`
Creates clean before/after shadow copies of the target repository and updates `libs.versions.toml` to represent the version transition being studied.

### `phase2_static/`
Parses Kotlin sources, builds dependency relations, resolves `expect`/`actual` links, and propagates impact from directly affected files into transitive ones.

### `phase3_dynamic/`
Handles optional DroidBot execution or pre-generated UTG inputs and compares before/after navigation graphs.

### `phase4_consolidate/`
Merges static and dynamic evidence into a traceable result model.

### `phase5_visualize/`
Builds CodeCharta outputs for interactive exploration of the impacted codebase.

### `reporting/`
Formats existing pipeline outputs into a thesis-friendly HTML report and CI summary bundle. This is a presentation layer on top of the five analysis phases, not a new analysis methodology.

### `github_version_change.py`
Provides CI-focused logic to compare two `libs.versions.toml` files and extract dependency/version transitions from a PR.

## Artifact contract

The expected progression is:

1. `phase1/manifest.json`
2. `phase2/impact_graph.json`
3. `phase3/ui_regressions.json`
4. `phase4/consolidated.json`
5. `phase5/*.cc.json`

This structure makes the pipeline easy to inspect, debug, and cite in thesis material.
