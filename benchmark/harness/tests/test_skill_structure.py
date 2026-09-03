#!/usr/bin/env python3
"""Structural tests for split skills and versioned JSON contracts."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class SkillStructureTests(unittest.TestCase):
    def test_json_templates_parse(self) -> None:
        for path in (REPO_ROOT / "templates").glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_markdown_local_links_resolve(self) -> None:
        files = [REPO_ROOT / "SKILL.md", *sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))]
        for path in files:
            text = path.read_text(encoding="utf-8")
            for raw in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
                if "://" in raw or raw.startswith("#"):
                    continue
                with self.subTest(skill=path.name, target=raw):
                    self.assertTrue((path.parent / raw).resolve().exists(), raw)

    def test_each_phase_has_checkable_completion(self) -> None:
        for path in sorted((REPO_ROOT / "skills").glob("*/SKILL.md")):
            with self.subTest(skill=path.parent.name):
                text = path.read_text(encoding="utf-8")
                numbered_steps = re.findall(r"^\d+\. ", text, flags=re.MULTILINE)
                completions = re.findall(r"\*\*Complete when:\*\*", text)
                self.assertEqual(len(numbered_steps), len(completions))


if __name__ == "__main__":
    unittest.main()
