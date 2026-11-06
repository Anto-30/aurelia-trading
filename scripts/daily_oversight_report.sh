#!/usr/bin/env bash
# Generate a read-only, evidence-linked AURELIA daily oversight report.
# Requires gh CLI authenticated with read-only repository access and jq.
set -euo pipefail

REPO="${GITHUB_REPOSITORY:-Anto-30/aurelia-trading}"
OUTPUT="${1:-daily_oversight_$(date -u +%Y%m%d).md}"
DATE_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SOURCE_SHA="$(git rev-parse HEAD 2>/dev/null || printf 'UNKNOWN')"

command -v gh >/dev/null 2>&1 || { echo "OVERSIGHT_BLOCKED=GH_CLI_MISSING" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "OVERSIGHT_BLOCKED=JQ_MISSING" >&2; exit 2; }
test -n "${GH_TOKEN:-}${GITHUB_TOKEN:-}" || {
  echo "OVERSIGHT_BLOCKED=GITHUB_TOKEN_MISSING" >&2
  exit 2
}

mkdir -p "$(dirname "$OUTPUT")"
{
  echo "# AURELIA Daily Oversight Report"
  echo
  echo "**Date:** $DATE_UTC"
  echo "**Repository:** $REPO"
  echo "**Source commit:** $SOURCE_SHA"
  echo "**Governance:** LIVE_EXECUTION=BLOCKED | FINAL_EXECUTION_AUTHORIZATION=false"
  echo
  echo "## 1. Governance and release lock"
  echo
  if test -f config/LIVE_LOCK.yaml; then
    echo '~~~yaml'
    grep -E '^(live_trading_enabled|FINAL_EXECUTION_AUTHORIZATION|LIVE_EXECUTION|capital_plane_mode|research_capital_authority):' config/LIVE_LOCK.yaml || true
    echo '~~~'
  else
    echo "**LOCK FILE MISSING** — do not infer an enabled state."
  fi
  echo
  echo "## 2. Pull request stack"
  echo
  echo "| PR | Title | State | Draft | Review decision | Mergeable | Updated (UTC) |"
  echo "|---:|---|---|---|---|---|---|"
  for pr in 279 280 281 273 270 254 263 267 276; do
    if data="$(gh pr view "$pr" --repo "$REPO" --json number,title,state,isDraft,mergeable,reviewDecision,updatedAt 2>/dev/null)"; then
      printf '%s\n' "$data" | jq -r '"| #\(.number) | \(.title | gsub("\\|"; "/")) | \(.state) | \(.isDraft) | \(.reviewDecision // "NOT_RECORDED") | \(.mergeable) | \(.updatedAt) |"'
    else
      echo "| #$pr | Not found or not readable | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |"
    fi
  done
  echo
  echo "## 3. Recent GitHub Actions on main"
  echo
  echo "| Workflow | Event | Status | Conclusion | Created (UTC) | Commit |"
  echo "|---|---|---|---|---|---|"
  if runs="$(gh run list --repo "$REPO" --branch main --limit 20 --json workflowName,event,status,conclusion,createdAt,headSha 2>/dev/null)"; then
    printf '%s\n' "$runs" | jq -r '.[] | "| \(.workflowName // .name // "UNKNOWN") | \(.event // "UNKNOWN") | \(.status // "UNKNOWN") | \(.conclusion // "PENDING") | \(.createdAt // "UNKNOWN") | \((.headSha // "UNKNOWN")[0:12]) |"'
  else
    echo "| Unable to retrieve workflow runs | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |"
  fi
  echo
  echo "## 4. Legacy authentication static audit"
  echo
  if test -x scripts/audit_legacy_auth.sh || test -f scripts/audit_legacy_auth.sh; then
    set +e
    audit_output="$(bash scripts/audit_legacy_auth.sh 2>&1)"
    audit_status=$?
    set -e
    echo '~~~text'
    printf '%s\n' "$audit_output"
    echo '~~~'
    if test "$audit_status" -eq 0; then
      echo "**Result:** PASS (static source scan only)."
    else
      echo "**Result:** FAIL or INCOMPLETE; review findings above."
    fi
  else
    echo "**Result:** NOT AVAILABLE — audit script not present in this source revision."
  fi
  echo
  echo "## 5. Production evidence inventory"
  echo
  echo "| Evidence artifact | Presence |"
  echo "|---|---|"
  for name in broker_lifecycle.json recovery_matrix.json soak_3600s.json prospective_oos.json calibration.json execution_economics.json security_audit.json deployment.json strategy_eligibility.json; do
    if test -s "evidence/$name"; then state="PRESENT — CONTENT REQUIRES VALIDATION"; else state="MISSING"; fi
    echo "| evidence/$name | $state |"
  done
  echo
  echo "## 6. R_100 research inputs"
  echo
  echo "| Input | Presence |"
  echo "|---|---|"
  for path in data/raw/r100_1m.csv data/frozen/r100_dual_resolution_manifest.json config/costs.yaml; do
    if test -s "$path"; then state="PRESENT — PROVENANCE/CONTENT NOT VERIFIED BY THIS REPORT"; else state="MISSING"; fi
    echo "| $path | $state |"
  done
  echo
  echo "## 7. Strategy campaign disposition"
  echo
  seal="research/campaigns/SEALED_$(date -u +%Y%m%d)/CAMPAIGN_SEAL.md"
  if test -s "$seal"; then
    echo "Campaign seal present at $seal. Read the complete seal before interpreting strategy eligibility."
  elif test -s "research/campaigns/SEALED_20261106/CAMPAIGN_SEAL.md"; then
    echo "Campaign seal present at research/campaigns/SEALED_20261106/CAMPAIGN_SEAL.md. Read the complete seal before interpreting strategy eligibility."
  else
    echo "No campaign seal found in this checked-out revision."
  fi
  echo
  echo "## 8. Scope, limitations and next action"
  echo
  echo "- This report uses the checked-out commit, repository PR metadata, and recent Actions metadata."
  echo "- It does not read GitHub Actions secret values, Deriv credentials, account balances, or broker sessions."
  echo "- Artifact presence does not establish validity; each artifact requires source binding, freshness, signature and schema checks."
  echo "- A green workflow run is not a production release or proof of persistent runtime health."
  echo "- A PR with no human review remains unapproved regardless of AI or CI results."
  echo "- No broker orders, proposals, capital operations, secret rotations, deployments or LIVE_LOCK changes are performed by this report."
  echo
  echo "**Required governance state:** LIVE_EXECUTION=BLOCKED, FINAL_EXECUTION_AUTHORIZATION=false, capital_plane_mode=VERIFY_ONLY."
} > "$OUTPUT"

echo "OVERSIGHT_REPORT=$OUTPUT"
echo "OVERSIGHT_SOURCE_SHA=$SOURCE_SHA"
