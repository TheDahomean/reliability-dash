#!/bin/zsh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_DIR="$ROOT/pages-deploy"
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

for required_path in \
  "$BUNDLE_DIR/index.html" \
  "$BUNDLE_DIR/data.js" \
  "$BUNDLE_DIR/opsdash_status.json" \
  "$BUNDLE_DIR/favicon.svg" \
  "$BUNDLE_DIR/_headers" \
  "$BUNDLE_DIR/data/opsdash_snapshot.json" \
  "$BUNDLE_DIR/data/opsdash_snapshot_meta.json"; do
  if [[ ! -f "$required_path" ]]; then
    echo "Missing bundle artifact: $required_path" >&2
    exit 1
  fi
done

cd "$ROOT"
echo "Deploying $BUNDLE_DIR to Cloudflare Pages project $PROJECT_NAME"
"$NPX_BIN" --no-install wrangler pages deploy "$BUNDLE_DIR" \
  --project-name="$PROJECT_NAME" \
  --branch="$PRODUCTION_BRANCH" \
  --commit-dirty=true
echo "Deployed to $LIVE_URL"
