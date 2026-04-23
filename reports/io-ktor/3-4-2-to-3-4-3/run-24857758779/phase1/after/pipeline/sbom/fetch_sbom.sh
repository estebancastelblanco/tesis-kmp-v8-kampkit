#!/usr/bin/env bash
# =============================================================================
# fetch_sbom.sh
# =============================================================================
# Retrieves the SPDX 2.3 SBOM from a GitHub repository via the REST API
# and saves it locally as sbom.json.
#
# Required environment variables:
#   GITHUB_TOKEN  — Personal Access Token
#   GITHUB_OWNER  — Repository owner (e.g. Sreys54)
#   GITHUB_REPO   — Repository name  (e.g. CursoKmpApp-GitGraph)
#
# Optional environment variables:
#   SBOM_OUTPUT_PATH — Output file path (default: sbom.json)
#
# Usage:
#   export GITHUB_TOKEN="ghp_..."
#   export GITHUB_OWNER="Sreys54"
#   export GITHUB_REPO="CursoKmpApp-GitGraph"
#   bash fetch_sbom.sh
# =============================================================================

set -euo pipefail  # Exit on error, unset variable, or pipe failure

# ---------------------------------------------------------------------------
# Validate required environment variables
# ---------------------------------------------------------------------------
for var in GITHUB_TOKEN GITHUB_OWNER GITHUB_REPO; do
  if [ -z "${!var:-}" ]; then
    echo "[ERROR] Required environment variable '${var}' is not set." >&2
    echo "[ERROR] Set it with: export ${var}='value'" >&2
    exit 1
  fi
done

OUTPUT_FILE="${SBOM_OUTPUT_PATH:-sbom.json}"
ENDPOINT="https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/dependency-graph/sbom"

echo "[INFO] Fetching SBOM from: ${ENDPOINT}"

# ---------------------------------------------------------------------------
# Make the API call
# --silent        : suppress progress meter
# --show-error    : but still show errors
# --fail          : exit non-zero on HTTP errors (4xx/5xx)
# --write-out     : capture HTTP status code separately
# --output        : save body to file
# ---------------------------------------------------------------------------
HTTP_STATUS=$(curl \
  --silent \
  --show-error \
  --write-out "%{http_code}" \
  --output "${OUTPUT_FILE}" \
  --header "Authorization: Bearer ${GITHUB_TOKEN}" \
  --header "Accept: application/vnd.github+json" \
  --header "X-GitHub-Api-Version: 2022-11-28" \
  "${ENDPOINT}")

# ---------------------------------------------------------------------------
# Check HTTP response code
# ---------------------------------------------------------------------------
if [ "${HTTP_STATUS}" -eq 403 ]; then
  echo "[ERROR] HTTP 403 Forbidden — check token scopes and that Dependency Graph is enabled." >&2
  rm -f "${OUTPUT_FILE}"
  exit 1
elif [ "${HTTP_STATUS}" -eq 404 ]; then
  echo "[ERROR] HTTP 404 Not Found — verify GITHUB_OWNER and GITHUB_REPO are correct." >&2
  rm -f "${OUTPUT_FILE}"
  exit 1
elif [ "${HTTP_STATUS}" -ne 200 ]; then
  echo "[ERROR] GitHub API returned HTTP ${HTTP_STATUS}." >&2
  cat "${OUTPUT_FILE}" >&2
  rm -f "${OUTPUT_FILE}"
  exit 1
fi

echo "[INFO] SBOM saved to '${OUTPUT_FILE}'"

# ---------------------------------------------------------------------------
# Print a quick summary using python3 (available on most systems)
# ---------------------------------------------------------------------------
if command -v python3 &>/dev/null; then
  python3 - "${OUTPUT_FILE}" <<'EOF'
import json, sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = json.load(f)

sbom     = data.get("sbom", {})
packages = sbom.get("packages", [])

print("\n========== SBOM Summary ==========")
print(f"  SPDX Version   : {sbom.get('spdxVersion', 'N/A')}")
print(f"  Document name  : {sbom.get('name', 'N/A')}")
print(f"  Created        : {sbom.get('creationInfo', {}).get('created', 'N/A')}")
print(f"  Total packages : {len(packages)}")

if packages:
    print("\n  Sample (first 8 packages):")
    for pkg in packages[:8]:
        print(f"    - {pkg.get('name','?')} @ {pkg.get('versionInfo','?')}")
print("===================================")
EOF
fi

echo "[INFO] Done."
