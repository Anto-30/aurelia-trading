#!/usr/bin/env bash
# Securely provision protected Deriv secrets into GitHub Actions environment.
# Run locally on a trusted device with gh authenticated to the target repository.
set -euo pipefail
set +x
umask 077

readonly repo="Anto-30/aurelia-trading"
readonly environment="production"

fail() {
  printf 'DERIV_SECRET_PROVISIONING=BLOCKED\nREASON=%s\n' "$1" >&2
  exit 2
}

command -v gh >/dev/null 2>&1 || fail "GITHUB_CLI_NOT_INSTALLED"
gh auth status --hostname github.com >/dev/null 2>&1 || fail "GITHUB_CLI_NOT_AUTHENTICATED"

actual_repo="$(gh repo view "$repo" --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
[[ "$actual_repo" == "$repo" ]] || fail "REPOSITORY_ACCESS_NOT_VERIFIED"

gh api "repos/$repo/environments/$environment" >/dev/null 2>&1 || fail "PRODUCTION_ENVIRONMENT_NOT_ACCESSIBLE"

mode="${DERIV_AUTH_MODE:-}"
if [[ -z "$mode" ]]; then
  read -r -p "Deriv auth mode [pat/oauth; default pat]: " mode </dev/tty
  mode="${mode:-pat}"
fi
mode="$(printf '%s' "$mode" | tr '[:upper:]' '[:lower:]')"
[[ "$mode" == "pat" || "$mode" == "oauth" ]] || fail "INVALID_AUTH_MODE"

token="${DERIV_AUTH_TOKEN:-${DERIV_PAT:-}}"
if [[ -z "$token" ]]; then
  read -r -s -p "Enter the intended Deriv token/PAT (hidden input): " token </dev/tty
  printf '\n'
fi
[[ -n "$token" ]] || fail "DERIV_TOKEN_MISSING"

app_id="${DERIV_APP_ID:-}"
if [[ "$mode" == "pat" && -z "$app_id" ]]; then
  read -r -s -p "Enter the matching Deriv App ID (hidden input): " app_id </dev/tty
  printf '\n'
fi
if [[ "$mode" == "pat" ]]; then
  [[ -n "$app_id" ]] || fail "DERIV_APP_ID_REQUIRED_FOR_PAT"
fi

loginid="${DERIV_EXPECTED_LOGINID:-${DERIV_AUTHORIZED_ACCOUNT_ID:-}}"
if [[ -z "$loginid" ]]; then
  read -r -s -p "Enter the exact authorized Deriv login ID (hidden input): " loginid </dev/tty
  printf '\n'
fi
[[ -n "$loginid" ]] || fail "DERIV_EXPECTED_LOGINID_MISSING"

currency="${DERIV_EXPECTED_CURRENCY:-USD}"
[[ "$currency" == "USD" ]] || fail "UNEXPECTED_CURRENCY_FOR_THIS_CONFIGURATION"

set_secret() {
  local name="$1"
  local value="$2"
  # The value is delivered through stdin; it is not put in process arguments.
  printf '%s' "$value" | gh secret set "$name" --env "$environment" --repo "$repo" >/dev/null \
    || fail "GITHUB_SECRET_WRITE_FAILED_$name"
  printf 'CONFIGURED_SECRET_NAME=%s\n' "$name"
}

set_secret "DERIV_AUTH_TOKEN" "$token"
if [[ "$mode" == "pat" ]]; then
  set_secret "DERIV_APP_ID" "$app_id"
fi
set_secret "DERIV_EXPECTED_LOGINID" "$loginid"
set_secret "DERIV_EXPECTED_CURRENCY" "$currency"
set_secret "DERIV_AUTH_MODE" "$mode"

# Verify names only. GitHub never returns secret values from list endpoints.
names="$(gh secret list --env "$environment" --repo "$repo" --json name --jq '.[].name' 2>/dev/null)" \
  || fail "GITHUB_SECRET_NAME_VERIFICATION_FAILED"
for name in DERIV_AUTH_TOKEN DERIV_EXPECTED_LOGINID DERIV_EXPECTED_CURRENCY DERIV_AUTH_MODE; do
  printf '%s\n' "$names" | grep -Fxq "$name" || fail "SECRET_NAME_NOT_VISIBLE_$name"
done
if [[ "$mode" == "pat" ]]; then
  printf '%s\n' "$names" | grep -Fxq "DERIV_APP_ID" || fail "SECRET_NAME_NOT_VISIBLE_DERIV_APP_ID"
fi

unset token app_id loginid
printf 'DERIV_SECRET_PROVISIONING=COMPLETE\n'
printf 'SECRET_VALUES_PRINTED=false\n'
printf 'LIVE_EXECUTION=BLOCKED\n'
printf 'FINAL_EXECUTION_AUTHORIZATION=false\n'
