# Handoff

## Update rule

- Keep the snapshot sections below current for the latest session.
- Append one new entry to `## Session log` at the end of each agent session.
- If a referenced repo-local instruction file is missing, state that explicitly instead of guessing.

## Current goal

Keep the standalone reliability dashboard refresh/build/deploy flow stable, preserve the deployable bundle layout, and prevent regressions in workbook parsing and public snapshot generation.

## Last agent

Codex (`gpt-5.5`), 2026-05-16.

## Branch

`codex/2026-04-03-work`

## Commit / PR

- `HEAD` is `481cbad` on `codex/2026-04-03-work`.
- `origin/codex/2026-04-03-work` is still at `af7ac26`; the local branch is 2 commits ahead.
- Local `main` and `origin/main` refs in this checkout still point to `6af9ab1` because no post-push fetch was run.
- Remote GitHub `main` was advanced in this session to `8c13f27`, then `faf8d84`, then `481cbad`, confirmed via `git push` and the public GitHub API.
- No PR metadata was checked in this session.

## Files changed

- Before this session, the worktree already had modified `docs/HANDOFF.md` and untracked `AGENTS.md`.
- This session modified `build_workbook_data.py` to normalize workbook headers before record lookup.
- This session modified `index.template.html` to ignore blank/invalid harvest dates in client-side date math so the freshness badge still renders.
- This session regenerated the local `pages-deploy/` bundle from `latest_workbook.xlsx`, producing a fresh local snapshot at `generated_at=2026-05-16T09:30:55.391807Z`.
- The remaining uncommitted worktree state at session end is modified `build_workbook_data.py`, modified `index.template.html`, modified `docs/HANDOFF.md`, and untracked `AGENTS.md`.

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
- The public-staleness diagnosis is now concrete rather than inferred:
  - live `https://reliability.psfarms.co.ke/opsdash_status.json` and `https://opsdash-public.pages.dev/opsdash_status.json` were stale at `generated_at=2026-05-05T23:45:10.439443Z`
  - GitHub Actions scheduled runs on remote `main` were failing in `refresh_dashboard.py` / `build_workbook_data.py` before deploy
  - the failing traceback matched the out-of-range Excel serial overflow already fixed by `8c13f27`
- The latest local validation in this session passed:
  - `python3 validate_snapshot.py pages-deploy/data.js`
  - `python3 build_opsdash_public.py`
  - `python3 scripts/check_snapshot_freshness.py --status-json pages-deploy/opsdash_status.json`
- The latest verified local status snapshot in this session was:
  - `generated_at`: `2026-05-06T22:15:09.509806Z`
  - `build_version`: `af7ac26+dirty`
  - row counts: `bagging=15`, `pasteurization=15`, `incubation=143`, `fruiting=38`, `harvest=64`
- The repaired code path was proven in GitHub Actions run `#363` on remote `main` (`faf8d84`):
  - `Refresh data from Google Sheets`: success
  - `Validate snapshot`: success
  - `Build public reliability snapshot`: success
- The full refresh/build/deploy/health path was then proven in GitHub Actions run `#366` on remote `main` (`481cbad`):
  - `Refresh data from Google Sheets`: success
  - `Validate snapshot`: success
  - `Build public reliability snapshot`: success
  - `Deploy public Reliability dashboard`: success
  - `Health check`: success
- Live recovery is verified:
  - `https://reliability.psfarms.co.ke/opsdash_status.json`
  - `https://opsdash-public.pages.dev/opsdash_status.json`
  - both returned `generated_at=2026-05-07T03:25:13.025802Z`
  - both returned `build_version=481cbad+dirty`
  - both returned matching row counts: `bagging=15`, `pasteurization=15`, `incubation=143`, `fruiting=38`, `harvest=64`
- `bash -x ./verify_live.sh` passed after the secret fix and rerun.
- `docs/HANDOFF.md` exists and has been refreshed again to match the current branch/workflow state.
- The current local parser/build fixes are verified:
  - `rows_to_records()` now trims workbook header cells, so cosmetic header changes such as trailing newlines no longer break harvest parsing.
  - the browser render path now skips blank/invalid harvest dates instead of throwing before it can replace the build-time freshness label.
  - the locally regenerated bundle is fresh again at `generated_at=2026-05-16T09:30:55.391807Z`
  - the latest local row counts are `bagging=16`, `pasteurization=16`, `incubation=152`, `fruiting=47`, `harvest=74`

## What is incomplete

- There is still no automated regression coverage for the parser/build fixes.
- Local shell wrappers still include hard-coded shell/binary paths and a macOS notification call, even though the scheduled production path runs in GitHub Actions.
- `AGENTS.md` exists in this checkout but is currently untracked, so those instructions do not travel with the branch unless the file is committed.
- The live site is still stale as of this session because the fixed code and fresh local bundle were not deployed.
- Local deploy is still blocked by a missing `CLOUDFLARE_API_TOKEN`, and a second full Google refresh attempt in the sandbox hit DNS resolution failures for `oauth2.googleapis.com` after the workbook had already been downloaded once.

