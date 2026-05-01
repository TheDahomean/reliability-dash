# AGENTS.md

Instructions for AI coding agents (Codex, Claude Code, etc.) working in this repo.

## Repo overview

Standalone public reliability dashboard for PS Farms. Refreshes from Google Sheets every 15 minutes and deploys to Cloudflare Pages.

```
refresh_dashboard.py  →  pages-deploy/data.js
build_opsdash_public.py  →  pages-deploy/index.html + opsdash_status.json + data/
deploy_pages.sh  →  Cloudflare Pages (wrangler)
```

`pages-deploy/` is gitignored. It is created at build time. Do not commit it.
`index.template.html` is the source for the dashboard HTML. Do not edit `index.html` directly.

## Before starting any task

1. Read `CLAUDE.md`, `README.md`, and `docs/HANDOFF.md`.
2. Run `git status` and `git log --oneline -5`.
3. Run `./scripts/codex_qa.sh` and confirm it prints `PASS`.
4. Do not edit files until you understand what Codex or Claude last changed.

## Setup (first time on a new machine)

```bash
./scripts/codex_bootstrap.sh --force
pip install -r requirements.txt
```

This installs the pre-commit hook, configures git, and (if `crontab` is available) installs the 15-minute local cron job.

## Required QA commands

Run these before committing and before reporting a task complete:

```bash
./scripts/codex_qa.sh
python3 -m py_compile refresh_dashboard.py build_opsdash_public.py build_workbook_data.py build_data.py validate_snapshot.py
python3 validate_snapshot.py data.js
```

## Architecture rules

- Do not introduce a second refresh or deploy mechanism. One pipeline exists.
- All output goes to `pages-deploy/`. Do not write to the repo root as a deploy target.
- `refresh_dashboard.py` is the only script that writes `pages-deploy/data.js`.
- `build_opsdash_public.py` is the only script that writes `pages-deploy/index.html`.
- Shell scripts must use `#!/usr/bin/env bash`. Do not use `#!/bin/zsh` or absolute interpreter paths.
- Do not hardcode `/usr/bin/python3`, `/bin/date`, `/opt/homebrew/bin/`, or other machine-local paths in scripts. Use PATH-resolved commands.
- `osascript` and other macOS-only tools must be guarded with `[[ "$(uname)" == "Darwin" ]]`.

## Do-not-touch areas

- `refresh_dashboard.py` — core data parser; regressions break the entire pipeline.
- `build_workbook_data.py` — row coercion and label normalisation; bugs here corrupt dashboard data silently.
- `index.template.html` — source template; edit this, never `index.html`.
- `.github/workflows/refresh-and-deploy.yml` — changes to secrets references or output paths break scheduled deploys.
- `.githooks/pre-commit` and `scripts/codex_bootstrap.sh` — guardrail infrastructure; changes must keep `./scripts/codex_qa.sh` passing.

## Environment variables

Required for local `deploy_pages.sh`. In CI these are GitHub Actions secrets.

| Variable | Required locally | Notes |
|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Recommended | Path to service-account JSON for authenticated workbook access |
| `CLOUDFLARE_API_TOKEN` | Yes for deploy | Wrangler API token; set as `CLOUDFLARE_API_TOKEN` secret in GitHub Actions |
| `RELIABILITY_DASH_PAGES_PROJECT` | No | Default `opsdash-public` |
| `RELIABILITY_DASH_PAGES_BRANCH` | No | Default `main` |
| `RELIABILITY_DASH_LIVE_URL` | No | Default `https://reliability.psfarms.co.ke` |

Copy `.env.example` to `.env.local` and fill in values. `.env.local` is gitignored.

## Commit rules

- Use `#!/usr/bin/env bash` in all shell scripts.
- Do not commit `.env`, `.env.local`, `latest_workbook.xlsx`, `latest_sheet.csv`, or `pages-deploy/`.
- Do not commit files that fail `./scripts/codex_qa.sh`.
- Push to the branch specified at the start of your session. Do not push to `main` without explicit permission.

## Handoff

After completing a task:
1. Run QA commands above.
2. Update `docs/HANDOFF.md` with what you changed, what is complete, and what is incomplete.
3. Commit and push all changes including the updated `docs/HANDOFF.md`.
