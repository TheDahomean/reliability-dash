#!/usr/bin/env python3
"""
validate_snapshot.py — confirm data.js is a usable snapshot before deploying.

Usage:
    python3 validate_snapshot.py [path/to/data.js]

Exits 0 if valid, 1 if not.
"""

import json
import re
import sys

REQUIRED_KEYS = ("bagging", "incubation", "harvest")


def validate(path: str) -> tuple[bool, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        return False, f"cannot read {path}: {e}"

    match = re.search(r"window\.DASHBOARD_CONTEXT\s*=\s*(\{.+\})\s*;", content, re.DOTALL)
    if not match:
        return False, "window.DASHBOARD_CONTEXT not found or not parseable"

    try:
        ctx = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        return False, f"DASHBOARD_CONTEXT JSON parse error: {e}"

    if not ctx.get("generatedAt"):
        return False, "generatedAt is missing or empty"

    for key in REQUIRED_KEYS:
        if key not in ctx:
            return False, f"required key '{key}' is missing"
        val = ctx[key]
        # Accept either a non-empty list or a non-empty dict
        if not val:
            return False, f"required key '{key}' is empty"

    return True, "ok"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data.js"
    ok, reason = validate(path)
    if ok:
        print(f"[validate_snapshot] {path}: valid ({reason})")
        sys.exit(0)
    else:
        print(f"[validate_snapshot] {path}: INVALID — {reason}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
