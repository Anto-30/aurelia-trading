#!/usr/bin/env bash
# Non-destructive provisioning of protected Deriv secrets into GitHub Actions.
# Run on a trusted device where gh is authenticated with production environment-secret write permission.
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

# Query names only; GitHub does not return secret values. Existing names will never be overwritten.
names="$(gh secret list --env "$environment" --repo "$repo" --json name --jq '.[].name' 2>/dev/null)" \
  || fail "GITHUB_SECRET_NAME_LIST_FAILED"

has_secret() {
  printf '%s\n' "$names" | grep -Fxq "$1"
}

set_secret_if_missing() {
  local name="$1"
  local value="$2"
  if has_secret "$name"; then
    printf 'PRESERVED_EXISTING_SECRET_NAME=%s\n' "$name"
    return 0
  fi
  [[ -n "$value" ]] || fail "REQUIRED_VALUE_MISSING_$name"
  # Secret contents are passed on stdin; they are not placed in process arguments.
  printf '%s' "$value" | gh secret set "$name" --env "$environment" --repo "$repo" >/dev/null \
    || fail "GITHUB_SECRET_WRITE_FAILED_$name"
  printf 'CONFIGURED_SECRET_NAME=%s\n' "$name"
}

choose_value() {
  local current="$1"
  local prompt="$2"
  local value="$3"
  if [[ -n "$current" ]]; then
    REPLY="$current"
    return 0
  fi
  read -r -s -p "$prompt" REPLY </dev/tty
  printf '\n'
  [[ -n "$REPLY" ]] || fail "INPUT_REQUIRED"
}

mode="${DERIV_AUTH_MODE:-}"
if [[ -z "$mode" ]]; then
  read -r -p "Deriv auth mode to use for this setup [pat/oauth; default pat]: " mode </dev/tty
  mode="${mode:-pat}"
fi
mode="$(printf '%s' "$mode" | tr '[:upper:]' '[:lower:]')"
[[ "$mode" == "pat" || "$mode" == "oauth" ]] || fail "INVALID_AUTH_MODE"

# Preserve either configured token alias. Only ask for/store a token if neither exists.
token_name="DERIV_AUTH_TOKEN"
if has_secret "DERIV_AUTH_TOKEN"; then
  printf 'PRESERVED_EXISTING_SECRET_NAME=DERIV_AUTH_TOKEN\n'
  token=""
elif has_secret "DERIV_PAT"; then
  printf 'PRESERVED_EXISTING_SECRET_NAME=DERIV_PAT\n'
  token=""
else
  token="${DERIV_AUTH_TOKEN:-${DERIV_PAT:-}}"
  if [[ -z "$token" ]]; then
    read -r -s -p "Enter the intended Deriv token/PAT (hidden input): " token </dev/tty
    printf '\n'
  fi
  [[ -n "$token" ]] || fail "DERIV_TOKEN_MISSING"
  set_secret_if_missing "$token_name" "$token"
fi

# For PAT auth an App ID is required. Never overwrite an already configured App ID.
if [[ "$mode" == "pat" ]]; then
  app_id="${DERIV_APP_ID:-}"
  if has_secret "DERIV_APP_ID"; then
    printf 'PRESERVED_EXISTING_SECRET_NAME=DERIV_APP_ID\n'
  else
    if [[ -z "$app_id" ]]; then
      read -r -s -p "Enter the matching Deriv App ID (hidden input): " app_id </dev/tty
      printf '\n'
    fi
    set_secret_if_missing "DERIV_APP_ID" "$app_id"
  fi
fi

# Preserve either expected-account alias, and only create a canonical value if neither exists.
if has_secret "DERIV_EXPECTED_LOGINID"; then
  printf 'PRESERVED_EXISTING_SECRET_NAME=DERIV_EXPECTED_LOGINID\n'
elif has_secret "DERIV_AUTHORIZED_ACCOUNT_ID"; then
  printf 'PRESERVED_EXISTING_SECRET_NAME=DERIV_AUTHORIZED_ACCOUNT_ID\n'
else
  loginid="${DERIV_EXPECTED_LOGINID:-${DERIV_AUTHORIZED_ACCOUNT_ID:-}}"
  if [[ -z "$loginid" ]]; then
    read -r -s -p "Enter the exact authorized Deriv login ID (hidden input): " loginid </dev/tty
    printf '\n'
  fi
  set_secret_if_missing "DERIV_EXPECTED_LOGINID" "$loginid"
fi

currency="${DERIV_EXPECTED_CURRENCY:-USD}"
[[ "$currency" == "USD" ]] || fail "UNEXPECTED_CURRENCY_FOR_THIS_CONFIGURATION"
set_secret_if_missing "DERIV_EXPECTED_CURRENCY" "$currency"

# Authentication mode is configuration, not a credential. Store it as an environment variable.
printf '%s' "$mode" | gh variable set DERIV_AUTH_MODE --env "$environment" --repo "$repo" >/dev/null \
  || fail "GITHUB_VARIABLE_WRITE_FAILED_DERIV_AUTH_MODE"
printf 'CONFIGURED_VARIABLE_NAME=%s\n' "DERIV_AUTH_MODE"

# Verify presence of either supported token and account aliases, plus currency/mode.
names="$(gh secret list --env "$environment" --repo "$repo" --json name --jq '.[].name' 2>/dev/null)" \
  || fail "GITHUB_SECRET_NAME_VERIFICATION_FAILED"
has_secret "DERIV_AUTH_TOKEN" || has_secret "DERIV_PAT" || fail "TOKEN_SECRET_NAME_NOT_VISIBLE"
has_secret "DERIV_EXPECTED_LOGINID" || has_secret "DERIV_AUTHORIZED_ACCOUNT_ID" || fail "ACCOUNT_SECRET_NAME_NOT_VISIBLE"
has_secret DERIV_EXPECTED_CURRENCY || fail "SECRET_NAME_NOT_VISIBLE_DERIV_EXPECTED_CURRENCY"
variables="$(gh variable list --env "$environment" --repo "$repo" --json name --jq '.[].name' 2>/dev/null)" \
  || fail "GITHUB_VARIABLE_NAME_VERIFICATION_FAILED"
printf '%s\n' "$variables" | grep -Fxq "DERIV_AUTH_MODE" \
  || fail "VARIABLE_NAME_NOT_VISIBLE_DERIV_AUTH_MODE"
if [[ "$mode" == "pat" ]]; then
  has_secret "DERIV_APP_ID" || fail "SECRET_NAME_NOT_VISIBLE_DERIV_APP_ID"
fi

unset token app_id loginid
printf 'DERIV_SECRET_PROVISIONING=COMPLETE\n'
printf 'SECRET_VALUES_PRINTED=false\n'
printf 'EXISTING_SECRET_VALUES_OVERWRITTEN=false\n'
printf 'LIVE_EXECUTION=BLOCKED\n'
printf 'FINAL_EXECUTION_AUTHORIZATION=false\n'
