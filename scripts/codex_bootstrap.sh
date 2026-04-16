#!/usr/bin/env bash
set -euo pipefail

FORCE="no"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE="yes"; shift ;;
    --no-branch) shift ;;
    *) shift ;;
  esac
done

git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "Not a git repo" >&2; exit 1; }
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [[ "$FORCE" != "yes" && -n "$(git status --porcelain)" ]]; then
  echo "Working tree dirty. Re-run with --force." >&2
  exit 1
fi

mkdir -p .githooks scripts
touch .gitignore
append(){ grep -qxF "$1" .gitignore || echo "$1" >> .gitignore; }
append ""
append "# Codex guardrails"
append ".tmp/"
append ".auth/"
append "**/chromium-profile/"
append ".DS_Store"
append "node_modules/"
append ".venv/"
append ".env"
append ".env.*"
append "*backup*"

cat > .githooks/pre-commit <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${CODEX_ALLOW_HAZARDS:-0}" == "1" ]]; then exit 0; fi
forbidden='(^|/)(\.tmp/|\.auth/|chromium-profile/|node_modules/|\.venv/)|(^|/)\.env(\.|$)|backup'
staged="$(git diff --cached --name-only)"
[[ -n "$staged" ]] || exit 0
bad=0
while IFS= read -r f; do
  echo "$f" | grep -Eiq "$forbidden" && { echo "BLOCKED: $f" >&2; bad=1; }
done <<< "$staged"
[[ "$bad" -eq 0 ]] || exit 1
HOOK
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks

# Install cron refresh job (idempotent — removes any stale entry first)
CRON_LINE="*/15 * * * * $ROOT/scripts/cron_refresh.sh >> $ROOT/logs/refresh.log 2>&1"
(crontab -l 2>/dev/null | grep -v "reliability-dash/scripts/cron_refresh.sh"; echo "$CRON_LINE") | crontab -
echo "Cron refresh installed: $CRON_LINE"
