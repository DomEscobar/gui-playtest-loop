#!/usr/bin/env python3
"""Create or verify a SHA-256 manifest for protected playtest inputs."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return "sha256:" + value.hexdigest()


def parse_file(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--file must be LABEL=PATH")
    label, raw_path = value.split("=", 1)
    if not label.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("--file must contain a non-empty label and path")
    return label.strip(), Path(raw_path).expanduser().resolve()


def create_manifest(entries: list[tuple[str, Path]]) -> dict:
    labels: set[str] = set()
    files = []
    for label, path in entries:
        if label in labels:
            raise ValueError(f"duplicate protected label: {label}")
        labels.add(label)
        if not path.is_file():
            raise ValueError(f"protected file not found: {path}")
        files.append({"label": label, "path": str(path), "sha256": digest(path)})
    return {
        "version": 1,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "files": files,
    }


def verify_manifest(manifest_path: Path) -> list[str]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"integrity manifest unreadable: {exc}"]
    problems: list[str] = []
    if manifest.get("version") != 1 or not isinstance(manifest.get("files"), list):
        return ["integrity manifest must have version 1 and a files array"]
    labels: set[str] = set()
    for entry in manifest["files"]:
        label = entry.get("label")
        raw_path = entry.get("path")
        expected = entry.get("sha256")
        if not label or label in labels:
            problems.append(f"invalid or duplicate protected label: {label!r}")
            continue
        labels.add(label)
        path = Path(raw_path).expanduser() if raw_path else Path("<missing>")
        if not path.is_file():
            problems.append(f"protected file missing [{label}]: {path}")
        elif digest(path) != expected:
            problems.append(f"integrity mismatch [{label}]: {path}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--file", action="append", type=parse_file, default=[])
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.expanduser().resolve()
    if args.verify:
        problems = verify_manifest(manifest_path)
        if problems:
            for problem in problems:
                print(problem)
            return 1
        print("OK: protected contract matches integrity manifest.")
        return 0

    if not args.file:
        parser.error("at least one --file LABEL=PATH is required when creating a manifest")
    payload = create_manifest(args.file)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
