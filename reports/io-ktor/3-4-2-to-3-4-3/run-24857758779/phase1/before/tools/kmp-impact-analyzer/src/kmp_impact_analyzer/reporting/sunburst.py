"""Source-set Sunburst visualization embedded in the HTML report.

Adapted from Nuevosajustes/nuava visualizacion/generate_sunburst.py. Takes the
ConsolidatedResult produced by phase 4 (no file-system re-parsing) and builds
a D3 v7 hierarchical Sunburst grouped by source set → package directory → file.

The output is an HTML fragment (div + inline script) ready to be inserted into
report/index.html. The raw SVG (un-interactive) can also be requested for PR
comment rasterization.
"""

from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

from ..contracts import ConsolidatedResult, ImpactRelation


# Source sets to display in a stable order. Files whose source_set is not in
# this list are kept under the same key they carry in the ConsolidatedResult.
SOURCE_SET_ORDER = ("commonMain", "androidMain", "iosMain", "commonTest",
                    "common", "android", "ios")


# ---------------------------------------------------------------------------
# Source-set normalisation
# ---------------------------------------------------------------------------

def _normalise_source_set(raw: str) -> str:
    """Project source_sets sometimes come as 'common' vs 'commonMain'. Keep the
    expanded form for grouping so the Sunburst matches the user's mental model.
    """
    if not raw:
        return "common"
    lower = raw.lower()
    if lower in {"common", "commonmain"}:
        return "commonMain"
    if lower in {"android", "androidmain"}:
        return "androidMain"
    if lower in {"ios", "iosmain"}:
        return "iosMain"
    if lower in {"test", "commontest"}:
        return "commonTest"
    return raw


def _arc_value(entry: dict[str, Any] | None) -> int:
    """Arc arc-span weight. Directs get the biggest slice so they stand out."""
    if entry is None:
        return 1
    rel = entry["relation"]
    if rel == "direct":
        return 10
    if rel == "expect_actual":
        return 1
    # transitive: farther distance → smaller slice, min 2
    return max(2, 6 - int(entry.get("distance", 1)))


# ---------------------------------------------------------------------------
# Hierarchy builder
# ---------------------------------------------------------------------------

def _build_tree(consolidated: ConsolidatedResult) -> dict[str, Any]:
    """Root → source-set nodes → package dirs → leaf files.

    Files come from two sources:
      1. Impacted files (trace entries) — carry full metadata.
      2. Un-impacted files (static_impact.total_project_files - impacted)
         are represented as counts, not drawn. A placeholder "non-impacted"
         child is added per source-set so the ring reflects the full project.

    Since the ConsolidatedResult doesn't enumerate non-impacted files, the
    tree is built only from known files. This is consistent with how the
    existing propagation SVG already filters.
    """
    # index: ss -> package dir -> [leaves]
    leaves_per_ss: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # trace entries (impacted files with screens + metrics)
    for entry in consolidated.trace:
        p = PurePosixPath(entry.file_path)
        ss = _source_set_from_path(str(p))
        leaf = {
            "name": p.name,
            "path": str(p),
            "source_set": ss,
            "impact": entry.relation.value,
            "distance": entry.distance,
            "is_expect": False,
            "is_actual": False,
            "value": _arc_value(
                {"relation": entry.relation.value, "distance": entry.distance}
            ),
        }
        leaves_per_ss[ss].append(leaf)

    # Expect/actual pairs add flags on files already in trace (or introduce
    # new leaves if the file wasn't impacted). Build a path → leaf index.
    path_index: dict[str, dict[str, Any]] = {}
    for ss, files in leaves_per_ss.items():
        for leaf in files:
            path_index[leaf["path"]] = leaf

    for pair in consolidated.static_impact.expect_actual_pairs:
        expect_leaf = path_index.get(pair.expect_file)
        if expect_leaf:
            expect_leaf["is_expect"] = True
        else:
            ss = _source_set_from_path(pair.expect_file)
            leaf = {
                "name": PurePosixPath(pair.expect_file).name,
                "path": pair.expect_file,
                "source_set": ss,
                "impact": "expect_actual",
                "distance": -1,
                "is_expect": True,
                "is_actual": False,
                "value": 1,
            }
            leaves_per_ss[ss].append(leaf)
            path_index[pair.expect_file] = leaf
        for actual in pair.actual_files:
            act_leaf = path_index.get(actual)
            if act_leaf:
                act_leaf["is_actual"] = True
            else:
                ss = _source_set_from_path(actual)
                leaf = {
                    "name": PurePosixPath(actual).name,
                    "path": actual,
                    "source_set": ss,
                    "impact": "expect_actual",
                    "distance": -1,
                    "is_expect": False,
                    "is_actual": True,
                    "value": 1,
                }
                leaves_per_ss[ss].append(leaf)
                path_index[actual] = leaf

    # Assemble tree: root → source-set → dir chain → leaf
    root = {"name": "src", "children": []}
    order = [ss for ss in SOURCE_SET_ORDER if ss in leaves_per_ss]
    order += sorted(ss for ss in leaves_per_ss if ss not in SOURCE_SET_ORDER)

    for ss in order:
        ss_node = {"name": ss, "children": [], "source_set": ss}
        root["children"].append(ss_node)
        dir_map: dict[str, dict[str, Any]] = {"": ss_node}
        for leaf in sorted(leaves_per_ss[ss], key=lambda x: x["path"]):
            parts = _relative_kt_parts(leaf["path"], ss)
            for depth in range(len(parts) - 1):
                key = "/".join(parts[: depth + 1])
                parent_key = "/".join(parts[:depth])
                if key not in dir_map:
                    dir_node = {"name": parts[depth], "children": []}
                    dir_map[key] = dir_node
                    dir_map[parent_key]["children"].append(dir_node)
            leaf_parent = "/".join(parts[:-1])
            dir_map[leaf_parent]["children"].append(leaf)

    return root


