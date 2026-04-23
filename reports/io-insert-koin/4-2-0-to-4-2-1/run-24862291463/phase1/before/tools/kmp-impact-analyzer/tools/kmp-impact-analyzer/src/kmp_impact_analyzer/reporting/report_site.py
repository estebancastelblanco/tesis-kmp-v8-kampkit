"""Generate thesis-friendly HTML reports and CI summaries from pipeline outputs."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

from ..contracts import ConsolidatedResult, DynamicStatus, ImpactRelation, ShadowManifest, UIRegressions
from ..utils.log import get_logger

log = get_logger(__name__)

_SKIPPED_ARTIFACT_PARTS = {
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


def _risk_level(consolidated: ConsolidatedResult) -> str:
    direct = sum(1 for f in consolidated.static_impact.impacted_files if f.relation == ImpactRelation.DIRECT)
    screens = consolidated.total_impacted_screens
    if direct >= 8 or consolidated.total_impacted_files >= 20 or screens >= 6:
        return "high"
    if direct >= 3 or consolidated.total_impacted_files >= 8 or screens >= 2:
        return "medium"
    return "low"


def _recommendation(consolidated: ConsolidatedResult) -> str:
    risk = _risk_level(consolidated)
    dynamic = consolidated.dynamic_regressions.status
    if risk == "high":
        return "Hold merge until impacted files are reviewed and targeted regression checks pass."
    if dynamic == DynamicStatus.BLOCKED:
        return "Proceed cautiously: static evidence exists, but UI validation is still blocked and should be completed."
    if risk == "medium":
        return "Review the directly impacted files and run focused smoke tests before merging."
    return "Low apparent impact; merge is reasonable after normal review and basic validation."


def _dynamic_summary(ui: UIRegressions) -> str:
    if ui.status == DynamicStatus.COMPLETED:
        return f"completed ({len(ui.diffs)} screen diffs)"
    if ui.status == DynamicStatus.BLOCKED:
        return f"blocked ({ui.blocked_reason})"
    return "skipped"


def _top_impacted_files(consolidated: ConsolidatedResult, limit: int = 10) -> list[dict[str, Any]]:
    sorted_files = sorted(
        consolidated.static_impact.impacted_files,
        key=lambda fi: (
            0 if fi.relation == ImpactRelation.DIRECT else 1,
            -fi.metrics.mcc,
            -fi.metrics.rloc,
            fi.file_path,
        ),
    )
    rows: list[dict[str, Any]] = []
    for fi in sorted_files[:limit]:
        rows.append(
            {
                "file_path": fi.file_path,
                "relation": fi.relation.value,
                "distance": fi.distance,
                "source_set": fi.source_set,
                "rloc": fi.metrics.rloc,
                "mcc": fi.metrics.mcc,
                "declarations": fi.declarations,
            }
        )
    return rows


def _phase_status(consolidated: ConsolidatedResult) -> dict[str, dict[str, str]]:
    dynamic = consolidated.dynamic_regressions
    has_dynamic_data = len(dynamic.diffs) > 0 or len(dynamic.before_screens) > 0
    if dynamic.status == DynamicStatus.COMPLETED or has_dynamic_data:
        phase3_status = "completed"
        phase3_detail = f"{len(dynamic.diffs)} diferencias"
    elif dynamic.status == DynamicStatus.BLOCKED:
        phase3_status = "blocked"
        phase3_detail = dynamic.blocked_reason or "Bloqueado"
    else:
        phase3_status = "skipped"
        phase3_detail = "Omitido"

    return {
        "phase1": {
            "title": "Shadow Build",
            "status": "completed",
            "detail": "Completado",
        },
        "phase2": {
            "title": "Análisis Estático",
            "status": "completed",
            "detail": f"{consolidated.total_impacted_files} archivos",
        },
        "phase3": {
            "title": "Análisis Dinámico",
            "status": phase3_status,
            "detail": phase3_detail,
        },
        "phase4": {
            "title": "Consolidación",
            "status": "completed",
            "detail": f"{consolidated.total_impacted_screens} pantalla(s)",
        },
        "phase5": {
            "title": "Visualización",
            "status": "completed",
            "detail": "CodeCharta",
        },
    }


def build_summary_payload(
    consolidated: ConsolidatedResult,
    manifest: ShadowManifest | None = None,
    report_url: str = "",
) -> dict[str, Any]:
    risk = _risk_level(consolidated)
    payload = {
        "dependency_group": consolidated.dependency_group,
        "version_before": consolidated.version_before,
        "version_after": consolidated.version_after,
        "risk_level": risk,
        "recommendation": _recommendation(consolidated),
        "report_url": report_url,
        "total_impacted_files": consolidated.total_impacted_files,
        "total_impacted_screens": consolidated.total_impacted_screens,
        "direct_impacts": sum(1 for f in consolidated.static_impact.impacted_files if f.relation == ImpactRelation.DIRECT),
        "transitive_impacts": sum(1 for f in consolidated.static_impact.impacted_files if f.relation != ImpactRelation.DIRECT),
        "expect_actual_impacts": sum(1 for f in consolidated.static_impact.impacted_files if f.relation == ImpactRelation.EXPECT_ACTUAL),
        "total_project_files": consolidated.static_impact.total_project_files,
        "dynamic_status": consolidated.dynamic_regressions.status.value,
        "dynamic_summary": _dynamic_summary(consolidated.dynamic_regressions),
        "dynamic_diffs": len(consolidated.dynamic_regressions.diffs),
        "before_screens": len(consolidated.dynamic_regressions.before_screens),
        "after_screens": len(consolidated.dynamic_regressions.after_screens),
        "screen_mappings": len(consolidated.screen_mappings),
        "trace_entries": len(consolidated.trace),
        "seed_files": consolidated.static_impact.seed_files,
        "impacted_screens": consolidated.impacted_screens,
        "top_impacted_files": _top_impacted_files(consolidated),
    }
    if manifest is not None:
        payload["version_key"] = manifest.version_change.version_key
    return payload


def build_summary_markdown(summary: dict[str, Any]) -> str:
    report_line = (
        f"- **Full report:** {summary['report_url']}"
        if summary.get("report_url")
        else "- **Full report:** generated as static artifact/site in `output/report/`"
    )
    lines = [
        "### Dependabot impact companion",
        "",
        f"- **Dependency:** `{summary['dependency_group']}`",
        f"- **Version change:** `{summary['version_before']}` → `{summary['version_after']}`",
        f"- **Risk:** **{summary['risk_level'].upper()}**",
        f"- **Recommendation:** {summary['recommendation']}",
        f"- **Static impact:** {summary['total_impacted_files']} files ({summary['direct_impacts']} direct / {summary['transitive_impacts']} transitive-or-expect-actual)",
        f"- **UI impact:** {summary['total_impacted_screens']} screens",
        f"- **Dynamic analysis:** {summary['dynamic_summary']}",
        report_line,
        "",
        "### Top impacted files",
        "",
        "| File | Relation | Source set | RLOC | MCC |",
        "|------|----------|------------|------|-----|",
    ]
    for row in summary.get("top_impacted_files", []):
        lines.append(
            f"| `{row['file_path']}` | {row['relation']} | {row['source_set']} | {row['rloc']} | {row['mcc']} |"
        )
    if not summary.get("top_impacted_files"):
        lines.append("| _None_ | - | - | - | - |")
    return "\n".join(lines) + "\n"


def _artifact_links(output_dir: Path) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for pattern in ("*.json", "*.cc.json"):
        for path in sorted(output_dir.rglob(pattern)):
            rel = path.relative_to(output_dir)
            if set(rel.parts) & _SKIPPED_ARTIFACT_PARTS:
                continue
            pair = (rel.as_posix(), rel.as_posix())
            if pair in seen:
                continue
            seen.add(pair)
            links.append(pair)
    return links


def _load_toml_content(output_root: Path, variant: str) -> str:
    """Load libs.versions.toml content from phase1 shadow directories."""
    for candidate in [
        output_root / "phase1" / variant / "gradle" / "libs.versions.toml",
        output_root / "phase1" / variant / "gradle" / "libs.versions.toml",
    ]:
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except OSError:
                pass
    # Try to find any .toml in the variant directory
    variant_dir = output_root / "phase1" / variant
    if variant_dir.exists():
        for toml_path in variant_dir.rglob("libs.versions.toml"):
            try:
                return toml_path.read_text(encoding="utf-8")
            except OSError:
                pass
    return ""


def _load_embeddable_utg(output_root: Path) -> dict[str, Any] | None:
    iframe_path = output_root / 'phase3' / 'impact-utg' / 'index.html'
    if iframe_path.exists():
        return {'mode': 'iframe', 'href': 'phase3/impact-utg/index.html'}
    for rel in ['phase3/before/utg.js', 'phase3/after/utg.js']:
        path = output_root / rel
        if path.exists():
            return {'mode': 'js', 'path': path, 'label': rel}
    return None


def _render_propagation_graph_svg(consolidated: ConsolidatedResult) -> str:
    """Render an SVG propagation graph: DEPENDENCIA -> DIRECTOS -> TRANSITIVOS (dist 1) -> TRANSITIVOS (dist 2+)."""
    direct_files = []
    trans1_files = []
    trans2_files = []

    for fi in consolidated.static_impact.impacted_files:
        short_name = Path(fi.file_path).stem
        if fi.relation == ImpactRelation.DIRECT:
            direct_files.append(short_name)
        elif fi.distance <= 1:
            trans1_files.append(short_name)
        else:
            trans2_files.append(short_name)

    # Layout constants
    col_x = [60, 240, 440, 660]
    col_w = 150
    box_h = 40
    box_gap = 8
    max_show = 10
    header_y = 30

    def _column_boxes(files: list[str], cx: int) -> list[tuple[str, int, int]]:
        shown = files[:max_show]
        boxes = []
        start_y = 65
        for i, name in enumerate(shown):
            y = start_y + i * (box_h + box_gap)
            boxes.append((name[:18], cx, y))
        if len(files) > max_show:
            y = start_y + len(shown) * (box_h + box_gap)
            boxes.append((f"+{len(files) - max_show} more", cx, y))
        return boxes

    dep_box_y = 65 + max(0, (max(len(direct_files), 1) - 1)) * (box_h + box_gap) // 2
    direct_boxes = _column_boxes(direct_files, col_x[1])
    trans1_boxes = _column_boxes(trans1_files, col_x[2])
    trans2_boxes = _column_boxes(trans2_files, col_x[3])

    all_boxes_y = [b[2] for b in direct_boxes + trans1_boxes + trans2_boxes]
    max_y = max(all_boxes_y) + box_h + 20 if all_boxes_y else 200
    svg_h = max(max_y, 200)

    parts = [f"<svg viewBox='0 0 860 {svg_h}' xmlns='http://www.w3.org/2000/svg' style='width:100%;font-family:Inter,system-ui,sans-serif;'>"]

    # Column headers
    headers = [
        (col_x[0] + col_w // 2, "DEPENDENCIA", "#4338ca"),
        (col_x[1] + col_w // 2, "DIRECTOS", "#dc2626"),
        (col_x[2] + col_w // 2, f"TRANSITIVOS\n(dist 1: {len(trans1_files)})", "#f59e0b"),
        (col_x[3] + col_w // 2, f"TRANSITIVOS\n(dist 2+: {len(trans2_files)})", "#f97316"),
    ]
    for hx, label, color in headers:
        lines = label.split("\n")
        for li, line in enumerate(lines):
            parts.append(f"<text x='{hx}' y='{header_y + li * 16}' text-anchor='middle' fill='{color}' font-size='11' font-weight='700' text-transform='uppercase'>{html.escape(line)}</text>")

    dep_name = html.escape(consolidated.dependency_group.split(".")[-1].upper())
    dep_label2 = f"{html.escape(consolidated.version_before)} → {html.escape(consolidated.version_after)}"
    # Dependency box
    parts.append(f"<rect x='{col_x[0]}' y='{dep_box_y}' width='{col_w}' height='{box_h + 10}' rx='8' fill='#4338ca'/>")
    parts.append(f"<text x='{col_x[0] + col_w // 2}' y='{dep_box_y + 22}' text-anchor='middle' fill='white' font-size='13' font-weight='700'>{dep_name}</text>")
    parts.append(f"<text x='{col_x[0] + col_w // 2}' y='{dep_box_y + 38}' text-anchor='middle' fill='rgba(255,255,255,0.7)' font-size='10'>{dep_label2}</text>")

    def _draw_boxes(boxes: list[tuple[str, int, int]], fill: str, text_color: str = "white") -> None:
        for label, bx, by in boxes:
            parts.append(f"<rect x='{bx}' y='{by}' width='{col_w}' height='{box_h}' rx='6' fill='{fill}'/>")
            parts.append(f"<text x='{bx + col_w // 2}' y='{by + box_h // 2 + 4}' text-anchor='middle' fill='{text_color}' font-size='11' font-weight='600'>{html.escape(label)}</text>")
            parts.append(f"<text x='{bx + col_w // 2}' y='{by + box_h // 2 + 16}' text-anchor='middle' fill='{text_color}' font-size='9' opacity='0.7'>.kt</text>")

    _draw_boxes(direct_boxes, "#dc2626")
    _draw_boxes(trans1_boxes, "#f59e0b")
    _draw_boxes(trans2_boxes, "#f97316")

    # Draw connection lines: dep -> direct
    dep_cx = col_x[0] + col_w
    dep_cy = dep_box_y + (box_h + 10) // 2
    for _, bx, by in direct_boxes:
        parts.append(f"<line x1='{dep_cx}' y1='{dep_cy}' x2='{bx}' y2='{by + box_h // 2}' stroke='#4338ca' stroke-width='1.5' opacity='0.4'/>")

    # direct -> trans1
    for _, dx, dy in direct_boxes:
        for _, tx, ty in trans1_boxes:
            parts.append(f"<line x1='{dx + col_w}' y1='{dy + box_h // 2}' x2='{tx}' y2='{ty + box_h // 2}' stroke='#f59e0b' stroke-width='1' opacity='0.25'/>")

    # trans1 -> trans2
    for _, t1x, t1y in trans1_boxes:
        for _, t2x, t2y in trans2_boxes:
            parts.append(f"<line x1='{t1x + col_w}' y1='{t1y + box_h // 2}' x2='{t2x}' y2='{t2y + box_h // 2}' stroke='#f97316' stroke-width='1' opacity='0.2'/>")

    parts.append("</svg>")
    return "\n".join(parts)


def _render_donut_svg(summary: dict[str, Any]) -> str:
    """Render a donut chart SVG showing impact distribution."""
    total = summary["total_project_files"] or 1
    direct = summary["direct_impacts"]
    ea = summary["expect_actual_impacts"]
    transitive = summary["transitive_impacts"] - ea
    not_impacted = total - direct - transitive - ea

    segments = [
        (direct, "#dc2626", "Directos"),
        (transitive, "#f59e0b", "Transitivos"),
        (ea, "#7c3aed", "Expect/Actual"),
        (not_impacted, "#e2e8f0", "No impactados"),
    ]

    cx, cy, r = 120, 120, 90
    inner_r = 55
    svg = [f"<svg viewBox='0 0 240 300' xmlns='http://www.w3.org/2000/svg' style='width:100%;max-width:400px;font-family:Inter,system-ui,sans-serif;'>"]

    offset = 0
    for value, color, label in segments:
        if value <= 0:
            continue
        pct = value / total
        angle = pct * 360
        large = 1 if angle > 180 else 0
        start_rad = math.radians(offset - 90)
        end_rad = math.radians(offset + angle - 90)

        x1 = cx + r * math.cos(start_rad)
        y1 = cy + r * math.sin(start_rad)
        x2 = cx + r * math.cos(end_rad)
        y2 = cy + r * math.sin(end_rad)

        ix1 = cx + inner_r * math.cos(start_rad)
        iy1 = cy + inner_r * math.sin(start_rad)
        ix2 = cx + inner_r * math.cos(end_rad)
        iy2 = cy + inner_r * math.sin(end_rad)

        d = f"M {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} L {ix2:.1f} {iy2:.1f} A {inner_r} {inner_r} 0 {large} 0 {ix1:.1f} {iy1:.1f} Z"
        svg.append(f"<path d='{d}' fill='{color}'/>")

        # Percentage label
        mid_rad = math.radians(offset + angle / 2 - 90)
        label_r = (r + inner_r) / 2 + 20
        lx = cx + label_r * math.cos(mid_rad)
        ly = cy + label_r * math.sin(mid_rad)
        if pct >= 0.05:
            svg.append(f"<text x='{lx:.1f}' y='{ly:.1f}' text-anchor='middle' fill='#374151' font-size='12' font-weight='600'>{pct:.0%}</text>")

        offset += angle

    # Center text
    impacted_total = summary["total_impacted_files"]
    svg.append(f"<text x='{cx}' y='{cy - 4}' text-anchor='middle' fill='#1e293b' font-size='28' font-weight='700'>{impacted_total}</text>")
    svg.append(f"<text x='{cx}' y='{cy + 16}' text-anchor='middle' fill='#64748b' font-size='11'>impactados</text>")

    # Legend
    ly = 260
    for value, color, label in segments:
        if value <= 0 and label != "Expect/Actual":
            continue
        svg.append(f"<rect x='20' y='{ly - 8}' width='12' height='12' rx='2' fill='{color}'/>")
        svg.append(f"<text x='38' y='{ly + 2}' fill='#374151' font-size='11' font-weight='600'>{html.escape(label)}</text>")
        ly += 20

    svg.append("</svg>")
    return "\n".join(svg)


def _render_bar_charts_svg(consolidated: ConsolidatedResult) -> str:
    """Render horizontal bar charts for RLOC and MCC (top 15)."""
    files_sorted_rloc = sorted(
        consolidated.static_impact.impacted_files,
        key=lambda f: -f.metrics.rloc,
    )[:15]
    files_sorted_mcc = sorted(
        consolidated.static_impact.impacted_files,
        key=lambda f: -f.metrics.mcc,
    )[:15]

    def _bar_chart(files: list, metric: str, title: str, x_label: str) -> str:
        if not files:
            return ""
        max_val = max(getattr(f.metrics, metric) for f in files) or 1
        bar_h = 18
        gap = 6
        label_w = 140
        chart_w = 280
        total_h = 40 + len(files) * (bar_h + gap)
        svg = [f"<svg viewBox='0 0 {label_w + chart_w + 50} {total_h}' xmlns='http://www.w3.org/2000/svg' style='width:100%;font-family:Inter,system-ui,sans-serif;'>"]
        svg.append(f"<text x='{(label_w + chart_w + 50) // 2}' y='16' text-anchor='middle' fill='#374151' font-size='12' font-weight='700'>{html.escape(title)}</text>")
        y = 34
        for fi in files:
            val = getattr(fi.metrics, metric)
            w = (val / max_val) * chart_w if max_val > 0 else 0
            short = Path(fi.file_path).name
            if len(short) > 18:
                short = short[:16] + ".."
            is_direct = fi.relation == ImpactRelation.DIRECT
            color = "#dc2626" if is_direct else "#f59e0b"
            svg.append(f"<text x='{label_w - 4}' y='{y + bar_h // 2 + 4}' text-anchor='end' fill='#374151' font-size='10'>{html.escape(short)}</text>")
            svg.append(f"<rect x='{label_w}' y='{y}' width='{w:.1f}' height='{bar_h}' rx='3' fill='{color}'/>")
            svg.append(f"<text x='{label_w + w + 4:.1f}' y='{y + bar_h // 2 + 4}' fill='#374151' font-size='10' font-weight='600'>{val}</text>")
            y += bar_h + gap

        # X-axis label
        svg.append(f"<text x='{label_w + chart_w // 2}' y='{total_h - 2}' text-anchor='middle' fill='#94a3b8' font-size='9'>{html.escape(x_label)}</text>")
        svg.append("</svg>")
        return "\n".join(svg)

    rloc_svg = _bar_chart(files_sorted_rloc, "rloc", "Líneas de código reales (top 15)", "Líneas de código (RLOC)")
    # Label reflects whether Detekt or heuristic was used for complexity
    has_detekt = any(
        fi.metrics.metrics_source == "detekt"
        for fi in consolidated.static_impact.impacted_files
    )
    mcc_title = "Complejidad ciclomática — Detekt (top 15)" if has_detekt else "Complejidad heurística (top 15)"
    mcc_svg = _bar_chart(files_sorted_mcc, "mcc", mcc_title, "Complejidad ciclomática (MCC)")

    return f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;'>{rloc_svg}{mcc_svg}</div>"


def _build_html(
    summary: dict[str, Any],
    consolidated: ConsolidatedResult,
    manifest: ShadowManifest,
    output_root: Path,
) -> str:
    dep_group = html.escape(summary['dependency_group'])
    ver_before = html.escape(summary['version_before'])
    ver_after = html.escape(summary['version_after'])
    ea_count = summary['expect_actual_impacts']

    # Phase status
    phase_status = _phase_status(consolidated)

    # Pipeline steps
    pipe_steps = ""
    for idx, (key, data) in enumerate(phase_status.items(), start=1):
        status_cls = "green" if data["status"] == "completed" else ("amber" if data["status"] == "blocked" else "gray")
        status_prefix = "✓ " if data["status"] == "completed" else ""
        skip_cls = " skip" if data["status"] == "skipped" else ""
        pipe_steps += f'<div class="pipe-step"><div class="dot {status_cls}">{idx}</div><div class="title">{html.escape(data["title"])}</div><div class="status{skip_cls}">{status_prefix}{html.escape(data["detail"])}</div></div>\n'

    # Shadow build: load toml content
    before_toml = _load_toml_content(output_root, "before")
    after_toml = _load_toml_content(output_root, "after")

    version_key = manifest.version_change.version_key

    def _highlight_toml(content: str) -> str:
        """Highlight lines containing the version key."""
        if not content:
            return "<em>No se encontró libs.versions.toml</em>"
        lines = content.split("\n")
        result = []
        for line in lines:
            if version_key.lower() in line.lower():
                result.append(f'<span class="hl">{html.escape(line)}</span>')
            else:
                result.append(html.escape(line))
        return "\n".join(result)

    # Phase 2: Propagation graph SVG
    propagation_svg = _render_propagation_graph_svg(consolidated)

    # Donut chart
    donut_svg = _render_donut_svg(summary)

    # Bar charts
    bar_charts = _render_bar_charts_svg(consolidated)

    # Phase 3: Dynamic analysis
    utg = _load_embeddable_utg(output_root)
    dynamic = consolidated.dynamic_regressions

    dynamic_section = ""
    if utg and utg['mode'] == 'iframe':
        dynamic_section += f"""
