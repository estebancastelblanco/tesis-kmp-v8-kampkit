# Execution Guide

## 1. Environment setup

```bash
cd kmp-impact-analyzer
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Verify CLI is available
kmp-impact --version
```

## 2. Local analysis workflow

### Static-only execution

```bash
kmp-impact analyze \
  --repo /path/to/CursoKmpApp \
  --dependency io.ktor \
  --before-version 2.3.8 \
  --after-version 2.3.11 \
  --output-dir ./output \
  --skip-dynamic
```

### Dynamic execution

Dynamic analysis is optional and only runs when you provide APKs or pre-generated DroidBot outputs.

```bash
kmp-impact analyze \
  --repo /path/to/CursoKmpApp \
  --dependency io.ktor \
  --before-version 2.3.8 \
  --after-version 2.3.11 \
  --output-dir ./output \
  --before-apk /path/to/before.apk \
  --after-apk /path/to/after.apk
```

If DroidBot/ADB/device prerequisites are missing, the pipeline records the dynamic phase as blocked instead of crashing the whole analysis.

## 3. Scenario execution

```bash
kmp-impact run-scenario \
  --scenario-dir scenarios/cursokmpapp_ktor \
  --output-dir output-ktor \
  --skip-dynamic

kmp-impact run-scenario \
  --scenario-dir scenarios/cursokmpapp_sqldelight \
  --output-dir output-sqldelight \
  --skip-dynamic
```

## 4. Version-catalog diff detection for CI

This command is intended for GitHub Actions or manual CI debugging.

### JSON output

```bash
kmp-impact detect-version-changes \
  --before /tmp/base.libs.versions.toml \
  --after /tmp/head.libs.versions.toml
```

### GitHub Actions key-value output

```bash
kmp-impact detect-version-changes \
  --before /tmp/base.libs.versions.toml \
  --after /tmp/head.libs.versions.toml \
  --format github
```

Example output:

```text
has_changes=true
change_count=1
dependency_group=io.ktor
version_key=ktor
before_version=2.3.8
after_version=2.3.11
```

## 5. GitHub Actions setup

The included workflow is designed for a KMP repository that keeps dependency versions in `libs.versions.toml`.

### Pull-request automation

When a PR changes `libs.versions.toml`, the workflow:
1. extracts the base and head catalog files,
2. detects the changed dependency group/version pair,
3. runs `pytest -q`,
4. runs `kmp-impact analyze --skip-dynamic`,
5. generates `output/report/index.html` plus `summary.json` / `summary.md`,
6. uploads `output/` and a Pages-ready site bundle,
7. appends a GitHub job summary with risk/recommendation,
8. comments a short summary on the PR.

This PR automation is for **dependency-change PRs in the repository being analyzed** (for example Dependabot PRs that update `libs.versions.toml` in that target KMP repository).

### Manual execution

Go to **Actions → Dependency Impact Analysis → Run workflow** and provide:
- target repository path,
- dependency group,
- before version,
- after version.

This manual mode is mainly for **commits/pushes in this pipeline repository** or ad-hoc validation runs, where you want to exercise the analyzer itself and publish a stable GitHub Pages report without waiting for a target repo Dependabot PR.

## 6. Dependabot

`/.github/dependabot.yml` tracks:
- Gradle dependencies,
- Python dependencies,
- GitHub Actions versions.

This keeps the pipeline repo itself maintainable in GitHub, not just the analyzed KMP target project.

## 7. Evaluation

The current evaluation command remains available for the thesis first phase:

```bash
kmp-impact evaluate \
  --results output-ktor/phase4/consolidated.json \
  --ground-truth scenarios/cursokmpapp_ktor/ground_truth.yml \
  --output-dir output-ktor/evaluation
```

Generated files:
- `evaluation.json`
- `evaluation.md`

## 8. CodeCharta visualization

1. Run the pipeline and generate `output/phase5/*.cc.json`
2. Open <https://maibornwolff.github.io/codecharta/visualization/app/index.html>
3. Load `impact.cc.json` for a single enriched map, or `before.cc.json` + `after.cc.json` for delta mode

Suggested metrics:
- **Area** → `rloc`
- **Height** → `mcc`
- **Color** → `impacted`

## 9. Output structure

```text
output/
├── phase1/
│   ├── before/
│   ├── after/
│   └── manifest.json
├── phase2/
│   └── impact_graph.json
├── phase3/
│   └── ui_regressions.json
├── phase4/
│   └── consolidated.json
├── phase5/
│   ├── impact.cc.json
│   ├── before.cc.json
│   └── after.cc.json
├── report/
│   ├── index.html
│   ├── summary.json
│   └── summary.md
└── evaluation/
    ├── evaluation.json
    └── evaluation.md
```
