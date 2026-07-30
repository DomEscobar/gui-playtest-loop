#!/usr/bin/env python3
"""Run Tier-1 detection benchmark across all catalog fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib import load_catalog, repo_root, run_score, run_validate, utc_timestamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=("golden", "runs"),
        default="golden",
        help="Score benchmark/golden/<id>/round-1 or benchmark/runs/<id>/round-1",
    )
    parser.add_argument("--round-name", default="round-1")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--split", choices=("all", "train", "held-out"), default="all")
    parser.add_argument("--tier1-only", action="store_true", default=True)
    return parser.parse_args()


def round_dir_for(root: Path, source: str, fixture_id: str, round_name: str) -> Path:
    base = "golden" if source == "golden" else "runs"
    return root / "benchmark" / base / fixture_id / round_name


def main() -> int:
    args = parse_args()
    root = repo_root()
    catalog = load_catalog(root)
    ts = utc_timestamp()
    results_dir = root / "benchmark" / "results" / ts
    results_dir.mkdir(parents=True, exist_ok=True)

    fixtures = catalog["fixtures"]
    if args.split != "all":
        fixtures = [f for f in fixtures if f.get("split") == args.split]

    aggregate = {
        "timestamp": ts,
        "source": args.source,
        "split": args.split,
        "fixtures": [],
        "totals": {
            "count": 0,
            "passed": 0,
            "failed": 0,
            "detection_recall_sum": 0.0,
            "detection_precision_sum": 0.0,
        },
        "thresholds": catalog.get("thresholds", {}),
        "tier1_passed": False,
    }

    exit_code = 0
    for entry in fixtures:
        fixture_id = entry["id"]
        if args.tier1_only and not entry.get("tier1", True):
            continue

        fixture_dir = root / "benchmark" / "fixtures" / fixture_id
        goal_path = fixture_dir / "goal.json"
        truth_path = root / "benchmark" / "truth" / f"{fixture_id}.json"
        rd = round_dir_for(root, args.source, fixture_id, args.round_name)
        report_path = rd / "report.json"

        row = {
            "fixture_id": fixture_id,
            "class": entry.get("class"),
            "split": entry.get("split"),
            "round_dir": str(rd),
            "validate_ok": None,
            "score_ok": None,
            "detection_recall": None,
            "detection_precision": None,
            "problems": [],
        }

        if not report_path.is_file():
            row["score_ok"] = False
            row["problems"].append(f"missing report: {report_path}")
            aggregate["fixtures"].append(row)
            aggregate["totals"]["failed"] += 1
            exit_code = 1
            continue

        if not args.skip_validate:
            proc = run_validate(rd, goal_path, fixture_dir, root)
            row["validate_ok"] = proc.returncode == 0
            if proc.returncode != 0:
                row["problems"].append(proc.stdout.strip() or proc.stderr.strip())
                aggregate["fixtures"].append(row)
                aggregate["totals"]["failed"] += 1
                exit_code = 1
                continue

        score_json = results_dir / f"{fixture_id}.score.json"
        proc = run_score(truth_path, report_path, score_json, root)
        row["score_ok"] = proc.returncode == 0
        if score_json.is_file():
            score_data = json.loads(score_json.read_text(encoding="utf-8"))
            row["detection_recall"] = score_data.get("detection_recall")
            row["detection_precision"] = score_data.get("detection_precision")
            row["problems"] = score_data.get("problems", [])
        else:
            row["problems"].append(proc.stderr.strip() or proc.stdout.strip())

        aggregate["totals"]["count"] += 1
        if row["score_ok"]:
            aggregate["totals"]["passed"] += 1
            aggregate["totals"]["detection_recall_sum"] += row["detection_recall"] or 0.0
            aggregate["totals"]["detection_precision_sum"] += row["detection_precision"] or 0.0
        else:
            aggregate["totals"]["failed"] += 1
            exit_code = 1

        aggregate["fixtures"].append(row)
        status = "PASS" if row["score_ok"] else "FAIL"
        print(f"{status} {fixture_id}")

    n = aggregate["totals"]["passed"]
    if n:
        aggregate["totals"]["detection_recall_avg"] = (
            aggregate["totals"]["detection_recall_sum"] / n
        )
        aggregate["totals"]["detection_precision_avg"] = (
            aggregate["totals"]["detection_precision_sum"] / n
        )
    else:
        aggregate["totals"]["detection_recall_avg"] = 0.0
        aggregate["totals"]["detection_precision_avg"] = 0.0

    thresholds = catalog.get("thresholds", {})
    recall_min = thresholds.get("tier1_detection_recall_min", 0.85)
    precision_min = thresholds.get("tier1_detection_precision_min", 0.85)
    aggregate["tier1_passed"] = (
        exit_code == 0
        and aggregate["totals"]["detection_recall_avg"] >= recall_min
        and aggregate["totals"]["detection_precision_avg"] >= precision_min
    )

    (results_dir / "benchmark_summary.json").write_text(
        json.dumps(aggregate, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"\nTier-1: {aggregate['totals']['passed']}/{aggregate['totals']['count']} fixtures passed"
    )
    print(
        f"Avg recall={aggregate['totals']['detection_recall_avg']:.2f} "
        f"precision={aggregate['totals']['detection_precision_avg']:.2f}"
    )
    print(f"Summary: {results_dir / 'benchmark_summary.json'}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