<div style="background:white;border-radius:12px;border:1px solid #e2e8f0;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:16px;">
  <iframe src="{html.escape(utg['href'])}" style="width:100%;height:600px;border:none;border-radius:12px;"></iframe>
</div>
<div style="text-align:center;margin-bottom:16px;">
  <a href="{html.escape(utg['href'])}" target="_blank" style="display:inline-block;padding:12px 28px;background:#4338ca;color:white;border-radius:8px;font-weight:600;font-size:13px;text-decoration:none;">
    Abrir grafo interactivo completo
  </a>
</div>"""
    elif utg and utg['mode'] == 'js':
        dynamic_section += f"""
<div style="background:#f8fafc;border-radius:12px;border:1px solid #cbd5e1;padding:16px;display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
  <div>
    <div style="font-size:14px;font-weight:700;color:#1e293b;">UTG capturado (DroidBot)</div>
    <div style="font-size:12px;color:#64748b;">Se usará el grafo para calcular pantallas afectadas y diffs.</div>
  </div>
  <a href="{html.escape(utg['label'])}" style="font-size:12px;color:#4338ca;font-weight:700;">Descargar utg.js</a>
</div>"""
    else:
        has_real_data = len(dynamic.diffs) > 0 or len(dynamic.before_screens) > 0
        if has_real_data:
            dynamic_section += """
