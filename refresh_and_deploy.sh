#!/bin/zsh

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$ROOT/pages-deploy"

for env_file in "$ROOT/.env.local" "$ROOT/.env"; do
  if [[ -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$env_file"; set +a
  fi
done

notify() {
  /usr/bin/osascript -e "display notification \"$2\" with title \"$1\""
}

timestamp() {
  /bin/date "+%Y-%m-%d %H:%M:%S"
}

echo "[$(timestamp)] refresh_and_deploy started"

REFRESH_STATUS="OK"
STALE_WARNING=""
DEPLOY_STATUS="OK"

if /bin/zsh "$ROOT/refresh_dashboard.sh"; then
  echo "[$(timestamp)] refresh step succeeded"
else
  echo "[$(timestamp)] refresh step failed; checking for usable snapshot" >&2
  REFRESH_STATUS="FAILED"
  if [[ -f "$BUNDLE_DIR/data.js" ]] && /usr/bin/python3 "$ROOT/validate_snapshot.py" "$BUNDLE_DIR/data.js" 2>/dev/null; then
    echo "[$(timestamp)] valid stale snapshot found; proceeding with deploy using cached data" >&2
    STALE_WARNING=" (STALE DATA)"
  else
    echo "[$(timestamp)] no valid snapshot available; aborting deploy" >&2
    notify "ReliabilityDash Failed" "Refresh failed and no valid snapshot exists. Deploy aborted."
    exit 1
  fi
fi

/usr/bin/python3 "$ROOT/build_opsdash_public.py"
echo "[$(timestamp)] rebuilt public reliability site"

if /bin/zsh "$ROOT/deploy_pages.sh"; then
  echo "[$(timestamp)] deploy step succeeded"
else
  echo "[$(timestamp)] deploy step failed" >&2
  DEPLOY_STATUS="FAILED"
fi

SUMMARY="Refresh: ${REFRESH_STATUS}${STALE_WARNING} | Deploy: ${DEPLOY_STATUS}"
echo "[$(timestamp)] ${SUMMARY}"
notify "ReliabilityDash" "$SUMMARY"
