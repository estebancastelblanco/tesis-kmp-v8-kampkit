#!/usr/bin/env node
/**
 * get_diff.js
 * ===========
 * Step 1 of the CI pipeline.
 *
 * Calls the GitHub Dependency Graph Comparison API to find exactly which
 * packages were added, removed, or updated between the base commit (main)
 * and the head commit (the PR branch).
 *
 * ----------------------------------------------------------------------------
 * GitHub API used
 * ----------------------------------------------------------------------------
 *
 *   GET /repos/{owner}/{repo}/dependency-graph/compare/{basehead}
 *
 *   where basehead = "{base_sha}...{head_sha}"
 *
 * Each item in the response array has:
 *   change_type  : "added" | "removed"
 *   name         : Maven group:artifact  (e.g. "org.jetbrains.kotlin:kotlin-stdlib")
 *   version      : resolved version string (e.g. "1.9.23")
 *   manifest     : the file that declared it (e.g. "composeApp/build.gradle.kts")
 *   ecosystem    : "Maven", "pip", etc.
 *   package_url  : purl string
 *   vulnerabilities: [] — populated if GitHub Advanced Security is enabled
 *
 * A "version update" (same package, different version) appears as one "removed"
 * entry (old version) + one "added" entry (new version) with the same name.
 * This script detects and collapses those pairs into "updated" entries.
 *
 * ----------------------------------------------------------------------------
 * Output  (DIFF_OUT_PATH, default: pipeline/ci/diff.json)
 * ----------------------------------------------------------------------------
 *
 *   {
 *     "baseSha":      "abc1234...",
 *     "headSha":      "def5678...",
 *     "added":   [ { name, version, manifest, ecosystem, packageUrl } ],
 *     "removed": [ { name, version, manifest, ecosystem, packageUrl } ],
 *     "updated": [ { name, previousVersion, newVersion, manifest, ecosystem } ],
 *     "totalChanges": 3
 *   }
 *
 * ----------------------------------------------------------------------------
 * Environment variables
 * ----------------------------------------------------------------------------
 *   GITHUB_TOKEN   — Personal Access Token or Actions GITHUB_TOKEN
 *   GITHUB_OWNER   — Repository owner
 *   GITHUB_REPO    — Repository name
 *   BASE_SHA       — Base commit SHA (PR base)
 *   HEAD_SHA       — Head commit SHA (PR head)
 *   DIFF_OUT_PATH  — Output file path (default: pipeline/ci/diff.json)
 */

"use strict";

const https = require("https");
const fs    = require("fs");
const path  = require("path");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const GITHUB_OWNER = process.env.GITHUB_OWNER;
const GITHUB_REPO  = process.env.GITHUB_REPO;
const BASE_SHA     = process.env.BASE_SHA;
const HEAD_SHA     = process.env.HEAD_SHA;
const OUT_PATH     = process.env.DIFF_OUT_PATH
  || path.join(__dirname, "diff.json");

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function validate() {
  const required = { GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, BASE_SHA, HEAD_SHA };
  const missing  = Object.entries(required)
    .filter(([, v]) => !v)
    .map(([k]) => k);

  if (missing.length > 0) {
    throw new Error(
      `Missing required environment variables: ${missing.join(", ")}\n` +
      `Set them in the workflow YAML or your local .env file.`
    );
  }
}

// ---------------------------------------------------------------------------
// HTTP helper
// ---------------------------------------------------------------------------

/**
 * Makes a single authenticated GET request to the GitHub API.
 * Returns { status, data, headers }.
 * Throws on network error or invalid JSON.
 */