def _source_set_from_path(path: str) -> str:
    """Infer source set from a file path like
    '.../src/commonMain/kotlin/foo/Bar.kt' → 'commonMain'. Falls back to
    the last directory under /src/ if no match."""
    parts = PurePosixPath(path).parts
    for i, p in enumerate(parts):
        if p == "src" and i + 1 < len(parts):
            return _normalise_source_set(parts[i + 1])
    return "commonMain"


def _relative_kt_parts(path: str, source_set: str) -> list[str]:
    """'/repo/shared/src/commonMain/kotlin/data/Repo.kt' → ['data', 'Repo.kt'].
    Strips everything up to and including 'kotlin'."""
    parts = list(PurePosixPath(path).parts)
    if "kotlin" in parts:
        idx = parts.index("kotlin")
        rel = parts[idx + 1:]
    else:
        # Fallback: strip up to the source set
        try:
            idx = parts.index(source_set)
            rel = parts[idx + 1:]
        except ValueError:
            rel = [PurePosixPath(path).name]
    if not rel:
        rel = [PurePosixPath(path).name]
    return rel


# ---------------------------------------------------------------------------
# Direct-files + expect/actual tree list (static HTML — sidebar)
# ---------------------------------------------------------------------------

def _direct_tree_html(consolidated: ConsolidatedResult) -> str:
    direct_by_ss: dict[str, list[str]] = defaultdict(list)
    for entry in consolidated.trace:
        if entry.relation == ImpactRelation.DIRECT:
            ss = _source_set_from_path(entry.file_path)
            direct_by_ss[ss].append(entry.file_path)

    if not direct_by_ss:
        return '<div class="sb-empty">No direct files.</div>'

    parts = []
    for ss in sorted(direct_by_ss):
        parts.append(f'<div class="sb-tree-ss">{html.escape(ss)}/</div>')
        for p in sorted(direct_by_ss[ss]):
            rel = _relative_kt_parts(p, ss)
            name = rel[-1]
            subdir = "/".join(rel[:-1])
            prefix = (
                f'<span class="sb-tree-dim">{html.escape(subdir)}/</span>'
                if subdir else ""
            )
            parts.append(
                '<div class="sb-tree-leaf sb-direct">'
                '<span class="sb-tree-bul"></span>'
                f'<span>{prefix}{html.escape(name)}</span>'
                '</div>'
            )
    return "".join(parts)