## Risks / uncertainties

- Another malformed workbook date, blank date field, or batch-ID variant could still regress silently because validation is script-level, not targeted regression coverage.
- Local `main` / `origin/main` refs are stale in this checkout after the pushes; use `git fetch` before relying on them in a future session.
- The published site currently reports `build_version=481cbad+dirty` because the workflow deploys from a generated bundle after refresh/build, not from a pristine git tree.
- Because `AGENTS.md` is currently untracked, other clones or clean checkouts will not see those repo-local instructions unless the file is committed.
- The local `latest_workbook.xlsx` used for verification is fresh for this session, but it is only a local artifact until the code is committed and a deploy path publishes the regenerated bundle.

## QA commands run

- `bash -x ./verify_live.sh`
- `python3 validate_snapshot.py pages-deploy/data.js`
- `python3 build_opsdash_public.py`
- `python3 scripts/check_snapshot_freshness.py --status-json pages-deploy/opsdash_status.json`
- `zsh ./refresh_and_deploy.sh`
- `node` headless execution of the inline dashboard script against `pages-deploy/index.html`
- `./refresh_dashboard.sh`
- `python3 - <<'PY' from build_workbook_data import build_context ... PY`
- `python3 - <<'PY' from build_workbook_data import build_context, write_data_js ... PY`

## QA results

- Initial `verify_live.sh`: failed freshness against live `generated_at=2026-05-05T23:45:10.439443Z`.
- `validate_snapshot.py`: passed, `pages-deploy/data.js` valid.
- `build_opsdash_public.py`: passed, rebuilt the public snapshot bundle successfully.
- `check_snapshot_freshness.py`: passed, local `pages-deploy/opsdash_status.json` was fresh in this session.
- Local `refresh_and_deploy.sh`: refresh succeeded and rebuilt the public bundle, but deploy failed because the local environment lacks a usable `CLOUDFLARE_API_TOKEN`.
- GitHub Actions run `#363` on remote `main`: refresh, validate, and build succeeded; deploy failed in `cloudflare/wrangler-action@v3` because the configured `apiToken` secret expanded to an invalid multi-line header value containing Google service-account JSON.
- GitHub Actions run `#366` on remote `main`: refresh, validate, build, deploy, and health check all succeeded.
- Final `verify_live.sh`: passed against live `generated_at=2026-05-07T03:25:13.025802Z`.
- Headless execution of the unpatched browser bundle initially failed with `TypeError: Cannot read properties of null (reading 'getTime')` on blank-date harvest rows.
- After the `index.template.html` patch, the same headless execution passed and updated the freshness UI without crashing.
- `./refresh_dashboard.sh` no longer failed on the harvest header lookup after `rows_to_records()` was normalized; the remaining rerun failure was outbound DNS resolution to `oauth2.googleapis.com` in the sandbox.
- `build_context('latest_workbook.xlsx')` passed after the header-normalization fix and produced `bagging=16`, `pasteurization=16`, `incubation=152`, `fruiting=47`, `harvest=74`.
- Manual local regeneration of `pages-deploy/data.js` from `latest_workbook.xlsx` succeeded, and the rebuilt `pages-deploy/opsdash_status.json` then passed freshness with `generated_at=2026-05-16T09:30:55.391807Z`.

## Next recommended task

Deploy the current fixes and refreshed local bundle, then add regression coverage for:

1. publishing the modified `build_workbook_data.py` and `index.template.html` so production can refresh again
2. out-of-range and malformed Excel serial handling in `build_workbook_data.py`
3. batch normalization and splitting for slash-form and hyphen-form `SB-YYYY-MM-DD-NN` IDs with vendor suffixes
4. blank harvest dates flowing through the recent-harvest windows in `build_opsdash_public.py`

## Do not touch without asking

- Do not undo the standalone repo structure or move generated deploy artifacts out of `pages-deploy/`.
- Do not reintroduce hard-coded macOS commands if you edit the shell wrappers; preserve or continue portability cleanup instead.
- Do not create duplicate refresh/deploy helpers, duplicate API clients, or alternate architecture paths.
- Treat `index.template.html` as the source template and `pages-deploy/` as the generated deploy bundle.

## Resume prompt for next agent

Read `AGENTS.md`, `CLAUDE.md`, and `docs/HANDOFF.md` first. `AGENTS.md` is currently untracked in the worktree. The worktree now contains uncommitted fixes in `build_workbook_data.py` and `index.template.html`:

- `build_workbook_data.py`: header cells are normalized before records are built, fixing harvest-sheet header drift such as trailing newlines.
- `index.template.html`: browser-side harvest date math now skips blank/invalid dates, preventing the stale build-time "Snapshot refreshed just now" label from sticking when render crashes.

The latest local generated bundle is fresh at `generated_at=2026-05-16T09:30:55.391807Z`, but the live site was not updated in this session because local deploy still lacks `CLOUDFLARE_API_TOKEN`. Next useful step: publish these fixes, then rerun:

