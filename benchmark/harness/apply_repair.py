#!/usr/bin/env python3
"""Apply a harness repair manifest (JSON find/replace) to app.html."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def apply_repair(app_html: Path, repair_path: Path) -> tuple[bool, list[str]]:
    manifest = json.loads(repair_path.read_text(encoding="utf-8"))
    text = app_html.read_text(encoding="utf-8")
    problems: list[str] = []
    for idx, rep in enumerate(manifest.get("replacements", [])):
        find = rep.get("find", "")
        replace = rep.get("replace", "")
        if find not in text:
            problems.append(f"replacement {idx}: find string not found")
            continue
        text = text.replace(find, replace, 1)
    if problems:
        return False, problems
    app_html.write_text(text, encoding="utf-8")
    return True, []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-html", type=Path, required=True)
    parser.add_argument("--repair", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ok, problems = apply_repair(args.app_html, args.repair)
    if ok:
        print(f"Applied repair to {args.app_html}")
        return 0
    for p in problems:
        print(p)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