<div style="background:#f0fdf4;border-radius:12px;border:1px solid #bbf7d0;padding:16px;text-align:center;margin-bottom:16px;">
  <div style="font-size:14px;font-weight:700;color:#166534;">DroidBot exploró la app correctamente</div>
</div>"""
        else:
            reason = dynamic.blocked_reason or "No se generaron artefactos DroidBot en esta corrida."
            status_label = "OMITIDO" if dynamic.status == DynamicStatus.SKIPPED else "BLOQUEADO"
            dynamic_section += f"""
<div style="background:#f8fafc;border-radius:12px;border:1px dashed #cbd5e1;padding:40px 24px;text-align:center;margin-bottom:16px;">
  <div style="font-size:16px;font-weight:700;color:#94a3b8;margin-bottom:8px;">{status_label}</div>
  <div style="font-size:13px;color:#64748b;">{html.escape(reason)}</div>
</div>"""

    # Dynamic stats
    explored = len(set(dynamic.before_screens) | set(dynamic.after_screens))
    diffs_count = len(dynamic.diffs)
    dynamic_section += f"""
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
  <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:16px;text-align:center;">
    <div style="font-size:24px;font-weight:700;color:#1e293b;">{explored}</div>
    <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Pantallas exploradas</div>
  </div>
  <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:16px;text-align:center;">
    <div style="font-size:24px;font-weight:700;color:#dc2626;">{diffs_count}</div>
    <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Con cambios detectados</div>
  </div>
  <div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:16px;text-align:center;">
    <div style="font-size:24px;font-weight:700;color:#4338ca;">{summary['total_impacted_screens']}</div>
    <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;">Pantallas impactadas</div>
  </div>
