#!/usr/bin/env python3
"""Shared helpers for benchmark harness scripts."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 1x1 PNG (red pixel)
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_catalog(root: Path | None = None) -> dict:
    root = root or repo_root()
    return json.loads((root / "benchmark" / "catalog.json").read_text(encoding="utf-8"))


def load_truth(fixture_id: str, root: Path | None = None) -> dict:
    root = root or repo_root()
    path = root / "benchmark" / "truth" / f"{fixture_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_placeholder_png(screenshots_dir: Path) -> Path:
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    path = screenshots_dir / "placeholder.png"
    if not path.is_file():
        path.write_bytes(_PLACEHOLDER_PNG)
    return path


def run_validate(
    round_dir: Path,
    goal_path: Path,
    app_dir: Path,
    root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    root = root or repo_root()
    cmd = [
        sys.executable,
        str(root / "scripts" / "validate_evidence.py"),
        "--round-dir",
        str(round_dir),
        "--goal",
        str(goal_path),
        "--app-dir",
        str(app_dir),
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def run_score(
    truth_path: Path,
    report_path: Path,
    json_out: Path | None = None,
    root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    root = root or repo_root()
    cmd = [
        sys.executable,
        str(root / "benchmark" / "harness" / "score.py"),
        "--truth",
        str(truth_path),
        "--report",
        str(report_path),
    ]
    if json_out is not None:
        cmd.extend(["--json-out", str(json_out)])
    return subprocess.run(cmd, capture_output=True, text=True)


def copytree_clean(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
