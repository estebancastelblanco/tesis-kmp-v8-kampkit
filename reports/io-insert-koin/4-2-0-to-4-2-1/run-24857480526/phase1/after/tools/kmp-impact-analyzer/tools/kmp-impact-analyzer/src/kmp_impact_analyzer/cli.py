"""CLI entry point using Click."""

from __future__ import annotations

from pathlib import Path

import click

from .config import AnalysisConfig
from .github_version_change import detect_version_changes
from .utils.log import get_logger

log = get_logger(__name__)


@click.group()
@click.version_option(version="0.1.0", prog_name="kmp-impact-analyzer")
def main() -> None:
    """KMP Impact Analyzer — Dependency impact analysis for Kotlin Multiplatform projects."""


@main.command()
@click.option("--repo", required=True, help="Path or URL to the KMP project repository")
@click.option("--dependency", required=True, help="Dependency group (e.g. io.ktor)")
@click.option("--before-version", required=True, help="Version before the change")
@click.option("--after-version", required=True, help="Version after the change")
@click.option("--output-dir", default="output", help="Output directory")
@click.option("--skip-dynamic", is_flag=True, help="Skip dynamic analysis (Phase 3)")
@click.option("--before-apk", default="", help="Path to APK built with before-version")
@click.option("--after-apk", default="", help="Path to APK built with after-version")
@click.option("--droidbot-before-output", default="", help="Path to pre-generated DroidBot output for before APK")
@click.option("--droidbot-after-output", default="", help="Path to pre-generated DroidBot output for after APK")
def analyze(
    repo: str,
    dependency: str,
    before_version: str,
    after_version: str,
    output_dir: str,
    skip_dynamic: bool,
    before_apk: str,
    after_apk: str,
    droidbot_before_output: str,
    droidbot_after_output: str,
) -> None:
    """Run full impact analysis pipeline."""
    from .pipeline import run_pipeline

    config = AnalysisConfig(
        repo_path=repo,
        dependency_group=dependency,
        before_version=before_version,
        after_version=after_version,
        output_dir=output_dir,
        skip_dynamic=skip_dynamic,
        before_apk=before_apk,
        after_apk=after_apk,
        droidbot_before_output=droidbot_before_output,
        droidbot_after_output=droidbot_after_output,
    )
    run_pipeline(config)


@main.command("run-scenario")
@click.option("--scenario-dir", required=True, type=click.Path(exists=True), help="Path to scenario directory")
@click.option("--output-dir", default="output", help="Output directory")
@click.option("--skip-dynamic", is_flag=True, help="Skip dynamic analysis (Phase 3)")
def run_scenario(scenario_dir: str, output_dir: str, skip_dynamic: bool) -> None:
    """Run analysis from a predefined scenario file."""
    import yaml

    from .pipeline import run_pipeline

    scenario_path = Path(scenario_dir) / "scenario.yml"
    if not scenario_path.exists():
        raise click.ClickException(f"scenario.yml not found in {scenario_dir}")

    with open(scenario_path) as f:
        scenario = yaml.safe_load(f)

    config = AnalysisConfig(
        repo_path=scenario.get("repo_path", scenario.get("repo_url", "")),
        dependency_group=scenario["dependency_group"],
        before_version=scenario["before_version"],
        after_version=scenario["after_version"],
        output_dir=output_dir,
        skip_dynamic=skip_dynamic,
    )
    run_pipeline(config)


@main.command("detect-version-changes")
@click.option("--before", "before_toml", required=True, type=click.Path(exists=True), help="Path to base libs.versions.toml")
@click.option("--after", "after_toml", required=True, type=click.Path(exists=True), help="Path to head libs.versions.toml")
@click.option("--format", "output_format", type=click.Choice(["json", "github"]), default="json", show_default=True, help="Output format")
def detect_version_changes_cmd(before_toml: str, after_toml: str, output_format: str) -> None:
    """Detect changed dependency groups between two Gradle version catalogs."""
    changes = detect_version_changes(before_toml, after_toml)

    if output_format == "json":
        click.echo(changes.model_dump_json(indent=2))
        return

    click.echo(f"has_changes={'true' if changes.has_changes else 'false'}")
    click.echo(f"change_count={len(changes.changes)}")
    if changes.changes:
        first = changes.changes[0]
        click.echo(f"dependency_group={first.dependency_group}")
        click.echo(f"version_key={first.version_key}")
        click.echo(f"before_version={first.before_version}")
        click.echo(f"after_version={first.after_version}")


@main.command()
@click.option("--results", required=True, type=click.Path(exists=True), help="Path to consolidated.json")
@click.option("--ground-truth", required=True, type=click.Path(exists=True), help="Path to ground_truth.yml")
@click.option("--output-dir", default="output/evaluation", help="Output directory for evaluation report")
def evaluate(results: str, ground_truth: str, output_dir: str) -> None:
    """Evaluate pipeline results against ground truth."""
    from .contracts import ConsolidatedResult
    from .evaluation.report import generate_report
    from .evaluation.scorer import score
    from .utils.json_io import load_json

    consolidated = load_json(ConsolidatedResult, results)
    result = score(consolidated, ground_truth)
    generate_report(result, output_dir)
    log.info(f"F1={result.f1:.2f}  Precision={result.precision:.2f}  Recall={result.recall:.2f}")
