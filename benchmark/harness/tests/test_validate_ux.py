#!/usr/bin/env python3
"""Tests for the UX finding rules in scripts/validate_evidence.py."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_evidence import validate  # noqa: E402


BASE_CHECK = {
    "id": "only-check",
    "status": "pass",
    "evidence": ["screenshots/shot.png"],
}

GOAL = {"goal_id": "g", "checks": [{"id": "only-check", "statement": "x", "required": True}]}

VALID_MEASURED = {
    "id": "ux-1",
    "layer": "measured",
    "rule": "low-legibility",
    "severity": "blocker",
    "observation": "Subtitle renders at 1.5:1 against white.",
    "user_impact": "The subtitle is unreadable.",
    "evidence": ["screenshots/shot.png"],
    "measurement": {
        "metric": "contrast_ratio",
        "actual": 1.54,
        "threshold": 4.5,
        "unit": "ratio",
    },
}

VALID_JUDGED = {
    "id": "ux-2",
    "layer": "judged",
    "heuristic": "feedback-missing",
    "severity": "major",
    "observation": "Saving shows no confirmation.",
    "user_impact": "Users cannot tell whether the save worked.",
    "rationale": "No element changes after the request completes.",
    "confidence": "high",
    "evidence": ["screenshots/shot.png"],
}


class UxValidationTests(unittest.TestCase):
    def _run(self, ux_findings: list[dict], write_probe: bool = True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        round_dir = root / "round-1"
        (round_dir / "screenshots").mkdir(parents=True)
        (round_dir / "screenshots" / "shot.png").write_bytes(b"\x89PNG")
        (round_dir / "action.log").write_text("open app\n", encoding="utf-8")

        report = {
            "goal_id": "g",
            "round": 1,
            "playtester_run_id": "r",
            "checks": [BASE_CHECK],
            "ux_findings": ux_findings,
        }
        (round_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
        if write_probe:
            (round_dir / "ux_probe.1280.json").write_text("{}", encoding="utf-8")

        goal_path = root / "goal.json"
        goal_path.write_text(json.dumps(GOAL), encoding="utf-8")

        app_dir = root / "app"
        app_dir.mkdir()
        (app_dir / "index.html").write_text("<html></html>", encoding="utf-8")

        return validate(round_dir, goal_path, app_dir, skip_marker_scan=False)

    def test_valid_findings_pass(self) -> None:
        result = self._run([VALID_MEASURED, VALID_JUDGED])
        self.assertTrue(result.ok, result.problems)

    def test_judged_blocker_is_rejected(self) -> None:
        bad = dict(VALID_JUDGED, severity="blocker")
        result = self._run([bad])
        self.assertFalse(result.ok)
        self.assertTrue(any("may never block" in p for p in result.problems))

    def test_unknown_heuristic_is_rejected(self) -> None:
        bad = dict(VALID_JUDGED, heuristic="looks-ugly")
        result = self._run([bad])
        self.assertFalse(result.ok)
        self.assertTrue(any("unknown heuristic" in p for p in result.problems))

    def test_measured_without_measurement_is_rejected(self) -> None:
        bad = {k: v for k, v in VALID_MEASURED.items() if k != "measurement"}
        result = self._run([bad])
        self.assertFalse(result.ok)
        self.assertTrue(any("no measurement object" in p for p in result.problems))

    def test_measured_with_non_numeric_actual_is_rejected(self) -> None:
        bad = dict(VALID_MEASURED)
        bad["measurement"] = dict(VALID_MEASURED["measurement"], actual="very low")
        result = self._run([bad])
        self.assertFalse(result.ok)
        self.assertTrue(any("must be a number" in p for p in result.problems))

    def test_measured_without_probe_artifact_is_rejected(self) -> None:
        result = self._run([VALID_MEASURED], write_probe=False)
        self.assertFalse(result.ok)
        self.assertTrue(any("ux_probe" in p for p in result.problems))

    def test_judged_only_needs_no_probe_artifact(self) -> None:
        result = self._run([VALID_JUDGED], write_probe=False)
        self.assertTrue(result.ok, result.problems)

    def test_duplicate_ids_are_rejected(self) -> None:
        result = self._run([VALID_JUDGED, dict(VALID_JUDGED)])
        self.assertFalse(result.ok)
        self.assertTrue(any("duplicate" in p for p in result.problems))

    def test_missing_evidence_is_rejected(self) -> None:
        bad = dict(VALID_JUDGED, evidence=[])
        result = self._run([bad])
        self.assertFalse(result.ok)
        self.assertTrue(any("no evidence" in p for p in result.problems))

    def test_report_without_ux_findings_still_valid(self) -> None:
        result = self._run([], write_probe=False)
        self.assertTrue(result.ok, result.problems)


if __name__ == "__main__":
    unittest.main()
