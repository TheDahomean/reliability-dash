#!/usr/bin/env python3

import argparse
import datetime as dt
import json
import pathlib
from typing import Any

DEFAULT_MAX_AGE_MINUTES = 45


def iso_to_datetime(value: str) -> dt.datetime:
    if value.endswith("Z"):
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def load_status(source: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse status json from {source}: {exc}") from exc


def age_minutes(generated_at: str) -> int:
    generated = iso_to_datetime(generated_at)
    now = dt.datetime.now(dt.timezone.utc)
    return max(0, round((now - generated).total_seconds() / 60))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail if an opsdash status file is older than an allowed threshold.")
    parser.add_argument("--status-json", required=True, help="Path to opsdash_status.json")
    parser.add_argument(
        "--max-age-minutes",
        type=int,
        default=DEFAULT_MAX_AGE_MINUTES,
        help=f"Maximum allowed age in minutes. Defaults to {DEFAULT_MAX_AGE_MINUTES}.",
    )
    args = parser.parse_args()

    status = load_status(pathlib.Path(args.status_json).resolve())
    generated_at = str(status.get("generated_at") or "").strip()
    if not generated_at:
        raise SystemExit("Status file is missing generated_at.")

    age = age_minutes(generated_at)
    if age > args.max_age_minutes:
        raise SystemExit(
            f"Snapshot freshness check failed: generated_at={generated_at}, age={age}m, limit={args.max_age_minutes}m."
        )
    print(f"Snapshot freshness ok: generated_at={generated_at}, age={age}m.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
