# CLAUDE.md

## Common commands

```bash
./refresh_dashboard.sh
python3 build_opsdash_public.py
./refresh_and_deploy.sh
./deploy_pages.sh
./verify_live.sh
python3 validate_snapshot.py data.js
python3 scripts/check_snapshot_freshness.py --status-json opsdash_status.json
python3 -m http.server 8080
./scripts/refresher.sh
./scripts/codex_bootstrap.sh
```

## Architecture

This repo is standalone. It does not depend on `visualization/`.

Refresh flow:

```text
Google Sheets workbook export / Sheets API
  -> refresh_dashboard.py
  -> data.js
  -> build_opsdash_public.py
  -> index.html + opsdash_status.json + data snapshot files
  -> deploy_pages.sh
  -> Cloudflare Pages
```

`index.template.html` is the source template. `index.html` is the generated artifact that gets deployed.

## Environment

Put local secrets in `.env.local` (gitignored).

| Variable | Notes |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Local service-account JSON path for workbook access |
| `GOOGLE_SHEETS_WORKBOOK_URL` | Optional workbook override |
| `GOOGLE_SHEETS_CSV_URL` | Optional incubation CSV override |
| `RELIABILITY_DASH_PAGES_PROJECT` | Default `opsdash-public` |
| `RELIABILITY_DASH_PAGES_BRANCH` | Default `main` |
| `RELIABILITY_DASH_LIVE_URL` | Default `https://reliability.psfarms.co.ke` |

## Scheduler

Primary scheduler: GitHub Actions `*/15` in `.github/workflows/refresh-and-deploy.yml`.

Local cron helper: `scripts/cron_refresh.sh`, which now runs `refresh_and_deploy.sh`.

## Deploy safety

- `refresh_and_deploy.sh` falls back to the last valid local `data.js` only if `validate_snapshot.py` passes.
- `deploy_pages.sh` deploys only the public bundle files via a temporary staging directory.
- The public HTML loads immediately with no password gate.
