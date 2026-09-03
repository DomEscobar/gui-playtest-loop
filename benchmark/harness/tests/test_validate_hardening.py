#!/usr/bin/env python3
"""Adversarial validation tests for version-2 strict playtest contracts."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seal_evidence import create_evidence_manifest  # noqa: E402
from validate_evidence import validate  # noqa: E402


GOAL = {
    "contract_version": 2,
    "goal_id": "g",
    "source_prompt": "test",
    "profile": "standard",
    "app": {"start_command": "serve", "url": "http://127.0.0.1"},
    "checks": [{"id": "a", "statement": "A is visible", "required": True}],
    "ux_policy": {"enabled": False, "gate_on": [], "viewports": [320]},
    "responsive_policy": {"breakpoints": [], "probe_breakpoint_edges": False},
    "protection": {"integrity_required": False},
}

REPORT = {
    "goal_id": "g",
    "round": 1,
    "playtester_run_id": "r",
    "evidence_origin": "live-agent",
    "phase_timestamps": {
        "behavior_verdict_frozen_at": "2026-01-01T10:00:00+00:00",
        "ux_verdict_frozen_at": "2026-01-01T10:01:00+00:00",
        "diagnosis_started_at": "2026-01-01T10:02:00+00:00",
    },
    "checks": [{"id": "a", "status": "pass", "evidence": ["screenshots/a.png"]}],
}


class HardeningValidationTests(unittest.TestCase):
    def _fixture(self, goal: dict | None = None, report: dict | None = None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        round_dir = root / "round-1"
        (round_dir / "screenshots").mkdir(parents=True)
        (round_dir / "screenshots" / "a.png").write_bytes(b"png")
        (round_dir / "action.log").write_text(
            json.dumps({
                "sequence": 1,
                "timestamp": "2026-01-01T09:59:00+00:00",
                "action": "open",
                "target": "app",
                "observation": "A is visible",
            }) + "\n",
            encoding="utf-8",
        )
        goal_data = copy.deepcopy(goal or GOAL)
        report_data = copy.deepcopy(report or REPORT)
        goal_path = root / "goal.json"
        goal_path.write_text(json.dumps(goal_data), encoding="utf-8")
        (round_dir / "report.json").write_text(json.dumps(report_data), encoding="utf-8")
        manifest = create_evidence_manifest(round_dir, report_data["evidence_origin"])
        (round_dir / "evidence_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        app_dir = root / "app"
        app_dir.mkdir()
        (app_dir / "index.html").write_text("<p>A</p>", encoding="utf-8")
        return root, round_dir, goal_path, app_dir

    def test_valid_standard_round_passes(self) -> None:
        _, round_dir, goal_path, app_dir = self._fixture()
        result = validate(round_dir, goal_path, app_dir, False)
        self.assertTrue(result.ok, result.problems)

    def test_tampered_evidence_is_rejected(self) -> None:
        _, round_dir, goal_path, app_dir = self._fixture()
        (round_dir / "screenshots" / "a.png").write_bytes(b"changed")
        result = validate(round_dir, goal_path, app_dir, False)
        self.assertTrue(any("hash mismatch" in problem for problem in result.problems))

    def test_diagnosis_before_verdict_is_rejected(self) -> None:
        report = copy.deepcopy(REPORT)
        report["phase_timestamps"]["diagnosis_started_at"] = "2026-01-01T09:00:00+00:00"
        _, round_dir, goal_path, app_dir = self._fixture(report=report)
        result = validate(round_dir, goal_path, app_dir, False)
        self.assertTrue(any("diagnosis timestamp" in problem for problem in result.problems))

    def test_breakpoint_edges_require_probe_artifacts(self) -> None:
        goal = copy.deepcopy(GOAL)
        goal["ux_policy"] = {"enabled": True, "gate_on": ["blocker"], "viewports": [320]}
        goal["responsive_policy"] = {"breakpoints": [768], "probe_breakpoint_edges": True}
        _, round_dir, goal_path, app_dir = self._fixture(goal=goal)
        result = validate(round_dir, goal_path, app_dir, False)
        expected = {320, 767, 768, 769}
        missing = {
            width for width in expected
            if any(f"required viewport {width}px" in problem for problem in result.problems)
        }
        self.assertEqual(missing, expected)

    def test_synthetic_origin_cannot_claim_strict_agent_run(self) -> None:
        report = copy.deepcopy(REPORT)
        report["evidence_origin"] = "synthetic-golden"
        _, round_dir, goal_path, app_dir = self._fixture(report=report)
        result = validate(round_dir, goal_path, app_dir, False)
        self.assertTrue(any("requires evidence_origin 'live-agent'" in p for p in result.problems))

    def test_release_requires_contract_integrity_manifest(self) -> None:
        goal = copy.deepcopy(GOAL)
        goal["profile"] = "release"
        _, round_dir, goal_path, app_dir = self._fixture(goal=goal)
        result = validate(round_dir, goal_path, app_dir, False)
        self.assertTrue(any("requires --integrity" in p for p in result.problems))

    def test_unstructured_action_log_is_rejected(self) -> None:
        _, round_dir, goal_path, app_dir = self._fixture()
        (round_dir / "action.log").write_text("clicked the button\n", encoding="utf-8")
        result = validate(round_dir, goal_path, app_dir, False)
        self.assertTrue(any("is not JSON" in p for p in result.problems))
        self.assertTrue(any("hash mismatch" in p for p in result.problems))

    def test_previous_pass_regression_fails(self) -> None:
        report = copy.deepcopy(REPORT)
        report["round"] = 2
        report["checks"] = [{
            "id": "a",
            "status": "fail",
            "evidence": ["screenshots/a.png"],
            "repro": ["open app"],
            "user_facing_bug": "A disappeared",
        }]
        report["regression"] = {
            "baseline_round": 1,
            "previous_passes_rechecked": ["a"],
            "regressions": ["a"],
        }
        root, round_dir, goal_path, app_dir = self._fixture(report=report)
        previous = root / "previous.json"
        previous.write_text(json.dumps(REPORT), encoding="utf-8")
        result = validate(round_dir, goal_path, app_dir, False, previous_report_path=previous)
        self.assertTrue(any("regressed: a" in problem for problem in result.problems))


if __name__ == "__main__":
    unittest.main()
