#!/usr/bin/env python3
"""Deterministically evaluate a validated playtest report against its frozen goal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate(goal: dict, report: dict) -> dict:
    required = {entry["id"] for entry in goal.get("checks", []) if entry.get("required", True)}
    statuses = {entry.get("id"): entry.get("status") for entry in report.get("checks", [])}
    behavior_failures = sorted(check_id for check_id in required if statuses.get(check_id) != "pass")

    policy = goal.get("ux_policy") or {}
    severities = set(policy.get("gate_on", ["blocker"])) if policy.get("enabled", True) else set()
    configured_rules = policy.get("gate_rules")
    rules = set(configured_rules) if configured_rules is not None else None
    ux_failures = []
    for finding in report.get("ux_findings") or []:
        if finding.get("layer") != "measured" or finding.get("severity") not in severities:
            continue
        if rules is not None and finding.get("rule") not in rules:
            continue
        ux_failures.append(finding.get("id") or finding.get("rule") or "<unknown>")

    regressions = sorted((report.get("regression") or {}).get("regressions") or [])
    return {
        "passed": not behavior_failures and not ux_failures and not regressions,
        "behavior_failures": behavior_failures,
        "gating_ux_findings": sorted(ux_failures),
        "regressions": regressions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goal", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    try:
        goal = json.loads(args.goal.read_text(encoding="utf-8"))
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}")
        return 2
    result = evaluate(goal, report)
    payload = json.dumps(result, indent=2) + "\n"
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
