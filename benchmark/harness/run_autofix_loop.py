#!/usr/bin/env python3
"""Tier-2 autofix loop: detect on broken fixture, apply repair, verify goal completion."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from apply_repair import apply_repair
from lib import load_catalog, repo_root, run_score, run_validate, utc_timestamp


def goal_required_ids(goal: dict) -> list[str]:
    return [c["id"] for c in goal.get("checks", []) if c.get("required", True)]


def score_goal_completion(goal: dict, report: dict) -> tuple[bool, list[str]]:
    required = set(goal_required_ids(goal))
    by_id = {c["id"]: c.get("status") for c in report.get("checks", [])}
    problems: list[str] = []
    for check_id in sorted(required):
        status = by_id.get(check_id)
        if status != "pass":
            problems.append(f"required check '{check_id}' is '{status}', expected pass")
    return not problems, problems


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--max-rounds", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    catalog = load_catalog(root)
    entry = next((f for f in catalog["fixtures"] if f["id"] == args.fixture), None)
    if entry is None:
        print(f"Unknown fixture: {args.fixture}", file=sys.stderr)
        return 1
    if not entry.get("tier2_autofix"):
        print(f"{args.fixture} is not tier-2 autofix", file=sys.stderr)
        return 1

    repair_path = root / entry["repair_hint_file"]
    fixture_dir = root / "benchmark" / "fixtures" / args.fixture
    goal_path = fixture_dir / "goal.json"
    goal = json.loads(goal_path.read_text(encoding="utf-8"))
    truth_path = root / "benchmark" / "truth" / f"{args.fixture}.json"

    ts = utc_timestamp()
    run_dir = root / "benchmark" / "runs" / args.fixture / f"autofix-{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    workspace = run_dir / "workspace"
    workspace.mkdir()
    app_html = workspace / "app.html"
    shutil.copy2(fixture_dir / "app.html", app_html)

    manifest = {"fixture_id": args.fixture, "timestamp": ts, "rounds": [], "passed": False}

    # Round 1 — detection on broken app (golden report)
    broken_round = root / "benchmark" / "golden" / args.fixture / "round-1"
    det_score = run_score(truth_path, broken_round / "report.json", run_dir / "detection.score.json", root)
    manifest["rounds"].append(
        {
            "round": 1,
            "phase": "detection",
            "score_exit": det_score.returncode,
        }
    )
    if det_score.returncode != 0:
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print("Detection phase failed", file=sys.stderr)
        return 1

    # Round 2 — apply repair + goal completion
    if repair_path.suffix == ".json":
        ok, problems = apply_repair(app_html, repair_path)
    else:
        ok, problems = False, [f"unsupported repair format: {repair_path}"]
    manifest["rounds"].append({"round": 2, "phase": "repair", "applied": ok, "problems": problems})
    if not ok:
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return 1

    repaired_round_src = root / "benchmark" / "golden" / f"{args.fixture}-repaired" / "round-1"
    repaired_round = run_dir / "round-2"
    shutil.copytree(repaired_round_src, repaired_round)

    proc = run_validate(repaired_round, goal_path, workspace, root)
    manifest["rounds"][-1]["validate_exit"] = proc.returncode
    if proc.returncode != 0:
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(proc.stdout, proc.stderr, sep="\n", file=sys.stderr)
        return 1

    report = json.loads((repaired_round / "report.json").read_text(encoding="utf-8"))
    goal_ok, goal_problems = score_goal_completion(goal, report)
    manifest["rounds"][-1]["goal_complete"] = goal_ok
    manifest["rounds"][-1]["goal_problems"] = goal_problems
    manifest["passed"] = goal_ok

    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0 if goal_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
