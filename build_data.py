#!/usr/bin/env python3

import csv
import datetime as dt
import json
import pathlib
import re
import sys
from typing import Optional

HEADER_ROW_INDEX = 3
QUALIFIED_BATCH_COMPONENT_RE = re.compile(r"(SB-\d{4}/\d{2}/\d{2}-\d{2}-[A-Z]{2,3})\s*(?:\((\d+)\s*bags?\))?", re.IGNORECASE)
REPEATED_BASE_VENDOR_COMPONENT_RE = re.compile(
    r"(SB-\d{4}/\d{2}/\d{2}-\d{2})\s+([A-Z]{2,3})\s*\(?\s*(\d+)\s*bags?\)?",
    re.IGNORECASE,
)
BASE_BATCH_RE = re.compile(r"SB-\d{4}/\d{2}/\d{2}-\d{2}", re.IGNORECASE)
SHORTHAND_VENDOR_BAGS_RE = re.compile(
    r"(?:^|[\s,;])([A-Z]{2,3})\s*-?\s*\(?\s*(\d+)\s*(?:bags?)?\)?(?=$|[\s,;])",
    re.IGNORECASE,
)
VENDOR_NAME_HINTS = {
    "nature niche": "NN",
    "natureniche": "NN",
}


def first_present(record: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in record:
            return record[key]
    raise KeyError(keys[0])


def parse_date(value: str) -> str:
    raw = value.strip()
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", raw)
    if not match:
        # Handle missing second slash: MM/DDYYYY (e.g. "04/102026")
        match = re.fullmatch(r"(\d{1,2})/(\d{2})(\d{4})", raw)
    if match:
        part1, part2, year = match.groups()
        if len(year) == 2:
            year = str(2000 + int(year))
        yr = int(year)
        a, b = int(part1), int(part2)
        parsed = dt.date(yr, a, b)
        # If the MM/DD parse lands in the future, try DD/MM. Staff sometimes
        # enter dates in DD/MM format despite the column header saying MMDDYYYY.
        if parsed > dt.date.today() and 1 <= b <= 12:
            try:
                swapped = dt.date(yr, b, a)
                if swapped <= dt.date.today():
                    return swapped.isoformat()
            except ValueError:
                pass
        return parsed.isoformat()
    raise ValueError(f"Unsupported date format: {raw}")


def load_csv_rows(source: pathlib.Path) -> list[list[str]]:
    return list(csv.reader(source.open(newline="", encoding="utf-8-sig")))


def clean_string(value: str) -> str:
    return str(value or "").strip()


def parse_number(value: str) -> float:
    text = clean_string(value)
    if not text or text.upper() in {"NA", "N/A", "-"}:
        return 0.0
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else 0.0


def parse_int(value: str, default: int = 0) -> int:
    text = clean_string(value)
    if not text or text.upper() in {"NA", "N/A", "-"}:
        return default
    try:
        return int(parse_number(text))
    except (TypeError, ValueError):
        return default


def parse_optional_int(value: str) -> Optional[int]:
    text = clean_string(value)
    if not text or text.upper() in {"NA", "N/A", "-"}:
        return None
    try:
        parsed = int(parse_number(text))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def normalize_batch(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\s*\([^)]*\)", "", clean_string(value))).strip()


def base_batch_id(batch_id: str) -> str:
    normalized = normalize_batch(batch_id)
    return re.sub(r"-[A-Z]{2,3}$", "", normalized)


def batch_vendor(batch_id: str) -> str:
    match = re.search(r"-([A-Z]{2,3})$", normalize_batch(batch_id))
    return match.group(1) if match else ""


def component_entry(batch_id: str, bag_count: int) -> dict[str, object]:
    normalized_batch = normalize_batch(batch_id)
    return {
        "batch": normalized_batch,
        "batchNorm": normalized_batch,
        "baseBatch": base_batch_id(normalized_batch),
        "vendor": batch_vendor(normalized_batch),
        "bagCount": bag_count,
    }


def parse_batch_components(value: str) -> list[dict[str, object]]:
    normalized = clean_string(value)
    components = []
    seen = set()

    def add_component(batch_id: str, bag_count: int) -> None:
        normalized_batch = normalize_batch(batch_id)
        if not normalized_batch or normalized_batch in seen:
            return
        seen.add(normalized_batch)
        components.append(component_entry(normalized_batch, bag_count))

    for match in QUALIFIED_BATCH_COMPONENT_RE.finditer(normalized):
        add_component(match.group(1), int(match.group(2)) if match.group(2) else 0)

    for match in REPEATED_BASE_VENDOR_COMPONENT_RE.finditer(normalized):
        base_batch = normalize_batch(match.group(1))
        vendor = match.group(2).upper()
        add_component(f"{base_batch}-{vendor}", int(match.group(3)))

    if components:
        return components

    base_matches = list(BASE_BATCH_RE.finditer(normalized))
    if base_matches:
        base_batch = normalize_batch(base_matches[0].group(0))
        shorthand_components = []
        shorthand_seen = set()
        for match in SHORTHAND_VENDOR_BAGS_RE.finditer(normalized[base_matches[0].end() :]):
            vendor = match.group(1).upper()
            batch_id = f"{base_batch}-{vendor}"
            if batch_id in shorthand_seen:
                continue
            shorthand_seen.add(batch_id)
            shorthand_components.append(component_entry(batch_id, int(match.group(2))))
        if shorthand_components:
            return shorthand_components

    if normalized:
        components.append(component_entry(normalized, 0))

    return components


def build_component_catalog(records: list[dict[str, str]]) -> dict[str, list[dict[str, object]]]:
    catalog: dict[str, dict[str, dict[str, object]]] = {}

    for record in records:
        for component in parse_batch_components(record["Substrate Batch ID (SB-YYMMDD-XX-VID)"]):
            if not component["vendor"]:
                continue
            batch_id = str(component["batchNorm"])
            base_batch = str(component["baseBatch"])
            catalog.setdefault(base_batch, {})
            existing = catalog[base_batch].get(batch_id)
            if existing is None or (not existing["bagCount"] and component["bagCount"]):
                catalog[base_batch][batch_id] = component

    return {base: list(components.values()) for base, components in catalog.items()}


def find_affected_components(text: str, components: list[dict[str, object]]) -> list[dict[str, object]]:
    lowered = clean_string(text).lower()
    collapsed = re.sub(r"[^a-z0-9]+", "", lowered)
    vendor_codes = set()

    for component in components:
        vendor = str(component["vendor"] or "").lower()
        if vendor and re.search(rf"\b{re.escape(vendor)}\b", lowered):
            vendor_codes.add(vendor.upper())

    for phrase, code in VENDOR_NAME_HINTS.items():
        if phrase in lowered or phrase.replace(" ", "") in collapsed:
            vendor_codes.add(code)

    return [component for component in components if str(component["vendor"]) in vendor_codes]


def allocate_removed(
    removed: int,
    components: list[dict[str, object]],
    affected: list[dict[str, object]],
) -> dict[str, int]:
    allocations = {str(component["batchNorm"]): 0 for component in components}
    if removed <= 0 or not components:
        return allocations

    targets = affected or components
    target_capacity = sum(int(component["bagCount"] or 0) for component in targets)
    if affected and target_capacity and removed > target_capacity:
        targets = components

    weights = [max(int(component["bagCount"] or 0), 1) for component in targets]
    total_weight = sum(weights) or len(targets)
    raw_allocations = [removed * weight / total_weight for weight in weights]
    assigned = [int(value) for value in raw_allocations]
    remainder = removed - sum(assigned)
    order = sorted(
        range(len(targets)),
        key=lambda index: (raw_allocations[index] - assigned[index], weights[index]),
        reverse=True,
    )
    for index in order[:remainder]:
        assigned[index] += 1

    for component, value in zip(targets, assigned):
        allocations[str(component["batchNorm"])] = value

    return allocations


def build_payload_from_records(records: list[dict[str, str]]) -> list[dict[str, object]]:
    component_catalog = build_component_catalog(records)
    expanded_records = []
    start_dates_by_base_batch: dict[str, dt.date] = {}
    earliest_dates_by_base_batch: dict[str, dt.date] = {}

    for record in records:
        batch = clean_string(record["Substrate Batch ID (SB-YYMMDD-XX-VID)"])
        components = parse_batch_components(batch)
        if len(components) == 1 and not components[0]["vendor"]:
            inferred_components = component_catalog.get(str(components[0]["baseBatch"]))
            if inferred_components:
                components = [dict(component) for component in inferred_components]

        record_date = dt.date.fromisoformat(parse_date(first_present(record, "Date", "Date(MMDDYYYY)")))
        explicit_day = parse_optional_int(record["Day of Incubation"])
        expanded_records.append((record, record_date, explicit_day, components))

        for component in components:
            base_batch = str(component["baseBatch"])
            earliest = earliest_dates_by_base_batch.get(base_batch)
            if earliest is None or record_date < earliest:
                earliest_dates_by_base_batch[base_batch] = record_date
            if explicit_day is not None:
                start_date = record_date - dt.timedelta(days=explicit_day - 1)
                existing = start_dates_by_base_batch.get(base_batch)
                if existing is None or start_date < existing:
                    start_dates_by_base_batch[base_batch] = start_date

    for base_batch, earliest in earliest_dates_by_base_batch.items():
        start_dates_by_base_batch.setdefault(base_batch, earliest)

    payload = []
    for record, record_date, explicit_day, components in expanded_records:
        batch = clean_string(record["Substrate Batch ID (SB-YYMMDD-XX-VID)"])

        removed = parse_int(record["Number of Bags Removed"])

        notes = clean_string(record["Notes"])
        removal_reason = clean_string(record["Reason for Removal"])
        affected_components = find_affected_components(f"{removal_reason} {notes}", components)
        removed_allocations = allocate_removed(removed, components, affected_components)
        targeted_batches = {str(component["batchNorm"]) for component in affected_components}
        scoped_alert = bool(targeted_batches) and removed <= sum(int(component["bagCount"] or 0) for component in affected_components)

        for component in components:
            batch_id = str(component["batchNorm"])
            base_batch = str(component["baseBatch"])
            start_date = start_dates_by_base_batch.get(base_batch, record_date)
            derived_day = max(1, (record_date - start_date).days + 1)
            payload.append(
                {
                    "date": record_date.isoformat(),
                    "room": clean_string(record["Room Name"]),
                    "batch": batch_id,
                    "batchNorm": batch_id,
                    "baseBatch": base_batch,
                    "vendor": str(component["vendor"]),
                    "bagCount": int(component["bagCount"] or 0),
                    "batchGroup": batch,
                    "day": explicit_day if explicit_day is not None else derived_day,
                    "growth": clean_string(record["Mycelium Growth (Good/Slow/Poor)"]),
                    "contamination": clean_string(record["Contamination Observed (Y/N)"]) == "Y"
                    and (not scoped_alert or batch_id in targeted_batches),
                    "smell": clean_string(record["Abnormal Smell (Y/N)"]) == "Y"
                    and (not scoped_alert or batch_id in targeted_batches),
                    "removed": removed_allocations[batch_id],
                    "removalReason": removal_reason,
                    "notes": notes,
                    "checkedBy": clean_string(record["Checked By (Name/Signature)"]),
                }
            )

    return payload


def build_payload(rows: list[list[str]]) -> list[dict[str, object]]:
    header = rows[HEADER_ROW_INDEX]
    records = []

    for raw in rows[HEADER_ROW_INDEX + 1:]:
        if not any(cell.strip() for cell in raw):
            continue
        raw = raw + [""] * (len(header) - len(raw))
        records.append(dict(zip(header, raw)))

    return build_payload_from_records(records)


def write_data_js(target: pathlib.Path, payload: list[dict[str, object]]) -> None:
    target.write_text(
        "window.DASHBOARD_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )


def convert_csv_to_js(source: pathlib.Path, target: pathlib.Path) -> int:
    rows = load_csv_rows(source)
    payload = build_payload(rows)
    write_data_js(target, payload)
    return len(payload)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: build_data.py <input.csv> <output.js>", file=sys.stderr)
        return 1

    source = pathlib.Path(sys.argv[1])
    target = pathlib.Path(sys.argv[2])
    convert_csv_to_js(source, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
