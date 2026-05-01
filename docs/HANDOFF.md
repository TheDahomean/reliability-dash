# Handoff After Codex

## Last known goal

Codex was given this repo as a standalone split from a larger `visualization/` monorepo. Its task was to build and stabilise an independent refresh-and-deploy pipeline for the PS Farms reliability dashboard (Cloudflare Pages, `https://reliability.psfarms.co.ke`).

The active branch is `claude/add-status-feature-CwmkE`. Its name implies a "status feature" task, but no implementation of that feature exists in any commit on this branch. The branch currently contains only the Codex handoff state plus one housekeeping commit (gitignore).

---

## Current git state

```
Branch:  claude/add-status-feature-CwmkE
Remote:  origin/claude/add-status-feature-CwmkE (up to date)
Working tree: clean
```

Commit log (newest first):

| Hash      | Author  | Message |
|-----------|---------|---------|
| `aa825b4` | Claude  | chore: ignore Python bytecode cache |
| `6af9ab1` | Codex   | Fix: stabilize reliability refresh bundle and mainline parser |
| `26f8739` | Codex   | Restore password gate, fix debug log capture, idiomatic regex |
| `f86271e` | Codex   | Fix: blank row coercion, clipped labels, batch ID normalization |
| `0bab8cd` | Codex   | Init: standalone refresh, deploy, GitHub Actions, password gate removed |
| `33716b0` | pre-Codex | Add repository guardrails and setup scripts |
| `7afff14` | pre-Codex | Refresh generated dashboard artifacts before split |
| `6d4f685` | pre-Codex | Prepare reliability dashboard split state |

---

## Files changed

All changes below were made by Codex across commits `0bab8cd`–`6af9ab1`.

**Created from scratch:**
- `refresh_dashboard.py` — downloads workbook/CSV, parses, writes `pages-deploy/data.js`
- `build_opsdash_public.py` — renders `index.template.html` → `pages-deploy/index.html`, writes status JSON and snapshot files
- `build_workbook_data.py` — workbook parsing helpers (batches, labels, coercion)
- `build_data.py` — lower-level data utilities
- `validate_snapshot.py` — validates `pages-deploy/data.js` structure before deploy
- `refresh_dashboard.sh` — shell wrapper for `refresh_dashboard.py`
- `refresh_and_deploy.sh` — orchestrates refresh → build → deploy with stale-snapshot fallback
- `deploy_pages.sh` — runs `wrangler pages deploy pages-deploy/`
- `verify_live.sh` — curls live URL and checks freshness
- `.github/workflows/refresh-and-deploy.yml` — GitHub Actions, `*/15` cron schedule
- `scripts/cron_refresh.sh` — local cron wrapper
- `scripts/check_snapshot_freshness.py` — checks `opsdash_status.json` age against a limit
- `.env.example` — documents required environment variables
- `CLAUDE.md`, `README.md`

**Modified:**
- `index.template.html` — major additions: password gate UI (commit `26f8739`), template placeholders for snapshot sections
- `index.html` — same changes applied to the generated copy
- `data/opsdash_snapshot.json` — data refresh artifacts (committed at root; see Risks)
- `data/opsdash_snapshot_meta.json` — metadata for the snapshot
- `data.js` — dashboard data bundle (committed at root; see Risks)
- `opsdash_status.json` — build status record (committed at root; see Risks)
- `.gitignore` — added Codex guardrails entries; `pages-deploy/` is gitignored

---

## What appears complete

- **Python pipeline logic:** all five Python scripts (`refresh_dashboard.py`, `build_opsdash_public.py`, `build_workbook_data.py`, `build_data.py`, `validate_snapshot.py`) compile cleanly and are structurally coherent.
- **Snapshot validation:** `validate_snapshot.py data.js` passes against the root-level copy.
- **Password gate:** present and wired in both `index.template.html` and `index.html`; localStorage-backed, case-insensitive.
- **GitHub Actions workflow:** structure is complete; uses `GOOGLE_SERVICE_ACCOUNT_JSON` and `CLOUDFLARE_API_TOKEN` secrets; deploys via `cloudflare/wrangler-action@v3`.
- **Guardrail scripts:** `scripts/codex_bootstrap.sh`, `scripts/codex_qa.sh`, and the pre-commit hook are present and functional.
- **Missing-baseline handling:** `refresh_dashboard.py` checks `baseline_js_input.exists()` before loading it and falls back gracefully — a missing `pages-deploy/data.js` will not crash the script.

---

## What appears incomplete

**1. `pages-deploy/` does not exist.**
Every shell script and `build_opsdash_public.py` writes output to `pages-deploy/`. The directory is gitignored and has never been bootstrapped in this checkout. Running any of the local scripts cold will fail immediately. `deploy_pages.sh` validates required files under `pages-deploy/` before deploying and will exit non-zero.

