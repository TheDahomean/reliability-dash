#!/usr/bin/env python3

import argparse
import contextlib
import json
import math
import os
import pathlib
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from typing import Optional


def _resolve_sa_json(cli_value: Optional[str]) -> Optional[pathlib.Path]:
    raw = cli_value or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not raw:
        return None
    p = pathlib.Path(raw).expanduser()
    return p if p.exists() else None


_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def _sheet_id_from_url(url: str) -> Optional[str]:
    m = _SHEET_ID_RE.search(url)
    return m.group(1) if m else None


def _build_xlsx_from_sheets_api(sheet_id: str, dst: pathlib.Path, creds) -> None:
    """Read all sheets via Sheets API v4 and write as XLSX using openpyxl.

    This path is not affected by the Drive/Docs file-level 'disable download'
    restriction because it reads cell data through the Sheets data API, not
    the file export endpoint.
    """
    try:
        import openpyxl
        from googleapiclient.discovery import build as gapi_build
    except ImportError:
        raise SystemExit(
            "openpyxl and google-api-python-client are required for Sheets API fallback.\n"
            "  pip install openpyxl google-api-python-client"
        )

    print(f"Drive export blocked; falling back to Sheets API v4 for sheet {sheet_id}", file=sys.stderr)
    service = gapi_build("sheets", "v4", credentials=creds, cache_discovery=False)
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()

    sheet_names = [s["properties"]["title"] for s in spreadsheet["sheets"]]

    # batchGet fetches all sheets in a single API call, avoiding per-sheet rate limits.
    batch_result = service.spreadsheets().values().batchGet(
        spreadsheetId=sheet_id,
        ranges=sheet_names,
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    value_ranges = {
        vr.get("range", "").split("!")[0].strip("'"):  vr.get("values", [])
        for vr in batch_result.get("valueRanges", [])
    }

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # drop the default empty sheet

    for sheet_name in sheet_names:
        ws = wb.create_sheet(title=sheet_name)
        for row in value_ranges.get(sheet_name, []):
            ws.append(row)

    temp = dst.with_suffix(dst.suffix + ".tmp")
    wb.save(str(temp))
    temp.replace(dst)
    print(f"Sheets API fallback: wrote {len(sheet_names)} sheets to {dst}", file=sys.stderr)


def _download_xlsx_with_sa(workbook_url: str, dst: pathlib.Path, sa_json: pathlib.Path) -> None:
    """Download a Google Sheet as XLSX using service account credentials.

    Tries Drive API export first (fast, single request). If the file owner has
    disabled exports for viewers (cannotExportFile / 403), falls back to reading
    cell data via Sheets API v4 and reconstructing an XLSX with openpyxl.
    """
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
    except ImportError:
        raise SystemExit(
            "google-auth is required for service account downloads.\n"
            "  pip install google-auth requests"
        )
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = service_account.Credentials.from_service_account_file(str(sa_json), scopes=scopes)
    session = AuthorizedSession(creds)

    sheet_id = _sheet_id_from_url(workbook_url)

    if sheet_id:
        xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        api_url = f"https://www.googleapis.com/drive/v3/files/{sheet_id}/export?mimeType={xlsx_mime}"
        print(f"Attempting Drive API export: {api_url}", file=sys.stderr)
        resp = session.get(api_url, timeout=120)

        if resp.status_code == 403:
            # cannotExportFile: the file owner has disabled downloads for viewers.
            # Fall back to reading cell data via the Sheets API and building XLSX locally.
            _build_xlsx_from_sheets_api(sheet_id, dst, creds)
            return

        if resp.status_code != 200:
            snippet = resp.text[:600] if resp.headers.get("content-type", "").startswith("text") else repr(resp.content[:200])
            raise SystemExit(
                f"Drive API export failed: HTTP {resp.status_code}\n"
                f"URL: {api_url}\n"
                f"Response: {snippet}"
            )
        if resp.content[:2] != b"PK":
            raise SystemExit(
                f"Drive API export returned non-XLSX content. "
                f"Status: {resp.status_code}. First 200 bytes: {resp.content[:200]!r}"
            )
        temp = dst.with_suffix(dst.suffix + ".tmp")
        temp.write_bytes(resp.content)
        temp.replace(dst)
    else:
        print(f"No sheet ID in URL; using direct AuthorizedSession download: {workbook_url}", file=sys.stderr)
        resp = session.get(workbook_url, timeout=120, allow_redirects=True)
        if resp.status_code != 200:
            raise SystemExit(f"Download failed: HTTP {resp.status_code} for {workbook_url}")
        if resp.content[:2] != b"PK":
            raise SystemExit(f"Downloaded content is not a valid XLSX file. Status: {resp.status_code}")
        temp = dst.with_suffix(dst.suffix + ".tmp")
        temp.write_bytes(resp.content)
        temp.replace(dst)

def _download_csv_with_sa(csv_url: str, dst: pathlib.Path, sa_json: pathlib.Path) -> None:
    """Download a Google Sheets CSV export using service account credentials."""
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
    except ImportError:
        raise SystemExit(
            "google-auth is required for service account downloads.\n"
            "  pip install google-auth requests"
        )
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = service_account.Credentials.from_service_account_file(str(sa_json), scopes=scopes)
    session = AuthorizedSession(creds)
    resp = session.get(csv_url, timeout=120, allow_redirects=True)
    if resp.status_code == 403:
        print(
            f"CSV export blocked (403) for {csv_url}; "
            "will use workbook sheet directly.",
            file=sys.stderr,
        )
        return False
    if resp.status_code != 200:
        raise SystemExit(f"CSV download failed: HTTP {resp.status_code} for {csv_url}")
    temp = dst.with_suffix(dst.suffix + ".tmp")
    temp.write_bytes(resp.content)
    temp.replace(dst)
    print(f"CSV downloaded via service account to {dst}", file=sys.stderr)
    return True


from build_workbook_data import build_context, write_data_js

DATASET_KEYS = ("bagging", "pasteurization", "incubation", "fruiting", "harvest")
DEFAULT_BASELINE_SUBPATH = pathlib.Path("pages-deploy/data.js")
JS_PREFIX = "window.DASHBOARD_CONTEXT = "


def download_file(
    url: str,
    destination: pathlib.Path,
    timeout_seconds: int,
    attempts: int = 1,
    retry_delay_seconds: int = 0,
) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "reliability-refresh/1.0",
            "Accept": "*/*",
        },
    )
    temp_destination = destination.with_suffix(destination.suffix + ".tmp")
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                temp_destination.write_bytes(response.read())
            temp_destination.replace(destination)
            return
        except (TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            with contextlib.suppress(FileNotFoundError):
                temp_destination.unlink()
            if attempt >= attempts:
                raise
            delay_seconds = retry_delay_seconds * attempt
            print(
                f"Download attempt {attempt}/{attempts} failed for {url}: {exc}. "
                f"Retrying in {delay_seconds} seconds.",
                file=sys.stderr,
            )
            if delay_seconds > 0:
                time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error


@contextlib.contextmanager
def deadline(seconds: int):
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    def handle_timeout(signum, frame):
        raise TimeoutError(f"Refresh exceeded {seconds} seconds.")

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, handle_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def dataset_counts(context: dict[str, object]) -> dict[str, int]:
    return {key: len(context.get(key, [])) for key in DATASET_KEYS}


def total_operational_rows(counts: dict[str, int]) -> int:
    return counts["incubation"] + counts["fruiting"] + counts["harvest"]


def load_dashboard_context(source: pathlib.Path) -> dict[str, object]:
    content = source.read_text(encoding="utf-8").strip()
    if not content.startswith(JS_PREFIX):
        raise ValueError(f"{source} does not contain DASHBOARD_CONTEXT.")
    payload = content[len(JS_PREFIX):].strip()
    if payload.endswith(";"):
        payload = payload[:-1]
    return json.loads(payload)


def resolve_baseline_path(raw_path: Optional[str], js_output: pathlib.Path) -> Optional[pathlib.Path]:
    if raw_path:
        return pathlib.Path(raw_path).resolve()

    default_path = (js_output.parent / DEFAULT_BASELINE_SUBPATH).resolve()
    if default_path.exists():
        return default_path

    if js_output.exists():
        return js_output

    return None


def validate_context(
    context: dict[str, object],
    min_rows: int,
    baseline_context: Optional[dict[str, object]] = None,
    min_row_ratio_vs_baseline: float = 0.5,
) -> dict[str, int]:
    counts = dataset_counts(context)
    empty_datasets = [name for name, count in counts.items() if count <= 0]
    if empty_datasets:
        raise SystemExit(
            "Parsed zero rows for required dataset(s): "
            + ", ".join(empty_datasets)
            + ". Refusing to publish."
        )

    total_rows = total_operational_rows(counts)
    if baseline_context is None:
        if total_rows < min_rows:
            raise SystemExit(
                f"Parsed only {total_rows} operational rows (<{min_rows}) with no baseline snapshot available. "
                "Refusing to publish."
            )
        return counts

    baseline_counts = dataset_counts(baseline_context)
    regressions = []
    for name, count in counts.items():
        previous = baseline_counts.get(name, 0)
        if previous <= 0:
            continue
        minimum_allowed = max(1, math.ceil(previous * min_row_ratio_vs_baseline))
        if count < minimum_allowed:
            regressions.append(
                f"{name}: {count} rows (previous {previous}, minimum allowed {minimum_allowed})"
            )

    if regressions:
        raise SystemExit(
            "Parsed row counts regressed too sharply versus the previous successful snapshot: "
            + "; ".join(regressions)
            + ". Refusing to publish."
        )

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch the latest Google Sheets workbook export and rebuild data.js.",
    )
    parser.add_argument(
        "--workbook-url",
        required=True,
        help="Direct XLSX export URL for the Google Sheets workbook.",
    )
    parser.add_argument(
        "--workbook-output",
        default="latest_workbook.xlsx",
        help="Local workbook snapshot path. Defaults to latest_workbook.xlsx.",
    )
    parser.add_argument(
        "--js-output",
        default="pages-deploy/data.js",
        help="Dashboard data payload output path. Defaults to pages-deploy/data.js.",
    )
    parser.add_argument(
        "--incubation-csv-url",
        help="Optional direct CSV export URL for the incubation tab, used to preserve date parsing fidelity.",
    )
    parser.add_argument(
        "--incubation-csv-output",
        default="latest_sheet.csv",
        help="Local incubation CSV snapshot path when --incubation-csv-url is used. Defaults to latest_sheet.csv.",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=60,
        help="Per-request timeout for workbook/CSV downloads. Defaults to 60 seconds.",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=200,
        help="Bootstrap-only floor for operational rows when no baseline snapshot exists.",
    )
    parser.add_argument(
        "--baseline-js-input",
        help="Existing successful dashboard snapshot used to validate row-count regressions. "
        "Defaults to pages-deploy/data.js when present.",
    )
    parser.add_argument(
        "--min-row-ratio-vs-baseline",
        type=float,
        default=0.5,
        help="Fail refresh if any dataset drops below this fraction of the baseline snapshot. Defaults to 0.5.",
    )
    parser.add_argument(
        "--download-attempts",
        type=int,
        default=3,
        help="Number of download attempts for each source before failing. Defaults to 3.",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=int,
        default=5,
        help="Base backoff delay between download retries. Defaults to 5 seconds.",
    )

    parser.add_argument(
        "--overall-timeout-seconds",
        type=int,
        default=300,
        help="Maximum total runtime for the refresh process. Defaults to 300 seconds.",
    )
    parser.add_argument(
        "--service-account-json",
        help="Path to Google service account JSON key file. Falls back to "
             "GOOGLE_SERVICE_ACCOUNT_JSON / GOOGLE_APPLICATION_CREDENTIALS env vars.",
    )
    args = parser.parse_args()

    workbook_output = pathlib.Path(args.workbook_output).resolve()
    js_output = pathlib.Path(args.js_output).resolve()
    incubation_csv_output = pathlib.Path(args.incubation_csv_output).resolve()
    baseline_js_input = resolve_baseline_path(args.baseline_js_input, js_output)

    if not 0 < args.min_row_ratio_vs_baseline <= 1:
        raise SystemExit("--min-row-ratio-vs-baseline must be between 0 and 1.")
    if args.download_attempts < 1:
        raise SystemExit("--download-attempts must be at least 1.")
    if args.retry_delay_seconds < 0:
        raise SystemExit("--retry-delay-seconds must be 0 or greater.")

    sa_json = _resolve_sa_json(args.service_account_json)

    with deadline(args.overall_timeout_seconds):
        if sa_json:
            print(f"Using service account: {sa_json}", file=sys.stderr)
            _download_xlsx_with_sa(args.workbook_url, workbook_output, sa_json)
        else:
            download_file(
                args.workbook_url,
                workbook_output,
                args.request_timeout_seconds,
                attempts=args.download_attempts,
                retry_delay_seconds=args.retry_delay_seconds,
            )
        csv_available = False
        if args.incubation_csv_url:
            if sa_json:
                csv_available = _download_csv_with_sa(args.incubation_csv_url, incubation_csv_output, sa_json)
            else:
                download_file(
                    args.incubation_csv_url,
                    incubation_csv_output,
                    args.request_timeout_seconds,
                    attempts=args.download_attempts,
                    retry_delay_seconds=args.retry_delay_seconds,
                )
                csv_available = True
        if csv_available:
            context = build_context(workbook_output, incubation_csv_path=incubation_csv_output)
        else:
            context = build_context(workbook_output)

    baseline_context = None
    if baseline_js_input and baseline_js_input.exists():
        try:
            baseline_context = load_dashboard_context(baseline_js_input)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(
                f"Warning: could not load baseline snapshot {baseline_js_input}: {exc}. "
                "Falling back to the bootstrap row floor.",
                file=sys.stderr,
            )

    counts = validate_context(
        context,
        args.min_rows,
        baseline_context=baseline_context,
        min_row_ratio_vs_baseline=args.min_row_ratio_vs_baseline,
    )
    write_data_js(js_output, context)

    print(
        "Downloaded "
        f"{workbook_output.name} and rebuilt {js_output.name} with "
        f"{counts['incubation']} incubation rows, "
        f"{counts['fruiting']} fruiting rows, "
        f"{counts['harvest']} harvest rows."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
