#!/usr/bin/env python3
"""Unit tests for benchmark/harness/score.py (stdlib unittest)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))

from score import score_fixture  # noqa: E402


class ScoreFixtureTests(unittest.TestCase):
    def test_clean_control_all_pass(self) -> None:
        truth = {
            "fixture_id": "memory-clean-control",
            "must_fail": [],
            "must_pass": ["a", "b"],
        }
        report = {"checks": [{"id": "a", "status": "pass"}, {"id": "b", "status": "pass"}]}
        result = score_fixture(truth, report)
        self.assertTrue(result.passed)
        self.assertEqual(result.detection_recall, 1.0)

    def test_must_fail_detected(self) -> None:
        truth = {
            "fixture_id": "x",
            "must_fail": ["broken"],
            "must_pass": ["ok"],
        }
        report = {
            "checks": [
                {"id": "ok", "status": "pass"},
                {"id": "broken", "status": "fail"},
            ]
        }
        result = score_fixture(truth, report)
        self.assertTrue(result.passed)
        self.assertEqual(result.expected_fails_hit, ["broken"])

    def test_cascade_from_primary_fail(self) -> None:
        truth = {
            "fixture_id": "dead-start",
            "primary_fail": "start-begins-game",
            "must_fail": ["start-begins-game"],
            "cascade_fail_if_primary": {
                "start-begins-game": ["card-flips-on-click", "mismatch-flips-back"]
            },
            "must_pass": ["initial-state-hidden"],
        }
        report = {
            "checks": [
                {"id": "initial-state-hidden", "status": "pass"},
                {"id": "start-begins-game", "status": "fail"},
                {"id": "card-flips-on-click", "status": "blocked"},
                {"id": "mismatch-flips-back", "status": "fail"},
            ]
        }
        result = score_fixture(truth, report)
        self.assertTrue(result.passed)
        self.assertIn("card-flips-on-click", result.expected_fails_hit)

    def test_missed_must_fail(self) -> None:
        truth = {"fixture_id": "x", "must_fail": ["broken"], "must_pass": []}
        report = {"checks": [{"id": "broken", "status": "pass"}]}
        result = score_fixture(truth, report)
        self.assertFalse(result.passed)
        self.assertEqual(result.expected_fails_missed, ["broken"])

    def test_ux_rule_hit(self) -> None:
        truth = {"fixture_id": "x", "must_pass": [], "must_flag_ux": ["viewport-overflow"]}
        report = {
            "checks": [{"id": "a", "status": "pass"}],
            "ux_findings": [
                {"id": "ux-1", "layer": "measured", "rule": "viewport-overflow"}
            ],
        }
        result = score_fixture(truth, report)
        self.assertTrue(result.passed, result.problems)
        self.assertEqual(result.ux_recall, 1.0)

    def test_ux_rule_missed(self) -> None:
        truth = {"fixture_id": "x", "must_pass": [], "must_flag_ux": ["viewport-overflow"]}
        report = {"checks": [{"id": "a", "status": "pass"}], "ux_findings": []}
        result = score_fixture(truth, report)
        self.assertFalse(result.passed)
        self.assertEqual(result.ux_rules_missed, ["viewport-overflow"])
        self.assertEqual(result.ux_recall, 0.0)

    def test_judged_finding_does_not_satisfy_ux_rule(self) -> None:
        truth = {"fixture_id": "x", "must_pass": [], "must_flag_ux": ["low-legibility"]}
        report = {
            "checks": [{"id": "a", "status": "pass"}],
            "ux_findings": [
                {"id": "ux-1", "layer": "judged", "rule": "low-legibility"}
            ],
        }
        result = score_fixture(truth, report)
        self.assertFalse(result.passed)

    def test_control_rejects_ux_false_positives(self) -> None:
        truth = {"fixture_id": "control", "must_pass": [], "forbid_ux_findings": True}
        report = {
            "checks": [{"id": "a", "status": "pass"}],
            "ux_findings": [
                {"id": "ux-1", "layer": "measured", "rule": "low-legibility"}
            ],
        }
        result = score_fixture(truth, report)
        self.assertFalse(result.passed)
        self.assertEqual(result.ux_false_positives, ["low-legibility"])

    def test_golden_landing_visual_defects(self) -> None:
        root = Path(__file__).resolve().parents[2]
        truth = json.loads(
            (root / "truth" / "landing-visual-defects.json").read_text(encoding="utf-8")
        )
        report = json.loads(
            (root / "golden" / "landing-visual-defects" / "round-1" / "report.json").read_text(
                encoding="utf-8"
            )
        )
        result = score_fixture(truth, report)
        self.assertTrue(result.passed, result.problems)
        self.assertEqual(result.ux_recall, 1.0)

    def test_golden_memory_dead_start_button(self) -> None:
        root = Path(__file__).resolve().parents[2]
        truth = json.loads(
            (root / "truth" / "memory-dead-start-button.json").read_text(encoding="utf-8")
        )
        report = json.loads(
            (root / "golden" / "memory-dead-start-button" / "round-1" / "report.json").read_text(
                encoding="utf-8"
            )
        )
        result = score_fixture(truth, report)
        self.assertTrue(result.passed, result.problems)


if __name__ == "__main__":
    unittest.main()