- `python3 validate_snapshot.py pages-deploy/data.js`
- `python3 build_opsdash_public.py`
- `python3 scripts/check_snapshot_freshness.py --status-json pages-deploy/opsdash_status.json`
- `bash -x ./verify_live.sh`
- optional headless browser-script smoke test against `pages-deploy/index.html`

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

### 2026-05-04 | Codex (`gpt-5.5`)

- Re-read `AGENTS.md`, `CLAUDE.md`, and the existing handoff before editing.
- Refreshed the handoff metadata to match current `HEAD` `af7ac26` on `codex/2026-04-03-work`, which is now 2 commits ahead of `main`.
- Recorded that `AGENTS.md` exists in this checkout as an untracked worktree file rather than a committed repo file.
- Left the previously recorded validation status intact and marked that no build/test/lint commands were rerun in this doc-only session.

### 2026-05-06 | Codex (`gpt-5.5`)

- Re-read `AGENTS.md`, `CLAUDE.md`, and the existing handoff before editing.
- Confirmed `HEAD` is still `af7ac26` on `codex/2026-04-03-work`, 2 commits ahead of `main`.
- Updated the handoff snapshot to reflect the actual current worktree state: modified `docs/HANDOFF.md` and untracked `AGENTS.md`.
- Kept the previously recorded validation history intact and explicitly left this session marked as doc-only with no QA rerun.

### 2026-05-07 | Codex (`gpt-5.5`)

- Re-read `AGENTS.md`, `CLAUDE.md`, and the existing handoff before changing anything.
- Verified the live staleness directly: both public status URLs were stuck at `generated_at=2026-05-05T23:45:10.439443Z`.
- Queried the public GitHub Actions API and confirmed scheduled runs on remote `main` were failing in the refresh step on commit `6af9ab1`.
- Pulled the failing job log and confirmed the traceback matched the out-of-range Excel serial overflow already fixed by branch commit `8c13f27`.
- Ran the local validation path successfully on the current branch and confirmed local refresh/build still work; local deploy remained blocked by missing `CLOUDFLARE_API_TOKEN`.
- Pushed `8c13f27` to remote `main` so production uses the parser/build fix again.
- Added `.github/workflows/refresh-and-deploy.yml` trigger support for `push` to `main`, committed it as `faf8d84`, and pushed that commit to remote `main`.
- Confirmed the push-triggered GitHub Actions run `#363` started immediately and that refresh, validate, and build all succeeded.
- Pulled the run `#363` logs and narrowed the remaining production blocker to the GitHub secret `CLOUDFLARE_API_TOKEN`, which is behaving like a multi-line Google service-account JSON and causing the Cloudflare deploy step to fail with an invalid header value.
- Refreshed this handoff so the next agent can start with the exact remaining blocker instead of repeating the diagnosis.
- After the user corrected the Cloudflare secret, attempted to rerun `#363` via GitHub API but the available integration lacked Actions write permissions.
- Created no-op trigger commit `481cbad`, pushed it to remote `main`, and confirmed workflow run `#366` completed successfully end-to-end.
- Verified both public status URLs advanced to `generated_at=2026-05-07T03:25:13.025802Z` and that `bash -x ./verify_live.sh` passed.

### 2026-05-16 | Codex (`gpt-5.5`)

- Re-read `AGENTS.md`, `CLAUDE.md`, and `docs/HANDOFF.md`, then confirmed the worktree already had modified `docs/HANDOFF.md` and untracked `AGENTS.md`.
- Confirmed the live/public status was stale again: `https://reliability.psfarms.co.ke/opsdash_status.json` returned `generated_at=2026-05-13T08:12:14.110586Z`.
- Reproduced the browser-side freshness bug locally with a headless `node` harness: blank-date harvest rows caused `index.template.html` to throw before it could replace the static build-time freshness label.
- Patched `index.template.html` so the client-side model and harvest chart skip blank/invalid harvest dates, then rebuilt the public bundle and confirmed the headless render path completed successfully.
- Ran the local refresh/deploy path and found a second production blocker: `build_workbook_data.py` failed on a cosmetic header change where the harvest workbook column carried a trailing newline in `Fresh Harvest Lot ID (FH-YYMMDD-XX)\n`.
- Patched `build_workbook_data.py` so `rows_to_records()` trims header cells before constructing records, then verified the fix directly against `latest_workbook.xlsx`.
- Regenerated `pages-deploy/data.js` and the local public bundle from the downloaded workbook snapshot, producing a fresh local `generated_at=2026-05-16T09:30:55.391807Z` with row counts `bagging=16`, `pasteurization=16`, `incubation=152`, `fruiting=47`, `harvest=74`.
- Confirmed `python3 validate_snapshot.py pages-deploy/data.js` and `python3 scripts/check_snapshot_freshness.py --status-json pages-deploy/opsdash_status.json` both pass after the rebuild.
- Local deploy still failed because `wrangler` could not find a usable `CLOUDFLARE_API_TOKEN`, so the live site was not updated in this session.
