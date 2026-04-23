#!/usr/bin/env node
/**
 * analyze_impact.js
 * =================
 * Step 4 of the CI pipeline.
 *
 * Reads graph.json (the current project dependency graph) and diff.json (what
 * changed in this PR) and computes, for every changed package:
 *
 *   - How many nodes in the project currently depend on it  (in-degree)
 *   - The list of direct dependents (sources whose target is this package)
 *   - A criticality level  (CRÍTICO / ALTO / MEDIO / BAJO)
 *   - A Mermaid subgraph that mirrors the arc diagram's focus mode — incoming
 *     arcs only, showing who depends on the changed library
 *
 * The output is a report.json file that contains:
 *   - The full diff (re-exported for convenience)
 *   - An `impacts` map (packageName → impact object)
 *   - A `markdown` string ready to be posted as a GitHub PR comment
 *
 * ----------------------------------------------------------------------------
 * Dependency direction reminder
 * ----------------------------------------------------------------------------
 *
 *   In graph.json, every link has:
 *     source → target   meaning "source DEPENDS_ON target"
 *
 *   So to answer "who depends on package X?" we look for all links where
 *     link.target === X   (the source packages are X's dependents)
 *
 *   This is the same direction used by the arc diagram's focus mode.
 *
 * ----------------------------------------------------------------------------
 * Mermaid subgraph format
 * ----------------------------------------------------------------------------
 *
 *   ```mermaid
 *   graph LR
 *       N0["ktor-client-core"] --> TARGET["kotlin-stdlib ⬆️"]
 *       N1["CursoKmpApp"]      --> TARGET
 *       N2["atomicfu"]         --> TARGET
 *       MORE["... +95 más"]   --> TARGET
 *   ```
 *
 *   - Arrows point TO the changed package (incoming = dependents)
 *   - The changed package is highlighted with a blue fill via classDef
 *   - Maximum MAX_MERMAID_DEPS dependents shown to keep the diagram readable
 *
 * ----------------------------------------------------------------------------
 * Environment variables
 * ----------------------------------------------------------------------------
 *   GRAPH_PATH   — path to graph.json   (default: pipeline/sbom/graph.json)
 *   DIFF_PATH    — path to diff.json    (default: pipeline/ci/diff.json)
 *   REPORT_PATH  — output report.json   (default: pipeline/ci/report.json)
 */

"use strict";

const fs   = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const GRAPH_PATH     = process.env.GRAPH_PATH     || path.join(__dirname, "../sbom/graph.json");
const DIFF_PATH      = process.env.DIFF_PATH      || path.join(__dirname, "diff.json");
const REPORT_PATH    = process.env.REPORT_PATH    || path.join(__dirname, "report.json");

// Base URL of the GitHub Pages deployment (no trailing slash).
// When set, the PR comment will include a deep-link that opens the arc diagram
// with the changed library pre-selected in focus mode via ?focus=<name>.
// Example: "https://sreys54.github.io/CursoKmpApp-GitGraph"
// Leave empty (or unset) to omit links, e.g. in local/offline runs.
const PAGES_BASE_URL = (process.env.PAGES_BASE_URL || "").replace(/\/$/, "");

// Maximum direct dependents to show in the Mermaid diagram.
// Beyond this, a summary node ("... +N más") is appended.
const MAX_MERMAID_DEPS = 12;

// Criticality thresholds (by number of in-project dependents)
const THRESHOLDS = { critical: 50, high: 15, medium: 5 };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function loadJson(p) {
  const resolved = path.resolve(p);
  if (!fs.existsSync(resolved)) {
    throw new Error(`File not found: ${resolved}`);
  }
  return JSON.parse(fs.readFileSync(resolved, "utf-8"));
}

/**
 * Returns the artifact part of a node ID without the version.
 * "org.jetbrains.kotlin:kotlin-stdlib@1.9.23" → "kotlin-stdlib"
 */
function artifactOnly(nodeId) {
  return (nodeId.split(":")[1] || nodeId).split("@")[0];
}

/**
 * Sanitises a string so it can be used as a Mermaid node identifier.
 * Mermaid identifiers must match [a-zA-Z0-9_-]+.
 */
function mermaidId(str) {
  return str.replace(/[^a-zA-Z0-9_]/g, "_").replace(/_+/g, "_");
}

