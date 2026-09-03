#!/usr/bin/env python3
"""Seal all artifacts used by a playtest report into an evidence manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from seal_contract import digest


VALID_ORIGINS = {"live-agent", "human-live", "replayed", "synthetic-golden"}


def inside(root: Path, raw: str) -> Path:
    path = (root / raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"evidence path escapes round directory: {raw}") from exc
    return path


def referenced_files(round_dir: Path, report: dict) -> set[Path]:
    paths = {round_dir / "action.log"}
    for collection in (report.get("checks", []), report.get("ux_findings", [])):
        for entry in collection:
            for raw in entry.get("evidence") or []:
                paths.add(inside(round_dir, raw))
    paths.update(round_dir.glob("ux_probe.*.json"))
    instrumentation = round_dir / "instrumentation"
    if report.get("instrumented_findings") and instrumentation.is_dir():
        paths.update(p for p in instrumentation.rglob("*") if p.is_file())
    return paths


def create_evidence_manifest(
    round_dir: Path, origin: str, include_timestamp: bool = True
) -> dict:
    if origin not in VALID_ORIGINS:
        raise ValueError(f"invalid evidence origin: {origin}")
    report_path = round_dir / "report.json"
    if not report_path.is_file():
        raise ValueError(f"report.json not found: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("evidence_origin") != origin:
        raise ValueError(
            f"report evidence_origin {report.get('evidence_origin')!r} does not match {origin!r}"
        )
    rows = []
    for path in sorted(referenced_files(round_dir, report)):
        if not path.is_file():
            raise ValueError(f"referenced evidence not found: {path}")
        rows.append({
            "path": path.resolve().relative_to(round_dir.resolve()).as_posix(),
            "sha256": digest(path),
        })
    manifest = {
        "version": 1,
        "origin": origin,
        "files": rows,
    }
    if include_timestamp:
        manifest["sealed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round-dir", required=True, type=Path)
    parser.add_argument("--origin", required=True, choices=sorted(VALID_ORIGINS))
    args = parser.parse_args()
    round_dir = args.round_dir.expanduser().resolve()
    try:
        payload = create_evidence_manifest(round_dir, args.origin)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}")
        return 1
    output = round_dir / "evidence_manifest.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
