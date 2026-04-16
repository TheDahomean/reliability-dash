#!/usr/bin/env bash
# Cron wrapper for refresh_and_deploy.sh.
# Loads .env.local from repo root (gitignored), then refreshes and deploys.
# Add to crontab with:
#   */15 * * * * /path/to/reliability-dash/scripts/cron_refresh.sh >> /path/to/reliability-dash/logs/refresh.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT/.env.local"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  set -a; source "$ENV_FILE"; set +a
fi

mkdir -p "$ROOT/logs"
echo "=== $(date -u +"%Y-%m-%dT%H:%M:%SZ") cron_refresh start ==="
exec "$ROOT/refresh_and_deploy.sh"