/**
 * Determines the criticality level and emoji for a given dependent count.
 */
function criticality(count) {
  if (count >= THRESHOLDS.critical) return { level: "CRÍTICO", emoji: "🔴" };
  if (count >= THRESHOLDS.high)     return { level: "ALTO",    emoji: "🟠" };
  if (count >= THRESHOLDS.medium)   return { level: "MEDIO",   emoji: "🟡" };
  return                                   { level: "BAJO",    emoji: "🟢" };
}

// ---------------------------------------------------------------------------
// Core analysis — one changed package
// ---------------------------------------------------------------------------

/**
 * Analyses the impact of one changed package against the full dependency graph.
 *
 * Matching strategy: the diff provides package names without version (e.g.
 * "org.jetbrains.kotlin:kotlin-stdlib") while graph nodes include the version
 * (e.g. "org.jetbrains.kotlin:kotlin-stdlib@1.9.23").  We match any node
 * whose ID starts with "{changedName}@" to handle multi-version scenarios.
 *
 * @param {Object}   graph        — parsed graph.json { nodes, links }
 * @param {string}   changedName  — package name from the diff API (no @version)
 * @param {string}   changeLabel  — human label for the change type (for Mermaid)
 * @returns {Object} impact report for this package
 */
function analyzeOne(graph, changedName, changeLabel) {
  // 1. Find every graph node that corresponds to this package name.
  //    There may be more than one if multiple versions are resolved
  //    (common in KMP projects with platform-specific variants).
  const matchingNodes = graph.nodes.filter((n) =>
    n.id === changedName ||
    n.id.startsWith(changedName + "@")
  );

  // Build the deep-link URL regardless of whether the node is found.
  // The arc diagram's ?focus= handler does a prefix match, so passing the
  // versionless package name is correct even when multiple versions exist.
  const diagramUrl = PAGES_BASE_URL
    ? `${PAGES_BASE_URL}/visualization/arc_diagram.html` +
      `?focus=${encodeURIComponent(changedName)}`
    : null;

  if (matchingNodes.length === 0) {
    // Package is not in the current graph (e.g. it was just added in this PR)
    return {
      found:           false,
      packageName:     changedName,
      changeLabel,
      matchingNodes:   [],
      dependentCount:  0,
      dependents:      [],
      mermaidSubgraph: null,
      diagramUrl,
      criticality:     { level: "DESCONOCIDO", emoji: "⚪" },
    };
  }

  // 2. Collect all unique dependents across all matching nodes.
  //    A dependent is a node where link.target matches one of our nodes,
  //    i.e. the source DEPENDS ON our package.
  const matchingIds  = new Set(matchingNodes.map((n) => n.id));
  const dependentSet = new Set();

  graph.links.forEach((l) => {
    if (matchingIds.has(l.target)) {
      dependentSet.add(l.source);
    }
  });

  const dependents = Array.from(dependentSet);
  const count      = dependents.length;
  const crit       = criticality(count);

  // 3. Build the Mermaid subgraph.
  //    Format: graph LR — dependents → changed package (incoming direction)
  //    We show at most MAX_MERMAID_DEPS dependents; the rest become a summary node.
  const primaryNodeId = matchingNodes[0].id;
  const displayName   = artifactOnly(primaryNodeId);
  const targetId      = mermaidId(displayName);
  const targetLabel   = `${displayName} ${changeLabel}`;

  const topDeps    = dependents.slice(0, MAX_MERMAID_DEPS);
  const remainder  = count - topDeps.length;

  const lines = [
    "```mermaid",
    "graph LR",
    `    classDef changed fill:#388bfd,color:#fff,stroke:#79c0ff,stroke-width:2px`,
    "",
  ];

  topDeps.forEach((dep, i) => {
    const label  = artifactOnly(dep);
    const nodeId = `N${i}`;
    lines.push(`    ${nodeId}["${label}"] --> ${targetId}["${targetLabel}"]`);
  });

  if (remainder > 0) {
    lines.push(`    MORE["... +${remainder} más"] --> ${targetId}`);
  }

  lines.push(`    class ${targetId} changed`);
  lines.push("```");

  const mermaidSubgraph = lines.join("\n");

  return {
    found:           true,
    packageName:     changedName,
    changeLabel,
    matchingNodes:   matchingNodes.map((n) => n.id),
    dependentCount:  count,
    dependents,
    mermaidSubgraph,
    diagramUrl,
    criticality:     crit,
  };
}