</div>"""

    # Dynamic diffs
    for diff in dynamic.diffs:
        dynamic_section += f"""
<div style="background:white;border-radius:10px;border-left:4px solid #fbbf24;padding:12px 16px;margin-top:8px;display:flex;align-items:center;gap:12px;">
  <span style="font-size:18px;">&#9888;&#65039;</span>
  <div>
    <strong style="font-size:13px;color:#1e293b;">{html.escape(diff.screen_name)}</strong>
    <div style="font-size:12px;color:#64748b;margin-top:2px;">{html.escape(diff.details)}</div>
  </div>
</div>"""

    # Phase 4: Traceability table
    trace_rows = ""
    for i, entry in enumerate(sorted(consolidated.trace, key=lambda item: (item.distance, item.file_path))):
        short_name = Path(entry.file_path).name
        alt_cls = ' class="row-alt"' if i % 2 == 1 else ''
        if entry.relation == ImpactRelation.DIRECT:
            badge = '<span class="badge badge-red">Directo</span>'
        elif entry.relation == ImpactRelation.EXPECT_ACTUAL:
            badge = '<span class="badge badge-purple">Expect/Actual</span>'
        else:
            badge = '<span class="badge badge-yellow">Transitivo</span>'
        screens_str = ", ".join(html.escape(s) for s in entry.screens) if entry.screens else "—"
        trace_rows += f"""<tr{alt_cls}>
  <td class="fname">{html.escape(short_name)}</td>
  <td>{badge}</td>
  <td class="c">{entry.distance}</td>
  <td class="c">{entry.metrics.rloc}</td>
  <td class="c">{entry.metrics.mcc}</td>
  <td>{screens_str}</td>