**2. Root-level artifacts are git-tracked but architecturally redundant.**
`index.html`, `data.js`, `opsdash_status.json`, `favicon.svg`, `_headers`, and `data/` at the repo root are leftovers from the pre-split state. The README states `pages-deploy/` is the deploy bundle and is gitignored. These root copies are 14 days stale (`generated_at: 2026-04-17T03:49:26Z`, `build_version: f86271e+dirty`) and are not read by any script in the current architecture. They were never removed or re-gitignored.

**3. Shell scripts use `/bin/zsh` and macOS-specific paths.**
`refresh_dashboard.sh`, `refresh_and_deploy.sh`, and `deploy_pages.sh` all have `#!/bin/zsh` shebangs. `refresh_and_deploy.sh` calls `/usr/bin/osascript` (macOS Notification Center). The GitHub Actions runner (`ubuntu-latest`) may not have `/bin/zsh`; if the CI ever invokes these scripts directly (rather than inlining the Python commands) they will fail. `scripts/cron_refresh.sh` correctly uses `#!/usr/bin/env bash`.

**4. No "status feature" implemented.**
The branch name `claude/add-status-feature-CwmkE` implies a task that has not been started. No new status UI, endpoint, or logic exists in any commit on this branch.

**5. Last real build was dirty.**
`opsdash_status.json` records `build_version: f86271e+dirty`, meaning the last build that wrote these artifacts ran against uncommitted changes. The committed root-level artifacts cannot be relied on as a clean reference.

---

## Risks / uncertainties

- **Snapshot age:** local `opsdash_status.json` shows data from 2026-04-17, 14 days before current date (2026-05-01). `check_snapshot_freshness.py` reports age 20478 minutes against a 45-minute limit — this will fail any freshness-based health check.
- **CI first-run behaviour:** the workflow passes `--baseline-js-input pages-deploy/data.js`; because `pages-deploy/` is gitignored, this path will not exist on a fresh runner. `refresh_dashboard.py` handles this gracefully (falls back to bootstrap floor), but the `validate_snapshot.py pages-deploy/data.js` step that follows will fail if the refresh step did not produce output.
- **`osascript` in `refresh_and_deploy.sh`:** `notify()` calls `osascript`. On Linux this will print an error but the script does not use `set -e` around it, so it continues. Non-fatal but noisy.
- **Root-level tracked artifacts vs. gitignored `pages-deploy/`:** future contributors may be confused about which copy is authoritative. The two copies can silently diverge.
- **No tests:** there are no unit or integration tests. QA is limited to compile checks, snapshot validation, and a live HTTP check.

---

## Required QA commands

```bash
# Python compile check
python3 -m py_compile refresh_dashboard.py build_opsdash_public.py \
  build_workbook_data.py build_data.py validate_snapshot.py \
  scripts/check_snapshot_freshness.py

# Guardrail QA
./scripts/codex_qa.sh

# Snapshot validation (root copy; passes)
python3 validate_snapshot.py data.js

# Snapshot validation (deploy bundle; requires pages-deploy/ to exist)
python3 validate_snapshot.py pages-deploy/data.js

# Freshness check (will fail until a live refresh has run)
python3 scripts/check_snapshot_freshness.py --status-json opsdash_status.json

# Live verification (requires network access and a deployed live URL)
./verify_live.sh
```

---

## Recommended next action

Before implementing the status feature, resolve the broken local pipeline:

1. Bootstrap `pages-deploy/` from the root-level artifacts so scripts have something to work with:
   ```bash
   mkdir -p pages-deploy/data
   cp index.html pages-deploy/
   cp data.js pages-deploy/
   cp opsdash_status.json pages-deploy/
   cp favicon.svg pages-deploy/
   cp _headers pages-deploy/
   cp data/opsdash_snapshot.json pages-deploy/data/
   cp data/opsdash_snapshot_meta.json pages-deploy/data/
   python3 validate_snapshot.py pages-deploy/data.js
   ```
2. Clarify what "add status feature" means before writing any code.
3. Consider replacing `#!/bin/zsh` with `#!/usr/bin/env bash` in the three local shell scripts if CI invocation of those scripts is intended.

---

## Do-not-touch areas

- **`refresh_dashboard.py`** — core parser; last stabilised in `6af9ab1`. Regressions here break the entire data pipeline.
- **`build_workbook_data.py`** — row coercion and label normalisation logic was fixed across multiple commits (`f86271e`, `26f8739`, `6af9ab1`). Changes risk reintroducing blank-row or clipped-label bugs.
- **`index.template.html`** — source of truth for the dashboard UI. `index.html` is generated from it; edit only the template, never `index.html` directly.
- **`.github/workflows/refresh-and-deploy.yml`** — any change that breaks the secrets references (`GOOGLE_SERVICE_ACCOUNT_JSON`, `CLOUDFLARE_API_TOKEN`) or the `pages-deploy/` output path will silently break scheduled deploys.
- **Root-level `data/opsdash_snapshot.json`** — 14-day-old data; do not use as a source of truth. Do not delete without understanding whether anything outside this repo references the root path.
