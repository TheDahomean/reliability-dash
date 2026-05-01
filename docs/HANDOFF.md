# Handoff After Codex

## Last known goal

Codex built a standalone refresh-and-deploy pipeline for the PS Farms reliability dashboard (Cloudflare Pages, `https://reliability.psfarms.co.ke`), split from a larger `visualization/` monorepo. The branch `claude/add-status-feature-CwmkE` was handed over for a "status feature" that has not yet been implemented. Claude has since performed a portability and cleanup pass.

---

## Current git state

```
Branch:  claude/add-status-feature-CwmkE
Remote:  origin/claude/add-status-feature-CwmkE (up to date as of this commit)
Working tree: clean
```

Commit log (newest first):

| Hash | Author | Message |
|---|---|---|
| (this commit) | Claude | cleanup: portability pass and AGENTS.md |
| `b790218` | Claude | fix: make shell scripts portable for Linux/CI |
| `d0f0ed7` | Claude | docs: add HANDOFF.md with post-Codex audit findings |
| `aa825b4` | Claude | chore: ignore Python bytecode cache |
| `6af9ab1` | Codex | Fix: stabilize reliability refresh bundle and mainline parser |
| `26f8739` | Codex | Restore password gate, fix debug log capture, idiomatic regex |
| `f86271e` | Codex | Fix: blank row coercion, clipped labels, batch ID normalization |
| `0bab8cd` | Codex | Init: standalone refresh, deploy, GitHub Actions, password gate removed |
| `33716b0` | pre-Codex | Add repository guardrails and setup scripts |

---

## Files changed

### By Codex (commits `0bab8cd`–`6af9ab1`)

Created: `refresh_dashboard.py`, `build_opsdash_public.py`, `build_workbook_data.py`, `build_data.py`, `validate_snapshot.py`, `refresh_dashboard.sh`, `refresh_and_deploy.sh`, `deploy_pages.sh`, `verify_live.sh`, `.github/workflows/refresh-and-deploy.yml`, `scripts/cron_refresh.sh`, `scripts/check_snapshot_freshness.py`, `.env.example`, `CLAUDE.md`, `README.md`.

Modified: `index.template.html` (password gate, template placeholders), `index.html` (same), `data/opsdash_snapshot.json`, `data/opsdash_snapshot_meta.json`, `data.js`, `opsdash_status.json`, `.gitignore`.

### By Claude (cleanup pass)

| File | Change |
|---|---|
| `refresh_dashboard.sh` | `#!/bin/zsh` → `#!/usr/bin/env bash`; `/bin/date` → `date`; `/usr/bin/python3` → `python3` |
| `refresh_and_deploy.sh` | Same shebang/path fixes; `notify()` guarded behind `uname == Darwin`; `/bin/zsh` sub-invocations → `bash` |
| `deploy_pages.sh` | `#!/bin/zsh` → `#!/usr/bin/env bash`; guard for empty `NPX_BIN` with actionable error |
| `scripts/codex_qa.sh` | Fixed `.env.example` false positive in hazard regex |
| `.githooks/pre-commit` | Same false positive fix (matches codex_qa.sh) |
| `scripts/codex_bootstrap.sh` | Fixed embedded pre-commit heredoc; crontab install now guarded by `command -v crontab` |
| `.env.example` | Added `CLOUDFLARE_API_TOKEN` (required for local `deploy_pages.sh`) |
| `CLAUDE.md` | Fixed stale `pages-deploy/opsdash_status.json` path → `opsdash_status.json`; added `CLOUDFLARE_API_TOKEN` to env table |
| `requirements.txt` | Created: `openpyxl`, `google-auth`, `google-api-python-client`, `requests` |
| `.gitignore` | Added `__pycache__/` and `*.pyc` |
| `AGENTS.md` | Created (did not exist) |
| `docs/HANDOFF.md` | This file |

---

## What appears complete

- **Python pipeline:** all five scripts compile cleanly; `validate_snapshot.py data.js` passes.
- **Shell scripts:** all use `#!/usr/bin/env bash`; no hardcoded macOS paths remain in shebangs or binary invocations; `osascript` guarded.
- **Password gate:** present in `index.template.html` and reflected in `index.html`.
- **GitHub Actions workflow:** structurally complete; uses `GOOGLE_SERVICE_ACCOUNT_JSON` and `CLOUDFLARE_API_TOKEN` secrets; deploys via `cloudflare/wrangler-action@v3`.
- **Guardrails:** `codex_qa.sh` passes; pre-commit hook correctly blocks real hazards without false-positiving on `.env.example`; `codex_bootstrap.sh` heredoc matches the live hook.
- **Documentation:** `AGENTS.md` exists; `CLAUDE.md` is accurate; `README.md` is accurate; `.env.example` documents all required variables.
- **`requirements.txt`:** present; CI already checked for it and will use it.
- **Missing-baseline handling:** `refresh_dashboard.py` handles absent `pages-deploy/data.js` gracefully (warns and continues).
- **`pages-deploy/` self-creation:** `write_data_js()` in `build_workbook_data.py` calls `mkdir(parents=True, exist_ok=True)`; `build_opsdash_public.py` does the same for `SNAPSHOT_DIR`. The directory is created on first run without manual bootstrapping.

