#!/usr/bin/env python3
"""Run a single benchmark spike: serve fixture, validate evidence, score vs truth.

For v0 the playtester step is invoked externally (browser MCP or agent CLI).
This script wires the deterministic parts and records results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default="memory-dead-start-button")
    parser.add_argument("--round-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--skip-validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    fixture_id = args.fixture
    fixture_dir = root / "benchmark" / "fixtures" / fixture_id
    truth_path = root / "benchmark" / "truth" / f"{fixture_id}.json"
    goal_path = fixture_dir / "goal.json"
    round_dir = args.round_dir.resolve()
    report_path = round_dir / "report.json"

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_dir = root / "benchmark" / "results" / ts
    results_dir.mkdir(parents=True, exist_ok=True)

    goal_hash_before = sha256_file(goal_path)
    manifest = {
        "fixture_id": fixture_id,
        "timestamp": ts,
        "goal_hash_before": goal_hash_before,
        "round_dir": str(round_dir),
        "steps": {},
    }

    if not report_path.is_file():
        manifest["steps"]["report"] = "missing"
        (results_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Report not found: {report_path}", file=sys.stderr)
        print("Run the playtester against the served fixture, then re-run with --round-dir.")
        return 1

    manifest["steps"]["report"] = "present"

    if not args.skip_validate:
        validate_cmd = [
            sys.executable,
            str(root / "scripts" / "validate_evidence.py"),
            "--round-dir",
            str(round_dir),
            "--goal",
            str(goal_path),
            "--app-dir",
            str(fixture_dir),
        ]
        proc = subprocess.run(validate_cmd, capture_output=True, text=True)
        manifest["steps"]["validate"] = {
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
        print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, end="")
        if proc.returncode != 0:
            (results_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            return proc.returncode

    goal_hash_after = sha256_file(goal_path)
    manifest["goal_hash_after"] = goal_hash_after
    manifest["goal_tampered"] = goal_hash_before != goal_hash_after

    score_out = results_dir / "score.json"
    score_cmd = [
        sys.executable,
        str(root / "benchmark" / "harness" / "score.py"),
        "--truth",
        str(truth_path),
        "--report",
        str(report_path),
        "--json-out",
        str(score_out),
    ]
    proc = subprocess.run(score_cmd, capture_output=True, text=True)
    manifest["steps"]["score"] = {
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }
    print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")

    shutil.copy2(report_path, results_dir / "report.json")
    shutil.copy2(goal_path, results_dir / "goal.json")
    shutil.copy2(truth_path, results_dir / "truth.json")

    (results_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Results written to {results_dir}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