</tr>\n"""

    # Expect/Actual pairs
    ea_section = ""
    if consolidated.static_impact.expect_actual_pairs:
        ea_rows = ""
        for pair in consolidated.static_impact.expect_actual_pairs:
            actual_parts = []
            for af in pair.actual_files:
                af_name = Path(af).name
                # Detect platform
                if "android" in af.lower():
                    actual_parts.append(f"&#129302; {html.escape(af_name)}")
                elif "ios" in af.lower():
                    actual_parts.append(f"&#127822; {html.escape(af_name)}")
                elif "jvm" in af.lower() or "desktop" in af.lower():
                    actual_parts.append(html.escape(af_name))
                elif "wasm" in af.lower() or "js" in af.lower():
                    actual_parts.append(html.escape(af_name))
                else:
                    actual_parts.append(html.escape(af_name))
            ea_rows += f"""<tr>
  <td class="fname">{html.escape(pair.expect_fqcn)}</td>
  <td><code>{html.escape(Path(pair.expect_file).name)}</code></td>
  <td>{"<br>".join(actual_parts)}</td>
</tr>\n"""

        ea_section = f"""
<div class="section">
  <div class="section-header">
    <div class="phase-num" style="background:#7c3aed;">&#128279;</div>
    <div><h2>Pares Expect/Actual detectados</h2><div class="desc">Declaraciones multiplataforma que vinculan commonMain con implementaciones de cada plataforma</div></div>
  </div>
  <table class="data-table">
    <thead><tr><th>FQCN</th><th>Archivo expect</th><th>Archivos actual</th></tr></thead>
    <tbody>{ea_rows}</tbody>
  </table>
