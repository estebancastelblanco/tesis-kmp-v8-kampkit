"""KSP enrichment layer for Phase 2 static analysis.

Injects a custom KSP processor into the shadow copy, runs
``kspCommonMainKotlinMetadata``, and parses the generated JSON
to extract resolved type references that tree-sitter cannot provide.

This is an OPTIONAL enrichment — the pipeline works correctly with
tree-sitter alone.  KSP adds:
  - Resolved FQCNs for all type references (parameters, return types, properties)
  - Supertype hierarchy traversal
  - Definitive expect/actual detection via the Kotlin compiler
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..utils.log import get_logger

log = get_logger(__name__)

KSP_VERSION = "2.3.2"
_PROCESSOR_JAR_NAME = "impact-analysis-processor.jar"


def _find_processor_jar(project_dir: Path | None = None) -> Path | None:
    """Locate the pre-built KSP processor JAR.

    Searches in order:
      1. Inside the analyzed project's tools/ directory
      2. Relative to this Python package (development mode)
      3. In the current working directory
    """
    candidates = []

    # Search in the project being analyzed (tools/kmp-impact-analyzer/tools/ksp/)
    if project_dir:
        candidates.append(project_dir / "tools" / "kmp-impact-analyzer" / "tools" / "ksp" / _PROCESSOR_JAR_NAME)

    # Search relative to the Python package
    candidates.extend([
        Path(__file__).parent.parent.parent.parent / "tools" / "ksp" / _PROCESSOR_JAR_NAME,
        Path(__file__).parent.parent.parent / "tools" / "ksp" / _PROCESSOR_JAR_NAME,
        Path.cwd() / "tools" / "kmp-impact-analyzer" / "tools" / "ksp" / _PROCESSOR_JAR_NAME,
        Path.cwd() / "tools" / "ksp" / _PROCESSOR_JAR_NAME,
    ])

    for c in candidates:
        if c.exists():
            log.info(f"KSP processor JAR found: {c}")
            return c
    return None


def _inject_ksp(project_dir: Path, processor_jar: Path) -> bool:
    """Inject KSP plugin and the custom processor into the shadow copy.

    Modifies ``settings.gradle.kts`` and subproject ``build.gradle.kts``
    files to add the KSP plugin and register the processor JAR.
    """
    settings = project_dir / "settings.gradle.kts"
    if not settings.exists():
        return False

    content = settings.read_text(encoding="utf-8", errors="replace")
    if "ksp" not in content.lower() and "pluginManagement {" in content:
        plugin_line = f'        id("com.google.devtools.ksp") version "{KSP_VERSION}" apply false\n'
        if "plugins {" in content.split("pluginManagement {")[1].split("}")[0]:
            # pluginManagement already has a plugins block — insert into it
            content = content.replace(
                'apply false\n    }',
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

    # Find the shared/common module and inject KSP + processor
    injected = False
    for bg in project_dir.rglob("build.gradle.kts"):
        if bg == project_dir / "build.gradle.kts":
            continue
        if "build" in bg.parts:
            continue
        # Only inject into modules that have Kotlin multiplatform
        src = bg.read_text(encoding="utf-8", errors="replace")
        if "kotlin.multiplatform" not in src and "kotlin-multiplatform" not in src:
            continue
        if "ksp" in src.lower():
            continue  # already has KSP

        src = src.replace(
            "plugins {",
            'plugins {\n    id("com.google.devtools.ksp")',
            1,
        )
        # Add the processor as a KSP dependency
        jar_path = str(processor_jar.resolve()).replace("\\", "/")
        src += f'\ndependencies {{\n    add("kspCommonMainMetadata", files("{jar_path}"))\n}}\n'
        bg.write_text(src, encoding="utf-8")
        log.info(f"Injected KSP into {bg.relative_to(project_dir)}")
        injected = True

    return injected


def run_ksp_enrichment(project_dir: Path) -> dict | None:
    """Run KSP on the shadow copy and return the type-resolution JSON.

    Returns a dict with ``{"files": [...]}`` containing per-file type
    references, supertypes, and expect/actual info.  Returns ``None``
    if KSP cannot run (no Java, no Gradle, compilation fails).
    """
    # Search for JAR: in the original repo checkout (CWD), in shadow copy, in package
    processor_jar = _find_processor_jar(Path.cwd())
    if processor_jar is None:
        log.info("KSP processor JAR not found — skipping type enrichment")
        return None

    gradlew = project_dir / "gradlew"
    if not gradlew.exists():
        log.info("No gradlew — skipping KSP enrichment")
        return None

    if not shutil.which("java"):
        log.info("Java not available — skipping KSP enrichment")
        return None

    # Inject KSP into the shadow copy
    if not _inject_ksp(project_dir, processor_jar):
        log.info("KSP injection failed — skipping enrichment")
        return None

    # Run KSP
    log.info("Running KSP type resolution on shadow copy...")
    try:
        result = subprocess.run(
            ["./gradlew", ":shared:kspCommonMainKotlinMetadata", "--no-daemon"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            # Try alternative module names
            for mod in ["composeApp", "common"]:
                alt = subprocess.run(
                    ["./gradlew", f":{mod}:kspCommonMainKotlinMetadata", "--no-daemon"],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if alt.returncode == 0:
                    break
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning(f"KSP execution failed: {exc}")
        return None

    # Find and parse the output JSON
    for json_path in project_dir.rglob("impact-ksp-output.json"):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            file_count = len(data.get("files", []))
            total_refs = sum(len(f.get("type_references", [])) for f in data.get("files", []))
            log.info(f"KSP enrichment: {file_count} files, {total_refs} type references")
            return data
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(f"Failed to parse KSP output: {exc}")
            return None

    log.warning("KSP ran but no output JSON found")
    return None


def enrich_graph_with_ksp(
    import_edges: dict[str, set[str]],
    reverse_edges: dict[str, set[str]],
    ksp_data: dict,
    project_root: str,
) -> int:
    """Add type-level edges to the dependency graph from KSP data.

    For each file that references a type declared in another file,
    adds an edge if one doesn't already exist from import analysis.

    Returns the number of new edges added.
    """
    # Build map: FQCN → file path
    type_to_file: dict[str, str] = {}
    file_path_map: dict[str, str] = {}  # short name → full path

    for file_info in ksp_data.get("files", []):
        fp = file_info.get("file_path", "")
        for decl in file_info.get("declarations", []):
            type_to_file[decl] = fp
        # Map short filename for matching
        short = fp.split("/")[-1] if "/" in fp else fp
        file_path_map[short] = fp

    new_edges = 0
    for file_info in ksp_data.get("files", []):
        source = file_info.get("file_path", "")
        for type_ref in file_info.get("type_references", []):
            if type_ref in type_to_file:
                target = type_to_file[type_ref]
                if source != target and target not in import_edges.get(source, set()):
                    # New edge that import analysis missed
                    import_edges.setdefault(source, set()).add(target)
                    reverse_edges.setdefault(target, set()).add(source)
                    new_edges += 1

    if new_edges > 0:
        log.info(f"KSP enrichment added {new_edges} type-level edges to the graph")
    return new_edges
