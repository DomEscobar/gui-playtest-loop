#!/usr/bin/env python3
"""Validate that a playtest round produced structurally complete evidence.

This script does not and cannot judge whether the app works. It only checks
that the playtester actually looked: every goal check is covered, every pass
has an artifact that exists on disk, every fail has repro steps, the action
log is non-empty, no temporary instrumentation markers were left behind, and
every instrumented finding has an archived patch and an explicit clean-rerun
flag.

Usage:
    python validate_evidence.py --round-dir <path/to/evidence/round-N> \
        --goal <path/to/goal.json> \
        [--app-dir <path/to/app/source>] \
        [--skip-marker-scan]

Exit code 0 means the evidence package is structurally complete.
Exit code 1 means something is missing; every problem is printed.

Stdlib only, no third-party dependencies, so it runs next to any agent.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

INSTRUMENTATION_MARKER = "PLAYTEST-TMP"
VALID_STATUSES = {"pass", "fail", "blocked"}
VALID_FINDING_SOURCES = {"console", "network", "runtime-injection", "temp-log"}

DEFAULT_SCAN_EXCLUDES = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    ".cache",
}


@dataclass
class ValidationResult:
    problems: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.problems.append(message)

    @property
    def ok(self) -> bool:
        return not self.problems


def load_json(path: Path, result: ValidationResult, label: str) -> dict | None:
    if not path.is_file():
        result.add(f"{label} not found: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.add(f"{label} is not valid JSON ({path}): {exc}")
        return None


def check_report_shape(report: dict, result: ValidationResult) -> None:
    for required_key in ("goal_id", "round", "playtester_run_id", "checks"):
        if required_key not in report:
            result.add(f"report.json is missing required field '{required_key}'")

    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        result.add("report.json 'checks' must be a non-empty list")
        return

    for entry in checks:
        check_id = entry.get("id")
        if not check_id:
            result.add("a check result is missing 'id'")
            continue
        status = entry.get("status")
        if status not in VALID_STATUSES:
            result.add(f"check '{check_id}' has invalid status '{status}'")


def check_goal_coverage(goal: dict, report: dict, result: ValidationResult) -> None:
    goal_checks = goal.get("checks", [])
    goal_ids = {c["id"] for c in goal_checks if "id" in c}
    report_ids = {c["id"] for c in report.get("checks", []) if "id" in c}

    missing = goal_ids - report_ids
    for check_id in sorted(missing):
        result.add(f"goal check '{check_id}' has no result in report.json")


def check_evidence_artifacts(
    report: dict, round_dir: Path, result: ValidationResult
) -> None:
    for entry in report.get("checks", []):
        check_id = entry.get("id", "<unknown>")
        status = entry.get("status")
        evidence = entry.get("evidence") or []

        if status == "pass":
            if not evidence:
                result.add(f"check '{check_id}' is marked pass but has no evidence")
            _check_paths_exist(evidence, round_dir, check_id, result)

        elif status == "fail":
            if not evidence:
                result.add(f"check '{check_id}' is marked fail but has no evidence")
            if not entry.get("repro"):
                result.add(f"check '{check_id}' is marked fail but has no repro steps")
            if not entry.get("user_facing_bug"):
                result.add(
                    f"check '{check_id}' is marked fail but has no user_facing_bug"
                )
            _check_paths_exist(evidence, round_dir, check_id, result)


def _check_paths_exist(
    evidence_paths: list[str], round_dir: Path, check_id: str, result: ValidationResult
) -> None:
    for rel_path in evidence_paths:
        full_path = round_dir / rel_path
        if not full_path.is_file():
            result.add(
                f"check '{check_id}' references evidence that does not exist: {rel_path}"
            )


def check_action_log(round_dir: Path, result: ValidationResult) -> None:
    action_log = round_dir / "action.log"
    if not action_log.is_file():
        result.add(f"action.log not found in {round_dir}")
        return
    if not action_log.read_text(encoding="utf-8", errors="replace").strip():
        result.add("action.log exists but is empty")


def check_instrumented_findings(
    report: dict, round_dir: Path, result: ValidationResult
) -> None:
    findings = report.get("instrumented_findings") or []
    if not findings:
        return

    instrumentation_dir = round_dir / "instrumentation"
    has_patch = instrumentation_dir.is_dir() and any(
        p.suffix == ".patch" for p in instrumentation_dir.iterdir()
    )
    if not has_patch:
        result.add(
            "instrumented_findings is non-empty but no archived .patch file was "
            f"found under {instrumentation_dir}"
        )

    for finding in findings:
        finding_id = finding.get("id", "<unknown>")
        if finding.get("source") not in VALID_FINDING_SOURCES:
            result.add(
                f"instrumented finding '{finding_id}' has invalid source "
                f"'{finding.get('source')}'"
            )
        if "clean_rerun_reproduced" not in finding or not isinstance(
            finding["clean_rerun_reproduced"], bool
        ):
            result.add(
                f"instrumented finding '{finding_id}' is missing a boolean "
                "'clean_rerun_reproduced' flag"
            )
        if not finding.get("observation"):
            result.add(f"instrumented finding '{finding_id}' has no observation")


def scan_for_leftover_markers(
    app_dir: Path, result: ValidationResult, excludes: set[str]
) -> None:
    if not app_dir.is_dir():
        result.add(f"--app-dir does not exist or is not a directory: {app_dir}")
        return

    for path in app_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part in excludes for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        if INSTRUMENTATION_MARKER in content:
            result.add(
                f"leftover instrumentation marker '{INSTRUMENTATION_MARKER}' "
                f"found in {path}"
            )


def validate(
    round_dir: Path,
    goal_path: Path,
    app_dir: Path | None,
    skip_marker_scan: bool,
) -> ValidationResult:
    result = ValidationResult()

    report = load_json(round_dir / "report.json", result, "report.json")
    goal = load_json(goal_path, result, "goal.json")

    if report is not None:
        check_report_shape(report, result)
        check_evidence_artifacts(report, round_dir, result)
        check_instrumented_findings(report, round_dir, result)

    if report is not None and goal is not None:
        check_goal_coverage(goal, report, result)

    check_action_log(round_dir, result)

    if skip_marker_scan:
        pass
    elif app_dir is None:
        result.add(
            "no --app-dir given and --skip-marker-scan not set: cannot confirm "
            "no PLAYTEST-TMP markers were left in the app source"
        )
    else:
        scan_for_leftover_markers(app_dir, result, DEFAULT_SCAN_EXCLUDES)

    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--round-dir",
        required=True,
        type=Path,
        help="Path to evidence/round-N containing report.json and action.log",
    )
    parser.add_argument(
        "--goal",
        required=True,
        type=Path,
        help="Path to the frozen goal.json for this run",
    )
    parser.add_argument(
        "--app-dir",
        type=Path,
        default=None,
        help="Path to the app's source tree, scanned for leftover PLAYTEST-TMP markers",
    )
    parser.add_argument(
        "--skip-marker-scan",
        action="store_true",
        help="Skip the leftover-instrumentation-marker scan (not recommended)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = validate(
        round_dir=args.round_dir,
        goal_path=args.goal,
        app_dir=args.app_dir,
        skip_marker_scan=args.skip_marker_scan,
    )

    if result.ok:
        print("OK: evidence package is structurally complete.")
        return 0

    print("FAIL: evidence package is incomplete.", file=sys.stderr)
    for problem in result.problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
