#!/usr/bin/env python3
"""Create or refresh golden playtest evidence for all catalog fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from lib import ensure_placeholder_png, load_catalog, repo_root


def _base_report(goal_id: str, checks: list[dict]) -> dict:
    return {
        "goal_id": goal_id,
        "round": 1,
        "playtester_run_id": f"golden-{goal_id}",
        "checks": checks,
        "instrumented_findings": [],
    }


def _pass(check_id: str) -> dict:
    return {
        "id": check_id,
        "status": "pass",
        "evidence": ["screenshots/placeholder.png"],
        "action_log_lines": [1],
    }


def _fail(check_id: str, bug: str) -> dict:
    return {
        "id": check_id,
        "status": "fail",
        "evidence": ["screenshots/placeholder.png"],
        "action_log_lines": [2, 3],
        "repro": [f"Reproduce failure for {check_id}"],
        "user_facing_bug": bug,
    }


def _blocked(check_id: str, reason: str) -> dict:
    return {
        "id": check_id,
        "status": "blocked",
        "evidence": ["screenshots/placeholder.png"],
        "action_log_lines": [1],
        "repro": [reason],
        "user_facing_bug": reason,
    }


GOLDEN_REPORTS: dict[str, dict] = {
    "memory-clean-control": _base_report(
        "memory-clean-control",
        [
            _pass("initial-state-hidden"),
            _pass("start-begins-game"),
            _pass("card-flips-on-click"),
            _pass("mismatch-flips-back"),
        ],
    ),
    "memory-dead-start-button": _base_report(
        "memory-dead-start-button",
        [
            _pass("initial-state-hidden"),
            _fail("start-begins-game", "Clicking Start does nothing; the game never begins."),
            _fail("card-flips-on-click", "Cards stay face down because Start never begins the game."),
            _fail("mismatch-flips-back", "Mismatch behavior cannot be tested because the game never starts."),
            _blocked("restart-resets", "Restart is disabled before the game starts."),
        ],
    ),
    "memory-mismatch-stays-visible": _base_report(
        "memory-mismatch-stays-visible",
        [
            _pass("start-begins-game"),
            _fail("mismatch-flips-back", "Wrong pairs stay face up instead of flipping back."),
        ],
    ),
    "form-loses-data-on-validation": _base_report(
        "form-loses-data-on-validation",
        [
            _pass("invalid-email-shows-error"),
            _fail(
                "data-retained-after-error",
                "Email and name fields are cleared after a validation error.",
            ),
            _pass("valid-submit-succeeds"),
        ],
    ),
    "dashboard-fake-filter": _base_report(
        "dashboard-fake-filter",
        [
            _pass("all-items-visible-initially"),
            _fail("fruit-filter-hides-veg", "Selecting Fruit only does not hide vegetable items."),
            _fail("veg-filter-hides-fruit", "Selecting Vegetables only does not hide fruit items."),
        ],
    ),
    "trap-overlay-blocks-clicks": _base_report(
        "trap-overlay-blocks-clicks",
        [
            _pass("start-begins-game"),
            _fail("card-flips-on-click", "Cards do not flip; clicks appear to hit an invisible overlay."),
        ],
    ),
}


REPAIRED_REPORTS: dict[str, dict] = {
    "memory-dead-start-button-repaired": _base_report(
        "memory-dead-start-button",
        [
            _pass("initial-state-hidden"),
            _pass("start-begins-game"),
            _pass("card-flips-on-click"),
            _pass("mismatch-flips-back"),
            _pass("restart-resets"),
        ],
    ),
    "memory-mismatch-stays-visible-repaired": _base_report(
        "memory-mismatch-stays-visible",
        [_pass("start-begins-game"), _pass("mismatch-flips-back")],
    ),
    "form-loses-data-on-validation-repaired": _base_report(
        "form-loses-data-on-validation",
        [
            _pass("invalid-email-shows-error"),
            _pass("data-retained-after-error"),
            _pass("valid-submit-succeeds"),
        ],
    ),
}


def _write_round(root: Path, folder: str, report: dict) -> Path:
    round_dir = root / "benchmark" / "golden" / folder / "round-1"
    round_dir.mkdir(parents=True, exist_ok=True)
    ensure_placeholder_png(round_dir / "screenshots")
    (round_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (round_dir / "action.log").write_text(
        f"golden playtest for {folder}\nopen app\nobserve checks\n",
        encoding="utf-8",
    )
    return round_dir


def write_golden(root: Path) -> list[Path]:
    written: list[Path] = []
    catalog = load_catalog(root)
    for entry in catalog["fixtures"]:
        fixture_id = entry["id"]
        written.append(_write_round(root, fixture_id, GOLDEN_REPORTS[fixture_id]))
    for folder, report in REPAIRED_REPORTS.items():
        written.append(_write_round(root, folder, report))
    return written


def main() -> int:
    root = repo_root()
    paths = write_golden(root)
    print(f"Wrote {len(paths)} golden round folders under benchmark/golden/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
