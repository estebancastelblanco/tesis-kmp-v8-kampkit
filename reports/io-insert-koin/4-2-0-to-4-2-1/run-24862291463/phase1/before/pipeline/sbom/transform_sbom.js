#!/usr/bin/env node
/**
 * transform_sbom.js
 * =================
 * Transforms a GitHub-generated SPDX 2.3 SBOM (sbom.json) into a D3-compatible
 * arc diagram graph format (graph.json).
 *
 * ----------------------------------------------------------------------------
 * SPDX 2.3 STRUCTURE (what GitHub gives us)
 * ----------------------------------------------------------------------------
 *
 * The file is a flat JSON object with two key arrays:
 *
 *  "packages" — Every dependency detected in the repository.
 *    Each package has:
 *      - SPDXID        : unique ID used internally to link relationships
 *                        e.g. "SPDXRef-maven-org.jetbrains.kotlin-kotlin-stdlib-1.9.23-763561"
 *      - name          : human-readable package name (group:artifact in Maven)
 *                        e.g. "org.jetbrains.kotlin:kotlin-stdlib"
 *      - versionInfo   : resolved version string  e.g. "1.9.23"
 *      - licenseConcluded : SPDX license expression (may be absent)
 *      - externalRefs  : array of references; the purl entry gives ecosystem info
 *
 *  "relationships" — Every directed dependency edge.
 *    Each entry has:
 *      - spdxElementId     : the package that has the dependency  (source)
 *      - relatedSpdxElement: the package being depended on         (target)
 *      - relationshipType  : always "DEPENDS_ON" for dep edges
 *                            (one "DESCRIBES" entry links the root document — ignored)
 *
 * This gives us a directed graph where an edge A → B means "A depends on B".
 *
 * ----------------------------------------------------------------------------
 * OUTPUT FORMAT  (D3 arc diagram)
 * ----------------------------------------------------------------------------
 *
 *  {
 *    "nodes": [ { "id": "package-name@version" }, ... ],
 *    "links": [ { "source": "...", "target": "..." }, ... ]
 *  }
 *
 * ----------------------------------------------------------------------------
 * ENVIRONMENT VARIABLES
 * ----------------------------------------------------------------------------
 *  SBOM_INPUT_PATH   — path to the input SBOM JSON  (default: sbom.json)
 *  GRAPH_OUTPUT_PATH — path for the output graph JSON (default: graph.json)
 *
 * Usage:
 *   node transform_sbom.js
 *   SBOM_INPUT_PATH=../../sbom.json GRAPH_OUTPUT_PATH=graph.json node transform_sbom.js
 */

"use strict";

const fs   = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const INPUT_PATH  = process.env.SBOM_INPUT_PATH   || "sbom.json";
const OUTPUT_PATH = process.env.GRAPH_OUTPUT_PATH  || "graph.json";

// ---------------------------------------------------------------------------
// Step 1 — Load and validate the SBOM file
// ---------------------------------------------------------------------------

/**
 * Reads and parses the SBOM JSON from disk.
 * Validates that the required top-level keys exist.
 * Throws if the file is missing, unreadable, or malformed.
 */
function loadSbom(inputPath) {
  const resolved = path.resolve(inputPath);
  console.log(`[INFO] Reading SBOM from: ${resolved}`);

  if (!fs.existsSync(resolved)) {
    throw new Error(`File not found: ${resolved}`);
  }

  let raw;
  try {
    raw = fs.readFileSync(resolved, "utf-8");
  } catch (err) {
    throw new Error(`Cannot read file: ${err.message}`);
  }

  let data;
  try {
    data = JSON.parse(raw);
  } catch (err) {
    throw new Error(`Invalid JSON: ${err.message}`);
  }

  // The GitHub API wraps the SPDX doc in a top-level "sbom" key.
  // If running fetch_sbom.js output, unwrap it. If using the raw export, skip.
  if (data.sbom && data.sbom.packages) {
    console.log(`[INFO] Detected API wrapper — unwrapping top-level 'sbom' key.`);
    data = data.sbom;
  }

  // Validate required SPDX fields
  if (!Array.isArray(data.packages)) {
    throw new Error(`Malformed SBOM: 'packages' array not found.`);
  }
  if (!Array.isArray(data.relationships)) {
    throw new Error(`Malformed SBOM: 'relationships' array not found.`);
  }

  console.log(`[INFO] SBOM loaded — ${data.packages.length} packages, ${data.relationships.length} relationships.`);
  return data;
}

// ---------------------------------------------------------------------------
// Step 2 — Build a lookup map: SPDXID → node ID string
// ---------------------------------------------------------------------------

/**
 * Creates a Map from each package's SPDXID to a human-readable node ID.
 *
 * Node ID format: "name@version"
 *   e.g. "org.jetbrains.kotlin:kotlin-stdlib@1.9.23"
 *
 * Why SPDXID as the key?
 *   Relationships reference packages by SPDXID, not by name.
 *   We need this map to translate SPDXID → readable label when building edges.
 *
 * Edge cases handled:
 *   - Missing name     → falls back to the SPDXID itself
 *   - Missing version  → omits the "@version" suffix
 *   - Duplicate IDs    → last entry wins (should not happen in valid SPDX)
 */