def _ea_tree_html(consolidated: ConsolidatedResult) -> str:
    pairs = consolidated.static_impact.expect_actual_pairs
    if not pairs:
        return ""

    parts = []
    for pair in pairs:
        expect_name = PurePosixPath(pair.expect_file).stem
        parts.append(
            f'<div class="sb-tree-ss">{html.escape(expect_name)}</div>'
        )
        entries = [(pair.expect_file, True)] + [
            (a, False) for a in pair.actual_files
        ]
        for fp, is_expect in entries:
            ss = _source_set_from_path(fp)
            rel = _relative_kt_parts(fp, ss)
            name = rel[-1]
            subdir = "/".join(rel[:-1])
            if subdir:
                prefix = (
                    f'<span class="sb-tree-dim">{html.escape(ss)}/'
                    f'{html.escape(subdir)}/</span>'
                )
            else:
                prefix = f'<span class="sb-tree-dim">{html.escape(ss)}/</span>'
            tag = (
                '<span class="sb-ea-tag">expect</span>'
                if is_expect else
                '<span class="sb-ea-tag">actual</span>'
            )
            parts.append(
                '<div class="sb-tree-leaf sb-ea">'
                '<span class="sb-tree-bul"></span>'
                f'<span>{prefix}{html.escape(name)} {tag}</span>'
                '</div>'
            )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def build_sunburst_html(
    consolidated: ConsolidatedResult,
) -> str:
    """Build the HTML fragment (D3 Sunburst + info sidebar) to embed as a tab
    inside the report. All D3 + styles are scoped with a ``sb-`` / ``#sb-``
    prefix so they don't collide with the main report styles."""
    tree = _build_tree(consolidated)
    data_json = json.dumps(tree, ensure_ascii=False)

    dep_before = html.escape(consolidated.version_before)
    dep_after = html.escape(consolidated.version_after)
    dep_group = html.escape(consolidated.dependency_group)

    static = consolidated.static_impact
    total_files = static.total_project_files or len(consolidated.trace)
    direct_count = sum(
        1 for f in static.impacted_files if f.relation == ImpactRelation.DIRECT
    )
    trans_count = sum(
        1 for f in static.impacted_files
        if f.relation == ImpactRelation.TRANSITIVE
    )
    ea_file_count = sum(
        1 for f in static.impacted_files
        if f.relation == ImpactRelation.EXPECT_ACTUAL
    )
    ea_units = len(static.expect_actual_pairs)
    affected = direct_count + trans_count
    none_count = max(total_files - affected, 0)

    direct_rows = _direct_tree_html(consolidated)
    ea_rows = _ea_tree_html(consolidated)
    ea_block = (
        '<div><div class="sb-sec-label">Expect / Actual</div>'
        f'{ea_rows}</div>'
        if ea_rows else ""
    )

    # Single quotes used in the nested f-string because the outer is a
    # triple-quoted double-quoted string with many embedded braces escaped for
    # f-string literal output.
    return f"""
<style>
  .sb-wrap {{ background:#F5F4F0; color:#2C2C2C; padding:32px;
    border-radius:12px; border:1px solid #e2e8f0; }}
  .sb-card {{ display:grid; grid-template-columns:260px 1fr; gap:32px;
    align-items:start; }}
  .sb-info {{ display:flex; flex-direction:column; gap:14px; }}
  .sb-title {{ font-size:15px; font-weight:700; letter-spacing:-.01em; }}
  .sb-sub {{ font-size:12px; color:#888; margin-top:2px; }}
  .sb-sub .sb-ver {{ color:#B91C1C; font-weight:600; }}
  .sb-sec-label {{ font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:.07em; color:#777; margin-bottom:6px; padding-bottom:4px;
    border-bottom:1px solid #D8D6D0; }}
  .sb-block {{ border-radius:6px; padding:9px 11px; margin-bottom:4px; }}
  .sb-block-aff {{ background:#FEF2F2; border:1px solid #FECACA; }}
  .sb-block-safe {{ background:#F8F8F7; border:1px solid #E2E0DA; }}
  .sb-block-label {{ font-size:10px; font-weight:700; text-transform:uppercase;
    letter-spacing:.07em; margin-bottom:5px; }}
  .sb-block-label.sb-aff {{ color:#B91C1C; }}
  .sb-block-label.sb-saf {{ color:#555; }}
  .sb-stat-row {{ display:flex; justify-content:space-between;
    align-items:baseline; padding:3px 0;
    border-bottom:1px solid rgba(0,0,0,.05); font-size:12px; }}
  .sb-stat-row:last-child {{ border-bottom:none; }}
  .sb-stat-n {{ font-size:15px; font-weight:800; }}
  .sb-subtotal {{ display:flex; justify-content:space-between;
    align-items:baseline; padding-top:5px; margin-top:3px;
    border-top:1px solid rgba(0,0,0,.1); font-size:11px; font-weight:700; }}
  .sb-leg-row {{ display:flex; align-items:center; gap:7px; font-size:11px;
    padding:2px 0; }}
  .sb-sw {{ width:12px; height:12px; border-radius:2px; flex-shrink:0; }}
  .sb-tree-ss {{ font-size:11px; font-weight:700; color:#333;
    padding:4px 0 2px; }}
  .sb-tree-leaf {{ display:flex; align-items:flex-start; gap:6px;
    padding:1px 0 1px 10px; font-size:11px; line-height:1.5; color:#333; }}
  .sb-tree-bul {{ width:6px; height:6px; border-radius:50%; flex-shrink:0;
    margin-top:5px; }}
  .sb-tree-leaf.sb-direct .sb-tree-bul {{ background:#B91C1C; }}
  .sb-tree-leaf.sb-ea .sb-tree-bul {{ border:1.5px dashed #64748B; }}
  .sb-tree-dim {{ color:#888; }}
  .sb-ea-tag {{ font-size:9px; font-weight:700; text-transform:uppercase;
    letter-spacing:.05em; color:#64748B; background:#F1F5F9; border-radius:3px;
    padding:0 3px; vertical-align:middle; }}
  .sb-empty {{ font-size:11px; color:#9ca3af; font-style:italic; }}
  .sb-chart {{ display:flex; align-items:center; justify-content:center; }}
  #sb-tt {{ position:fixed; background:#fff; border:1px solid #D8D6D0;
    border-radius:5px; padding:7px 11px; font-size:11px; pointer-events:none;
    box-shadow:0 2px 10px rgba(0,0,0,.08); max-width:240px; line-height:1.45;
    display:none; z-index:100; color:#2C2C2C; }}
  #sb-tt strong {{ display:block; font-size:12px; margin-bottom:1px; }}
  #sb-tt .sb-sub2 {{ color:#64748B; font-size:10px; }}
</style>
<div class="sb-wrap">
  <div class="sb-card">
    <div class="sb-info">
      <div>
        <div class="sb-title">KMP Impact · {dep_group}</div>
        <div class="sb-sub">
          <span class="sb-ver">{dep_before} &rarr; {dep_after}</span>
          &nbsp;&middot;&nbsp; {total_files} archivos
        </div>
      </div>
      <div>
        <div class="sb-sec-label">Impacto</div>
        <div class="sb-block sb-block-aff">
          <div class="sb-block-label sb-aff">Afectados</div>
          <div class="sb-stat-row"><span>Directo</span>
            <span class="sb-stat-n" style="color:#B91C1C">
              {direct_count}</span></div>
          <div class="sb-stat-row"><span>Transitivo</span>
            <span class="sb-stat-n" style="color:#1D4ED8">
              {trans_count}</span></div>
          <div class="sb-subtotal" style="color:#B91C1C">
            <span>Total</span><span>{affected}</span></div>
        </div>
        <div class="sb-block sb-block-safe">
          <div class="sb-block-label sb-saf">No afectados</div>
          <div class="sb-stat-row"><span>Sin cambios</span>
            <span class="sb-stat-n" style="color:#64748B">
              {max(none_count - ea_file_count, 0)}</span></div>
          <div class="sb-stat-row"><span>Expect/Actual</span>
            <span class="sb-stat-n" style="color:#94A3B8">{ea_units}
              <span style="font-size:10px;font-weight:400">unid.</span>
            </span></div>
          <div class="sb-subtotal" style="color:#AAA">
            <span>Total</span><span>{none_count}</span></div>
        </div>
      </div>
      <div>
        <div class="sb-sec-label">Escala</div>
        <div class="sb-leg-row">
          <span class="sb-sw" style="background:#B91C1C"></span>Directo</div>
        <div class="sb-leg-row">
          <span class="sb-sw" style="background:#1D4ED8"></span>
          Transitivo dist. 1</div>
        <div class="sb-leg-row">
          <span class="sb-sw" style="background:#60A5FA"></span>
          Transitivo dist. 2+</div>
        <div class="sb-leg-row">
          <span class="sb-sw"
            style="background:#94A3B8;opacity:.5"></span>Sin impacto</div>
        <div class="sb-leg-row">
          <span class="sb-sw"
            style="background:none;border:1.5px dashed #94A3B8"></span>
          Expect/Actual (KMP)</div>
      </div>
      <div>
        <div class="sb-sec-label">Archivos directos</div>
        {direct_rows}
      </div>
      {ea_block}
    </div>
    <div class="sb-chart"><svg id="sb-sun"></svg></div>
  </div>
  <div id="sb-tt"></div>
</div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
(function() {{
  const DATA = {data_json};
  const W = 640, R = W / 6;
  const MAX_FS = 12, MIN_FS = 7, CH_RATIO = 0.58;
  function dispName(d) {{ return d.data.name.replace(/\\.kt$/, ""); }}
  function arcSpan(x0,x1,y0,y1) {{ return (x1-x0)*((y0+y1)/2)*R; }}
  function calcFS(x0,x1,y0,y1,n) {{
    if (!n) return MAX_FS;
    return Math.min(MAX_FS, Math.max(MIN_FS, arcSpan(x0,x1,y0,y1)/(n*CH_RATIO)));
  }}
  function leafColour(d) {{
    const imp = d.data.impact, dist = d.data.distance;
    if (imp === "direct") return "#B91C1C";
    if (imp === "transitive") return dist <= 1 ? "#1D4ED8" : "#60A5FA";
    return "#94A3B8";
  }}
  function folderColour(d) {{
    const leaves = d.descendants().filter(c => !c.children);
    if (leaves.some(c => c.data.impact === "direct")) return "#B91C1C";
    if (leaves.some(c => c.data.impact === "transitive")) {{
      const mn = d3.min(leaves.filter(c => c.data.impact === "transitive"),
                        c => c.data.distance);
      return mn <= 1 ? "#1D4ED8" : "#60A5FA";
    }}
    return "#94A3B8";
  }}
  const colour = d => d.children ? folderColour(d) : leafColour(d);
  function isImp(d) {{
    if (!d.children) {{
      const i = d.data.impact;
      return i === "direct" || i === "transitive";
    }}
    return d.descendants().some(
      c => c.data.impact === "direct" || c.data.impact === "transitive"
    );
  }}
  const opacity = d => isImp(d) ? 1 : 0.28;
  const root = d3.hierarchy(DATA)
    .sum(d => d.value || 0)
    .sort((a, b) => b.value - a.value);
  d3.partition().size([2*Math.PI, root.height + 1])(root);
  const arc = d3.arc()
    .startAngle(d => d.x0).endAngle(d => d.x1)
    .padAngle(d => Math.min((d.x1 - d.x0) / 2, 0.004))
    .padRadius(R * 1.5)
    .innerRadius(d => d.y0 * R)
    .outerRadius(d => Math.max(d.y0 * R, d.y1 * R - 1));
  const svg = d3.select("#sb-sun")
    .attr("viewBox", [-W/2, -W/2, W, W])
    .attr("width", W).attr("height", W);
  root.each(d => d.current = d);
  function arcVis(d) {{ return d.y1 <= 3 && d.y0 >= 1 && d.x1 > d.x0; }}
  function lblVis(d) {{
    return d.y1 <= 3 && d.y0 >= 1 && (d.y1-d.y0)*(d.x1-d.x0) > 0.02;
  }}
  function lblTransform(d) {{
    const x = ((d.x0+d.x1)/2)*180/Math.PI, y=(d.y0+d.y1)/2*R;
    return `rotate(${{x-90}}) translate(${{y}},0) rotate(${{x<180?0:180}})`;
  }}
  const path = svg.append("g")
    .selectAll("path")
    .data(root.descendants().slice(1))
    .join("path")
    .attr("fill", d => colour(d))
    .attr("fill-opacity", d => arcVis(d.current) ? opacity(d) : 0)
    .attr("pointer-events", d => arcVis(d.current) ? "auto" : "none")
    .attr("stroke", d => (d.data.is_expect || d.data.is_actual)
      ? "#64748B" : "none")
    .attr("stroke-width", d => (d.data.is_expect || d.data.is_actual)
      ? 1.5 : 0)
    .attr("stroke-dasharray", d => (d.data.is_expect || d.data.is_actual)
      ? "3,2" : "none")
    .attr("d", d => arc(d.current))
    .style("cursor", d => d.children ? "pointer" : "default")
    .on("click", (ev, p) => {{ if (p.children) zoomTo(p); }});
  const label = svg.append("g")
    .attr("pointer-events", "none")
    .attr("text-anchor", "middle")
    .style("user-select", "none")
    .selectAll("text")
    .data(root.descendants().slice(1))
    .join("text")
    .attr("dy", "0.35em")
    .attr("fill-opacity", d => +lblVis(d.current))
    .attr("transform", d => lblTransform(d.current))
    .style("font-size", d =>
      `${{calcFS(d.x0,d.x1,d.y0,d.y1,dispName(d).length).toFixed(1)}}px`)
    .style("font-weight", "700")
    .style("fill", d => {{
      const c = colour(d);
      return (c === "#B91C1C" || c === "#1D4ED8") ? "#FFF" : "#1E293B";
    }})
    .text(d => dispName(d));
  const cg = svg.append("g").style("cursor", "pointer");
  cg.append("circle").attr("r", R).attr("fill", "#F5F4F0")
    .attr("stroke", "#D8D6D0");
  const clbl = cg.append("text")
    .attr("text-anchor", "middle").attr("dy", "0.35em")
    .style("font-size", "11px").style("font-weight", "600")
    .style("fill", "#64748B").text("src");
  cg.on("click", () => zoomTo(currentFocus.parent || root));
  const tt = document.getElementById("sb-tt");
  path.on("mousemove", (ev, d) => {{
    const imp = d.data.impact, dist = d.data.distance;
    let badge, detail = "";
    if (d.children) {{
      const leaves = d.descendants().filter(c => !c.children);
      const nD = leaves.filter(c => c.data.impact === "direct").length;
      const nT = leaves.filter(c => c.data.impact === "transitive").length;
      const parts = [];
      if (nD) parts.push(`${{nD}} directo${{nD>1?"s":""}}`);
      if (nT) parts.push(`${{nT}} transitivo${{nT>1?"s":""}}`);
      badge = d.data.source_set
        ? `Source set: ${{d.data.name}}` : "Carpeta";
      detail = parts.join(" · ") || "sin impacto";
    }} else {{
      badge =
        imp === "direct" ? "Directo" :
        imp === "transitive" ? `Transitivo — dist. ${{dist}}` :
        imp === "expect_actual" ? "Expect/Actual (KMP)" : "Sin impacto";
      if (d.data.is_expect) badge += " · expect";
      if (d.data.is_actual) badge += " · actual";
      detail = d.data.path || "";
    }}
    tt.innerHTML =
      `<strong>${{d.data.name}}</strong>` +
      `<span class="sb-sub2">${{badge}}</span>` +
      (detail ? `<br><span class="sb-sub2">${{detail}}</span>` : "");
    tt.style.display = "block";
    tt.style.left = ev.clientX + 14 + "px";
    tt.style.top = ev.clientY - 10 + "px";
  }}).on("mouseleave", () => tt.style.display = "none");
  let currentFocus = root;
  function zoomTo(focus) {{
    currentFocus = focus;
    root.each(d => d.target = {{
      x0: Math.max(0, Math.min(1,
        (d.x0-focus.x0)/(focus.x1-focus.x0))) * 2 * Math.PI,
      x1: Math.max(0, Math.min(1,
        (d.x1-focus.x0)/(focus.x1-focus.x0))) * 2 * Math.PI,
      y0: Math.max(0, d.y0 - focus.depth),
      y1: Math.max(0, d.y1 - focus.depth),
    }});
    const tr = svg.transition().duration(480);
    path.transition(tr)
      .tween("data", d => {{
        const i = d3.interpolate(d.current, d.target);
        return t => d.current = i(t);
      }})
      .filter(function(d) {{
        return +this.getAttribute("fill-opacity") || arcVis(d.target);
      }})
      .attr("fill-opacity", d => arcVis(d.target) ? opacity(d) : 0)
      .attr("pointer-events", d => arcVis(d.target) ? "auto" : "none")
      .attrTween("d", d => () => arc(d.current));
    label
      .filter(function(d) {{
        return +this.getAttribute("fill-opacity") || lblVis(d.target);
      }})
      .transition(tr)
      .attr("fill-opacity", d => +lblVis(d.target))
      .attrTween("transform", d => () => lblTransform(d.current))
      .on("end", function(d) {{
        const pos = d.target || d.current;
        const n = dispName(d);
        d3.select(this).text(n).style("font-size",
          `${{calcFS(pos.x0,pos.x1,pos.y0,pos.y1,n.length).toFixed(1)}}px`);
      }});
    clbl.text(focus.data.name);
  }}
}})();
</script>
"""


