#!/usr/bin/env bash
set -euo pipefail

say(){ echo; echo "== $*"; }
fail(){ echo "FAIL: $*" >&2; exit 1; }

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$ROOT" ]] || fail "Not in a git repo."
cd "$ROOT"

say "Repo context"
git rev-parse --verify HEAD >/dev/null 2>&1 || fail "No git HEAD. NEXT: git add -A && git commit -m 'Initial commit'"

say "Hazards tracked?"
tracked="$(git ls-files | grep -E '(^|/)(\.tmp/|\.auth/|chromium-profile/|node_modules/|\.venv/)|(^|/)\.env(\.|$)|backup' || true)"
[[ -z "$tracked" ]] || fail "Hazards are tracked. NEXT: add to .gitignore and git rm --cached ..."

say "Python compile"
command -v python3 >/dev/null 2>&1 && python3 -m compileall -q ./scripts/ || true

echo "PASS"