function httpGet(url) {
  return new Promise((resolve, reject) => {
    const opts = {
      headers: {
        "Authorization":        `Bearer ${GITHUB_TOKEN}`,
        "Accept":               "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent":           "dependency-analysis-pipeline/1.0",
      },
    };

    const req = https.get(url, opts, (res) => {
      let body = "";
      res.on("data", (chunk) => { body += chunk; });
      res.on("end", () => {
        try {
          resolve({
            status:  res.statusCode,
            headers: res.headers,
            data:    JSON.parse(body),
          });
        } catch (e) {
          reject(new Error(
            `Could not parse response JSON.\n` +
            `Status: ${res.statusCode}\n` +
            `Body (first 300 chars): ${body.slice(0, 300)}`
          ));
        }
      });
    });

    req.setTimeout(30_000, () => {
      req.destroy(new Error("Request timed out after 30 s"));
    });

    req.on("error", reject);
  });
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  validate();

  const basehead = `${BASE_SHA}...${HEAD_SHA}`;
  const url = [
    "https://api.github.com",
    "repos", GITHUB_OWNER, GITHUB_REPO,
    "dependency-graph", "compare", basehead,
  ].join("/");

  console.log(`[INFO] Comparing dependencies: ${BASE_SHA.slice(0, 7)} → ${HEAD_SHA.slice(0, 7)}`);
  console.log(`[INFO] GET ${url}`);

  const { status, headers, data } = await httpGet(url);

  // Log rate-limit headroom so CI logs show throttling risk early
  if (headers["x-ratelimit-remaining"]) {
    console.log(
      `[INFO] Rate limit — remaining: ${headers["x-ratelimit-remaining"]}, ` +
      `resets: ${new Date(+headers["x-ratelimit-reset"] * 1000).toISOString()}`
    );
  }

  if (status !== 200) {
    // 404 often means the Dependency Graph feature is not enabled
    const hint = status === 404
      ? "Ensure the Dependency Graph is enabled: Settings → Security → Dependency graph."
      : status === 403
        ? "The GITHUB_TOKEN may lack 'dependency_graph: read' permission."
        : "";
    throw new Error(
      `API returned HTTP ${status}.\n${hint}\nResponse: ${JSON.stringify(data).slice(0, 300)}`
    );
  }

  // data is an array of change objects
  const changes = Array.isArray(data) ? data : [];

  const rawAdded   = changes.filter((c) => c.change_type === "added");
  const rawRemoved = changes.filter((c) => c.change_type === "removed");

  // Detect version updates: same name appears in both added and removed.
  // Collapse them into a single "updated" entry.
  const removedByName = new Map(rawRemoved.map((c) => [c.name, c]));
  const addedByName   = new Map(rawAdded.map((c) => [c.name, c]));

  const updated      = [];
  const trulyAdded   = [];
  const trulyRemoved = [];

  for (const dep of rawAdded) {
    if (removedByName.has(dep.name)) {
      const old = removedByName.get(dep.name);
      updated.push({
        name:            dep.name,
        previousVersion: old.version,
        newVersion:      dep.version,
        manifest:        dep.manifest || old.manifest,
        ecosystem:       dep.ecosystem,
        packageUrl:      dep.package_url,
      });
    } else {
      trulyAdded.push(normalise(dep));
    }
  }

  for (const dep of rawRemoved) {
    if (!addedByName.has(dep.name)) {
      trulyRemoved.push(normalise(dep));
    }
  }

  const diff = {
    baseSha:      BASE_SHA,
    headSha:      HEAD_SHA,
    added:        trulyAdded,
    removed:      trulyRemoved,
    updated,
    totalChanges: trulyAdded.length + trulyRemoved.length + updated.length,
  };

  fs.writeFileSync(OUT_PATH, JSON.stringify(diff, null, 2), "utf-8");

  console.log(
    `[INFO] Diff saved to: ${path.resolve(OUT_PATH)}\n` +
    `[INFO]   ➕ Added:   ${trulyAdded.length}\n` +
    `[INFO]   ➖ Removed: ${trulyRemoved.length}\n` +
    `[INFO]   ⬆️  Updated: ${updated.length}\n` +
    `[INFO]   Total:    ${diff.totalChanges}`
  );

  if (diff.totalChanges === 0) {
    console.log("[INFO] No dependency changes detected in this PR.");
  }
}

// Normalise a raw API change object to the fields we care about
function normalise(dep) {
  return {
    name:       dep.name,
    version:    dep.version,
    manifest:   dep.manifest,
    ecosystem:  dep.ecosystem,
    packageUrl: dep.package_url,
  };
}

main().catch((err) => {
  console.error(`[ERROR] ${err.message}`);
  process.exit(1);
});
