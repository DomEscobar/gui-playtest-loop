#!/usr/bin/env python3
"""Tests for protected-contract and evidence sealing helpers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seal_contract import create_manifest, verify_manifest  # noqa: E402
from seal_evidence import create_evidence_manifest  # noqa: E402


class IntegrityTests(unittest.TestCase):
    def test_contract_manifest_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            goal = root / "goal.json"
            goal.write_text('{"goal_id":"g"}\n', encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(create_manifest([("goal", goal)])), encoding="utf-8"
            )
            self.assertEqual(verify_manifest(manifest_path), [])
            goal.write_text('{"goal_id":"changed"}\n', encoding="utf-8")
            problems = verify_manifest(manifest_path)
            self.assertTrue(any("integrity mismatch" in problem for problem in problems))

    def test_evidence_manifest_covers_referenced_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            round_dir = Path(tmp)
            (round_dir / "screenshots").mkdir()
            (round_dir / "screenshots" / "a.png").write_bytes(b"png")
            (round_dir / "action.log").write_text("{}\n", encoding="utf-8")
            report = {
                "goal_id": "g",
                "round": 1,
                "playtester_run_id": "r",
                "evidence_origin": "live-agent",
                "checks": [{"id": "a", "status": "pass", "evidence": ["screenshots/a.png"]}],
            }
            (round_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
            manifest = create_evidence_manifest(round_dir, "live-agent")
            self.assertEqual(
                {entry["path"] for entry in manifest["files"]},
                {"action.log", "screenshots/a.png"},
            )

    def test_evidence_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            round_dir = Path(tmp) / "round"
            round_dir.mkdir()
            (round_dir / "action.log").write_text("{}\n", encoding="utf-8")
            report = {
                "evidence_origin": "live-agent",
                "checks": [{"id": "a", "status": "pass", "evidence": ["../outside.png"]}],
            }
            (round_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "escapes round directory"):
                create_evidence_manifest(round_dir, "live-agent")


if __name__ == "__main__":
    unittest.main()
