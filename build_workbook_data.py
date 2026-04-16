#!/usr/bin/env python3

import datetime as dt
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from typing import Optional

from build_data import build_payload as build_incubation_payload
from build_data import load_csv_rows

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

SHEET_PREFIXES = {
    "bagging": "LOG 5",
    "pasteurization": "LOG 6",
    "incubation": "LOG 9 - Incubation Daily Check",
    "fruiting": "LOG 10 - Fruiting Room And Envi",
    "harvest": "LOG 11 - Harvest (Ccp 2)",
}


def excel_serial_to_date(value: str) -> str:
    serial = float(value)
    base = dt.datetime(1899, 12, 30)
    return (base + dt.timedelta(days=serial)).date().isoformat()


def clean_string(value: str) -> str:
    return str(value or "").strip()


def first_present(record: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in record:
            return record[key]
    raise KeyError(keys[0])


def parse_date(value: str) -> str:
    value = clean_string(value)
    if not value:
        return ""
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", value)
    if match:
        part1, part2, year = match.groups()
        first = int(part1)
        second = int(part2)
        if len(year) == 2:
            year = str(2000 + int(year))
        yr = int(year)
        if first > 12:
            # Unambiguously DD/MM (day can't be a month)
            return dt.date(yr, second, first).isoformat()
        parsed = dt.date(yr, first, second)
        # If the MM/DD parse lands in the future, try DD/MM. Staff sometimes
        # enter dates in DD/MM format despite the column header saying MMDDYYYY.
        if parsed > dt.date.today() and 1 <= second <= 12:
            try:
                swapped = dt.date(yr, second, first)
                if swapped <= dt.date.today():
                    return swapped.isoformat()
            except ValueError:
                pass
        return parsed.isoformat()
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return excel_serial_to_date(value)
    return value


def normalize_lot_year(iso_date: str, lot_id: str, pattern: str) -> str:
    if not iso_date:
        return iso_date
    match = re.match(pattern, clean_string(lot_id))
    if not match:
        return iso_date
    expected_year = 2000 + int(match.group(1))
    parsed = dt.date.fromisoformat(iso_date)
    if abs(parsed.year - expected_year) >= 2:
        return dt.date(expected_year, parsed.month, parsed.day).isoformat()
    return iso_date


def parse_number(value: str) -> float:
    value = clean_string(value)
    if not value or value.upper() in {"NA", "N/A", "-"}:
        return 0.0
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else 0.0


def parse_int(value: str) -> int:
    return int(parse_number(value))


def parse_yes_no(value: str) -> bool:
    return clean_string(value).upper() in {"Y", "YES", "PASS", "TRUE"}


def normalize_batch(value: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", clean_string(value)).strip()


def split_batch_ids(value: str) -> list[str]:
    return [item for item in re.findall(r"SB-\d{4}/\d{2}/\d{2}-\d{2}", clean_string(value))]


def load_sheet_rows(workbook_path: pathlib.Path, sheet_prefix: str) -> list[list[str]]:
    with zipfile.ZipFile(workbook_path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst:
                shared.append(
                    "".join(t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"))
                )

        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        relmap = {
            rel.attrib["Id"]: (
                t if (t := rel.attrib["Target"].lstrip("/")).startswith("xl/") else "xl/" + t
            )
            for rel in rels
        }

        target = None
        for sheet in workbook.find("a:sheets", NS):
            if sheet.attrib["name"].startswith(sheet_prefix):
                target = relmap[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
                break

        if target is None:
            raise KeyError(f"Sheet starting with {sheet_prefix!r} not found")

        root = ET.fromstring(zf.read(target))
        rows = []
        for row in root.find("a:sheetData", NS):
            current = []
            for cell in row:
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    # openpyxl writes text as <c t="inlineStr"><is><t>value</t></is></c>
                    is_node = cell.find("a:is", NS)
                    if is_node is not None:
                        value = "".join(
                            t.text or ""
                            for t in is_node.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                        )
                    else:
                        value = ""
                else:
                    value_node = cell.find("a:v", NS)
                    value = value_node.text or "" if value_node is not None else ""
                    if cell_type == "s" and value:
                        value = shared[int(value)]
                current.append(value)
            rows.append(current)
        return rows


def rows_to_records(rows: list[list[str]], header_row_index: int) -> list[dict[str, str]]:
    header = rows[header_row_index]
    records = []
    for raw in rows[header_row_index + 1 :]:
        if not any(clean_string(cell) for cell in raw):
            continue
        padded = raw + [""] * (len(header) - len(raw))
        records.append(dict(zip(header, padded)))
    return records


def detect_header_row(rows: list[list[str]], expected_first_header: str) -> int:
    for index, row in enumerate(rows):
        if row and clean_string(row[0]) == expected_first_header:
            return index
    raise KeyError(f"Header row starting with {expected_first_header!r} not found")


def detect_header_row_any(rows: list[list[str]], *expected_first_headers: str) -> int:
    for expected_first_header in expected_first_headers:
        try:
            return detect_header_row(rows, expected_first_header)
        except KeyError:
            continue
    joined = ", ".join(repr(header) for header in expected_first_headers)
    raise KeyError(f"Header row starting with one of [{joined}] not found")


def build_incubation(records: list[dict[str, str]]) -> list[dict[str, object]]:
    payload = []
    for record in records:
        batch = clean_string(record["Substrate Batch ID (SB-YYMMDD-XX-VID)"])
        payload.append(
            {
                "date": parse_date(first_present(record, "Date", "Date(MMDDYYYY)")),
                "room": clean_string(record["Room Name"]),
                "batch": batch,
                "batchNorm": normalize_batch(batch),
                "day": parse_int(record["Day of Incubation"]),
                "growth": clean_string(record["Mycelium Growth (Good/Slow/Poor)"]),
                "contamination": parse_yes_no(record["Contamination Observed (Y/N)"]),
                "smell": parse_yes_no(record["Abnormal Smell (Y/N)"]),
                "removed": int(parse_number(record["Number of Bags Removed"])),
                "removalReason": clean_string(record["Reason for Removal"]),
                "notes": clean_string(record["Notes"]),
                "checkedBy": clean_string(record["Checked By (Name/Signature)"]),
            }
        )
    return payload


def build_fruiting(records: list[dict[str, str]]) -> list[dict[str, object]]:
    payload = []
    for record in records:
        lot = clean_string(record["Fruiting Lot ID (FR-YYMMDD-XX)"])
        if not lot:
            continue
        parsed_date = normalize_lot_year(parse_date(first_present(record, "Date", "Date(MMDDYYYY)")), lot, r"^FR-(\d{2})/")
        payload.append(
            {
                "date": parsed_date,
                "fruitingLot": lot,
                "sourceBatchIds": split_batch_ids(record["Source Substrate Batch ID(s) (SB-YYMMDD-XX)"]),
                "room": clean_string(record["Room/Chamber ID"]),
                "fruitingStartDate": parse_date(record["Fruiting Start Date"]),
                "tempReading": clean_string(first_present(record, "Temp Reading", "Temp Reading (sonoffs)")),
                "humidityReading": clean_string(first_present(record, "Humidity Reading", "Humidity Reading (sonoffs)")),
                "humidifierWorking": parse_yes_no(record["Humidifier Working (Y/N)"]),
                "fansWorking": parse_yes_no(record["Fans Working (Y/N)"]),
                "acStatus": clean_string(record["A/C Status"]),
                "cleaningDone": parse_yes_no(record["Cleaning Done Today (Y/N)"]),
                "issuesObserved": clean_string(record["Issues Observed"]),
                "actionTaken": clean_string(record["Action Taken"]),
                "recordedBy": clean_string(record["Recorded By (Name/Signature)"]),
            }
        )
    return payload


def build_harvest(records: list[dict[str, str]]) -> list[dict[str, object]]:
    payload = []
    for record in records:
        harvest_lot = clean_string(record["Fresh Harvest Lot ID (FH-YYMMDD-XX)"])
        fruiting_lot = clean_string(record["Source Fruiting Lot ID(s) (FR-YYMMDD-XX)"])
        if not harvest_lot or not fruiting_lot:
            continue
        parsed_date = normalize_lot_year(parse_date(first_present(record, "Date", "Date(MMDDYYYY)")), harvest_lot, r"^FH-(\d{2})/")
        payload.append(
            {
                "date": parsed_date,
                "harvestLot": harvest_lot,
                "fruitingLot": fruiting_lot,
                "strain": clean_string(record["Strain"]),
                "visualQualityAcceptable": parse_yes_no(record["Visual Quality Acceptable (Y/N)"]),
                "moldPresent": parse_yes_no(record["Mold Present (Y/N)"]),
                "sliminessPresent": parse_yes_no(record["Sliminess Present (Y/N)"]),
                "quantityHarvestedKg": parse_number(
                    first_present(record, "Quantity Harvested (Kg)", "Quantity Harvested (Kg) Economic Yield")
                ),
                "quantityRejectedKg": parse_number(record["Quantity Rejected (Kg)"]),
                "reasonForRejection": clean_string(record["Reason for Rejection"]),
            }
        )
    return payload


def build_bagging(records: list[dict[str, str]]) -> list[dict[str, object]]:
    payload = []
    for record in records:
        bags_filled = parse_int(record["Number of Bags Filled"])
        bag_size = clean_string(first_present(record, "Target Weight (2 kg)", "Target Weight"))
        if not bags_filled and not bag_size:
            continue
        payload.append(
            {
                "bagsFilled": bags_filled,
                "targetWeight": bag_size,
                "responsibleParty": clean_string(record["Responsible Party Initials"]),
                "supervisor": clean_string(record["Supervisor"]),
            }
        )
    return payload


def build_pasteurization(records: list[dict[str, str]]) -> list[dict[str, object]]:
    payload = []
    for record in records:
        batch = clean_string(record["Substrate Batch ID (SB-YYMMDD-XX)"])
        if not batch:
            continue
        payload.append(
            {
                "batch": batch,
                "batchNorm": normalize_batch(batch),
                "date": parse_date(record["Date"]),
                "substrateType": clean_string(record["Substrate Type"]),
                "bagSize": clean_string(record["Bag Size"]),
                "criticalLimitMet": parse_yes_no(record["Critical Limit Met (Y/N)"]),
                "actionTaken": clean_string(record["If No, Action Taken"]),
                "disposition": clean_string(record["Re-pasteurised/Discarded"]),
            }
        )
    return payload


def build_context(workbook_path: pathlib.Path, incubation_csv_path: Optional[pathlib.Path] = None) -> dict[str, object]:
    bagging_rows = load_sheet_rows(workbook_path, SHEET_PREFIXES["bagging"])
    pasteurization_rows = load_sheet_rows(workbook_path, SHEET_PREFIXES["pasteurization"])
    fruiting_rows = load_sheet_rows(workbook_path, SHEET_PREFIXES["fruiting"])
    harvest_rows = load_sheet_rows(workbook_path, SHEET_PREFIXES["harvest"])

    if incubation_csv_path is not None and incubation_csv_path.exists():
        incubation = build_incubation_payload(load_csv_rows(incubation_csv_path))
    else:
        incubation_rows = load_sheet_rows(workbook_path, SHEET_PREFIXES["incubation"])
        incubation = build_incubation(rows_to_records(incubation_rows, detect_header_row_any(incubation_rows, "Date(MMDDYYYY)", "Date")))
    bagging = build_bagging(rows_to_records(bagging_rows, detect_header_row_any(bagging_rows, "Start Time")))
    pasteurization = build_pasteurization(
        rows_to_records(
            pasteurization_rows,
            detect_header_row_any(pasteurization_rows, "Substrate Batch ID (SB-YYMMDD-XX)")
        )
    )
    fruiting = build_fruiting(
        rows_to_records(fruiting_rows, detect_header_row_any(fruiting_rows, "Date(MMDDYYYY)", "Date"))
    )
    harvest = build_harvest(
        rows_to_records(harvest_rows, detect_header_row_any(harvest_rows, "Date", "Date(MMDDYYYY)"))
    )

    return {
        "generatedAt": dt.datetime.utcnow().isoformat() + "Z",
        "bagging": bagging,
        "pasteurization": pasteurization,
        "incubation": incubation,
        "fruiting": fruiting,
        "harvest": harvest,
    }


def write_data_js(target: pathlib.Path, context: dict[str, object]) -> None:
    target.write_text(
        "window.DASHBOARD_CONTEXT = " + json.dumps(context, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )


def convert_workbook_to_js(
    workbook_path: pathlib.Path,
    target: pathlib.Path,
    incubation_csv_path: Optional[pathlib.Path] = None,
) -> dict[str, object]:
    context = build_context(workbook_path, incubation_csv_path=incubation_csv_path)
    write_data_js(target, context)
    return context


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        print("usage: build_workbook_data.py <input.xlsx> <output.js> [incubation.csv]", file=sys.stderr)
        return 1

    workbook_path = pathlib.Path(sys.argv[1])
    target = pathlib.Path(sys.argv[2])
    incubation_csv_path = pathlib.Path(sys.argv[3]) if len(sys.argv) == 4 else None
    convert_workbook_to_js(workbook_path, target, incubation_csv_path=incubation_csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
