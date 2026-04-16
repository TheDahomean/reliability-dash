#!/usr/bin/env python3

import datetime as dt
import html
import json
import pathlib
import shutil
import subprocess
from collections import defaultdict
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent
PUBLIC_DIR = ROOT
TEMPLATE_PATH = ROOT / "index.template.html"
OUTPUT_HTML_PATH = ROOT / "index.html"
ROOT_DATA_JS_PATH = ROOT / "data.js"
PUBLIC_DATA_JS_PATH = ROOT / "data.js"
SNAPSHOT_DIR = PUBLIC_DIR / "data"
SNAPSHOT_PATH = SNAPSHOT_DIR / "opsdash_snapshot.json"
SNAPSHOT_META_PATH = SNAPSHOT_DIR / "opsdash_snapshot_meta.json"
STATUS_PATH = PUBLIC_DIR / "opsdash_status.json"

REFRESH_INTERVAL_MINUTES = 15
STALE_WARNING_MINUTES = REFRESH_INTERVAL_MINUTES * 3
STALE_ALERT_MINUTES = REFRESH_INTERVAL_MINUTES * 6
SOURCE_SPREADSHEET_ID = "1IlCrI_aPESNDtPZ9629GSCjsCBhTakxbMP9eTlgzxUg"
SOURCE_LOGS = {
    "bagging": "LOG 5",
    "pasteurization": "LOG 6",
    "incubation": "LOG 9 - Incubation Daily Check",
    "fruiting": "LOG 10 - Fruiting Room And Envi",
    "harvest": "LOG 11 - Harvest (Ccp 2)",
}
REQUIRED_PLACEHOLDERS = (
    "__SNAPSHOT_BANNER__",
    "__SNAPSHOT_HERO_META__",
    "__SNAPSHOT_FILTER_OPTIONS__",
    "__SNAPSHOT_FOCUS_STATUS__",
    "__SNAPSHOT_KPIS__",
    "__SNAPSHOT_HARVEST_CONSISTENCY__",
    "__SNAPSHOT_PIPELINE__",
    "__SNAPSHOT_RISK_SUMMARY__",
    "__SNAPSHOT_VENDOR_STABILITY__",
    "__SNAPSHOT_FOCUSED_BATCH_HIDDEN__",
    "__SNAPSHOT_FOCUSED_BATCH_SUMMARY__",
    "__SNAPSHOT_FOCUSED_BATCH_CARDS__",
    "__SNAPSHOT_PRODUCTION_SUMMARY__",
    "__SNAPSHOT_PRODUCTION_CARDS__",
    "__SNAPSHOT_YIELD_SUMMARY__",
    "__SNAPSHOT_YIELD_BRIDGE__",
    "__SNAPSHOT_VENDOR_SUMMARY__",
    "__SNAPSHOT_VENDOR_CARDS__",
    "__SNAPSHOT_TIMELINE__",
    "__SNAPSHOT_REMOVALS__",
    "__SNAPSHOT_DAILY_HARVEST__",
    "__SNAPSHOT_BATCH_CARDS__",
    "__SNAPSHOT_EVENTS__",
    "__SNAPSHOT_FOOTER__",
    "__SNAPSHOT_META_JSON__",
)


def load_context_from_data_js(source: pathlib.Path) -> dict[str, Any]:
    if not source.exists():
        raise SystemExit(f"Snapshot source missing: {source}")
    prefix = "window.DASHBOARD_CONTEXT = "
    content = source.read_text(encoding="utf-8").strip()
    if not content.startswith(prefix):
        raise SystemExit(f"Snapshot source is not DASHBOARD_CONTEXT JS: {source}")
    payload = content[len(prefix):].strip()
    if payload.endswith(";"):
        payload = payload[:-1]
    try:
        context = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse snapshot source {source}: {exc}") from exc
    if not isinstance(context, dict):
        raise SystemExit(f"Unexpected snapshot structure in {source}")
    return context


def iso_to_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def iso_to_datetime(value: str) -> dt.datetime:
    if value.endswith("Z"):
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def fmt_date(value: str) -> str:
    if not value:
        return "Unknown date"
    parsed = iso_to_date(value)
    return parsed.strftime("%-d %b %Y")


def fmt_datetime(value: str, tz_name: str) -> str:
    parsed = iso_to_datetime(value)
    tz = dt.timezone.utc if tz_name == "UTC" else dt.timezone(dt.timedelta(hours=3 if tz_name == "EAT" else -4))
    localized = parsed.astimezone(tz)
    return localized.strftime("%-d %b %Y, %-I:%M %p")


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def card(label: str, value: str, note: str, tone: str) -> str:
    return (
        f'<article class="yield-summary-card {tone}">'
        f'<p class="section-label">{escape(label)}</p>'
        f'<div class="kpi-value">{escape(value)}</div>'
        f'<div class="kpi-note">{escape(note)}</div>'
        "</article>"
    )


def kpi_card(label: str, value: str, note: str, tone: str) -> str:
    return (
        f'<article class="panel kpi {tone}">'
        f'<p class="section-label">{escape(label)}</p>'
        f'<div class="kpi-value">{escape(value)}</div>'
        f'<div class="kpi-note">{escape(note)}</div>'
        "</article>"
    )


def yield_card(title: str, body: str, tone: str = "stage-incubation", full_span: bool = False) -> str:
    span_class = " full-span" if full_span else ""
    return (
        f'<article class="yield-card {tone}{span_class}">'
        f'<div class="yield-title">{escape(title)}</div>'
        f'<div class="yield-note">{body}</div>'
        "</article>"
    )


def batch_card(batch: str, latest: dict[str, Any], note: str) -> str:
    tone = "stage-contamination" if latest.get("contamination") or latest.get("smell") else "stage-incubation"
    risk = "watch" if tone == "stage-contamination" else str(latest.get("growth", "Unknown"))
    return (
        f'<article class="batch-card {tone}">'
        "<header>"
        f'<div class="batch-title">{escape(batch)}</div>'
        f'<span class="pill">{escape(risk)}</span>'
        "</header>"
        '<div class="mini-stats">'
        f'<div><strong>Day {escape(latest.get("day", "N/A"))}</strong> Latest incubation day</div>'
        f'<div><strong>{escape(latest.get("removed", 0))}</strong> Removed on latest row</div>'
        f'<div><strong>{escape(fmt_date(latest.get("date", "")))}</strong> Latest checkpoint</div>'
        "</div>"
        f'<p class="focus-note">{note}</p>'
        "</article>"
    )