---

## What appears incomplete

**1. "Status feature" not implemented.**
The branch `claude/add-status-feature-CwmkE` was named for a task that has not been started. No new status UI, endpoint, or data field exists.

**2. Root-level artifacts are git-tracked but architecturally redundant.**
`index.html`, `data.js`, `opsdash_status.json`, `favicon.svg`, `_headers`, and `data/` at the repo root are pre-split leftovers. The active pipeline writes everything to `pages-deploy/`. These root copies are 14 days stale (`generated_at: 2026-04-17`, `build_version: f86271e+dirty`). They are not read by any current script. They have not been removed because doing so requires care: `validate_snapshot.py data.js` currently passes against the root copy, and removing them from git history is a separate decision.

**3. CI hardcodes project name and Cloudflare account ID.**
`refresh-and-deploy.yml` hardcodes `--project-name=opsdash-public` and `accountId: 549ca24bcbb7ee6769c08e2516ac583b`. `deploy_pages.sh` uses `RELIABILITY_DASH_PAGES_PROJECT` env var with the same default. The values are consistent but the CI bypasses the env var mechanism. This is not broken; it is a latent inconsistency.

**4. No unit or integration tests.**
QA is limited to Python compile, snapshot validation, and a live HTTP health check. No test suite exists.

---

## Risks / uncertainties

- **Snapshot is 14 days stale.** `opsdash_status.json` shows `generated_at: 2026-04-17T03:49:26Z`. `check_snapshot_freshness.py` will report failure against any age limit ≤ 20478 minutes. This resolves when CI runs a successful refresh.
- **Root-level artifacts vs. `pages-deploy/`.** Two sets of generated files exist (root = stale + tracked; `pages-deploy/` = gitignored + not yet populated locally). Future contributors may edit the wrong copy.
- **`deploy_pages.sh` requires `npx` locally.** CI uses `cloudflare/wrangler-action@v3` which bundles wrangler. Local deploys need `npx` in PATH or `NPX_BIN` set. The script now emits a clear error if `npx` is missing.
- **`build_version: f86271e+dirty`.** The committed root-level status JSON reflects a dirty-tree build. It cannot be trusted as a clean reference.

---

## Required QA commands

```bash
# Guardrail check (must print PASS)
./scripts/codex_qa.sh

# Python compile
python3 -m py_compile refresh_dashboard.py build_opsdash_public.py \
  build_workbook_data.py build_data.py validate_snapshot.py \
  scripts/check_snapshot_freshness.py

# Snapshot validation (root copy)
python3 validate_snapshot.py data.js

# Snapshot validation (deploy bundle — requires pages-deploy/ to exist after a build)
python3 validate_snapshot.py pages-deploy/data.js

# Freshness check (will fail until CI has run a successful refresh)
python3 scripts/check_snapshot_freshness.py --status-json opsdash_status.json

# Live verification (requires network + deployed live site)
./verify_live.sh
```

---

## Recommended next action

Clarify the "status feature" requirement before writing code. The pipeline is now portable and deployable; the next substantive task is implementing what the branch name describes.

If the goal is a scheduled CI run first: ensure `GOOGLE_SERVICE_ACCOUNT_JSON` and `CLOUDFLARE_API_TOKEN` are set as GitHub Actions secrets in the repository settings, then trigger the workflow manually via `workflow_dispatch`.

---

## Do-not-touch areas

- **`refresh_dashboard.py`** — core parser; regressions break the entire data pipeline.
- **`build_workbook_data.py`** — row coercion and label normalisation fixed across multiple commits; bugs here corrupt data silently.
- **`index.template.html`** — source of truth for dashboard HTML; never edit `index.html` directly.
- **`.github/workflows/refresh-and-deploy.yml`** — changes to secrets references or `pages-deploy/` output path silently break scheduled deploys.
- **`.githooks/pre-commit` and `scripts/codex_bootstrap.sh`** — guardrail infrastructure; any change must keep `./scripts/codex_qa.sh` passing and must keep the hook and bootstrap heredoc in sync.
- **Root-level `data/opsdash_snapshot.json`** — 14-day-old stale data; do not use as source of truth; do not delete without understanding downstream references.
