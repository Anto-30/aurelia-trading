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

# Read the existing environment variable value without printing it. Its value
# takes precedence in GitHub Actions, so a mismatched prompt must fail closed.
variables="$(gh variable list --env "$environment" --repo "$repo" --json name --jq '.[].name' 2>/dev/null)" \
  || fail "GITHUB_VARIABLE_LIST_FAILED"

has_variable() {
  printf '%s\n' "$variables" | grep -Fxq "$1"
}

existing_mode=""
if has_variable "DERIV_AUTH_MODE"; then
  existing_mode="$(gh api "repos/$repo/environments/$environment/variables/DERIV_AUTH_MODE" --jq '.value' 2>/dev/null)" \
    || fail "EXISTING_DERIV_AUTH_MODE_READ_FAILED"
  existing_mode="$(printf '%s' "$existing_mode" | tr '[:upper:]' '[:lower:]')"
  [[ "$existing_mode" == "pat" || "$existing_mode" == "oauth" ]] \
    || fail "EXISTING_DERIV_AUTH_MODE_INVALID"
fi

mode="${DERIV_AUTH_MODE:-$existing_mode}"
mode="$(printf '%s' "$mode" | tr '[:upper:]' '[:lower:]')"
if [[ -n "$existing_mode" && -n "$mode" && "$mode" != "$existing_mode" ]]; then
  fail "LOCAL_AUTH_MODE_MISMATCH_WITH_EXISTING_ENVIRONMENT_VARIABLE"
fi
if [[ -z "$mode" ]]; then
  [[ -t 0 ]] || fail "DERIV_AUTH_MODE_REQUIRED_NONINTERACTIVE"
  read -r -p "Deriv auth mode to use [oauth/pat; no default]: " mode </dev/tty || fail "DERIV_AUTH_MODE_REQUIRED"
  [[ -n "$mode" ]] || fail "DERIV_AUTH_MODE_REQUIRED"
  mode="$(printf '%s' "$mode" | tr '[:upper:]' '[:lower:]')"
fi
[[ "$mode" == "pat" || "$mode" == "oauth" ]] || fail "INVALID_AUTH_MODE"

# Currency must be explicitly supplied or already exist as a protected secret.
# Never synthesize USD when the account currency binding is absent.
currency="${DERIV_EXPECTED_CURRENCY:-}"
if [[ -n "$currency" ]]; then
  currency="$(printf '%s' "$currency" | tr '[:lower:]' '[:upper:]')"
  [[ "$currency" == "USD" ]] || fail "UNEXPECTED_CURRENCY_FOR_THIS_CONFIGURATION"
fi
if ! has_secret "DERIV_EXPECTED_CURRENCY"; then
  if [[ -z "$currency" ]]; then
    if ! read -r -p "Enter the exact Deriv Options account currency (currently supported: USD): " currency </dev/tty; then
      fail "DERIV_EXPECTED_CURRENCY_REQUIRED"
    fi
    currency="$(printf '%s' "$currency" | tr '[:lower:]' '[:upper:]')"
  fi
  [[ "$currency" == "USD" ]] || fail "UNEXPECTED_CURRENCY_FOR_THIS_CONFIGURATION"
fi

# Select the credential by the explicit auth mode. Never fall back between aliases.
if [[ "$mode" == "oauth" ]]; then
  token_name="DERIV_AUTH_TOKEN"
  if has_secret "$token_name"; then
    printf 'PRESERVED_EXISTING_SECRET_NAME=%s\n' "$token_name"
    token=""
  else
    token="${DERIV_AUTH_TOKEN:-}"
    if [[ -z "$token" ]]; then
      [[ -t 0 ]] || fail "DERIV_AUTH_TOKEN_REQUIRED_NONINTERACTIVE"
      read -r -s -p "Enter the OAuth access token (hidden input): " token </dev/tty
      printf '\n'
    fi
    [[ -n "$token" ]] || fail "DERIV_AUTH_TOKEN_MISSING_FOR_OAUTH"
    set_secret_if_missing "$token_name" "$token"
  fi
else
  token_name="DERIV_PAT"
  if has_secret "$token_name"; then
    printf 'PRESERVED_EXISTING_SECRET_NAME=%s\n' "$token_name"
    token=""
  else
    token="${DERIV_PAT:-}"
    if [[ -z "$token" ]]; then
      [[ -t 0 ]] || fail "DERIV_PAT_REQUIRED_NONINTERACTIVE"
      read -r -s -p "Enter the Deriv PAT (hidden input): " token </dev/tty
      printf '\n'
    fi
    [[ -n "$token" ]] || fail "DERIV_PAT_MISSING_FOR_PAT_MODE"
    set_secret_if_missing "$token_name" "$token"
  fi
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

if has_secret "DERIV_EXPECTED_CURRENCY"; then
  printf 'PRESERVED_EXISTING_SECRET_NAME=DERIV_EXPECTED_CURRENCY\n'
else
  set_secret_if_missing "DERIV_EXPECTED_CURRENCY" "$currency"
fi

# Authentication mode is configuration, not a credential. Preserve an existing variable.
if ! has_variable "DERIV_AUTH_MODE"; then
  printf '%s' "$mode" | gh variable set DERIV_AUTH_MODE --env "$environment" --repo "$repo" >/dev/null \
    || fail "GITHUB_VARIABLE_WRITE_FAILED_DERIV_AUTH_MODE"
  printf 'CONFIGURED_VARIABLE_NAME=%s\n' "DERIV_AUTH_MODE"
else
  printf 'PRESERVED_EXISTING_VARIABLE_NAME=%s\n' "DERIV_AUTH_MODE"
fi

# Verify presence of either supported token and account aliases, plus currency/mode.
names="$(gh secret list --env "$environment" --repo "$repo" --json name --jq '.[].name' 2>/dev/null)" \
  || fail "GITHUB_SECRET_NAME_VERIFICATION_FAILED"
has_secret "$token_name" || fail "TOKEN_SECRET_NAME_NOT_VISIBLE_FOR_SELECTED_MODE"
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
