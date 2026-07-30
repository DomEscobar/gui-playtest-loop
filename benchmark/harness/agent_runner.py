#!/usr/bin/env python3
"""Invoke a headless agent CLI for benchmark playtesting (best-effort probe)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from lib import repo_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("codex", "claude"), default="codex")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--round-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def build_prompt(root: Path, fixture: str, round_dir: Path) -> str:
    template = root / "benchmark" / "harness" / "spike_playtester_prompt.txt"
    goal_path = root / "benchmark" / "fixtures" / fixture / "goal.json"
    text = template.read_text(encoding="utf-8")
    return (
        text.replace("{{FIXTURE}}", fixture)
        .replace("{{GOAL_PATH}}", str(goal_path))
        .replace("{{ROUND_DIR}}", str(round_dir))
        .replace("{{URL}}", "http://127.0.0.1:8765/app.html")
    )


def probe_codex(prompt: str) -> list[str]:
    if not shutil.which("codex"):
        return ["codex CLI not found on PATH"]
    return [
        "codex",
        "exec",
        "-c",
        "features.multi_agent_v2=false",
        prompt,
    ]


def probe_claude(prompt: str) -> list[str]:
    if not shutil.which("claude"):
        return ["claude CLI not found on PATH"]
    return ["claude", "-p", prompt]


def main() -> int:
    args = parse_args()
    root = repo_root()
    args.round_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(root, args.fixture, args.round_dir)

    if args.agent == "codex":
        cmd = probe_codex(prompt)
    else:
        cmd = probe_claude(prompt)

    if len(cmd) == 1:
        print(cmd[0], file=sys.stderr)
        return 2

    if args.dry_run:
        print("Would run:", " ".join(cmd[:4]), "...")
        print(prompt[:500], "...")
        return 0

    proc = subprocess.run(cmd, text=True)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
