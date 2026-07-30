#!/usr/bin/env python3
"""Unit tests for apply_repair.py."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
ROOT = HARNESS.parents[1]
sys.path.insert(0, str(HARNESS))

from apply_repair import apply_repair  # noqa: E402


class ApplyRepairTests(unittest.TestCase):
    def test_memory_dead_start_button_repair(self) -> None:
        src = ROOT / "benchmark" / "fixtures" / "memory-dead-start-button" / "app.html"
        repair = HARNESS / "repairs" / "memory-dead-start-button.json"
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "app.html"
            shutil.copy2(src, app)
            ok, problems = apply_repair(app, repair)
            self.assertTrue(ok, problems)
            text = app.read_text(encoding="utf-8")
            self.assertIn("startBtn.addEventListener('click'", text)
            self.assertNotIn("MUTATION: Start handler intentionally not wired", text)


if __name__ == "__main__":
    unittest.main()
