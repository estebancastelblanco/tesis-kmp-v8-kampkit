#!/usr/bin/env python3
"""
fetch_sbom.py
=============
Retrieves the SPDX 2.3 SBOM from a GitHub repository via the
Dependency Graph REST API and saves it locally as sbom.json.

Required environment variables:
  GITHUB_TOKEN  — Personal Access Token
                  Classic PAT:       'repo' scope (private repos) or no scope (public)
                  Fine-grained PAT:  'dependency_graph: read' permission
  GITHUB_OWNER  — Repository owner  (e.g. Sreys54)
  GITHUB_REPO   — Repository name   (e.g. CursoKmpApp-GitGraph)

Optional environment variables:
  SBOM_OUTPUT_PATH — Output file path (default: sbom.json)

Usage:
  export GITHUB_TOKEN="ghp_..."
  export GITHUB_OWNER="Sreys54"
  export GITHUB_REPO="CursoKmpApp-GitGraph"
  python fetch_sbom.py
"""

import os
import json
import sys
import requests


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API_BASE  = "https://api.github.com"
API_VERSION      = "2022-11-28"
DEFAULT_OUTPUT   = "sbom.json"
REQUEST_TIMEOUT  = 30  # seconds


# ---------------------------------------------------------------------------
# Configuration — sourced exclusively from environment variables
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """
    Read required credentials from the environment.
    Exits immediately with a descriptive message if any variable is missing.
    """
    required = ("GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO")
    missing  = [k for k in required if not os.environ.get(k)]

    if missing:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        print("[ERROR] Set them with: export VARIABLE_NAME='value'", file=sys.stderr)
        sys.exit(1)

    return {
        "token":       os.environ["GITHUB_TOKEN"],
        "owner":       os.environ["GITHUB_OWNER"],
        "repo":        os.environ["GITHUB_REPO"],
        "output_path": os.environ.get("SBOM_OUTPUT_PATH", DEFAULT_OUTPUT),
    }


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def build_headers(token: str) -> dict:
    """
    Build the three headers required by every GitHub REST API call:
      - Authorization : authenticates the request
      - Accept        : requests the GitHub JSON response format
      - X-GitHub-Api-Version : pins the API version for stability
    """
    return {
        "Authorization":       f"Bearer {token}",
        "Accept":              "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }


def log_rate_limit(headers: dict) -> None:
    """Log rate-limit headers so we can detect throttling in CI logs."""
    remaining = headers.get("X-RateLimit-Remaining", "unknown")
    reset_ts  = headers.get("X-RateLimit-Reset",     "unknown")
    print(f"[INFO] Rate limit — remaining: {remaining}, resets at unix ts: {reset_ts}")


# ---------------------------------------------------------------------------
# SBOM retrieval
# ---------------------------------------------------------------------------

def fetch_sbom(owner: str, repo: str, token: str) -> dict:
    """
    Call GET /repos/{owner}/{repo}/dependency-graph/sbom.

    Returns the parsed JSON response (top-level key is 'sbom').
    Raises RuntimeError on any non-200 response or unexpected response shape.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/dependency-graph/sbom"
    print(f"[INFO] Fetching SBOM from: {url}")

    try:
        response = requests.get(url, headers=build_headers(token), timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Network error while calling GitHub API: {exc}") from exc

    log_rate_limit(response.headers)

    if response.status_code == 403:
        raise RuntimeError(
            "HTTP 403 Forbidden — check that your token has the correct scopes "
            "and that the Dependency Graph is enabled for this repository."
        )
    if response.status_code == 404:
        raise RuntimeError(
            "HTTP 404 Not Found — verify GITHUB_OWNER and GITHUB_REPO are correct "
            "and that the Dependency Graph feature is enabled under Insights → Dependency graph."
        )
    if response.status_code != 200:
        raise RuntimeError(f"GitHub API returned HTTP {response.status_code}: {response.text}")

    data = response.json()

    if "sbom" not in data:
        raise RuntimeError(f"Unexpected API response shape — 'sbom' key not found. Got: {list(data.keys())}")

    return data


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_sbom(data: dict, output_path: str) -> None:
    """
    Write the full API response to disk as pretty-printed JSON.
    The file includes the top-level 'sbom' wrapper so the raw API
    response is preserved exactly.
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[INFO] SBOM saved to '{output_path}'")


# ---------------------------------------------------------------------------
# Human-readable summary
# ---------------------------------------------------------------------------

def print_summary(data: dict) -> None:
    """
    Print a quick summary of the SBOM to stdout.
    Useful for verifying the fetch worked correctly in CI logs.
    """
    sbom     = data["sbom"]
    packages = sbom.get("packages", [])

    print("\n========== SBOM Summary ==========")
    print(f"  SPDX Version   : {sbom.get('spdxVersion', 'N/A')}")
    print(f"  Document name  : {sbom.get('name', 'N/A')}")
    print(f"  Created        : {sbom.get('creationInfo', {}).get('created', 'N/A')}")
    print(f"  Total packages : {len(packages)}")

    if packages:
        print("\n  Sample (first 8 packages):")
        for pkg in packages[:8]:
            name    = pkg.get("name", "unknown")
            version = pkg.get("versionInfo", "?")
            print(f"    - {name} @ {version}")
    print("===================================\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    config = load_config()

    sbom_data = fetch_sbom(
        owner=config["owner"],
        repo=config["repo"],
        token=config["token"],
    )

    save_sbom(sbom_data, output_path=config["output_path"])
    print_summary(sbom_data)
    print("[INFO] Done.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as err:
        print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)
