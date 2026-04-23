"""Source code metrics: LOC, function count, complexity.

Supports two sources:
  - Heuristic: regex-based approximation (always available, no compilation needed)
  - Detekt: real cyclomatic complexity from Detekt XML reports (requires Gradle)
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..contracts import SourceMetrics
from ..utils.log import get_logger

log = get_logger(__name__)

_BRANCH_KEYWORDS = re.compile(r"\b(if|else|when|for|while|catch|&&|\|\|)\b")
_FUN_RE = re.compile(r"^\s*(override\s+)?fun\s+", re.MULTILINE)


def compute_metrics(
    file_path: str,
    detekt_findings: dict[str, list[dict]] | None = None,
    kover_coverage: dict[str, float] | None = None,
) -> SourceMetrics:
    """Compute source metrics for a Kotlin file.

    If ``detekt_findings`` is provided and contains data for this file,
    the MCC is taken from Detekt's CyclomaticComplexMethod findings
    and ``metrics_source`` is set to ``"detekt"``.  Otherwise a lightweight
    heuristic based on branching-keyword counting is used.

    If ``kover_coverage`` is provided, the ``test_coverage`` field is
    populated with the line coverage percentage from Kover.
    """
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return SourceMetrics()

    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return SourceMetrics()

    lines = content.splitlines()

    # ── RLOC (non-blank, non-comment lines) ──
    rloc = 0
    in_block_comment = False
    for line in lines:
        stripped = line.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue
        if stripped.startswith("//") or not stripped:
            continue
        rloc += 1

    # ── Function count ──
    functions = len(_FUN_RE.findall(content))

    # ── Test coverage (Kover) ──
    coverage = -1.0
    if kover_coverage:
        filename = p.name
        cov = kover_coverage.get(filename)
        if cov is not None:
            coverage = cov

    # ── Complexity (Detekt or heuristic) ──
    abs_path = str(p.resolve())
    findings_count = 0
    source = "heuristic"

    if detekt_findings:
        file_findings = detekt_findings.get(abs_path)
        if file_findings is None:
            for key, val in detekt_findings.items():
                if abs_path.endswith(key) or key.endswith(str(p)):
                    file_findings = val
                    break

        if file_findings:
            source = "detekt"
            findings_count = len(file_findings)
            cyclo = [f for f in file_findings if "Cyclomatic" in f.get("source", "")]
            mcc = (len(cyclo) + 1) if cyclo else (1 + findings_count)

            return SourceMetrics(
                rloc=rloc,
                functions=functions,
                mcc=mcc,
                detekt_findings=findings_count,
                test_coverage=coverage,
                metrics_source=source,
            )

    # ── Heuristic fallback ──
    mcc = 1 + len(_BRANCH_KEYWORDS.findall(content))
    return SourceMetrics(
        rloc=rloc,
        functions=functions,
        mcc=mcc,
        detekt_findings=0,
        test_coverage=coverage,
        metrics_source="heuristic",
    )


def parse_detekt_xml(xml_path: Path) -> dict[str, list[dict]]:
    """Parse a Detekt XML report (checkstyle format) into per-file findings.

    Returns a dict mapping absolute file paths to lists of finding dicts,
    each containing ``line``, ``message``, and ``source`` (rule name).
    """
    if not xml_path.exists():
        return {}

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        log.warning(f"Failed to parse Detekt XML {xml_path}: {exc}")
        return {}

    findings: dict[str, list[dict]] = {}
    for file_elem in tree.findall(".//file"):
        file_name = file_elem.get("name", "")
        if not file_name:
            continue
        file_findings = []
        for error in file_elem.findall("error"):
            file_findings.append({
                "line": int(error.get("line", 0)),
                "message": error.get("message", ""),
                "source": error.get("source", ""),
                "severity": error.get("severity", "warning"),
            })
        if file_findings:
            findings[file_name] = file_findings

    log.info(
        f"Parsed Detekt XML: {len(findings)} files with findings "
        f"({sum(len(v) for v in findings.values())} total)"
    )
    return findings


def parse_kover_xml(xml_path: Path) -> dict[str, float]:
    """Parse a Kover/JaCoCo XML report into per-file line coverage percentages.

    Returns a dict mapping source file names (e.g. ``BreedViewModel.kt``)
    to line coverage as a percentage (0.0--100.0).
    """
    if not xml_path.exists():
        return {}

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        log.warning(f"Failed to parse Kover XML {xml_path}: {exc}")
        return {}

    coverage: dict[str, float] = {}
    for sourcefile in tree.findall(".//sourcefile"):
        filename = sourcefile.get("name", "")
        if not filename:
            continue
        line_counter = sourcefile.find("counter[@type='LINE']")
        if line_counter is not None:
            missed = int(line_counter.get("missed", 0))
            covered = int(line_counter.get("covered", 0))
            total = missed + covered
            pct = (covered / total * 100) if total > 0 else 0.0
            coverage[filename] = round(pct, 1)

    log.info(f"Parsed Kover XML: {len(coverage)} files with coverage data")
    return coverage