def event_row(date_text: str, title: str, note: str, score: str) -> str:
    return (
        '<div class="event-row">'
        f'<div class="event-date">{escape(date_text)}</div>'
        f'<div class="event-main">{escape(title)}<div class="event-sub">{escape(note)}</div></div>'
        f'<div class="event-score">{escape(score)}</div>'
        "</div>"
    )


def chart_items(items: list[tuple[str, str]]) -> str:
    if not items:
        return '<div class="snapshot-static-note">No snapshot rows available.</div>'
    return "".join(
        (
            '<div class="snapshot-chart-item">'
            f"<strong>{escape(title)}</strong>"
            f"<div>{escape(detail)}</div>"
            "</div>"
        )
        for title, detail in items
    )


def normalize_fruiting_lot_id(value: str) -> str:
    text = str(value or "")
    if text.startswith("FR-") and text.count("-") >= 2:
        parts = text.split("-", 2)
        if len(parts) == 3 and "/" in parts[2]:
            return f"{parts[0]}-{parts[1]}/{parts[2]}"
    return text


def has_meaningful_text(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text and text != "-" and text != '"')


def clip_sentence(value: Any, fallback: str = "No current issue note.") -> str:
    text = str(value or "").strip()
    if not has_meaningful_text(text):
        return fallback
    for stop in (". ", "! ", "? "):
        if stop in text:
            return text.split(stop, 1)[0].strip().strip('"')
    return text.strip().strip('"')


