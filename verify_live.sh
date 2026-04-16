#!/usr/bin/env bash

set -euo pipefail

LIVE_URL="${RELIABILITY_DASH_LIVE_URL:-https://reliability.psfarms.co.ke}"
MAX_SNAPSHOT_AGE_MINUTES="${RELIABILITY_DASH_MAX_SNAPSHOT_AGE_MINUTES:-45}"
export PATH="${PATH}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ROOT_HTML="$(curl --max-time 15 --retry 4 --retry-delay 1 --retry-all-errors -sS "$LIVE_URL/")"
STATUS_JSON="$(curl --max-time 15 --retry 4 --retry-delay 1 --retry-all-errors -sS "$LIVE_URL/opsdash_status.json")"

echo "$STATUS_JSON" | grep -q '"ok": true'
echo "$ROOT_HTML" | grep -q 'Buyer FAQ'
echo "$ROOT_HTML" | grep -q 'How do you define what you can reliably supply'
echo "$ROOT_HTML" | grep -q 'What should a buyer take away from the dashboard overall'

STATUS_FILE="$(mktemp "${TMPDIR:-/tmp}/reliability-status.XXXXXX.json")"
cleanup() {
  rm -f "$STATUS_FILE"
}
trap cleanup EXIT
printf '%s' "$STATUS_JSON" > "$STATUS_FILE"
python3 "$(cd "$(dirname "$0")" && pwd)/scripts/check_snapshot_freshness.py" \
  --status-json "$STATUS_FILE" \
  --max-age-minutes "$MAX_SNAPSHOT_AGE_MINUTES"

echo "Live verification passed for $LIVE_URL"
