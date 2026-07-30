#!/usr/bin/env python3
"""Score a playtest report against a ground-truth manifest."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScoreResult:
    fixture_id: str
    passed: bool
    problems: list[str] = field(default_factory=list)
    expected_fails_hit: list[str] = field(default_factory=list)
    expected_fails_missed: list[str] = field(default_factory=list)
    false_passes: list[str] = field(default_factory=list)
    false_fails: list[str] = field(default_factory=list)

    @property
    def detection_recall(self) -> float:
        must_fail = set(self.expected_fails_hit) | set(self.expected_fails_missed)
        if not must_fail:
            return 1.0
        return len(self.expected_fails_hit) / len(must_fail)

    @property
    def detection_precision(self) -> float:
        reported_fails = set(self.expected_fails_hit) | set(self.false_fails)
        if not reported_fails:
            return 1.0 if not self.false_fails else 0.0
        return len(self.expected_fails_hit) / len(reported_fails)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _status_satisfies_fail(status: str | None, truth: dict) -> bool:
    if status == "fail":
        return True
    if status == "blocked" and truth.get("accept_blocked_as_fail", True):
        return True
    return False


def score_fixture(truth: dict, report: dict) -> ScoreResult:
    result = ScoreResult(fixture_id=truth["fixture_id"], passed=True)
    by_id = {c["id"]: c.get("status") for c in report.get("checks", [])}

    primary = truth.get("primary_fail")
    cascade_map = truth.get("cascade_fail_if_primary", {})
    cascade_ids: set[str] = set()
    if primary and _status_satisfies_fail(by_id.get(primary), truth):
        cascade_ids = set(cascade_map.get(primary, []))

    explicit_must_fail = set(truth.get("must_fail", []))
    all_must_fail = explicit_must_fail | cascade_ids

    for check_id in sorted(all_must_fail):
        status = by_id.get(check_id)
        if status is None:
            result.passed = False
            result.problems.append(f"missing result for must-fail check '{check_id}'")
            result.expected_fails_missed.append(check_id)
        elif not _status_satisfies_fail(status, truth):
            result.passed = False
            result.problems.append(
                f"must-fail check '{check_id}' reported as '{status}', expected fail or blocked"
            )
            result.expected_fails_missed.append(check_id)
        else:
            result.expected_fails_hit.append(check_id)

    for check_id in truth.get("must_pass", []):
        status = by_id.get(check_id)
        if status is None:
            result.passed = False
            result.problems.append(f"missing result for must-pass check '{check_id}'")
            result.false_fails.append(check_id)
        elif status != "pass":
            result.passed = False
            result.problems.append(
                f"must-pass check '{check_id}' reported as '{status}', expected 'pass'"
            )
            result.false_fails.append(check_id)

    for check_id, status in by_id.items():
        all_expected = all_must_fail | set(truth.get("must_pass", []))
        optional = set(truth.get("optional_pass", []))
        if check_id not in all_expected and check_id not in optional and status == "fail":
            if check_id not in result.false_fails:
                result.false_fails.append(check_id)
            result.passed = False
            result.problems.append(f"unexpected fail on check '{check_id}'")

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    truth = load_json(args.truth)
    report = load_json(args.report)
    result = score_fixture(truth, report)

    payload = {
        "fixture_id": result.fixture_id,
        "passed": result.passed,
        "detection_recall": result.detection_recall,
        "detection_precision": result.detection_precision,
        "expected_fails_hit": result.expected_fails_hit,
        "expected_fails_missed": result.expected_fails_missed,
        "false_fails": result.false_fails,
        "problems": result.problems,
    }

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if result.passed:
        print(
            f"PASS {result.fixture_id} "
            f"(recall={result.detection_recall:.2f}, precision={result.detection_precision:.2f})"
        )
        return 0

    print(f"FAIL {result.fixture_id}", file=sys.stderr)
    for problem in result.problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
