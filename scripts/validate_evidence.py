#!/usr/bin/env python3
"""Validate that a playtest round produced structurally complete evidence.

This script does not and cannot judge whether the app works or looks good. It
only checks that the playtester actually looked: every goal check is covered,
every pass has an artifact that exists on disk, every fail has repro steps,
the action log is non-empty, no temporary instrumentation markers were left
behind, every instrumented finding has an archived patch and an explicit
clean-rerun flag, and every UX finding obeys the two-layer contract — measured
findings carry numbers plus a saved probe run, judged findings name a known
heuristic and never claim blocker severity.

Version-2 standard/release goals also require honest evidence origin,
timezone-aware phase and action timestamps, sealed evidence hashes, complete
viewport probes, optional protected-contract integrity, and pass-to-fail
regression detection.

Usage:
    python validate_evidence.py --round-dir <path/to/evidence/round-N> \
        --goal <path/to/goal.json> \
        [--app-dir <path/to/app/source>] \
        [--integrity <path/to/protected-manifest.json>] \
        [--previous-report <path/to/previous/report.json>] \
        [--skip-marker-scan]

Exit code 0 means the evidence package is structurally complete.
Exit code 1 means something is missing; every problem is printed.

Stdlib only, no third-party dependencies, so it runs next to any agent.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from seal_contract import digest, verify_manifest

INSTRUMENTATION_MARKER = "PLAYTEST-TMP"
VALID_STATUSES = {"pass", "fail", "blocked"}
VALID_FINDING_SOURCES = {"console", "network", "runtime-injection", "temp-log"}

VALID_UX_LAYERS = {"measured", "judged"}
VALID_UX_SEVERITIES = {"blocker", "major", "minor"}
VALID_UX_CONFIDENCE = {"high", "medium", "low"}
VALID_EVIDENCE_ORIGINS = {"live-agent", "human-live", "replayed", "synthetic-golden"}
STRICT_PROFILES = {"standard", "release"}

# Judged findings must name one of these. Freeform aesthetic commentary is not
# a finding. See reference/ux-review.md.
VALID_UX_HEURISTICS = {
    "hierarchy-primary-action",
    "hierarchy-competing-emphasis",
    "affordance-unclear",
    "feedback-missing",
    "state-missing",
    "consistency-drift",
    "copy-unclear",
    "density-cramped",
    "density-bloated",
    "rhythm-templated",
    "motion-excessive",
    "motion-missing",
    "tone-mismatch",
    "flow-friction",
}

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

    round_number = report.get("round")
    if not isinstance(round_number, int) or isinstance(round_number, bool) or round_number < 1:
        result.add("report.json 'round' must be a positive integer")

    seen_ids: set[str] = set()
    for entry in checks:
        if not isinstance(entry, dict):
            result.add("each check result must be an object")
            continue
        check_id = entry.get("id")
        if not check_id:
            result.add("a check result is missing 'id'")
            continue
        if check_id in seen_ids:
            result.add(f"duplicate check result id '{check_id}'")
        seen_ids.add(check_id)
        status = entry.get("status")
        if status not in VALID_STATUSES:
            result.add(f"check '{check_id}' has invalid status '{status}'")


def check_goal_coverage(goal: dict, report: dict, result: ValidationResult) -> None:
    goal_checks = goal.get("checks", [])
    goal_ids = {c["id"] for c in goal_checks if isinstance(c, dict) and "id" in c}
    report_ids = {
        c["id"] for c in report.get("checks", []) if isinstance(c, dict) and "id" in c
    }

    missing = goal_ids - report_ids
    for check_id in sorted(missing):
        result.add(f"goal check '{check_id}' has no result in report.json")
    unexpected = report_ids - goal_ids
    for check_id in sorted(unexpected):
        result.add(f"report check '{check_id}' does not exist in goal.json")

    if report.get("goal_id") != goal.get("goal_id"):
        result.add(
            f"report goal_id {report.get('goal_id')!r} does not match "
            f"goal.json {goal.get('goal_id')!r}"
        )


def check_evidence_artifacts(
    report: dict, round_dir: Path, result: ValidationResult
) -> None:
    for entry in report.get("checks", []):
        if not isinstance(entry, dict):
            continue
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
        if not isinstance(finding, dict):
            result.add("an instrumented finding must be an object")
            continue
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


def check_ux_findings(report: dict, round_dir: Path, result: ValidationResult) -> None:
    """Enforce the two-layer UX contract from reference/ux-review.md.

    Measured findings must carry numbers and be backed by a saved probe run.
    Judged findings must name a known heuristic, explain themselves, and may
    never reach blocker severity — a judgment call cannot fail a goal.
    """
    findings = report.get("ux_findings") or []
    if not findings:
        return

    seen_ids: set[str] = set()
    has_measured = False

    for finding in findings:
        if not isinstance(finding, dict):
            result.add("a ux finding must be an object")
            continue
        finding_id = finding.get("id") or "<unknown>"
        if not finding.get("id"):
            result.add("a ux finding is missing 'id'")
        elif finding_id in seen_ids:
            result.add(f"duplicate ux finding id '{finding_id}'")
        seen_ids.add(finding_id)

        layer = finding.get("layer")
        if layer not in VALID_UX_LAYERS:
            result.add(f"ux finding '{finding_id}' has invalid layer '{layer}'")

        severity = finding.get("severity")
        if severity not in VALID_UX_SEVERITIES:
            result.add(f"ux finding '{finding_id}' has invalid severity '{severity}'")

        for field in ("observation", "user_impact"):
            if not finding.get(field):
                result.add(f"ux finding '{finding_id}' has no {field}")

        evidence = finding.get("evidence") or []
        if not evidence:
            result.add(f"ux finding '{finding_id}' has no evidence")
        _check_paths_exist(evidence, round_dir, f"ux finding '{finding_id}'", result)

        if layer == "measured":
            has_measured = True
            _check_measured_ux_finding(finding, finding_id, result)
        elif layer == "judged":
            _check_judged_ux_finding(finding, finding_id, severity, result)

    if has_measured and not any(round_dir.glob("ux_probe*.json")):
        result.add(
            "ux_findings contains measured findings but no ux_probe*.json artifact "
            f"was found in {round_dir}"
        )


def _check_measured_ux_finding(
    finding: dict, finding_id: str, result: ValidationResult
) -> None:
    if not finding.get("rule"):
        result.add(f"measured ux finding '{finding_id}' has no probe rule id")

    measurement = finding.get("measurement")
    if not isinstance(measurement, dict):
        result.add(f"measured ux finding '{finding_id}' has no measurement object")
        return

    for field in ("metric", "unit"):
        if not measurement.get(field):
            result.add(
                f"measured ux finding '{finding_id}' measurement is missing '{field}'"
            )
    for field in ("actual", "threshold"):
        value = measurement.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            result.add(
                f"measured ux finding '{finding_id}' measurement '{field}' "
                "must be a number"
            )


def _check_judged_ux_finding(
    finding: dict, finding_id: str, severity: str | None, result: ValidationResult
) -> None:
    heuristic = finding.get("heuristic")
    if heuristic not in VALID_UX_HEURISTICS:
        result.add(
            f"judged ux finding '{finding_id}' names unknown heuristic "
            f"'{heuristic}'; see reference/ux-review.md"
        )
    if not finding.get("rationale"):
        result.add(f"judged ux finding '{finding_id}' has no rationale")
    if finding.get("confidence") not in VALID_UX_CONFIDENCE:
        result.add(
            f"judged ux finding '{finding_id}' has invalid confidence "
            f"'{finding.get('confidence')}'"
        )
    if severity == "blocker":
        result.add(
            f"judged ux finding '{finding_id}' is marked blocker; a judgment call "
            "may never block the goal, use major instead"
        )


def _parse_timestamp(value: object, label: str, result: ValidationResult) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        result.add(f"missing phase timestamp '{label}'")
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        result.add(f"phase timestamp '{label}' is not valid ISO-8601: {value!r}")
        return None
    if parsed.tzinfo is None:
        result.add(f"phase timestamp '{label}' must include a timezone")
        return None
    return parsed


def check_phase_timestamps(goal: dict, report: dict, result: ValidationResult) -> None:
    timestamps = report.get("phase_timestamps")
    if not isinstance(timestamps, dict):
        result.add("strict profile requires a phase_timestamps object")
        return
    behavior = _parse_timestamp(
        timestamps.get("behavior_verdict_frozen_at"),
        "behavior_verdict_frozen_at",
        result,
    )
    ux = None
    if goal.get("ux_policy", {}).get("enabled", True):
        ux = _parse_timestamp(
            timestamps.get("ux_verdict_frozen_at"),
            "ux_verdict_frozen_at",
            result,
        )
    diagnosis_value = timestamps.get("diagnosis_started_at")
    diagnosis = None
    if diagnosis_value is not None:
        diagnosis = _parse_timestamp(diagnosis_value, "diagnosis_started_at", result)
    if behavior and ux and ux < behavior:
        result.add("ux verdict timestamp precedes behavior verdict timestamp")
    frozen = ux or behavior
    if diagnosis and frozen and diagnosis < frozen:
        result.add("diagnosis timestamp precedes the final frozen verdict")


def required_probe_widths(goal: dict, result: ValidationResult) -> set[int]:
    ux_policy = goal.get("ux_policy") or {}
    if not ux_policy.get("enabled", True):
        return set()
    widths: set[int] = set()
    for raw in ux_policy.get("viewports", [320, 768, 1280]):
        try:
            widths.add(int(raw))
        except (TypeError, ValueError):
            result.add(f"invalid UX viewport width: {raw!r}")
    responsive = goal.get("responsive_policy") or {}
    if responsive.get("probe_breakpoint_edges", False):
        for breakpoint in responsive.get("breakpoints", []):
            try:
                width = int(breakpoint)
            except (TypeError, ValueError):
                result.add(f"invalid responsive breakpoint: {breakpoint!r}")
                continue
            widths.update({width - 1, width, width + 1})
    return {width for width in widths if width > 0}


def check_probe_coverage(goal: dict, round_dir: Path, result: ValidationResult) -> None:
    for width in sorted(required_probe_widths(goal, result)):
        path = round_dir / f"ux_probe.{width}.json"
        if not path.is_file():
            result.add(f"required viewport {width}px has no ux_probe.{width}.json artifact")
            continue
        probe = load_json(path, result, f"ux probe {width}px")
        if probe is None:
            continue
        actual_width = (probe.get("viewport") or {}).get("width")
        if actual_width != width:
            result.add(
                f"ux_probe.{width}.json reports viewport width {actual_width!r}, expected {width}"
            )


def check_structured_action_log(round_dir: Path, result: ValidationResult) -> None:
    path = round_dir / "action.log"
    if not path.is_file():
        return
    previous_sequence = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            result.add(f"action.log line {line_number} is not JSON")
            continue
        if not isinstance(row, dict):
            result.add(f"action.log line {line_number} must be a JSON object")
            continue
        for field in ("sequence", "timestamp", "action", "observation"):
            if field not in row:
                result.add(f"action.log line {line_number} is missing '{field}'")
        sequence = row.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= previous_sequence:
            result.add(f"action.log line {line_number} has non-increasing integer sequence")
        else:
            previous_sequence = sequence
        if "timestamp" in row:
            _parse_timestamp(row["timestamp"], f"action.log line {line_number}", result)


def _manifest_referenced_paths(report: dict, round_dir: Path) -> set[str]:
    paths = {"action.log"}
    for collection in (report.get("checks", []), report.get("ux_findings", [])):
        for entry in collection:
            if not isinstance(entry, dict):
                continue
            for raw in entry.get("evidence") or []:
                paths.add(Path(raw).as_posix())
    paths.update(path.name for path in round_dir.glob("ux_probe.*.json"))
    return paths


def check_evidence_manifest(report: dict, round_dir: Path, result: ValidationResult) -> None:
    path = round_dir / "evidence_manifest.json"
    manifest = load_json(path, result, "evidence_manifest.json")
    if manifest is None:
        return
    if manifest.get("version") != 1 or not isinstance(manifest.get("files"), list):
        result.add("evidence manifest must have version 1 and a files array")
        return
    if manifest.get("origin") != report.get("evidence_origin"):
        result.add("evidence manifest origin does not match report evidence_origin")
    covered: set[str] = set()
    for entry in manifest["files"]:
        raw = entry.get("path")
        if not isinstance(raw, str):
            result.add("evidence manifest entry is missing path")
            continue
        candidate = (round_dir / raw).resolve()
        try:
            candidate.relative_to(round_dir.resolve())
        except ValueError:
            result.add(f"evidence manifest path escapes round directory: {raw}")
            continue
        covered.add(Path(raw).as_posix())
        if not candidate.is_file():
            result.add(f"sealed evidence is missing: {raw}")
        elif digest(candidate) != entry.get("sha256"):
            result.add(f"sealed evidence hash mismatch: {raw}")
    for raw in sorted(_manifest_referenced_paths(report, round_dir) - covered):
        result.add(f"evidence manifest does not cover referenced artifact: {raw}")


def check_regression(
    goal: dict,
    report: dict,
    previous_report_path: Path | None,
    result: ValidationResult,
) -> None:
    round_number = report.get("round", 1)
    if not isinstance(round_number, int) or isinstance(round_number, bool):
        return
    if round_number <= 1:
        return
    if previous_report_path is None:
        result.add("strict repair round requires --previous-report")
        return
    previous = load_json(previous_report_path, result, "previous report")
    if previous is None:
        return
    required = {
        entry["id"]
        for entry in goal.get("checks", [])
        if isinstance(entry, dict) and "id" in entry and entry.get("required", True)
    }
    previous_passes = {
        entry.get("id")
        for entry in previous.get("checks", [])
        if isinstance(entry, dict)
        and entry.get("status") == "pass"
        and entry.get("id") in required
    }
    current = {
        entry.get("id"): entry.get("status")
        for entry in report.get("checks", [])
        if isinstance(entry, dict)
    }
    regressions = sorted(check_id for check_id in previous_passes if current.get(check_id) != "pass")
    regression = report.get("regression")
    if not isinstance(regression, dict):
        result.add("strict repair round requires a regression object")
        return
    rechecked = set(regression.get("previous_passes_rechecked") or [])
    if rechecked != previous_passes:
        result.add("regression.previous_passes_rechecked does not match previous required passes")
    declared = sorted(regression.get("regressions") or [])
    if declared != regressions:
        result.add("regression.regressions does not match observed pass-to-nonpass transitions")
    for check_id in regressions:
        result.add(f"previously passing required check regressed: {check_id}")


def check_contract_integrity(
    goal: dict,
    integrity_path: Path | None,
    result: ValidationResult,
) -> None:
    profile = goal.get("profile", "standard")
    protection = goal.get("protection") or {}
    required = profile == "release" or protection.get("integrity_required", False)
    if integrity_path is None:
        if required:
            result.add("selected profile requires --integrity")
        return
    problems = verify_manifest(integrity_path)
    for problem in problems:
        result.add(problem)
    if problems:
        return
    manifest = json.loads(integrity_path.read_text(encoding="utf-8"))
    labels = {entry.get("label") for entry in manifest.get("files", [])}
    required_labels = {"goal", "goal-schema", "report-schema", "validator"}
    if goal.get("ux_policy", {}).get("enabled", True):
        required_labels.add("ux-probe")
    for label in sorted(required_labels - labels):
        result.add(f"integrity manifest is missing protected label '{label}'")


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
    integrity_path: Path | None = None,
    previous_report_path: Path | None = None,
    force_strict: bool = False,
) -> ValidationResult:
    result = ValidationResult()

    report = load_json(round_dir / "report.json", result, "report.json")
    goal = load_json(goal_path, result, "goal.json")

    if report is not None:
        check_report_shape(report, result)
        check_evidence_artifacts(report, round_dir, result)
        check_ux_findings(report, round_dir, result)
        check_instrumented_findings(report, round_dir, result)
        if (round_dir / "evidence_manifest.json").is_file():
            check_evidence_manifest(report, round_dir, result)

    if report is not None and goal is not None:
        check_goal_coverage(goal, report, result)

        strict = force_strict or (
            goal.get("contract_version", 1) >= 2
            and goal.get("profile", "standard") in STRICT_PROFILES
        )
        if strict:
            origin = report.get("evidence_origin")
            if origin not in VALID_EVIDENCE_ORIGINS:
                result.add(f"strict profile has invalid evidence_origin {origin!r}")
            elif origin != "live-agent":
                result.add(
                    f"strict agent playtest requires evidence_origin 'live-agent', got {origin!r}"
                )
            check_phase_timestamps(goal, report, result)
            check_probe_coverage(goal, round_dir, result)
            check_structured_action_log(round_dir, result)
            if not (round_dir / "evidence_manifest.json").is_file():
                result.add(f"evidence_manifest.json not found: {round_dir / 'evidence_manifest.json'}")
            check_regression(goal, report, previous_report_path, result)
            check_contract_integrity(goal, integrity_path, result)

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
    parser.add_argument(
        "--integrity",
        type=Path,
        default=None,
        help="Externally owned protected-contract integrity manifest",
    )
    parser.add_argument(
        "--previous-report",
        type=Path,
        default=None,
        help="Previous round report, required for strict repair rounds",
    )
    parser.add_argument(
        "--require-strict",
        action="store_true",
        help="Apply strict provenance, timestamps, viewport, sealing, and regression checks",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = validate(
        round_dir=args.round_dir,
        goal_path=args.goal,
        app_dir=args.app_dir,
        skip_marker_scan=args.skip_marker_scan,
        integrity_path=args.integrity,
        previous_report_path=args.previous_report,
        force_strict=args.require_strict,
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
