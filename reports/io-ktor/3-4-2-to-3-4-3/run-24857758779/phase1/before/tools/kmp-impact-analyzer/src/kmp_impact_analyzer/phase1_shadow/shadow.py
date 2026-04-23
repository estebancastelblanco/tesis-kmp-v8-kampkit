"""Phase 1 — Shadow build: clone/copy repo, inject Detekt, bump version."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ..config import AnalysisConfig
from ..contracts import ShadowManifest, VersionChange
from ..utils.log import get_logger
from .toml_parser import VersionCatalog

log = get_logger(__name__)

DETEKT_VERSION = "1.23.7"
KOVER_VERSION = "0.9.8"


def _find_version_toml(project_dir: Path) -> Path | None:
    candidates = [
        project_dir / "gradle" / "libs.versions.toml",
        project_dir / "libs.versions.toml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


_IGNORE_PATTERNS = shutil.ignore_patterns(
    ".git", "build", ".gradle", ".idea",
    "__pycache__", "*.egg-info", ".pytest_cache",
    "node_modules", ".venv", "venv", ".tox",
)


def _copy_project(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, 10_000))
    try:
        shutil.copytree(src, dest, ignore=_IGNORE_PATTERNS)
    finally:
        sys.setrecursionlimit(old_limit)


def _inject_init_script(project_dir: Path, init_script_src: Path) -> bool:
    gradle_dir = project_dir / "gradle"
    gradle_dir.mkdir(exist_ok=True)
    dest = gradle_dir / "impact-analyzer-init.gradle.kts"
    if init_script_src.exists():
        shutil.copy2(init_script_src, dest)
        log.info(f"Injected init script → {dest}")
        return True
    log.warning(f"Init script not found at {init_script_src}")
    return False


def _inject_detekt(project_dir: Path) -> bool:
    """Inject the Detekt plugin directly into the shadow copy's build files.

    Modifies ``settings.gradle.kts`` (adds plugin to ``pluginManagement``)
    and each subproject ``build.gradle.kts`` (applies the plugin with
    ``ignoreFailures = true`` so analysis never breaks the build).

    Returns True if injection succeeded for at least one subproject.
    """
    settings = project_dir / "settings.gradle.kts"
    if not settings.exists():
        log.warning("settings.gradle.kts not found — skipping Detekt injection")
        return False

    # Inject Detekt into pluginManagement
    content = settings.read_text(encoding="utf-8", errors="replace")
    plugin_line = (
        f'    plugins {{\n'
        f'        id("io.gitlab.arturbosch.detekt") version "{DETEKT_VERSION}" apply false\n'
        f'    }}\n'
    )
    if "pluginManagement {" in content and "detekt" not in content:
        content = content.replace(
            "pluginManagement {",
            f"pluginManagement {{\n{plugin_line}",
            1,
        )
        settings.write_text(content, encoding="utf-8")
        log.info("Injected Detekt plugin into settings.gradle.kts")

    # Apply Detekt to each subproject build file
    injected = False
    for bg in project_dir.rglob("build.gradle.kts"):
        if bg == project_dir / "build.gradle.kts":
            continue  # skip root
        if "build" in bg.parts:
            continue  # skip generated
        src = bg.read_text(encoding="utf-8", errors="replace")
        if "plugins {" in src and "detekt" not in src:
            src = src.replace(
                "plugins {",
                'plugins {\n    id("io.gitlab.arturbosch.detekt")',
                1,
            )
            src += '\ndetekt {\n    ignoreFailures = true\n    buildUponDefaultConfig = true\n    reports { xml { required.set(true) } }\n}\n'
            bg.write_text(src, encoding="utf-8")
            log.info(f"Injected Detekt into {bg.relative_to(project_dir)}")
            injected = True

    return injected


def _run_detekt(project_dir: Path) -> dict[str, Path]:
    """Run Detekt on the shadow copy and return paths to XML reports.

    Returns a mapping of ``subproject_name -> detekt.xml`` path.
    If Gradle is not available or the build fails, returns an empty dict
    (the pipeline falls back to heuristic metrics).
    """
    gradlew = project_dir / "gradlew"
    if not gradlew.exists():
        log.info("No gradlew found — Detekt skipped (using heuristic metrics)")
        return {}

    # Discover detekt tasks
    try:
        result = subprocess.run(
            ["./gradlew", "tasks", "--all", "--no-daemon"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        detekt_tasks = [
            t for t in set(
                w for w in result.stdout.split()
                if "detekt" in w.lower()
                and "baseline" not in w.lower()
                and (":" in w or w == "detekt")
            )
            if not t.endswith("GenerateConfig")
        ]
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning(f"Gradle task discovery failed: {exc}")
        return {}

    if not detekt_tasks:
        log.info("No detekt tasks found — using heuristic metrics")
        return {}

    # Prefer targeted tasks: :app:detekt and :shared:detektMetadataCommonMain
    preferred = [t for t in detekt_tasks if t in (
        ":app:detekt", ":shared:detektMetadataCommonMain", ":shared:detekt",
        ":composeApp:detekt", ":androidApp:detekt",
    )]
    tasks_to_run = preferred if preferred else detekt_tasks[:5]

    log.info(f"Running Detekt tasks: {' '.join(tasks_to_run)}")
    try:
        subprocess.run(
            ["./gradlew", *tasks_to_run, "--no-daemon", "--continue"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning(f"Detekt execution failed: {exc}")

    # Collect XML reports
    reports: dict[str, Path] = {}
    for xml in project_dir.rglob("reports/detekt/detekt.xml"):
        # Extract subproject name from path
        rel = xml.relative_to(project_dir)
        subproject = rel.parts[0] if len(rel.parts) > 1 else "root"
        reports[subproject] = xml
        log.info(f"Detekt report: {subproject} → {xml}")

    return reports


def _inject_kover(project_dir: Path) -> bool:
    """Inject the Kover plugin into the shadow copy for test coverage analysis.

    Same injection pattern as Detekt: modifies ``settings.gradle.kts`` and
    subproject ``build.gradle.kts`` files in the shadow copy.
    """
    settings = project_dir / "settings.gradle.kts"
    if not settings.exists():
        return False

    content = settings.read_text(encoding="utf-8", errors="replace")
    if "kover" not in content and "pluginManagement {" in content:
        plugin_line = f'        id("org.jetbrains.kotlinx.kover") version "{KOVER_VERSION}" apply false\n'
        # Insert after Detekt plugin if present, otherwise after pluginManagement {
        if "detekt" in content:
            content = content.replace(
                f'apply false\n    }}',
                f'apply false\n{plugin_line}    }}',
                1,
            )
        else:
            content = content.replace(
                "pluginManagement {",
                f"pluginManagement {{\n    plugins {{\n{plugin_line}    }}\n",
                1,
            )
        settings.write_text(content, encoding="utf-8")

    injected = False
    for bg in project_dir.rglob("build.gradle.kts"):
        if bg == project_dir / "build.gradle.kts":
            continue
        if "build" in bg.parts:
            continue
        src = bg.read_text(encoding="utf-8", errors="replace")
        if "plugins {" in src and "kover" not in src:
            src = src.replace(
                "plugins {",
                'plugins {\n    id("org.jetbrains.kotlinx.kover")',
                1,
            )
            bg.write_text(src, encoding="utf-8")
            log.info(f"Injected Kover into {bg.relative_to(project_dir)}")
            injected = True

    return injected


def _run_kover(project_dir: Path) -> dict[str, Path]:
    """Run Kover on the shadow copy and return paths to coverage XML reports.

    Kover triggers test execution and generates JaCoCo-format XML with
    per-file line coverage.  If tests fail, partial coverage may still
    be available.  Returns empty dict if Gradle is unavailable.
    """
    gradlew = project_dir / "gradlew"
    if not gradlew.exists():
        return {}

    log.info("Running Kover (test coverage)...")
    try:
        subprocess.run(
            ["./gradlew", "koverXmlReport", "--no-daemon", "--continue"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning(f"Kover execution failed: {exc}")

    reports: dict[str, Path] = {}
    for xml in project_dir.rglob("reports/kover/*.xml"):
        rel = xml.relative_to(project_dir)
        subproject = rel.parts[0] if len(rel.parts) > 1 else "root"
        reports[subproject] = xml
        log.info(f"Kover report: {subproject} → {xml}")

    return reports


def _run_compilation_check(project_dir: Path) -> dict:
    """Compile the shadow copy and return success/failure with error details.

    This validates whether the dependency change introduces breaking changes.
    Compilation errors pinpoint exactly which files and lines break.
    """
    gradlew = project_dir / "gradlew"
    if not gradlew.exists():
        return {"status": "skipped", "reason": "no gradlew"}

    # Discover compile tasks
    compile_tasks = []
    try:
        result = subprocess.run(
            ["./gradlew", "tasks", "--all", "--no-daemon"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        compile_tasks = [
            w for w in set(result.stdout.split())
            if "compileKotlin" in w and ":" in w and "Test" not in w
        ][:3]
    except (subprocess.TimeoutExpired, OSError):
        pass

    if not compile_tasks:
        compile_tasks = [":shared:compileKotlinMetadata"]

    log.info(f"Compilation check: {' '.join(compile_tasks)}")
    try:
        result = subprocess.run(
            ["./gradlew", *compile_tasks, "--no-daemon", "--continue"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )
        errors = [
            line.strip()
            for line in (result.stderr + result.stdout).splitlines()
            if line.strip().startswith("e: ") or "error:" in line.lower()
        ][:50]
        status = "success" if result.returncode == 0 else "failure"
        log.info(f"Compilation {status}: {len(errors)} errors")
        return {"status": status, "errors": errors, "tasks": compile_tasks}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "tasks": compile_tasks}


def run_shadow(config: AnalysisConfig) -> ShadowManifest:
    """Execute Phase 1: create BEFORE/AFTER copies and bump version in AFTER."""
    output = Path(config.output_dir) / "phase1"
    output.mkdir(parents=True, exist_ok=True)

    repo = Path(config.repo_path)
    if not repo.is_dir():
        raise FileNotFoundError(f"Repository not found: {repo}")

    before_dir = output / "before"
    after_dir = output / "after"

    log.info("Copying project to BEFORE and AFTER directories...")
    _copy_project(repo, before_dir)
    _copy_project(repo, after_dir)

    # Inject Gradle init script into both copies
    init_script = config.resolve_init_script()
    injected_before = _inject_init_script(before_dir, init_script)
    injected_after = _inject_init_script(after_dir, init_script)

    # Find and parse the version catalog in BEFORE — pin to before_version
    before_toml_path = _find_version_toml(before_dir)
    if before_toml_path is None:
        raise FileNotFoundError("libs.versions.toml not found in project")

    before_catalog = VersionCatalog(before_toml_path)
    version_key = before_catalog.find_version_key(config.dependency_group)
    if version_key is None:
        raise ValueError(
            f"Dependency group '{config.dependency_group}' not found in version catalog"
        )

    current_version = before_catalog.get_version(version_key)
    log.info(f"Found {config.dependency_group} using version key '{version_key}' = {current_version}")

    # Pin BEFORE to before_version
    before_catalog.set_version(version_key, config.before_version)

    # Find and parse the version catalog in AFTER — set to after_version
    after_toml_path = _find_version_toml(after_dir)
    after_catalog = VersionCatalog(after_toml_path)
    after_catalog.set_version(version_key, config.after_version)

    # ── Gradle-based analysis on BEFORE copy (stable build) ──
    detekt_reports: dict[str, str] = {}
    kover_reports: dict[str, str] = {}
    compilation_before: dict = {"status": "skipped"}
    compilation_after: dict = {"status": "skipped"}

    # Inject and run Detekt
    if _inject_detekt(before_dir):
        log.info("Running Detekt on BEFORE shadow copy...")
        raw_detekt = _run_detekt(before_dir)
        detekt_reports = {k: str(v) for k, v in raw_detekt.items()}

    # Inject and run Kover (test coverage)
    if _inject_kover(before_dir):
        log.info("Running Kover on BEFORE shadow copy...")
        raw_kover = _run_kover(before_dir)
        kover_reports = {k: str(v) for k, v in raw_kover.items()}

    # Compilation check on AFTER copy (detect breaking changes)
    log.info("Compiling AFTER shadow copy (breaking change detection)...")
    compilation_after = _run_compilation_check(after_dir)

    manifest = ShadowManifest(
        before_dir=str(before_dir),
        after_dir=str(after_dir),
        version_change=VersionChange(
            dependency_group=config.dependency_group,
            version_key=version_key,
            before=config.before_version,
            after=config.after_version,
        ),
        init_script_injected=injected_before and injected_after,
        detekt_reports=detekt_reports,
        kover_reports=kover_reports,
        compilation_after=compilation_after,
    )

    log.info("[bold green]Phase 1 complete[/bold green]")
    return manifest
