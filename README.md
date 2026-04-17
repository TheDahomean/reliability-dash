# PS Farms Reliability Dashboard

Standalone public reliability dashboard for PS Farms, deployed to Cloudflare Pages at `https://reliability.psfarms.co.ke`.

## How it works

```
Google Sheets workbook export / Sheets API
  -> refresh_dashboard.py
  -> pages-deploy/data.js
  -> build_opsdash_public.py
  -> pages-deploy/index.html + pages-deploy/opsdash_status.json + pages-deploy/data/opsdash_snapshot*.json
  -> deploy_pages.sh
  -> Cloudflare Pages
```

The repo no longer depends on `visualization/`. It refreshes directly from the shared ops workbook and incubation CSV.

## Common commands

```bash
./refresh_dashboard.sh
python3 build_opsdash_public.py
./refresh_and_deploy.sh
./deploy_pages.sh
./verify_live.sh
```

## Local setup

1. Copy `.env.example` to `.env.local`.
2. Set `GOOGLE_SERVICE_ACCOUNT_JSON` to a local service-account JSON path that can read the workbook.
3. Optionally set `RELIABILITY_DASH_PAGES_PROJECT`, `RELIABILITY_DASH_PAGES_BRANCH`, and `RELIABILITY_DASH_LIVE_URL`.
4. Run `./refresh_and_deploy.sh`.

## Scheduled refresh

- GitHub Actions workflow: `.github/workflows/refresh-and-deploy.yml`
- Cron helper: `scripts/cron_refresh.sh`
- Target cadence: every 15 minutes

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Recommended | — | Service-account JSON path used for authenticated workbook access |
| `GOOGLE_SHEETS_WORKBOOK_URL` | No | Ops workbook export URL | Workbook source |
| `GOOGLE_SHEETS_CSV_URL` | No | Ops incubation CSV export URL | Incubation CSV source |
| `RELIABILITY_DASH_PAGES_PROJECT` | No | `opsdash-public` | Cloudflare Pages project |
| `RELIABILITY_DASH_PAGES_BRANCH` | No | `main` | Cloudflare Pages branch |
| `RELIABILITY_DASH_LIVE_URL` | No | `https://reliability.psfarms.co.ke` | Live URL for verification |

## Notes

- `index.template.html` is the source template.
- `pages-deploy/` is the generated deploy bundle and is gitignored.
- `validate_snapshot.py` verifies `pages-deploy/data.js` before fallback deploys.