def build_sunburst_svg_standalone(
    consolidated: ConsolidatedResult,
) -> str:
    """Static SVG (no JS) for PR-comment rasterization. Draws a simplified
    2-level ring: source set on the outer ring, coloured by aggregate impact.
    Kept intentionally simple so cairosvg can render it without running D3.
    """
    tree = _build_tree(consolidated)
    # Flatten source-set children counts: direct / transitive / none
    sets = []
    for ss_node in tree["children"]:
        leaves = _flatten_leaves(ss_node)
        if not leaves:
            continue
        direct = sum(1 for l in leaves if l["impact"] == "direct")
        trans = sum(1 for l in leaves if l["impact"] == "transitive")
        ea = sum(1 for l in leaves if l["impact"] == "expect_actual")
        none = len(leaves) - direct - trans - ea
        sets.append({
            "name": ss_node["name"],
            "direct": direct, "trans": trans, "ea": ea, "none": none,
            "total": len(leaves),
        })
    return _render_static_sunburst(sets, consolidated)


def _flatten_leaves(node: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    stack = [node]
    while stack:
        n = stack.pop()
        if "children" in n and n["children"]:
            stack.extend(n["children"])
        elif "impact" in n:
            out.append(n)
    return out


def _render_static_sunburst(
    sets: list[dict[str, Any]],
    consolidated: ConsolidatedResult,
) -> str:
    """Simple concentric donut: inner ring = source sets, outer ring = impact
    breakdown. Pure SVG, no scripts, ready for cairosvg."""
    W = 520
    CX = CY = W // 2
    INNER_R = 90
    MID_R = 140
    OUTER_R = 200
    import math

    total_files = sum(s["total"] for s in sets) or 1
    title = html.escape(consolidated.dependency_group)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {W+60}" '
        f'width="{W}" height="{W+60}" '
        'font-family="system-ui,sans-serif">',
        '<style>.lbl{font-size:12px;fill:#1e293b;font-weight:600}'
        '.cap{font-size:14px;fill:#1e293b;font-weight:700}'
        '.sub{font-size:11px;fill:#64748b}</style>',
        f'<text x="{CX}" y="26" text-anchor="middle" class="cap">'
        f'Impact Sunburst · {title}</text>',
        f'<text x="{CX}" y="44" text-anchor="middle" class="sub">'
        f'{consolidated.version_before} -&gt; {consolidated.version_after}'
        f' &#183; {total_files} archivos</text>',
    ]

    # Inner ring = source-sets
    ss_colors = {
        "commonMain": "#312e81", "androidMain": "#0f766e",
        "iosMain": "#9d174d", "commonTest": "#6b7280",
    }
    ang0 = -math.pi / 2
    for s in sets:
        frac = s["total"] / total_files
        ang1 = ang0 + frac * 2 * math.pi
        path = _ring_segment(
            CX, CY + 30, INNER_R, MID_R - 5, ang0, ang1
        )
        color = ss_colors.get(s["name"], "#475569")
        parts.append(f'<path d="{path}" fill="{color}" opacity="0.85"/>')
        # mid-angle label
        mid = (ang0 + ang1) / 2
        lbl_r = (INNER_R + MID_R) / 2 - 2
        lx = CX + math.cos(mid) * lbl_r
        ly = CY + 30 + math.sin(mid) * lbl_r
        if frac > 0.08:
            parts.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'class="lbl" fill="#fff">{html.escape(s["name"])}</text>'
            )
        ang0 = ang1

    # Outer ring = impact segments within each source-set
    impact_colors = {
        "direct": "#B91C1C", "trans": "#1D4ED8",
        "ea": "#94A3B8", "none": "#e5e7eb",
    }
    ang0 = -math.pi / 2
    for s in sets:
        ss_frac = s["total"] / total_files
        ss_ang1 = ang0 + ss_frac * 2 * math.pi
        sub_total = s["total"] or 1
        sub_ang = ang0
        for key in ("direct", "trans", "ea", "none"):
            count = s[key]
            if not count:
                continue
            portion = count / sub_total
            sub_next = sub_ang + portion * (ss_ang1 - ang0)
            path = _ring_segment(
                CX, CY + 30, MID_R, OUTER_R, sub_ang, sub_next
            )
            parts.append(
                f'<path d="{path}" fill="{impact_colors[key]}" '
                f'opacity="0.9"/>'
            )
            sub_ang = sub_next
        ang0 = ss_ang1

    # Legend
    legend_y = W + 40
    parts.append(
        f'<g transform="translate(20,{legend_y})">'
        '<rect width="14" height="14" fill="#B91C1C"/>'
        '<text x="20" y="11" class="sub">Directo</text>'
        '<rect x="90" width="14" height="14" fill="#1D4ED8"/>'
        '<text x="110" y="11" class="sub">Transitivo</text>'
        '<rect x="200" width="14" height="14" fill="#94A3B8"/>'
        '<text x="220" y="11" class="sub">Expect/Actual</text>'
        '<rect x="330" width="14" height="14" fill="#e5e7eb" '
        'stroke="#cbd5e1"/>'
        '<text x="350" y="11" class="sub">Sin impacto</text>'
        '</g>'
    )

    parts.append('</svg>')
    return "\n".join(parts)


def _ring_segment(cx: float, cy: float, r_in: float, r_out: float,
                  a0: float, a1: float) -> str:
    """SVG path for an annular sector."""
    import math
    large = 1 if (a1 - a0) > math.pi else 0
    x0i, y0i = cx + r_in * math.cos(a0), cy + r_in * math.sin(a0)
    x1i, y1i = cx + r_in * math.cos(a1), cy + r_in * math.sin(a1)
    x0o, y0o = cx + r_out * math.cos(a0), cy + r_out * math.sin(a0)
    x1o, y1o = cx + r_out * math.cos(a1), cy + r_out * math.sin(a1)
    return (
        f"M {x0i:.2f} {y0i:.2f} "
        f"L {x0o:.2f} {y0o:.2f} "
        f"A {r_out:.2f} {r_out:.2f} 0 {large} 1 {x1o:.2f} {y1o:.2f} "
        f"L {x1i:.2f} {y1i:.2f} "
        f"A {r_in:.2f} {r_in:.2f} 0 {large} 0 {x0i:.2f} {y0i:.2f} Z"
    )
