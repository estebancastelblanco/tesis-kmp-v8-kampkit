#!/usr/bin/env node
/**
 * fetch_sbom.js
 * =============
 * Retrieves the SPDX 2.3 SBOM from a GitHub repository via the
 * Dependency Graph REST API and saves it locally as sbom.json.
 *
 * Uses only Node.js built-in modules (https, fs) — no npm install required.
 *
 * Required environment variables:
 *   GITHUB_TOKEN  — Personal Access Token
 *   GITHUB_OWNER  — Repository owner (e.g. Sreys54)
 *   GITHUB_REPO   — Repository name  (e.g. CursoKmpApp-GitGraph)
 *
 * Optional environment variables:
 *   SBOM_OUTPUT_PATH — Output file path (default: sbom.json)
 *
 * Usage:
 *   export GITHUB_TOKEN="ghp_..."
 *   export GITHUB_OWNER="Sreys54"
 *   export GITHUB_REPO="CursoKmpApp-GitGraph"
 *   node fetch_sbom.js
 */

"use strict";

const fs    = require("fs");
const https = require("https");

const GITHUB_API_BASE = "https://api.github.com";
const API_VERSION     = "2022-11-28";
const DEFAULT_OUTPUT  = "sbom.json";

// ---------------------------------------------------------------------------
// Configuration — sourced exclusively from environment variables
// ---------------------------------------------------------------------------

/**
 * Reads required credentials from the environment.
 * Exits immediately with a descriptive message if any variable is missing.
 */
function loadConfig() {
  const required = ["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO"];
  const missing  = required.filter((k) => !process.env[k]);

  if (missing.length > 0) {
    console.error(`[ERROR] Missing required environment variables: ${missing.join(", ")}`);
    console.error(`[ERROR] Set them with: export VARIABLE_NAME='value'`);
    process.exit(1);
  }

  return {
    token:      process.env.GITHUB_TOKEN,
    owner:      process.env.GITHUB_OWNER,
    repo:       process.env.GITHUB_REPO,
    outputPath: process.env.SBOM_OUTPUT_PATH ?? DEFAULT_OUTPUT,
  };
}

// ---------------------------------------------------------------------------
// HTTP layer (native https — zero dependencies)
// ---------------------------------------------------------------------------

/**
 * Performs a GET request and returns a promise resolving to
 * { status, headers, body } where body is a raw string.
 */
function httpGet(url, headers) {
  return new Promise((resolve, reject) => {
    const options = {
      headers: {
        // GitHub requires a User-Agent header on all API requests
        "User-Agent": "sbom-fetcher-node/1.0",
        ...headers,
      },
    };

    const req = https.get(url, options, (res) => {
      let body = "";
      res.on("data",  (chunk) => { body += chunk; });
      res.on("end",   ()      => resolve({ status: res.statusCode, headers: res.headers, body }));
      res.on("error", reject);
    });

    req.on("error", reject);
    req.setTimeout(30_000, () => {
      req.destroy();
      reject(new Error("Request timed out after 30s"));
    });
  });
}

// ---------------------------------------------------------------------------
// Rate-limit logging
// ---------------------------------------------------------------------------

function logRateLimit(headers) {
  const remaining = headers["x-ratelimit-remaining"] ?? "unknown";
  const reset     = headers["x-ratelimit-reset"]     ?? "unknown";
  console.log(`[INFO] Rate limit — remaining: ${remaining}, resets at unix ts: ${reset}`);
}

// ---------------------------------------------------------------------------
// SBOM retrieval
// ---------------------------------------------------------------------------

/**
 * Calls GET /repos/{owner}/{repo}/dependency-graph/sbom.
 * Returns the parsed JSON object. Throws on non-200 or bad shape.
 */
async function fetchSbom(owner, repo, token) {
  const url = `${GITHUB_API_BASE}/repos/${owner}/${repo}/dependency-graph/sbom`;
  console.log(`[INFO] Fetching SBOM from: ${url}`);

  const { status, headers, body } = await httpGet(url, {
    Authorization:          `Bearer ${token}`,
    Accept:                 "application/vnd.github+json",
    "X-GitHub-Api-Version": API_VERSION,
  });

  logRateLimit(headers);

  if (status === 403) {
    throw new Error(
      "HTTP 403 Forbidden — check that your token has the correct scopes " +
      "and that the Dependency Graph is enabled for this repository."
    );
  }
  if (status === 404) {
    throw new Error(
      "HTTP 404 Not Found — verify GITHUB_OWNER and GITHUB_REPO are correct " +
      "and that the Dependency Graph is enabled under Insights → Dependency graph."
    );
  }
  if (status !== 200) {
    throw new Error(`GitHub API returned HTTP ${status}: ${body}`);
  }

  const data = JSON.parse(body);

  if (!data.sbom) {
    throw new Error(
      `Unexpected API response shape — 'sbom' key not found. Got keys: ${Object.keys(data).join(", ")}`
    );
  }

  return data;
}

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

/**
 * Writes the full API response to disk as pretty-printed JSON.
 * Preserves the top-level 'sbom' wrapper so the raw response is kept intact.
 */
function saveSbom(data, outputPath) {
  fs.writeFileSync(outputPath, JSON.stringify(data, null, 2), "utf-8");
  console.log(`[INFO] SBOM saved to '${outputPath}'`);
}

// ---------------------------------------------------------------------------
// Human-readable summary
// ---------------------------------------------------------------------------

function printSummary(data) {
  const sbom     = data.sbom;
  const packages = sbom.packages ?? [];

  console.log("\n========== SBOM Summary ==========");
  console.log(`  SPDX Version   : ${sbom.spdxVersion ?? "N/A"}`);
  console.log(`  Document name  : ${sbom.name ?? "N/A"}`);
  console.log(`  Created        : ${sbom.creationInfo?.created ?? "N/A"}`);
  console.log(`  Total packages : ${packages.length}`);

  if (packages.length > 0) {
    console.log("\n  Sample (first 8 packages):");
    packages.slice(0, 8).forEach((pkg) => {
      console.log(`    - ${pkg.name ?? "?"} @ ${pkg.versionInfo ?? "?"}`);
    });
  }
  console.log("===================================\n");
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function main() {
  const config = loadConfig();

  const sbomData = await fetchSbom(config.owner, config.repo, config.token);
  saveSbom(sbomData, config.outputPath);
  printSummary(sbomData);
  console.log("[INFO] Done.");
}

main().catch((err) => {
  console.error(`[ERROR] ${err.message}`);
  process.exit(1);
});
