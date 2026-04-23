"""Static SVG renderers for the PR comment images.

cairosvg can rasterize any of these directly. They intentionally avoid
HTML entities and DOM features (e.g. foreignObject, CSS class selectors in
named tags) so that the output is valid XML/SVG for the cairo parser.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

from ..contracts import ConsolidatedResult, ImpactRelation


# ---------------------------------------------------------------------------
# Phase 2 propagation graph
# ---------------------------------------------------------------------------

def build_propagation_svg(consolidated: ConsolidatedResult) -> str:
    """Column layout SVG: DEPENDENCY -> DIRECT -> TRANSITIVE(1) -> TRANSITIVE(2+).
    Same content as the in-report SVG but with XML-safe entities so cairosvg
    can rasterize it."""
    direct_files: list[str] = []
    trans1_files: list[str] = []
    trans2_files: list[str] = []
    for fi in consolidated.static_impact.impacted_files:
        name = Path(fi.file_path).stem
        if fi.relation == ImpactRelation.DIRECT:
            direct_files.append(name)
        elif fi.distance <= 1:
            trans1_files.append(name)
        else:
            trans2_files.append(name)

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

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 860 {svg_h}" '
        f'width="860" height="{svg_h}" '
        'font-family="system-ui,sans-serif">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]

    headers = [
        (col_x[0] + col_w // 2, "DEPENDENCY", "#4338ca"),
        (col_x[1] + col_w // 2, "DIRECT", "#dc2626"),
        (col_x[2] + col_w // 2, f"TRANSITIVE (dist 1: {len(trans1_files)})", "#f59e0b"),
        (col_x[3] + col_w // 2, f"TRANSITIVE (dist 2+: {len(trans2_files)})", "#f97316"),
    ]
    for hx, label, color in headers:
        parts.append(
            f'<text x="{hx}" y="{header_y}" text-anchor="middle" '
            f'fill="{color}" font-size="11" font-weight="700">{html.escape(label)}</text>'
        )

    dep_name = html.escape(consolidated.dependency_group.split(".")[-1].upper())
    dep_label2 = (
        f'{html.escape(consolidated.version_before)} -&gt; '
        f'{html.escape(consolidated.version_after)}'
    )
    parts.append(
        f'<rect x="{col_x[0]}" y="{dep_box_y}" width="{col_w}" '
        f'height="{box_h + 10}" rx="8" fill="#4338ca"/>'
    )
    parts.append(
        f'<text x="{col_x[0] + col_w // 2}" y="{dep_box_y + 22}" '
        f'text-anchor="middle" fill="white" font-size="13" '
        f'font-weight="700">{dep_name}</text>'
    )
    parts.append(
        f'<text x="{col_x[0] + col_w // 2}" y="{dep_box_y + 38}" '
        f'text-anchor="middle" fill="#e5e7eb" font-size="10">{dep_label2}</text>'
    )

    def _draw_boxes(boxes, fill: str):
        for label, bx, by in boxes:
            parts.append(
                f'<rect x="{bx}" y="{by}" width="{col_w}" height="{box_h}" '
                f'rx="6" fill="{fill}"/>'
            )
            parts.append(
                f'<text x="{bx + col_w // 2}" y="{by + box_h // 2 + 4}" '
                f'text-anchor="middle" fill="white" font-size="11" '
                f'font-weight="600">{html.escape(label)}</text>'
            )
            parts.append(
                f'<text x="{bx + col_w // 2}" y="{by + box_h // 2 + 16}" '
                f'text-anchor="middle" fill="#ffffff" opacity="0.7" '
                f'font-size="9">.kt</text>'
            )

    _draw_boxes(direct_boxes, "#dc2626")
    _draw_boxes(trans1_boxes, "#f59e0b")
    _draw_boxes(trans2_boxes, "#f97316")

    dep_cx = col_x[0] + col_w
    dep_cy = dep_box_y + (box_h + 10) // 2
    for _, bx, by in direct_boxes:
        parts.append(
            f'<line x1="{dep_cx}" y1="{dep_cy}" x2="{bx}" '
            f'y2="{by + box_h // 2}" stroke="#4338ca" stroke-width="1.5" '
            f'opacity="0.4"/>'
        )
    for _, dx, dy in direct_boxes:
        for _, tx, ty in trans1_boxes:
            parts.append(
                f'<line x1="{dx + col_w}" y1="{dy + box_h // 2}" '
                f'x2="{tx}" y2="{ty + box_h // 2}" stroke="#f59e0b" '
                f'stroke-width="1" opacity="0.25"/>'
            )
    for _, t1x, t1y in trans1_boxes:
        for _, t2x, t2y in trans2_boxes:
            parts.append(
                f'<line x1="{t1x + col_w}" y1="{t1y + box_h // 2}" '
                f'x2="{t2x}" y2="{t2y + box_h // 2}" stroke="#f97316" '
                f'stroke-width="1" opacity="0.2"/>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# GitGraph arc diagram (simplified static snapshot)
# ---------------------------------------------------------------------------

def build_gitgraph_svg(graph_json_path: Path, diff_json_path: Path | None) -> str:
    """Top-N libraries sorted by in-degree with arcs toward the focal package(s)
    flagged by the diff. Keeps the visual metaphor of the live arc diagram but
    rasterizable.

    Falls back to a neutral empty-state SVG when graph data is absent.
    """
    if not graph_json_path.exists():
        return _empty_state_svg(
            "Dependency graph not available",
            "The GitGraph SBOM pipeline did not produce graph.json.",
        )

    graph = json.loads(graph_json_path.read_text())
    nodes: list[dict[str, Any]] = graph.get("nodes", [])
    links: list[dict[str, Any]] = graph.get("links", [])

    in_degree: dict[str, int] = {}
    out_degree: dict[str, int] = {}
    dependents: dict[str, set[str]] = {}
    for l in links:
        in_degree[l["target"]] = in_degree.get(l["target"], 0) + 1
        out_degree[l["source"]] = out_degree.get(l["source"], 0) + 1
        dependents.setdefault(l["target"], set()).add(l["source"])

    # Highlight nodes that the diff touches.
    focal_ids: set[str] = set()
    if diff_json_path and diff_json_path.exists():
        diff = json.loads(diff_json_path.read_text())
        changed = (
            [d.get("name", "") for d in diff.get("added", [])]
            + [d.get("name", "") for d in diff.get("updated", [])]
            + [d.get("name", "") for d in diff.get("removed", [])]
        )
        for n in nodes:
            for c in changed:
                if c and (n["id"] == c or n["id"].startswith(c + "@")):
                    focal_ids.add(n["id"])
                    break

    # Top libraries by in-degree (the hubs), ensuring focals are included.
    sorted_nodes = sorted(
        nodes,
        key=lambda n: (n["id"] in focal_ids, in_degree.get(n["id"], 0)),
        reverse=True,
    )
    top = sorted_nodes[:14]
    for f in focal_ids:
        if not any(n["id"] == f for n in top):
            fn = next((n for n in nodes if n["id"] == f), None)
            if fn:
                top.append(fn)

    if not top:
        return _empty_state_svg(
            "Dependency graph is empty",
            f"{len(nodes)} nodes, {len(links)} edges parsed but nothing to chart.",
        )

    W = 860
    H = 420
    margin_x = 40
    baseline_y = H - 70
    radius = 7

    # Distribute nodes along a horizontal baseline; focals first (left), hubs
    # by in-degree after.
    placed = sorted(
        top,
        key=lambda n: (
            0 if n["id"] in focal_ids else 1,
            -in_degree.get(n["id"], 0),
        ),
    )
    n = len(placed)
    xs = [
        margin_x + int(i * (W - 2 * margin_x) / max(n - 1, 1))
        for i in range(n)
    ]
    id_to_x = {p["id"]: xs[i] for i, p in enumerate(placed)}

    def _short(name: str) -> str:
        n_ = name.split(":")[-1].split("@")[0]
        return n_[:18]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" '
        'font-family="system-ui,sans-serif">',
        '<rect width="100%" height="100%" fill="#0d1117"/>',
        f'<text x="{W//2}" y="30" text-anchor="middle" fill="#e6edf3" '
        f'font-size="14" font-weight="700">Transitive Dependency Graph</text>',
        f'<text x="{W//2}" y="50" text-anchor="middle" fill="#7d8590" '
        f'font-size="11">{len(nodes)} packages, {len(links)} edges '
        f'(showing top {n})</text>',
    ]

    # Arcs: for each focal, draw a semicircle up from each dependent to focal.
    for focal in focal_ids:
        fx = id_to_x.get(focal)
        if fx is None:
            continue
        deps = dependents.get(focal, set())
        visible_deps = [d for d in deps if d in id_to_x]
        for dep_id in visible_deps:
            dx = id_to_x[dep_id]
            if dx == fx:
                continue
            r = abs(fx - dx) / 2
            cx = (fx + dx) / 2
            # Upper semicircle from (dep_x, baseline) to (focal_x, baseline)
            sweep = 0 if dx < fx else 1
            parts.append(
                f'<path d="M {dx} {baseline_y} A {r:.1f} {r:.1f} 0 0 {sweep} '
                f'{fx} {baseline_y}" fill="none" stroke="#79c0ff" '
                f'stroke-width="1.2" opacity="0.45"/>'
            )

    # Nodes + labels
    for p in placed:
        px = id_to_x[p["id"]]
        is_focal = p["id"] in focal_ids
        color = "#388bfd" if is_focal else "#30363d"
        stroke = "#79c0ff" if is_focal else "#484f58"
        parts.append(
            f'<circle cx="{px}" cy="{baseline_y}" r="{radius + (2 if is_focal else 0)}" '
            f'fill="{color}" stroke="{stroke}" stroke-width="{2 if is_focal else 1}"/>'
        )
        label = _short(p["id"])
        parts.append(
            f'<text x="{px}" y="{baseline_y + radius + 18}" text-anchor="middle" '
            f'fill="#e6edf3" font-size="10" transform="rotate(35 {px} {baseline_y + radius + 18})">'
            f'{html.escape(label)}</text>'
        )
        if is_focal:
            parts.append(
                f'<text x="{px}" y="{baseline_y - radius - 8}" text-anchor="middle" '
                f'fill="#79c0ff" font-size="10" font-weight="700">'
                f'{len(dependents.get(p["id"], set()))} dependents</text>'
            )

    # Legend
    parts.append(
        '<g transform="translate(30, 70)" font-size="10" fill="#7d8590">'
        '<circle cx="6" cy="6" r="5" fill="#388bfd" stroke="#79c0ff" stroke-width="2"/>'
        '<text x="18" y="10">Changed in this PR</text>'
        '<circle cx="150" cy="6" r="5" fill="#30363d" stroke="#484f58"/>'
        '<text x="162" y="10">Other hub</text>'
        '<path d="M 250 10 A 20 20 0 0 1 290 10" fill="none" stroke="#79c0ff" '
        'stroke-width="1.2" opacity="0.45"/>'
        '<text x="298" y="10">Depends on changed package</text>'
        '</g>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def _empty_state_svg(title: str, subtitle: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 860 160" '
        'width="860" height="160" font-family="system-ui,sans-serif">'
        '<rect width="100%" height="100%" fill="#f8fafc" '
        'stroke="#cbd5e1" stroke-width="1" stroke-dasharray="4 4"/>'
        f'<text x="430" y="70" text-anchor="middle" fill="#64748b" '
        f'font-size="14" font-weight="700">{html.escape(title)}</text>'
        f'<text x="430" y="95" text-anchor="middle" fill="#94a3b8" '
        f'font-size="11">{html.escape(subtitle)}</text>'
        '</svg>'
    )