def format_pct(value: float) -> str:
    return f"{max(0.0, value):.1f}%"


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def standard_deviation(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = mean(values)
    return (sum((value - avg) ** 2 for value in values) / len(values)) ** 0.5


def decision_inline_metric(value: str, label: str) -> str:
    return (
        '<div class="decision-inline-card">'
        f'<div class="decision-inline-value">{escape(value)}</div>'
        f'<div class="decision-inline-label">{escape(label)}</div>'
        "</div>"
    )


def decision_panel_markup(highlight_value: str, highlight_label: str, metrics: list[str], bullets: list[str]) -> str:
    return (
        '<div class="decision-highlight">'
        f'<div class="decision-highlight-value">{escape(highlight_value)}</div>'
        f'<div class="decision-highlight-label">{escape(highlight_label)}</div>'
        "</div>"
        '<div class="decision-inline-metrics">'
        + "".join(metrics)
        + "</div>"
        + '<div class="decision-list">'
        + "".join(f'<div class="decision-list-item">{escape(item)}</div>' for item in bullets)
        + "</div>"
    )


def expected_bags(substrate_type: str, bag_size: str) -> int:
    substrate = str(substrate_type or "").lower().replace(" ", "")
    size = str(bag_size or "").lower().replace(" ", "")
    if "wheat" in substrate and size.startswith("1"):
        return 316
    if "cotton" in substrate and size.startswith("2"):
        return 125
    return 125


def extract_public_snapshot_inputs(context: dict[str, Any]) -> dict[str, Any]:
    rows = sorted(context.get("incubation", []), key=lambda row: (row.get("date", ""), int(row.get("day", 0))))
    bagging_rows = list(context.get("bagging", []))
    pasteurization_rows = list(context.get("pasteurization", []))
    fruiting_rows = list(context.get("fruiting", []))
    harvest_rows = list(context.get("harvest", []))

    if not rows:
        raise SystemExit("Snapshot build failed: incubation rows are empty.")

    required_lists = {
        "bagging": bagging_rows,
        "pasteurization": pasteurization_rows,
        "incubation": rows,
        "fruiting": fruiting_rows,
        "harvest": harvest_rows,
    }
    empty_sections = [name for name, values in required_lists.items() if len(values) == 0]
    if empty_sections:
        raise SystemExit(f"Snapshot build failed: required logs empty: {', '.join(empty_sections)}")

    return {
        "rows": rows,
        "bagging_rows": bagging_rows,
        "pasteurization_rows": pasteurization_rows,
        "fruiting_rows": fruiting_rows,
        "harvest_rows": harvest_rows,
        "required_lists": required_lists,
        "grouped_batches": by_batch(rows),
        "row_counts": {name: len(values) for name, values in required_lists.items()},
    }


def build_reliability_model(
    rows: list[dict[str, Any]],
    pasteurization_rows: list[dict[str, Any]],
    bagging_rows: list[dict[str, Any]],
    fruiting_rows: list[dict[str, Any]],
    harvest_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    production_by_base: dict[str, int] = {}
    for index, row in enumerate(pasteurization_rows):
        actual_bags = int((bagging_rows[index].get("bagsFilled", 0) or 0)) if index < len(bagging_rows) else 0
        production_by_base[row.get("batchNorm", "")] = actual_bags or expected_bags(row.get("substrateType", ""), row.get("bagSize", ""))

    latest_variants: dict[str, dict[str, Any]] = {}
    base_contexts: dict[str, dict[str, Any]] = {}
    fruiting_latest_by_lot: dict[str, dict[str, Any]] = {}
    harvest_by_lot: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def ensure_base_context(base_batch: str) -> dict[str, Any]:
        if base_batch not in base_contexts:
            base_contexts[base_batch] = {
                "base_batch": base_batch,
                "latest_date": "",
                "latest_day": 0,
                "latest_growth": "Unknown",
                "latest_smell": False,
                "latest_contam": False,
                "vendors": set(),
                "latest_variants": [],
                "logged_bags": 0,
                "prepared_bags": 0,
                "total_removed": 0,
                "total_alerts": 0,
                "fruiting_lots": set(),
            }
        return base_contexts[base_batch]

    for row in rows:
        base_batch = row.get("baseBatch") or row.get("batchNorm", "")
        context = ensure_base_context(base_batch)
        context["total_removed"] += int(row.get("removed", 0) or 0)
        context["total_alerts"] += int(bool(row.get("contamination"))) + int(bool(row.get("smell")))
        if (row.get("date", ""), int(row.get("day", 0) or 0)) >= (context["latest_date"], context["latest_day"]):
            context["latest_date"] = row.get("date", "")
            context["latest_day"] = int(row.get("day", 0) or 0)
            context["latest_growth"] = row.get("growth", "Unknown")
            context["latest_smell"] = bool(row.get("smell"))
            context["latest_contam"] = bool(row.get("contamination"))
        batch_norm = row.get("batchNorm", "")
        previous = latest_variants.get(batch_norm)
        if previous is None or (row.get("date", ""), int(row.get("day", 0) or 0)) >= (previous.get("date", ""), int(previous.get("day", 0) or 0)):
            latest_variants[batch_norm] = row

    for row in latest_variants.values():
        base_batch = row.get("baseBatch") or row.get("batchNorm", "")
        context = ensure_base_context(base_batch)
        context["logged_bags"] += int(row.get("bagCount", 0) or 0)
        context["latest_variants"].append(row)
        if row.get("vendor"):
            context["vendors"].add(row.get("vendor"))

    normalized_fruiting_rows = [
        {**row, "fruitingLot": normalize_fruiting_lot_id(row.get("fruitingLot", ""))}
        for row in fruiting_rows
    ]
    normalized_harvest_rows = [
        {**row, "fruitingLot": normalize_fruiting_lot_id(row.get("fruitingLot", ""))}
        for row in harvest_rows
    ]

    for row in normalized_fruiting_rows:
        lot_id = row.get("fruitingLot", "")
        existing = fruiting_latest_by_lot.get(lot_id)
        if existing is None or row.get("date", "") > existing.get("date", ""):
            fruiting_latest_by_lot[lot_id] = row

    for row in normalized_harvest_rows:
        harvest_by_lot[row.get("fruitingLot", "")].append(row)

    for lot_id, row in fruiting_latest_by_lot.items():
        for base_batch in row.get("sourceBatchIds", []):
            ensure_base_context(base_batch)["fruiting_lots"].add(lot_id)

    for base_batch, context in base_contexts.items():
        context["prepared_bags"] = production_by_base.get(base_batch, 0) or context["logged_bags"]

    latest_harvest_date_text = max((row.get("date", "") for row in normalized_harvest_rows), default="")
    anchor_date = iso_to_date(latest_harvest_date_text) if latest_harvest_date_text else iso_to_datetime(generated_at).date()
    active_fruiting_lots = []
    for lot_id, row in fruiting_latest_by_lot.items():
        harvest_entries = harvest_by_lot.get(lot_id, [])
        latest_signal = max([entry.get("date", "") for entry in harvest_entries] + [row.get("date", "")] or [""])
        if latest_signal and (anchor_date - iso_to_date(latest_signal)).days <= 7:
            active_fruiting_lots.append(lot_id)

    harvested_base_batches: set[str] = set()
    for lot_id, row in fruiting_latest_by_lot.items():
        if harvest_by_lot.get(lot_id):
            for base_batch in row.get("sourceBatchIds", []):
                harvested_base_batches.add(base_batch)

    total_harvested_kg = sum(float(row.get("quantityHarvestedKg", 0) or 0) for row in normalized_harvest_rows)
    linked_prepared_bags = sum(int(base_contexts.get(base_batch, {}).get("prepared_bags", 0) or 0) for base_batch in harvested_base_batches)
    kg_per_prepared_bag = (total_harvested_kg / linked_prepared_bags) if linked_prepared_bags else 0.205

    recent_harvest_rows_7 = [
        row for row in normalized_harvest_rows
        if latest_harvest_date_text and (anchor_date - iso_to_date(row.get("date", latest_harvest_date_text))).days <= 6
    ]
    recent_harvest_rows_14 = [
        row for row in normalized_harvest_rows
        if latest_harvest_date_text and (anchor_date - iso_to_date(row.get("date", latest_harvest_date_text))).days <= 13
    ]
    recent_harvest_7_kg = sum(float(row.get("quantityHarvestedKg", 0) or 0) for row in recent_harvest_rows_7)
    recent_harvest_14_kg = sum(float(row.get("quantityHarvestedKg", 0) or 0) for row in recent_harvest_rows_14)
    recent_rejected_14_kg = sum(float(row.get("quantityRejectedKg", 0) or 0) for row in recent_harvest_rows_14)
    recent_accepted_14_kg = max(recent_harvest_14_kg - recent_rejected_14_kg, 0.0)
    acceptance_rate = (recent_accepted_14_kg / recent_harvest_14_kg * 100) if recent_harvest_14_kg else 0.0
    rejection_rate = (recent_rejected_14_kg / recent_harvest_14_kg * 100) if recent_harvest_14_kg else 0.0

    daily_harvest_map: dict[str, dict[str, Any]] = {}
    for row in normalized_harvest_rows:
        day_key = row.get("date", "")
        if day_key not in daily_harvest_map:
            daily_harvest_map[day_key] = {"date": day_key, "harvested_kg": 0.0}
        daily_harvest_map[day_key]["harvested_kg"] += float(row.get("quantityHarvestedKg", 0) or 0)
    daily_harvest = [daily_harvest_map[key] for key in sorted(daily_harvest_map)]
    recent_daily_7 = daily_harvest[-7:]
    recent_daily_14 = daily_harvest[-14:]
    recent_7_values = [entry["harvested_kg"] for entry in recent_daily_7]
    average_daily_7 = mean(recent_7_values)
    deviation_daily_7 = standard_deviation(recent_7_values)
    volatility_7 = (deviation_daily_7 / average_daily_7) if average_daily_7 else 0.0
    consistency_label = "Stable" if volatility_7 <= 0.18 else "Watch" if volatility_7 <= 0.32 else "Volatile"

    base_entries = []
    for context in base_contexts.values():
        base_entries.append(
            {
                **context,
                "vendor_list": sorted(context["vendors"]),
                "fruiting_lot_list": sorted(context["fruiting_lots"]),
            }
        )

    excluded_entries = [
        context for context in base_entries
        if context["prepared_bags"] and context["total_removed"] >= max(context["prepared_bags"] * 0.9, context["logged_bags"] * 0.9)
    ]
    excluded_base_batches = {context["base_batch"] for context in excluded_entries}
    near_harvest_entries = [
        context for context in base_entries
        if not context["fruiting_lot_list"] and context["latest_day"] >= 13 and context["base_batch"] not in excluded_base_batches
    ]
    early_pipeline_entries = [
        context for context in base_entries
        if not context["fruiting_lot_list"] and 0 < context["latest_day"] < 13 and context["base_batch"] not in excluded_base_batches
    ]
    fruiting_base_batches = {
        base_batch
        for lot_id in active_fruiting_lots
        for base_batch in fruiting_latest_by_lot.get(lot_id, {}).get("sourceBatchIds", [])
    }
    active_fruiting_bags = sum(int(base_contexts.get(base_batch, {}).get("prepared_bags", 0) or 0) for base_batch in fruiting_base_batches)
    near_harvest_bags = sum(int(context["prepared_bags"] or 0) for context in near_harvest_entries)
    early_pipeline_bags = sum(int(context["prepared_bags"] or 0) for context in early_pipeline_entries)
    watched_near_harvest_bags = sum(
        int(context["prepared_bags"] or 0)
        for context in near_harvest_entries
        if context["latest_smell"] or context["latest_contam"]
    )

    active_fruiting_issue_row = next(
        (
            fruiting_latest_by_lot[lot_id]
            for lot_id in active_fruiting_lots
            if has_meaningful_text(fruiting_latest_by_lot[lot_id].get("issuesObserved")) or has_meaningful_text(fruiting_latest_by_lot[lot_id].get("actionTaken"))
        ),
        None,
    )
    open_flagged_batch_count = sum(
        1
        for context in base_entries
        if not context["fruiting_lot_list"] and (context["latest_smell"] or context["latest_contam"])
    )
    service_risk_score = 0
    if len(active_fruiting_lots) <= 1:
        service_risk_score += 2 if active_fruiting_lots else 1
    if active_fruiting_issue_row:
        service_risk_score += 1
    if watched_near_harvest_bags >= 150:
        service_risk_score += 1
    if open_flagged_batch_count >= 2:
        service_risk_score += 1
    if rejection_rate > 2 or acceptance_rate < 98:
        service_risk_score += 1
    if service_risk_score >= 4:
        service_risk = {"level": "High", "tone": "stage-contamination", "multiplier": 0.82}
    elif service_risk_score >= 2:
        service_risk = {"level": "Med", "tone": "stage-fruiting", "multiplier": 0.90}
    else:
        service_risk = {"level": "Low", "tone": "stage-harvest", "multiplier": 0.95}
    issue_multiplier = 0.92 if active_fruiting_issue_row else 1.0

    def stage_risk_multiplier(context: dict[str, Any]) -> float:
        if context["base_batch"] in excluded_base_batches:
            return 0.0
        if context["latest_contam"]:
            return 0.55
        if context["latest_smell"]:
            return 0.88
        return 0.95

    def next_7_share(context: dict[str, Any]) -> float:
        if context["latest_day"] >= 17:
            return 0.15
        if context["latest_day"] >= 15:
            return 0.05
        return 0.0

    def next_14_share(context: dict[str, Any]) -> float:
        if context["latest_day"] >= 17:
            return 0.40
        if context["latest_day"] >= 15:
            return 0.30
        if context["latest_day"] >= 13:
            return 0.22
        return 0.0

    near_harvest_7_kg = sum(
        context["prepared_bags"] * kg_per_prepared_bag * next_7_share(context) * stage_risk_multiplier(context)
        for context in near_harvest_entries
    )
    near_harvest_14_kg = sum(
        context["prepared_bags"] * kg_per_prepared_bag * next_14_share(context) * stage_risk_multiplier(context)
        for context in near_harvest_entries
    )
    available_7_kg = (recent_harvest_7_kg * service_risk["multiplier"] * issue_multiplier) + near_harvest_7_kg
    available_14_kg = (recent_harvest_7_kg * 1.25 * service_risk["multiplier"] * issue_multiplier) + near_harvest_14_kg
    weekly_moq_kg = min(available_7_kg, recent_harvest_7_kg or available_7_kg)

    risk_factors = []
    if len(active_fruiting_lots) <= 1:
        risk_factors.append(f"{len(active_fruiting_lots)} live fruiting lot{'s' if len(active_fruiting_lots) != 1 else ''} is carrying current shipment cadence.")
    if watched_near_harvest_bags > 0:
        risk_factors.append(f"{watched_near_harvest_bags} near-harvest bags are on smell or contamination watch before they can support the next promise window.")
    if active_fruiting_issue_row:
        risk_factors.append(
            f"Latest fruiting note on {fmt_date(active_fruiting_issue_row.get('date', ''))}: "
            f"{clip_sentence(active_fruiting_issue_row.get('issuesObserved') or active_fruiting_issue_row.get('actionTaken'))}."
        )
    elif excluded_entries:
        risk_factors.append(
            f"{sum(int(entry['prepared_bags'] or 0) for entry in excluded_entries)} prepared bags from failed batches are excluded from ATP rather than rolled forward."
        )

    vendor_exposure: dict[str, int] = defaultdict(int)
    watched_vendor_exposure: dict[str, int] = defaultdict(int)
    for context in [*near_harvest_entries, *early_pipeline_entries]:
        for row in context["latest_variants"]:
            vendor = row.get("vendor") or "Unknown"
            vendor_exposure[vendor] += int(row.get("bagCount", 0) or 0)
            if row.get("smell") or row.get("contamination"):
                watched_vendor_exposure[vendor] += int(row.get("bagCount", 0) or 0)
    vendor_exposure_list = sorted(vendor_exposure.items(), key=lambda item: item[1], reverse=True)
    current_vendor_total = sum(value for _vendor, value in vendor_exposure_list)
    top_vendor_exposure = sum(value for _vendor, value in vendor_exposure_list[:2])
    systemic_vendor_driver = (
        f"Current watch flags cut across {', '.join(watched_vendor_exposure.keys())}, which points to room conditions rather than a single-vendor miss."
        if len(watched_vendor_exposure) >= 2
        else (
            f"{vendor_exposure_list[0][0]} carries the largest share of open bags in the current promise window."
            if vendor_exposure_list
            else "No vendor-tagged open pipeline is available."
        )
    )
    service_risk_driver = (
        f"{service_risk['level']} because one live fruiting lot is carrying current shipments while {watched_near_harvest_bags} near-harvest bags remain on watch."
        if len(active_fruiting_lots) <= 1
        else f"{service_risk['level']} because multiple active watch flags are still open in the near-harvest pipeline."
    )

    return {
        "available_7_kg": available_7_kg,
        "available_14_kg": available_14_kg,
        "weekly_moq_kg": weekly_moq_kg,
        "acceptance_rate": acceptance_rate,
        "rejection_rate": rejection_rate,
        "recent_accepted_14_kg": recent_accepted_14_kg,
        "recent_rejected_14_kg": recent_rejected_14_kg,
        "recent_harvest_7_kg": recent_harvest_7_kg,
        "recent_harvest_14_kg": recent_harvest_14_kg,
        "latest_harvest_date_text": latest_harvest_date_text,
        "kg_per_prepared_bag": kg_per_prepared_bag,
        "service_risk": service_risk,
        "service_risk_driver": service_risk_driver,
        "consistency_label": consistency_label,
        "average_daily_7": average_daily_7,
        "deviation_daily_7": deviation_daily_7,
        "volatility_7": volatility_7,
        "recent_daily_7": recent_daily_7,
        "active_fruiting_lots": active_fruiting_lots,
        "active_fruiting_bags": active_fruiting_bags,
        "near_harvest_entries": near_harvest_entries,
        "near_harvest_bags": near_harvest_bags,
        "early_pipeline_entries": early_pipeline_entries,
        "early_pipeline_bags": early_pipeline_bags,
        "watched_near_harvest_bags": watched_near_harvest_bags,
        "excluded_entries": excluded_entries,
        "risk_factors": risk_factors[:3],
        "vendor_exposure_list": vendor_exposure_list,
        "watched_vendor_exposure": watched_vendor_exposure,
        "systemic_vendor_driver": systemic_vendor_driver,
        "top_vendor_exposure": top_vendor_exposure,
        "current_vendor_total": current_vendor_total,
    }


def build_version() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        sha = "unknown"
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return f"{sha}{'+dirty' if dirty else ''}"


def latest_batch(rows: list[dict[str, Any]]) -> str:
    ranked = sorted(
        rows,
        key=lambda row: (row.get("date", ""), int(row.get("day", 0)), row.get("batchNorm", "")),
    )
    return ranked[-1]["batchNorm"] if ranked else "all"


def by_batch(rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["batchNorm"]].append(row)
    return sorted(
        (
            batch,
            sorted(entries, key=lambda row: (row.get("date", ""), int(row.get("day", 0)))),
        )
        for batch, entries in grouped.items()
    )


def refresh_health(generated_at: str) -> dict[str, Any]:
    generated = iso_to_datetime(generated_at)
    now = dt.datetime.now(dt.timezone.utc)
    age_minutes = max(0, round((now - generated).total_seconds() / 60))
    if age_minutes >= STALE_ALERT_MINUTES:
        return {
            "ok": False,
            "banner_class": "alert",
            "label": f"Snapshot is overdue by {format_age(age_minutes)}",
        }
    if age_minutes >= STALE_WARNING_MINUTES:
        return {
            "ok": False,
            "banner_class": "warning",
            "label": f"Snapshot is delayed by {format_age(age_minutes)}",
        }
    return {
        "ok": True,
        "banner_class": "",
        "label": f"Snapshot refreshed {format_age(age_minutes)} ago" if age_minutes else "Snapshot refreshed just now",
    }


def format_age(minutes: int) -> str:
    if minutes <= 0:
        return "just now"
    hours, rem = divmod(minutes, 60)
    if hours and rem:
        return f"{hours}h {rem}m"
    if hours:
        return f"{hours}h"
    return f"{rem}m"


def build_public_payload(context: dict[str, Any], version: str) -> tuple[dict[str, Any], dict[str, str]]:
    snapshot = extract_public_snapshot_inputs(context)
    rows = snapshot["rows"]
    bagging_rows = snapshot["bagging_rows"]
    pasteurization_rows = snapshot["pasteurization_rows"]
    fruiting_rows = snapshot["fruiting_rows"]
    harvest_rows = snapshot["harvest_rows"]
    required_lists = snapshot["required_lists"]
    selected_batch = "all"
    grouped_batches = snapshot["grouped_batches"]
    refresh = refresh_health(context["generatedAt"])
    model = build_reliability_model(rows, pasteurization_rows, bagging_rows, fruiting_rows, harvest_rows, context["generatedAt"])

    row_counts = snapshot["row_counts"]
    batch_count = len(grouped_batches)
    vendors = sorted({row.get("vendor", "") for row in rows if row.get("vendor")})
    total_harvest_kg = sum(float(row.get("quantityHarvestedKg", 0) or 0) for row in harvest_rows)
    total_rejected_kg = sum(float(row.get("quantityRejectedKg", 0) or 0) for row in harvest_rows)
    total_bags_filled = sum(int(row.get("bagsFilled", 0) or 0) for row in bagging_rows)
    meta = {
        "generated_at": context["generatedAt"],
        "source_type": "google_sheets_workbook_export",
        "source_sheet": {
            "spreadsheet_id": SOURCE_SPREADSHEET_ID,
            "logs": SOURCE_LOGS,
        },
        "row_counts": row_counts,
        "selected_batch": "all",
        "build_version": version,
        "refresh_interval_minutes": REFRESH_INTERVAL_MINUTES,
    }

    tags = [
        f'<span class="tag">Harvest through {escape(fmt_date(model["latest_harvest_date_text"]))}</span>' if model["latest_harvest_date_text"] else '<span class="tag">Harvest through N/A</span>',
        f'<span class="tag {refresh["banner_class"]}">{escape(refresh["label"])}</span>',
        f'<span class="tag">Snapshot EAT {escape(fmt_datetime(context["generatedAt"], "EAT"))} | ET {escape(fmt_datetime(context["generatedAt"], "ET"))}</span>',
    ]

    filter_options = ['<option value="all" selected="selected">All batches</option>']
    for batch, _entries in grouped_batches:
        filter_options.append(f'<option value="{escape(batch)}">{escape(batch)}</option>')

    focus_status = [
        '<span class="focus-chip muted">Portfolio promise: all batches</span>',
        f'<span class="focus-chip{" " + refresh["banner_class"] if refresh["banner_class"] else ""}">{escape(refresh["label"])}</span>',
        f'<span class="focus-chip muted">Build {escape(version)}</span>',
    ]

    kpis = [
        kpi_card("Available-to-promise kg (next 7 days)", f"{model['available_7_kg']:.1f} kg", "Risk-adjusted from the live fruiting run-rate, with only day-17+ pipeline pulled forward.", "stage-harvest"),
        kpi_card("Available-to-promise kg (next 14 days)", f"{model['available_14_kg']:.1f} kg", f"Adds a conservative share of day-13+ pipeline at {model['kg_per_prepared_bag'] * 100:.1f} kg per 100 prepared bags.", "stage-fruiting"),
        kpi_card("Minimum Reliable Weekly MOQ", f"{model['weekly_moq_kg']:.1f} kg", "Set as the lower of recent shipped week and current next-7 ATP.", "stage-incubation"),
        kpi_card("Acceptance quality rate / rejection rate (recent)", f"{format_pct(model['acceptance_rate'])} / {format_pct(model['rejection_rate'])}", f"{model['recent_accepted_14_kg']:.1f} kg accepted in the last 14 days | {model['recent_rejected_14_kg']:.1f} kg rejected.", "stage-harvest" if model["rejection_rate"] <= 2 else "stage-contamination"),
        kpi_card("Service-risk flag", model["service_risk"]["level"], model["service_risk_driver"], model["service_risk"]["tone"]),
    ]

    recent_daily_values = [entry["harvested_kg"] for entry in model["recent_daily_7"]]
    recent_daily_low = min(recent_daily_values) if recent_daily_values else 0.0
    recent_daily_high = max(recent_daily_values) if recent_daily_values else 0.0
    excluded_bags = sum(int(entry["prepared_bags"] or 0) for entry in model["excluded_entries"])
    top_vendor_one = model["vendor_exposure_list"][0] if model["vendor_exposure_list"] else ("N/A", 0)
    top_vendor_two = model["vendor_exposure_list"][1] if len(model["vendor_exposure_list"]) > 1 else ("N/A", 0)
    top_vendor_share = (model["top_vendor_exposure"] / model["current_vendor_total"] * 100) if model["current_vendor_total"] else 0.0

    harvest_consistency = decision_panel_markup(
        model["consistency_label"],
        "Recent harvest cadence",
        [
            decision_inline_metric(f"{model['average_daily_7']:.1f} kg", "7-day daily average"),
            decision_inline_metric(format_pct(model["volatility_7"] * 100), "7-day volatility"),
        ],
        [
            f"{model['recent_harvest_14_kg']:.1f} kg shipped in the last 14 harvest days.",
            f"The last 7 days ranged from {recent_daily_low:.1f} kg to {recent_daily_high:.1f} kg per day.",
            f"Standard deviation is {model['deviation_daily_7']:.1f} kg per day, which reads as {model['consistency_label'].lower()} cadence.",
        ],
    )

    pipeline_summary = decision_panel_markup(
        f"{len(model['active_fruiting_lots'])} live lot{'s' if len(model['active_fruiting_lots']) != 1 else ''}",
        "Current shipment engine",
        [
            decision_inline_metric(f"{len(model['near_harvest_entries'])} batches / {model['near_harvest_bags']} bags", "Day-13+ near harvest"),
            decision_inline_metric(f"{len(model['early_pipeline_entries'])} batches / {model['early_pipeline_bags']} bags", "Too early for ATP"),
        ],
        [
            f"{model['recent_harvest_7_kg']:.1f} kg harvested in the last 7 days from the live fruiting lot.",
            f"{len(model['near_harvest_entries'])} base batches are close enough to count conservatively in next-14 ATP.",
            f"{excluded_bags} bags from failed batches are excluded from the promise rather than treated as pending supply.",
        ],
    )

    risk_summary = decision_panel_markup(
        f"{len(model['risk_factors'])} watch factor{'s' if len(model['risk_factors']) != 1 else ''}",
        "Current supply risks",
        [
            decision_inline_metric(f"{model['watched_near_harvest_bags']} bags", "Near-harvest on watch"),
            decision_inline_metric(str(len(model["active_fruiting_lots"])), "Live lots carrying supply"),
        ],
        model["risk_factors"] or ["No open risk factor is currently stronger than the baseline service assumptions."],
    )

    vendor_stability = decision_panel_markup(
        "Systemic watch" if len(model["watched_vendor_exposure"]) >= 2 else f"{len(model['vendor_exposure_list'])} active vendors",
        "Vendor effect on current promise",
        [
            decision_inline_metric(f"{top_vendor_one[0]} {top_vendor_one[1]} bags", "Largest open exposure"),
            decision_inline_metric(f"{top_vendor_two[0]} {top_vendor_two[1]} bags", "Second-largest exposure"),
        ],
        [
            f"{top_vendor_one[0]} and {top_vendor_two[0]} account for {format_pct(top_vendor_share)} of open pipeline bags that matter to the next promise window.",
            model["systemic_vendor_driver"],
            f"{excluded_bags} bags from failed batches remain excluded from ATP instead of inflating the vendor promise." if excluded_bags else "No excluded vendor failure is inflating the current ATP number.",
        ],
    )

    focused_summary: list[str] = []
    focused_cards: list[str] = []

    latest_pasteurization = sorted(
        pasteurization_rows,
        key=lambda row: (row.get("date", ""), row.get("batchNorm", "")),
    )[-1]
    production_summary = [
        card("Bagging rows", str(len(bagging_rows)), f"{total_bags_filled} total bags filled across the latest snapshot.", "stage-incubation"),
        card("Pasteurization rows", str(len(pasteurization_rows)), f"Latest batch {latest_pasteurization.get('batchNorm', latest_pasteurization.get('batch', 'N/A'))}.", "stage-incubation"),
        card("Bag-size mix", str(len({row.get('targetWeight', '') for row in bagging_rows if row.get('targetWeight')})), "Distinct bagging targets observed in LOG 5.", "stage-incubation"),
    ]
    production_cards = [
        yield_card(
            f"{row.get('batchNorm', row.get('batch', 'Unknown'))} | {fmt_date(row.get('date', ''))}",
            f"{row.get('substrateType', 'Unknown substrate')} | {row.get('bagSize', 'Unknown size')} | critical limit {'met' if row.get('criticalLimitMet') else 'flagged'} | disposition {row.get('disposition') or 'unspecified'}.",
            "stage-incubation" if row.get("criticalLimitMet") else "stage-contamination",
        )
        for row in sorted(pasteurization_rows, key=lambda item: (item.get("date", ""), item.get("batchNorm", "")))[-4:]
    ]

    recent_harvest = sorted(harvest_rows, key=lambda row: row.get("date", ""))[-5:]
    yield_summary = [
        card("Harvest lots", str(len({row.get('harvestLot', '') for row in harvest_rows if row.get('harvestLot')})), "Distinct harvest lots observed in the snapshot.", "stage-harvest"),
        card("Fruiting lots", str(len({row.get('fruitingLot', '') for row in fruiting_rows if row.get('fruitingLot')})), "Distinct fruiting lots feeding the yield bridge.", "stage-fruiting"),
        card("Latest harvest date", fmt_date(recent_harvest[-1].get("date", "")), f"{recent_harvest[-1].get('quantityHarvestedKg', 0):.2f} kg harvested on the latest row.", "stage-harvest"),
    ]
    yield_bridge_cards = [
        yield_card(
            f"{row.get('harvestLot', 'Unknown harvest lot')} -> {row.get('fruitingLot', 'Unknown fruiting lot')}",
            f"{row.get('quantityHarvestedKg', 0):.2f} kg harvested | rejected {row.get('quantityRejectedKg', 0):.2f} kg | strain {row.get('strain') or 'unspecified'}.",
            "stage-harvest",
        )
        for row in recent_harvest
    ]

    vendor_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        vendor_groups[row.get("vendor") or "Unassigned"].append(row)
    vendor_summary = [
        card("Active vendors", str(len(vendor_groups)), "Vendors derived from incubation batch suffixes.", "stage-fruiting"),
        card("Vendor with most rows", max(vendor_groups, key=lambda vendor: len(vendor_groups[vendor])), "By incubation row count in the current snapshot.", "stage-fruiting"),
        card("Row distribution", ", ".join(f"{vendor}: {len(entries)}" for vendor, entries in sorted(vendor_groups.items())[:3]), "Top three vendor row counts.", "stage-fruiting"),
    ]
    vendor_cards = []
    for vendor, entries in sorted(vendor_groups.items(), key=lambda item: len(item[1]), reverse=True):
        latest_vendor = sorted(entries, key=lambda row: (row.get("date", ""), int(row.get("day", 0))))[-1]
        vendor_cards.append(
            yield_card(
                vendor,
                f"{len(entries)} incubation rows | latest {latest_vendor.get('growth', 'Unknown')} growth on {fmt_date(latest_vendor.get('date', ''))} | total removed {sum(int(row.get('removed', 0) or 0) for row in entries)}.",
                "stage-fruiting" if not any(row.get("contamination") or row.get("smell") for row in entries) else "stage-contamination",
            )
        )

    timeline_items = [
        (
            batch,
            f"{fmt_date(entries[-1].get('date', ''))} | Day {entries[-1].get('day', 'N/A')} | {entries[-1].get('growth', 'Unknown')} growth",
        )
        for batch, entries in grouped_batches[-8:]
    ]
    removal_groups = sorted(
        (
            batch,
            sum(int(row.get("removed", 0) or 0) for row in entries),
            entries[-1].get("date", ""),
        )
        for batch, entries in grouped_batches
    )
    removal_items = [
        (batch, f"{removed} removed bag(s) through {fmt_date(last_date)}")
        for batch, removed, last_date in sorted(removal_groups, key=lambda item: (item[1], item[2]), reverse=True)[:8]
        if removed > 0
    ]
    harvest_by_date: dict[str, float] = defaultdict(float)
    for row in harvest_rows:
        harvest_by_date[row.get("date", "")] += float(row.get("quantityHarvestedKg", 0) or 0)
    harvest_items = [
        (fmt_date(date_text), f"{quantity:.2f} kg harvested")
        for date_text, quantity in sorted(harvest_by_date.items())[-8:]
    ]

    latest_batches = []
    for batch, entries in grouped_batches[-8:]:
        latest = entries[-1]
        note = latest.get("notes") or latest.get("removalReason") or "No immediate note captured."
        latest_batches.append(batch_card(batch, latest, note))

    exceptions = []
    exception_rows = [
        row for row in reversed(rows)
        if row.get("contamination") or row.get("smell") or int(row.get("removed", 0) or 0) > 0 or (row.get("notes") and row.get("notes") != "-")
    ][:10]
    for row in exception_rows:
        reasons = []
        if row.get("contamination"):
            reasons.append("contamination")
        if row.get("smell"):
            reasons.append("smell")
        if int(row.get("removed", 0) or 0) > 0:
            reasons.append(f"{row.get('removed', 0)} removed")
        exceptions.append(
            event_row(
                f"{fmt_date(row.get('date', ''))} | Day {row.get('day', 'N/A')}",
                row.get("batchNorm", "Unknown batch"),
                row.get("notes") or row.get("removalReason") or "No extra note captured.",
                " · ".join(reasons) or row.get("growth", "Unknown"),
            )
        )

    footer = (
        f"Snapshot generated {context['generatedAt']} UTC from Google Sheets workbook {SOURCE_SPREADSHEET_ID}. "
        f"Build {version}. Portfolio promise view. Row counts: "
        + ", ".join(f"{name}={count}" for name, count in row_counts.items())
        + "."
    )

    banner = ""
    if not refresh["ok"]:
        banner = (
            f'<div class="shell"><div class="panel snapshot-banner {refresh["banner_class"]}">'
            '<p class="snapshot-banner-title">Snapshot freshness warning</p>'
            f'<p class="snapshot-banner-copy">{escape(refresh["label"])}. Public readers are seeing a degraded but still readable static snapshot.</p>'
            "</div></div>"
        )

    sections = {
        "__SNAPSHOT_BANNER__": banner,
        "__SNAPSHOT_HERO_META__": "".join(tags),
        "__SNAPSHOT_FILTER_OPTIONS__": "".join(filter_options),
        "__SNAPSHOT_FOCUS_STATUS__": "".join(focus_status),
        "__SNAPSHOT_KPIS__": "".join(kpis),
        "__SNAPSHOT_HARVEST_CONSISTENCY__": harvest_consistency,
        "__SNAPSHOT_PIPELINE__": pipeline_summary,
        "__SNAPSHOT_RISK_SUMMARY__": risk_summary,
        "__SNAPSHOT_VENDOR_STABILITY__": vendor_stability,
        "__SNAPSHOT_FOCUSED_BATCH_HIDDEN__": "hidden",
        "__SNAPSHOT_FOCUSED_BATCH_SUMMARY__": "".join(focused_summary),
        "__SNAPSHOT_FOCUSED_BATCH_CARDS__": "".join(focused_cards),
        "__SNAPSHOT_PRODUCTION_SUMMARY__": "".join(production_summary),
        "__SNAPSHOT_PRODUCTION_CARDS__": "".join(production_cards),
        "__SNAPSHOT_YIELD_SUMMARY__": "".join(yield_summary),
        "__SNAPSHOT_YIELD_BRIDGE__": "".join(yield_bridge_cards),
        "__SNAPSHOT_VENDOR_SUMMARY__": "".join(vendor_summary),
        "__SNAPSHOT_VENDOR_CARDS__": "".join(vendor_cards),
        "__SNAPSHOT_TIMELINE__": f'<div class="snapshot-chart-list">{chart_items(timeline_items)}</div><p class="snapshot-static-note">Static snapshot fallback; interactive chart appears when JavaScript runs.</p>',
        "__SNAPSHOT_REMOVALS__": f'<div class="snapshot-chart-list">{chart_items(removal_items)}</div><p class="snapshot-static-note">Sorted by total removals within the latest snapshot.</p>',
        "__SNAPSHOT_DAILY_HARVEST__": f'<div class="snapshot-chart-list">{chart_items(harvest_items)}</div><p class="snapshot-static-note">Daily harvest totals from the committed local snapshot.</p>',
        "__SNAPSHOT_BATCH_CARDS__": "".join(latest_batches),
        "__SNAPSHOT_EVENTS__": "".join(exceptions) if exceptions else event_row("None", "No current exception rows", "The snapshot contains no contamination, smell, or removal exceptions.", "clear"),
        "__SNAPSHOT_FOOTER__": footer,
        "__SNAPSHOT_META_JSON__": json.dumps(meta, separators=(",", ":"), sort_keys=True).replace("</", "<\\/"),
    }

    required_sections = [
        sections["__SNAPSHOT_HERO_META__"],
        sections["__SNAPSHOT_FOCUS_STATUS__"],
        sections["__SNAPSHOT_KPIS__"],
        sections["__SNAPSHOT_HARVEST_CONSISTENCY__"],
        sections["__SNAPSHOT_PIPELINE__"],
        sections["__SNAPSHOT_RISK_SUMMARY__"],
        sections["__SNAPSHOT_VENDOR_STABILITY__"],
        sections["__SNAPSHOT_PRODUCTION_SUMMARY__"],
        sections["__SNAPSHOT_YIELD_SUMMARY__"],
        sections["__SNAPSHOT_VENDOR_SUMMARY__"],
        sections["__SNAPSHOT_TIMELINE__"],
        sections["__SNAPSHOT_DAILY_HARVEST__"],
        sections["__SNAPSHOT_BATCH_CARDS__"],
        sections["__SNAPSHOT_EVENTS__"],
    ]
    if any(not section.strip() for section in required_sections):
        raise SystemExit("Snapshot build failed: one or more required derived sections rendered empty.")

    return meta, sections


def write_status(meta: dict[str, Any], snapshot_bytes: int, ok: bool) -> None:
    status = {
        "ok": ok,
        "generated_at": meta["generated_at"],
        "snapshot_present": snapshot_bytes > 0,
        "snapshot_bytes": snapshot_bytes,
        "row_counts": meta["row_counts"],
        "refresh_interval_minutes": meta["refresh_interval_minutes"],
        "build_version": meta["build_version"],
    }
    STATUS_PATH.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


def build_public_site() -> None:
    if not TEMPLATE_PATH.exists():
        raise SystemExit(f"Template missing: {TEMPLATE_PATH}")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if ROOT_DATA_JS_PATH.resolve() != PUBLIC_DATA_JS_PATH.resolve():
        shutil.copy2(ROOT_DATA_JS_PATH, PUBLIC_DATA_JS_PATH)
    context = load_context_from_data_js(ROOT_DATA_JS_PATH)
    version = build_version()
    meta, sections = build_public_payload(context, version)

    SNAPSHOT_PATH.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    SNAPSHOT_META_PATH.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    snapshot_bytes = SNAPSHOT_PATH.stat().st_size
    refresh_ok = refresh_health(meta["generated_at"])["ok"]
    write_status(meta, snapshot_bytes, refresh_ok)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    missing = [token for token in REQUIRED_PLACEHOLDERS if token not in template]
    if missing:
        raise SystemExit(f"Template missing required placeholders: {', '.join(missing)}")
    output = template
    for token, value in sections.items():
        output = output.replace(token, value)
    if any(token in output for token in REQUIRED_PLACEHOLDERS):
        raise SystemExit("Snapshot build failed: unresolved template placeholders remain.")
    OUTPUT_HTML_PATH.write_text(output, encoding="utf-8")


def main() -> int:
    build_public_site()
    print(f"Built public opsdash snapshot into {PUBLIC_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
