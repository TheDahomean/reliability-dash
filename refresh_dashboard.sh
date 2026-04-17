#!/bin/zsh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$ROOT/pages-deploy"

for env_file in "$ROOT/.env.local" "$ROOT/.env"; do
  if [[ -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$env_file"; set +a
  fi
done

if [[ -n "${GOOGLE_SERVICE_ACCOUNT_FILE:-}" && -z "${GOOGLE_SERVICE_ACCOUNT_JSON:-}" ]]; then
  export GOOGLE_SERVICE_ACCOUNT_JSON="$GOOGLE_SERVICE_ACCOUNT_FILE"
fi

WORKBOOK_URL="${GOOGLE_SHEETS_WORKBOOK_URL:-https://docs.google.com/spreadsheets/d/1IlCrI_aPESNDtPZ9629GSCjsCBhTakxbMP9eTlgzxUg/export?format=xlsx}"
INCUBATION_CSV_URL="${GOOGLE_SHEETS_CSV_URL:-https://docs.google.com/spreadsheets/d/1IlCrI_aPESNDtPZ9629GSCjsCBhTakxbMP9eTlgzxUg/export?format=csv&gid=1179745250}"

timestamp() {
  /bin/date "+%Y-%m-%d %H:%M:%S"
}

echo "[$(timestamp)] refresh_dashboard started"

/usr/bin/python3 "$ROOT/refresh_dashboard.py" \
  --workbook-url "$WORKBOOK_URL" \
  --workbook-output "$ROOT/latest_workbook.xlsx" \
  --incubation-csv-url "$INCUBATION_CSV_URL" \
  --incubation-csv-output "$ROOT/latest_sheet.csv" \
  --baseline-js-input "$BUNDLE_DIR/data.js" \
  --request-timeout-seconds 180 \
  --overall-timeout-seconds 900 \
  --download-attempts 3 \
  --retry-delay-seconds 5 \
  --min-rows 150 \
  --js-output "$BUNDLE_DIR/data.js"

echo "[$(timestamp)] refresh_dashboard completed"
