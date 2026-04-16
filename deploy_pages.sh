#!/bin/zsh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="${RELIABILITY_DASH_PAGES_PROJECT:-opsdash-public}"
PRODUCTION_BRANCH="${RELIABILITY_DASH_PAGES_BRANCH:-main}"
LIVE_URL="${RELIABILITY_DASH_LIVE_URL:-https://reliability.psfarms.co.ke}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
NPX_BIN="${NPX_BIN:-$(command -v npx)}"

for env_file in "$ROOT/.env.local" "$ROOT/.env"; do
  if [[ -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$env_file"; set +a
  fi
done

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/reliability-dash-pages.XXXXXX")"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$TMP_DIR/data"
cp "$ROOT/index.html" "$TMP_DIR/index.html"
cp "$ROOT/data.js" "$TMP_DIR/data.js"
cp "$ROOT/opsdash_status.json" "$TMP_DIR/opsdash_status.json"
cp "$ROOT/favicon.svg" "$TMP_DIR/favicon.svg"
cp "$ROOT/_headers" "$TMP_DIR/_headers"
cp "$ROOT/data/opsdash_snapshot.json" "$TMP_DIR/data/opsdash_snapshot.json"
cp "$ROOT/data/opsdash_snapshot_meta.json" "$TMP_DIR/data/opsdash_snapshot_meta.json"

cd "$ROOT"
echo "Deploying $ROOT to Cloudflare Pages project $PROJECT_NAME"
"$NPX_BIN" --no-install wrangler pages deploy "$TMP_DIR" \
  --project-name="$PROJECT_NAME" \
  --branch="$PRODUCTION_BRANCH" \
  --commit-dirty=true
echo "Deployed to $LIVE_URL"
