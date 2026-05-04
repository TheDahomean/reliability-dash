# Handoff

## Update rule

- Keep the snapshot sections below current for the latest session.
- Append one new entry to `## Session log` at the end of each agent session.
- If a referenced repo-local instruction file is missing, state that explicitly instead of guessing.

## Current goal

Keep the standalone reliability dashboard refresh/build/deploy flow stable, preserve the deployable bundle layout, and prevent regressions in workbook parsing and public snapshot generation.

## Last agent

Codex (`gpt-5.5`), 2026-05-04.

## Branch

`codex/2026-04-03-work`

## Commit / PR

- `HEAD` is `8c13f27` on `codex/2026-04-03-work`.
- `main` and `origin/main` are at `6af9ab1`.
- This branch is 1 commit ahead of `main`.
- No PR metadata was checked in this session.

## Files changed

- Current uncommitted change: `docs/HANDOFF.md`
- Latest committed code changes before this handoff: `build_workbook_data.py`, `build_opsdash_public.py`

## What is complete

- The repo is standalone and no longer depends on `visualization/`.
- The refresh/deploy flow is established and documented:
  - Google Sheets workbook export / Sheets API
  - `refresh_dashboard.py`
  - `pages-deploy/data.js`
  - `build_opsdash_public.py`
  - `pages-deploy/index.html` + `pages-deploy/opsdash_status.json` + `pages-deploy/data/opsdash_snapshot*.json`
  - `deploy_pages.sh`
  - Cloudflare Pages
- Claude-visible work is committed, not left uncommitted:
  - `git status --short` was empty before this handoff file was created.
  - `git diff --stat`, `git diff --name-status`, and `git diff` were empty before this handoff file was created.
- The latest committed fix on this branch hardens the parser/build path against known data issues:
  - `excel_serial_to_date()` now returns blank for out-of-range Excel serials instead of crashing on overflow.
  - harvest-window calculations in `build_opsdash_public.py` now guard blank date values.
  - batch normalization and splitting now handle `SB-YYYY/MM/DD-NN`, `SB-YYYY-MM-DD-NN`, and vendor suffix variants more consistently.
- Local validation passed in this session:
  - `python3 validate_snapshot.py pages-deploy/data.js`
  - `python3 build_opsdash_public.py`
  - `python3 scripts/check_snapshot_freshness.py --status-json pages-deploy/opsdash_status.json`
- The latest verified local status snapshot after rebuild was:
  - `generated_at`: `2026-05-03T21:45:10.058994Z`
  - `build_version`: `8c13f27`
  - row counts: `bagging=14`, `pasteurization=14`, `incubation=139`, `fruiting=33`, `harvest=58`

- Live verification after deploy-collision fix:
  - `https://opsdash-public.pages.dev/opsdash_status.json`
  - `https://reliability.psfarms.co.ke/opsdash_status.json`
  - both returned `generated_at=2026-05-04T02:00:09.610747Z`
  - both returned `build_version=8c13f27+dirty`
  - both returned matching row counts: `bagging=14`, `pasteurization=14`, `incubation=139`, `fruiting=33`, `harvest=58`

## What is incomplete

- `docs/HANDOFF.md` did not exist before this session.
- There is no repo-local `AGENTS.md` in this checkout.
- There is no automated regression coverage for the recent parser/build fixes.
- Live URL verification was later run after resolving the visualization/reliability deploy collision.
- Local shell wrappers still include hard-coded shell/binary paths and a macOS notification call, even though the scheduled production path runs in GitHub Actions.

## Risks / uncertainties

- Another malformed workbook date, blank date field, or batch-ID variant could regress silently because the current validation is script-level, not targeted regression coverage.
- The scheduled production path is portable enough for GitHub Actions, but local helper scripts are still more environment-specific than the repo rules imply.
- `verify_live.sh` itself was not run, but both live status URLs were manually verified after the deploy-collision fix.
- Because `AGENTS.md` is missing in-repo, future agents should not assume repo-local instructions exist unless the file is added later.

## QA commands run

- `python3 validate_snapshot.py pages-deploy/data.js`
- `python3 build_opsdash_public.py`
- `python3 scripts/check_snapshot_freshness.py --status-json pages-deploy/opsdash_status.json`

## QA results

- `validate_snapshot.py`: passed, `pages-deploy/data.js` valid.
- `build_opsdash_public.py`: passed, rebuilt the public snapshot bundle successfully.
- `check_snapshot_freshness.py`: passed, local `opsdash_status.json` was fresh at the time of the check.

## Next recommended task

Add minimal standard-library regression coverage for the exact failure modes fixed on this branch before doing more refactors or portability edits. Cover at least:

1. out-of-range and malformed Excel serial handling in `build_workbook_data.py`
2. batch normalization and splitting for slash-form and hyphen-form `SB-YYYY-MM-DD-NN` IDs with vendor suffixes
3. blank harvest dates flowing through the recent-harvest windows in `build_opsdash_public.py`

Keep the solution within existing repo patterns. Do not introduce a parallel helper stack, a new API client, or a non-deployable file layout just to add tests.

## Do not touch without asking

- Do not undo the standalone repo structure or move generated deploy artifacts out of `pages-deploy/`.
- Do not reintroduce hard-coded macOS commands if you edit the shell wrappers; preserve or continue portability cleanup instead.
- Do not create duplicate refresh/deploy helpers, duplicate API clients, or alternate architecture paths.
- Treat `index.template.html` as the source template and `pages-deploy/` as the generated deploy bundle.

## Resume prompt for next agent

Read `CLAUDE.md` and `docs/HANDOFF.md` first. There is no repo-local `AGENTS.md` in this checkout. Continue on branch `codex/2026-04-03-work` by adding small regression coverage for the parser/build fixes in `build_workbook_data.py` and `build_opsdash_public.py`, then rerun:

- `python3 validate_snapshot.py pages-deploy/data.js`
- `python3 build_opsdash_public.py`
- `python3 scripts/check_snapshot_freshness.py --status-json pages-deploy/opsdash_status.json`

Keep the deployable structure unchanged and do not add new hard-coded macOS commands.

## Session log

### 2026-05-04 | Codex (`gpt-5.5`)

- Confirmed `CLAUDE.md` exists, but `AGENTS.md` and `docs/HANDOFF.md` were missing from the repo checkout at the start of the session.
- Confirmed branch `codex/2026-04-03-work` was clean and 1 commit ahead of `main`.
- Verified the latest visible Claude work was committed rather than uncommitted.
- Read the refresh/deploy flow and recent parser/build changes to reconstruct the current operational state.
- Ran the local validation path successfully against the current generated artifacts.
- Added this initial `docs/HANDOFF.md` so future agents have an explicit source of truth and a single concrete next task.
- After this handoff file was created, the visualization repo was patched and merged so it no longer deploys `opsdash-public` from GitHub Actions.
- Verified that the Pages alias and custom domain now return the same reliability dashboard status payload.
