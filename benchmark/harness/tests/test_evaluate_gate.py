#!/usr/bin/env python3
"""Tests for deterministic goal gating."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluate_gate import evaluate  # noqa: E402


class EvaluateGateTests(unittest.TestCase):
    def test_required_behavior_failure_gates(self) -> None:
        goal = {"checks": [{"id": "a", "required": True}], "ux_policy": {"enabled": False}}
        report = {"checks": [{"id": "a", "status": "fail"}]}
        self.assertEqual(evaluate(goal, report)["behavior_failures"], ["a"])

    def test_project_style_rule_stays_advisory_when_not_selected(self) -> None:
        goal = {
            "checks": [{"id": "a", "required": True}],
            "ux_policy": {"enabled": True, "gate_on": ["minor"], "gate_rules": ["text-clipped"]},
        }
        report = {
            "checks": [{"id": "a", "status": "pass"}],
            "ux_findings": [{
                "id": "ux-1", "layer": "measured", "severity": "minor", "rule": "palette-sprawl"
            }],
        }
        self.assertTrue(evaluate(goal, report)["passed"])

    def test_selected_measured_rule_gates(self) -> None:
        goal = {
            "checks": [{"id": "a", "required": True}],
            "ux_policy": {"enabled": True, "gate_on": ["blocker"], "gate_rules": ["text-clipped"]},
        }
        report = {
            "checks": [{"id": "a", "status": "pass"}],
            "ux_findings": [{
                "id": "ux-1", "layer": "measured", "severity": "blocker", "rule": "text-clipped"
            }],
        }
        self.assertEqual(evaluate(goal, report)["gating_ux_findings"], ["ux-1"])

    def test_judged_finding_never_gates(self) -> None:
        goal = {
            "checks": [{"id": "a", "required": True}],
            "ux_policy": {"enabled": True, "gate_on": ["major"], "gate_rules": ["feedback-missing"]},
        }
        report = {
            "checks": [{"id": "a", "status": "pass"}],
            "ux_findings": [{
                "id": "ux-1", "layer": "judged", "severity": "major", "heuristic": "feedback-missing"
            }],
        }
        self.assertTrue(evaluate(goal, report)["passed"])


if __name__ == "__main__":
    unittest.main()