function buildPackageIndex(packages) {
  const index = new Map(); // SPDXID → "name@version"

  for (const pkg of packages) {
    const spdxId = pkg.SPDXID;

    if (!spdxId) {
      console.warn(`[WARN] Package without SPDXID — skipping: ${JSON.stringify(pkg).slice(0, 80)}`);
      continue;
    }

    const name    = pkg.name    || spdxId;          // fallback to ID if name missing
    const version = pkg.versionInfo;
    const nodeId  = version ? `${name}@${version}` : name;

    index.set(spdxId, nodeId);
  }

  console.log(`[INFO] Package index built — ${index.size} entries.`);
  return index;
}

// ---------------------------------------------------------------------------
// Step 3 — Extract edges from relationships
// ---------------------------------------------------------------------------

/**
 * Filters and maps relationships to D3 link objects.
 *
 * Only "DEPENDS_ON" relationships are processed. The one "DESCRIBES"
 * relationship (which links the SPDX document root to the repo) is ignored
 * because it is a document-level metadata entry, not a package dependency.
 *
 * Each valid relationship becomes:
 *   { source: "packageA@1.0", target: "packageB@2.0" }
 *
 * Skipped cases (with warnings):
 *   - Either SPDXID not found in the package index
 *     (can happen if GitHub includes relationships to packages it omitted)
 *   - Self-loops (source === target)
 *   - Duplicate edges (same source+target pair)
 */
function extractEdges(relationships, packageIndex) {
  const links   = [];
  const seen    = new Set(); // deduplication key: "source||target"
  let skipped   = 0;

  for (const rel of relationships) {
    // Only process dependency edges
    if (rel.relationshipType !== "DEPENDS_ON") continue;

    const sourceId = rel.spdxElementId;
    const targetId = rel.relatedSpdxElement;

    // Resolve SPDXID → human-readable node ID
    const source = packageIndex.get(sourceId);
    const target = packageIndex.get(targetId);

    if (!source) {
      console.warn(`[WARN] Source SPDXID not in package index — skipping: ${sourceId}`);
      skipped++;
      continue;
    }
    if (!target) {
      console.warn(`[WARN] Target SPDXID not in package index — skipping: ${targetId}`);
      skipped++;
      continue;
    }

    // Drop self-loops
    if (source === target) {
      skipped++;
      continue;
    }

    // Deduplicate
    const key = `${source}||${target}`;
    if (seen.has(key)) {
      skipped++;
      continue;
    }

    seen.add(key);
    links.push({ source, target });
  }

  if (skipped > 0) {
    console.log(`[INFO] Skipped ${skipped} relationships (non-DEPENDS_ON / unresolved / duplicate / self-loop).`);
  }
  console.log(`[INFO] Edges extracted — ${links.length} unique dependency links.`);
  return links;
}

// ---------------------------------------------------------------------------
// Step 4 — Build the nodes array
// ---------------------------------------------------------------------------

/**
 * Collects every node ID that appears as source or target in at least one edge.
 *
 * Why not just use all packages?
 *   The SBOM contains 611 entries including the root repo document package.
 *   Some packages may have zero relationships (isolated nodes) which add visual
 *   clutter to an arc diagram without contributing graph structure.
 *   Only connected nodes are included.
 *
 * Returns an array of objects: [ { "id": "name@version" }, ... ]
 */
function buildNodes(links) {
  const nodeIds = new Set();

  for (const link of links) {
    nodeIds.add(link.source);
    nodeIds.add(link.target);
  }

  const nodes = Array.from(nodeIds).map((id) => ({ id }));
  console.log(`[INFO] Nodes collected — ${nodes.length} connected packages.`);
  return nodes;
}

// ---------------------------------------------------------------------------
// Step 5 — Assemble and save the graph
// ---------------------------------------------------------------------------

/**
 * Assembles the final D3-compatible graph object and writes it to disk.
 *
 * Output format:
 *   {
 *     "nodes": [ { "id": "name@version" }, ... ],
 *     "links": [ { "source": "...", "target": "..." }, ... ]
 *   }
 */
function saveGraph(nodes, links, outputPath) {
  const graph = { nodes, links };

  const resolved = path.resolve(outputPath);
  fs.writeFileSync(resolved, JSON.stringify(graph, null, 2), "utf-8");
  console.log(`[INFO] Graph saved to: ${resolved}`);
  return graph;
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

function printSummary(nodes, links) {
  // Count in-degree (how many packages depend on each node)
  const inDegree = {};
  for (const link of links) {
    inDegree[link.target] = (inDegree[link.target] || 0) + 1;
  }

  // Top 5 most depended-upon packages
  const top5 = Object.entries(inDegree)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  console.log("\n========== Graph Summary ==========");
  console.log(`  Total nodes (packages) : ${nodes.length}`);
  console.log(`  Total links (edges)    : ${links.length}`);
  console.log("\n  Top 5 most depended-upon packages:");
  top5.forEach(([id, count]) => {
    console.log(`    [${count} dependents] ${id}`);
  });
  console.log("====================================\n");
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function main() {
  // 1. Load SBOM
  const sbom = loadSbom(INPUT_PATH);

  // 2. Build SPDXID → "name@version" lookup
  const packageIndex = buildPackageIndex(sbom.packages);

  // 3. Extract directed edges (DEPENDS_ON only)
  const links = extractEdges(sbom.relationships, packageIndex);

  // 4. Collect connected nodes
  const nodes = buildNodes(links);

  // 5. Save graph.json
  saveGraph(nodes, links, OUTPUT_PATH);

  // 6. Print summary
  printSummary(nodes, links);

  console.log("[INFO] Done. graph.json is ready for D3 visualization.");
}

try {
  main();
} catch (err) {
  console.error(`[ERROR] ${err.message}`);
  process.exit(1);
}
