#!/usr/bin/env bash
# Deprecated: Deriv account credentials cannot be provisioned until the broker
# exposes and verifies a read-only permission for the required account APIs.
set -euo pipefail
set +x
printf 'DERIV_SECRET_PROVISIONING=BLOCKED\n' >&2
printf 'REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE\n' >&2
printf 'SECRET_VALUES_READ=false\n' >&2
exit 2
