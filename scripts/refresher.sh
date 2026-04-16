#!/usr/bin/env bash
set -euo pipefail

say(){ echo; echo "== $*"; }
fail(){ echo "FAIL: $*" >&2; exit 1; }
next(){ echo "NEXT: $*" >&2; }

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$ROOT" ]] || fail "Not in a git repo. NEXT: cd into a repo."
cd "$ROOT"

say "1) Repo root"
echo "$ROOT"

say "2) Guardrails present?"
[[ -x "./scripts/codex_bootstrap.sh" ]] || fail "Missing scripts/codex_bootstrap.sh. NEXT: run install_everywhere.sh"
[[ -x "./scripts/codex_qa.sh" ]] || fail "Missing scripts/codex_qa.sh. NEXT: run install_everywhere.sh"

say "3) Hooks enabled?"
hp="$(git config --get core.hooksPath 2>/dev/null || true)"
[[ "$hp" == ".githooks" ]] || fail "core.hooksPath != .githooks. NEXT: ./scripts/codex_bootstrap.sh --no-branch --force"

say "4) QA quick"
./scripts/codex_qa.sh >/dev/null || { next "Fix QA failure above then re-run ./scripts/refresher.sh"; exit 1; }

say "5) Dirty working tree?"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "WARN: uncommitted changes present."
fi

echo
echo "PASS: refresher ok"