// ---------------------------------------------------------------------------
// Markdown comment generator
// ---------------------------------------------------------------------------

/**
 * Generates the full markdown string for the PR comment.
 *
 * Structure:
 *   <!-- dependency-analysis-bot -->    ← HTML marker used to find/update the comment
 *   ## 🔍 Análisis de Dependencias
 *   Summary line
 *   ### ➕ Añadidas          (if any)
 *   ### ➖ Eliminadas         (if any)
 *   ### ⬆️ Actualizadas       (if any)
 *   ---
 *   ### 📊 Subgrafo de impacto   (for the top 2 most-impacted changes)
 *   [Mermaid diagram]
 *   ---
 *   > 🤖 footer
 */
function buildMarkdown(diff, impacts) {
  const lines = [];

  // HTML marker — used by the workflow to find the existing comment and update it
  lines.push("<!-- dependency-analysis-bot -->");
  lines.push("## 🔍 Análisis de Dependencias");
  lines.push("");

  const total = diff.totalChanges;

  if (total === 0) {
    lines.push("✅ No se detectaron cambios en las dependencias de este PR.");
    lines.push("");
    lines.push(`> 🤖 Pipeline ejecutado automáticamente · Commit: \`${diff.headSha.slice(0, 7)}\``);
    return lines.join("\n");
  }

  lines.push(
    `Se detectaron **${total} cambio${total !== 1 ? "s" : ""}** en las ` +
    `dependencias de este PR.`
  );
  lines.push("");

  // ── Added ──────────────────────────────────────────────────────────────────
  if (diff.added.length > 0) {
    lines.push("### ➕ Añadidas");
    lines.push("");
    lines.push("| Paquete | Versión | Manifiesto | Impacto en el proyecto |");
    lines.push("|---------|---------|-----------|------------------------|");

    for (const dep of diff.added) {
      const impact = impacts[dep.name];
      const impactStr = impact && impact.found && impact.dependentCount > 0
        ? `${impact.criticality.emoji} **${impact.dependentCount}** paquetes dependen de este`
        : "⚪ Sin dependientes en el grafo actual";
      const manifest = dep.manifest ? `\`${dep.manifest}\`` : "—";
      lines.push(`| \`${dep.name}\` | \`${dep.version}\` | ${manifest} | ${impactStr} |`);
    }
    lines.push("");
  }

  // ── Removed ────────────────────────────────────────────────────────────────
  if (diff.removed.length > 0) {
    lines.push("### ➖ Eliminadas");
    lines.push("");
    lines.push("| Paquete | Versión | Manifiesto |");
    lines.push("|---------|---------|-----------|");

    for (const dep of diff.removed) {
      const manifest = dep.manifest ? `\`${dep.manifest}\`` : "—";
      lines.push(`| \`${dep.name}\` | \`${dep.version}\` | ${manifest} |`);
    }
    lines.push("");
    lines.push(
      "> ⚠️ Verificar que no existan referencias directas a estas librerías en el código fuente."
    );
    lines.push("");
  }

  // ── Updated ────────────────────────────────────────────────────────────────
  if (diff.updated.length > 0) {
    lines.push("### ⬆️ Actualizadas");
    lines.push("");
    lines.push("| Paquete | Versión anterior | Nueva versión | Impacto en el proyecto |");
    lines.push("|---------|-----------------|---------------|------------------------|");

    for (const dep of diff.updated) {
      const impact = impacts[dep.name];
      let impactStr;
      if (!impact || !impact.found) {
        impactStr = "⚪ No encontrado en el grafo actual";
      } else if (impact.dependentCount === 0) {
        impactStr = "🟢 Sin dependientes directos";
      } else {
        impactStr =
          `${impact.criticality.emoji} **${impact.dependentCount}** ` +
          `paquete${impact.dependentCount !== 1 ? "s" : ""} depende${impact.dependentCount === 1 ? "" : "n"} de este`;
      }
      lines.push(
        `| \`${dep.name}\` | \`${dep.previousVersion}\` | ` +
        `\`${dep.newVersion}\` | ${impactStr} |`
      );
    }
    lines.push("");
  }

  // ── Mermaid subgraphs for the highest-impact changes ──────────────────────
  //
  // Show subgraphs only for packages that:
  //   a) were found in the current graph
  //   b) have at least one dependent
  // Sort by dependent count descending; show the top 2 to keep the comment
  // from becoming excessively long.

  const withSubgraph = Object.values(impacts)
    .filter((i) => i.found && i.dependentCount > 0 && i.mermaidSubgraph)
    .sort((a, b) => b.dependentCount - a.dependentCount)
    .slice(0, 2);

  if (withSubgraph.length > 0) {
    lines.push("---");
    lines.push("");
    lines.push("### 📊 Subgrafo de impacto");
    lines.push("");
    lines.push(
      "Los siguientes cambios afectan a paquetes que ya existen en el proyecto. " +
      "Los arcos apuntan hacia la librería modificada (arcos entrantes = quien depende de ella)."
    );
    lines.push("");

    for (const impact of withSubgraph) {
      const changeTypeStr =
        diff.updated.some((d) => d.name === impact.packageName) ? "actualizada" :
        diff.added.some((d)   => d.name === impact.packageName) ? "añadida"     : "modificada";

      // Heading includes a deep-link to the arc diagram pre-focused on this
      // library when PAGES_BASE_URL is configured (GitHub Pages deployment).
      const diagramLink = impact.diagramUrl
        ? ` · [🔗 Ver en diagrama interactivo](${impact.diagramUrl})`
        : "";

      lines.push(
        `#### \`${impact.packageName}\` — ${impact.criticality.emoji} ` +
        `${impact.dependentCount} dependiente${impact.dependentCount !== 1 ? "s" : ""} ` +
        `directos (${changeTypeStr})${diagramLink}`
      );
      lines.push("");
      lines.push(impact.mermaidSubgraph);
      lines.push("");
    }
  }

  // ── Footer ─────────────────────────────────────────────────────────────────
  lines.push("---");
  lines.push("");
  lines.push(
    `> 🤖 Pipeline ejecutado automáticamente · ` +
    `Commit: \`${diff.headSha.slice(0, 7)}\` · ` +
    `Grafo: ${Object.values(impacts).filter((i) => i.found).length} paquetes analizados`
  );

  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function main() {
  console.log("[INFO] Loading graph and diff...");

  const graph = loadJson(GRAPH_PATH);
  const diff  = loadJson(DIFF_PATH);

  console.log(
    `[INFO] Graph: ${graph.nodes.length} nodes, ${graph.links.length} links`
  );
  console.log(
    `[INFO] Diff:  +${diff.added.length} added, ` +
    `-${diff.removed.length} removed, ` +
    `~${diff.updated.length} updated`
  );

  // Build the list of all changed package names and their change labels
  const toAnalyze = [
    ...diff.added.map((d)   => ({ name: d.name, label: "➕" })),
    ...diff.removed.map((d) => ({ name: d.name, label: "➖" })),
    ...diff.updated.map((d) => ({ name: d.name, label: "⬆️" })),
  ];

  // Analyse impact for each changed package
  const impacts = {};
  for (const { name, label } of toAnalyze) {
    impacts[name] = analyzeOne(graph, name, label);
    const i = impacts[name];
    if (i.found) {
      console.log(
        `[INFO] ${name}: ${i.dependentCount} dependents ` +
        `[${i.criticality.level}]`
      );
    } else {
      console.log(`[INFO] ${name}: not found in current graph (may be newly added)`);
    }
  }

  // Generate markdown PR comment
  const markdown = buildMarkdown(diff, impacts);

  // Assemble and write report
  const report = { diff, impacts, markdown };
  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), "utf-8");

  console.log(`\n[INFO] Report saved to: ${path.resolve(REPORT_PATH)}`);
  console.log("\n========== PR Comment Preview (first 600 chars) ==========");
  console.log(markdown.slice(0, 600) + (markdown.length > 600 ? "\n..." : ""));
  console.log("===========================================================\n");
}

try {
  main();
} catch (err) {
  console.error(`[ERROR] ${err.message}`);
  process.exit(1);
}