</div>"""

    # Phase 5: CodeCharta
    cc_iframe = ""
    cc_viewer_path = output_root / "phase5" / "codecharta-viewer" / "index.html"
    if cc_viewer_path.exists():
        import time
        after_cc = output_root / "phase5" / "after.cc.json"
        ts = int(after_cc.stat().st_mtime) if after_cc.exists() else int(time.time())
        cc_src = (
            "phase5/codecharta-viewer/index.html"
            "?file=../after.cc.json"
            "&mode=Single&area=rloc&height=mcc&color=impacted"
            f"&ts={ts}"
        )
        cc_iframe = f"""
<div style="background:white;border-radius:12px;border:1px solid #e2e8f0;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:16px;">
  <iframe id="codecharta-frame" src="{cc_src}" style="width:100%;height:650px;border:none;border-radius:12px;"></iframe>
</div>
<div style="text-align:center;margin-bottom:16px;">
  <a href="{cc_src}" target="_blank" style="display:inline-block;padding:12px 28px;background:#4338ca;color:white;border-radius:8px;font-weight:600;font-size:13px;text-decoration:none;">
    Abrir CodeCharta en pantalla completa
  </a>
</div>"""
    else:
        # Fallback: show link to external CodeCharta viewer
        cc_iframe = """
<div style="background:#f8fafc;border-radius:12px;border:1px dashed #cbd5e1;padding:40px 24px;text-align:center;margin-bottom:16px;">
  <div style="font-size:14px;color:#64748b;margin-bottom:12px;">Los artefactos CodeCharta (.cc.json) están disponibles para exploración externa.</div>
  <a href="https://maibornwolff.github.io/codecharta/visualization/app/index.html" target="_blank" style="display:inline-block;padding:12px 28px;background:#4338ca;color:white;border-radius:8px;font-weight:600;font-size:13px;text-decoration:none;">
    Abrir CodeCharta Visualization
  </a>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte de Impacto — {dep_group}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Inter',system-ui,sans-serif; background:#f8fafc; color:#1e293b; line-height:1.6; }}

  /* Header */
  .header {{ background:linear-gradient(135deg,#1e1b4b 0%,#312e81 50%,#4338ca 100%); color:white; padding:48px 0 40px; }}
  .header-inner {{ max-width:1000px; margin:0 auto; padding:0 32px; }}
  .header h1 {{ font-size:28px; font-weight:700; margin-bottom:4px; }}
  .header .sub {{ font-size:14px; opacity:0.7; }}
  .version-pill {{ display:inline-block; background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.25);
    border-radius:20px; padding:6px 18px; margin-top:16px; font-size:15px; font-weight:600; }}
  .version-pill .arrow {{ color:#a5b4fc; margin:0 8px; }}

  /* Container */
  .container {{ max-width:1000px; margin:0 auto; padding:0 32px 60px; }}

  /* KPI cards */
  .kpi-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin:-32px 0 40px; position:relative; z-index:2; }}
  .kpi {{ background:white; border-radius:12px; padding:24px; text-align:center;
    box-shadow:0 1px 3px rgba(0,0,0,0.08),0 4px 12px rgba(0,0,0,0.04); border:1px solid #e2e8f0; }}
  .kpi .num {{ font-size:32px; font-weight:700; }}
  .kpi .lbl {{ font-size:12px; color:#64748b; margin-top:4px; text-transform:uppercase; letter-spacing:0.5px; }}
  .kpi .num.red {{ color:#dc2626; }}
  .kpi .num.amber {{ color:#d97706; }}
  .kpi .num.purple {{ color:#7c3aed; }}
  .kpi .num.blue {{ color:#2563eb; }}

  /* Section */
  .section {{ margin-bottom:40px; }}
  .section-header {{ display:flex; align-items:center; gap:12px; margin-bottom:20px; padding-bottom:12px; border-bottom:2px solid #e2e8f0; }}
  .phase-num {{ background:#4338ca; color:white; width:32px; height:32px; border-radius:50%;
    display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:700; flex-shrink:0; }}
  .section-header h2 {{ font-size:18px; font-weight:700; color:#1e293b; }}
  .section-header .desc {{ font-size:13px; color:#64748b; }}

  /* Pipeline */
  .pipeline {{ display:flex; gap:0; margin:24px 0 40px; justify-content:center; }}
  .pipe-step {{ text-align:center; flex:1; position:relative; }}
  .pipe-step .dot {{ width:40px; height:40px; border-radius:50%; margin:0 auto 8px;
    display:flex; align-items:center; justify-content:center; font-size:16px; font-weight:700; color:white; }}
  .pipe-step .dot.green {{ background:#16a34a; }}
  .pipe-step .dot.gray {{ background:#9ca3af; }}
  .pipe-step .dot.amber {{ background:#d97706; }}
  .pipe-step .title {{ font-size:12px; font-weight:600; color:#374151; }}
  .pipe-step .status {{ font-size:11px; color:#16a34a; font-weight:500; }}
  .pipe-step .status.skip {{ color:#9ca3af; }}
  .pipe-step:not(:last-child)::after {{ content:''; position:absolute; top:20px; left:calc(50% + 24px);
    width:calc(100% - 48px); height:3px; background:#d1d5db; }}

  /* Diff cards */
  .diff-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .diff-card {{ background:white; border-radius:10px; border:1px solid #e2e8f0; overflow:hidden;
    box-shadow:0 1px 3px rgba(0,0,0,0.05); }}
  .diff-card .card-head {{ padding:12px 16px; font-size:12px; font-weight:600; text-transform:uppercase;
    letter-spacing:0.5px; }}
  .diff-card.before .card-head {{ background:#fef2f2; color:#991b1b; border-bottom:2px solid #fca5a5; }}
  .diff-card.after .card-head {{ background:#f0fdf4; color:#166534; border-bottom:2px solid #86efac; }}
  .diff-card pre {{ padding:16px; font-size:12px; line-height:1.7; overflow-x:auto; background:#fafafa; margin:0; }}
  .diff-card pre .hl {{ background:#fef08a; font-weight:600; display:inline; padding:1px 4px; border-radius:3px; }}

  /* Chart card */
  .chart-card {{ background:white; border-radius:12px; border:1px solid #e2e8f0; padding:20px;
    box-shadow:0 1px 3px rgba(0,0,0,0.05); margin-bottom:16px; }}
  .chart-card .caption {{ font-size:12px; color:#64748b; margin-top:8px; text-align:center; }}

  /* Table */
  .data-table {{ width:100%; border-collapse:separate; border-spacing:0; background:white;
    border-radius:12px; overflow:hidden; border:1px solid #e2e8f0;
    box-shadow:0 1px 3px rgba(0,0,0,0.05); }}
  .data-table th {{ background:#f8fafc; color:#475569; padding:12px 16px; text-align:left;
    font-size:11px; text-transform:uppercase; letter-spacing:0.5px; font-weight:600; border-bottom:2px solid #e2e8f0; }}
  .data-table td {{ padding:11px 16px; font-size:13px; border-bottom:1px solid #f1f5f9; }}
  .data-table .row-alt td {{ background:#fafbfc; }}
  .data-table .fname {{ font-family:'SF Mono',Consolas,monospace; font-size:12.5px; font-weight:600; color:#1e293b; }}
  .data-table .c {{ text-align:center; }}
  .badge {{ padding:3px 10px; border-radius:10px; font-size:11px; font-weight:600; }}
  .badge-red {{ background:#fef2f2; color:#dc2626; border:1px solid #fecaca; }}
  .badge-yellow {{ background:#fffbeb; color:#d97706; border:1px solid #fde68a; }}
  .badge-purple {{ background:#f5f3ff; color:#7c3aed; border:1px solid #ddd6fe; }}

  /* Info box */
  .info-box {{ background:#eef2ff; border:1px solid #c7d2fe; border-radius:10px; padding:20px 24px; }}
  .info-box h4 {{ color:#4338ca; font-size:14px; margin-bottom:8px; }}
  .info-box p {{ font-size:13px; color:#4338ca; opacity:0.8; }}

  /* Footer */
  .footer {{ text-align:center; color:#94a3b8; font-size:12px; padding:32px 0; border-top:1px solid #e2e8f0; margin-top:20px; }}

  @media print {{
    .header {{ background:#1e1b4b !important; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
    .kpi, .chart-card, .diff-card, .data-table {{ break-inside:avoid; }}
    body {{ font-size:11px; }}
  }}
  @media (max-width:700px) {{
    .kpi-row {{ grid-template-columns:repeat(2,1fr); }}
    .diff-grid {{ grid-template-columns:1fr; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <h1>Reporte de Análisis de Impacto</h1>
    <div class="sub">KMP Impact Analyzer — Análisis estático de propagación de dependencias</div>
    <div class="version-pill">
      {dep_group} &nbsp;<code>{ver_before}</code>
      <span class="arrow">→</span>
      <code>{ver_after}</code>
    </div>
  </div>
</div>

<div class="container">

<!-- KPIs -->
<div class="kpi-row">
  <div class="kpi">
    <div class="num red">{summary['total_impacted_files']}</div>
    <div class="lbl">Archivos impactados</div>
  </div>
  <div class="kpi">
    <div class="num amber">{summary['total_project_files']}</div>
    <div class="lbl">Total archivos</div>
  </div>
  <div class="kpi">
    <div class="num purple">{ea_count}</div>
    <div class="lbl">Pares expect/actual</div>
  </div>
  <div class="kpi">
    <div class="num blue">{summary['total_impacted_screens']}</div>
    <div class="lbl">Pantallas afectadas</div>
  </div>
</div>

<!-- Pipeline overview -->
<div class="section">
  <div class="section-header">
    <div class="phase-num">&#9889;</div>
    <div><h2>Pipeline ejecutado</h2><div class="desc">Resumen de las 5 fases del análisis</div></div>
  </div>
  <div class="pipeline">
    {pipe_steps}
  </div>
</div>

<!-- Phase 1: Shadow Build -->
<div class="section">
  <div class="section-header">
    <div class="phase-num">1</div>
    <div><h2>Shadow Build</h2><div class="desc">Se crearon copias ANTES y DESPUÉS del proyecto, modificando la versión de la dependencia</div></div>
  </div>
  <div class="diff-grid">
    <div class="diff-card before">
      <div class="card-head">Antes — libs.versions.toml</div>
      <pre>{_highlight_toml(before_toml)}</pre>
    </div>
    <div class="diff-card after">
      <div class="card-head">Después — libs.versions.toml</div>
      <pre>{_highlight_toml(after_toml)}</pre>
    </div>
  </div>
</div>

<!-- Phase 2: Static Analysis -->
<div class="section">
  <div class="section-header">
    <div class="phase-num">2</div>
    <div><h2>Análisis Estático — Grafo de Propagación</h2><div class="desc">Cómo el cambio en <strong>{dep_group}</strong> se propaga a través del código fuente</div></div>
  </div>
  <div class="chart-card">
    {propagation_svg}
    <div class="caption">
      Cada caja representa un archivo .kt — el color indica si el impacto es
      <span style="color:#dc2626;font-weight:600">directo</span>,
      <span style="color:#f59e0b;font-weight:600">transitivo (dist 1)</span> o
      <span style="color:#f97316;font-weight:600">transitivo (dist 2+)</span>
    </div>
  </div>
  <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
    <div class="chart-card">
      {donut_svg}
    </div>
    <div class="chart-card">
      {bar_charts}
    </div>
  </div>
</div>

<!-- Phase 3: Dynamic Analysis -->
<div class="section">
  <div class="section-header">
    <div class="phase-num">3</div>
    <div><h2>Análisis Dinámico — Exploración UI con DroidBot</h2><div class="desc">Flujo de interacción de pantallas con las afectadas por el cambio marcadas en rojo</div></div>
  </div>
  {dynamic_section}
</div>

<!-- Phase 4: Traceability -->
<div class="section">
  <div class="section-header">
    <div class="phase-num">4</div>
    <div><h2>Trazabilidad — Archivo → Pantalla</h2><div class="desc">Cada archivo impactado con su relación, distancia al cambio, métricas y pantalla UI asociada</div></div>
  </div>
  <table class="data-table">
    <thead>
      <tr><th>Archivo</th><th>Relación</th><th>Dist.</th><th>RLOC</th><th>MCC</th><th>Pantalla</th></tr>
    </thead>
    <tbody>
    {trace_rows}
    </tbody>
  </table>
</div>

{ea_section}

<!-- Phase 5: CodeCharta -->
<div class="section">
  <div class="section-header">
    <div class="phase-num">5</div>
    <div><h2>Visualización CodeCharta — Mapa 3D de Impacto</h2><div class="desc">Cada archivo es un edificio: el área es líneas de código, la altura es complejidad, y el color rojo indica impacto</div></div>
  </div>
  {cc_iframe}
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
    <div style="background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;padding:14px 16px;">
      <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">Area (tamaño)</div>
      <div style="font-size:14px;font-weight:600;color:#1e293b;">rloc — Líneas de código reales</div>
    </div>
    <div style="background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;padding:14px 16px;">
      <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">Altura</div>
      <div style="font-size:14px;font-weight:600;color:#1e293b;">mcc — Complejidad ciclomática</div>
    </div>
    <div style="background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;padding:14px 16px;">
      <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">Color</div>
      <div style="font-size:14px;font-weight:600;color:#1e293b;">impacted — <span style="color:#dc2626;">Rojo</span> = afectado por el cambio</div>
    </div>
  </div>
</div>

<div class="footer">
  Generado por <strong>kmp-impact-analyzer</strong><br>
  Tesis: Pipeline de Contextualización y Visualización de Código KMP — Universidad de los Andes
</div>

</div>
</body>
</html>"""


def generate_report_site(
    consolidated: ConsolidatedResult,
    manifest: ShadowManifest,
    output_dir: str | Path,
    report_url: str = "",
) -> dict[str, Path]:
    output_root = Path(output_dir)
    report_dir = output_root / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary_payload(consolidated, manifest, report_url=report_url)
    summary_json_path = report_dir / "summary.json"
    summary_json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_md_path = report_dir / "summary.md"
    summary_md_path.write_text(build_summary_markdown(summary), encoding="utf-8")

    html_path = report_dir / "index.html"
    html_path.write_text(_build_html(summary, consolidated, manifest, output_root), encoding="utf-8")

    log.info(f"Generated HTML report site → {html_path}")
    return {
        "html": html_path,
        "summary_json": summary_json_path,
        "summary_md": summary_md_path,
        "report_dir": report_dir,
    }
