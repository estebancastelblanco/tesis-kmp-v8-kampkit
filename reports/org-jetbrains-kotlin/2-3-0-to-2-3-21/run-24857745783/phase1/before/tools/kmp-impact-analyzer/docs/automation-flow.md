# Automation Flow: pipeline repo vs analyzed target repo

This repository serves two related but distinct roles in the thesis first phase.

## 1. When you commit/push in `tesis-kmp-impact-pipeline`

This is the **pipeline implementation repository**.

Typical purpose:
- evolve the analyzer itself,
- validate tests,
- manually trigger `workflow_dispatch`,
- publish a stable GitHub Pages report for demos or thesis evidence.

What happens:
1. You update the analyzer code, workflow, or docs in this repository.
2. You run tests locally or in GitHub Actions.
3. You trigger `workflow_dispatch` with the dependency group and versions you want to study.
4. The workflow runs the analyzer, generates `output/report/index.html`, uploads artifacts, and can deploy the static report to GitHub Pages.

Interpretation:
- this mode validates the **tooling and reproducibility** of the pipeline,
- it does **not** require a real Dependabot PR in another repository.

## 2. When Dependabot opens a PR in a target analyzed KMP repository

This is the **real analysis scenario** that motivates the thesis flow.

Typical purpose:
- detect a dependency bump in `libs.versions.toml`,
- run the mini-Sonar-like impact analysis automatically,
- give maintainers a risk-oriented report before merge.

What happens:
1. Dependabot (or another author) updates a dependency version in the target repository.
2. The PR changes `libs.versions.toml`.
3. GitHub Actions detects the before/after versions from the PR diff.
4. The analyzer runs against the target repository checkout.
5. It produces:
   - static impact artifacts,
   - optional UI evidence,
   - CodeCharta visualization files,
   - a navigable HTML report,
   - a PR/job summary with recommendation and risk.

Interpretation:
- this mode validates the **usefulness of the pipeline in dependency-update reviews**,
- it stays aligned with the thesis first phase because it focuses on propagation, traceability, and explainable artifacts rather than new metrics.

## Why this distinction matters in the thesis

The pipeline repository and the analyzed target repository are not the same conceptual actor:

- **Pipeline repo:** where the method is built, tested, versioned, and documented.
- **Target repo:** where dependency changes happen and where the impact analysis is consumed by reviewers.

This separation helps the thesis argument:
- the method is reproducible as software,
- the analysis is applicable to real dependency-change PRs,
- the produced evidence is review-friendly and citeable.
