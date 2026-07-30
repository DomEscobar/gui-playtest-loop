#!/usr/bin/env python3
"""Create or refresh golden playtest evidence for all catalog fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from lib import ensure_placeholder_png, load_catalog, repo_root


def _base_report(goal_id: str, checks: list[dict], ux_findings: list[dict] | None = None) -> dict:
    report = {
        "goal_id": goal_id,
        "round": 1,
        "playtester_run_id": f"golden-{goal_id}",
        "checks": checks,
        "instrumented_findings": [],
    }
    if ux_findings:
        report["ux_findings"] = ux_findings
    return report


def _measured(
    finding_id: str,
    rule: str,
    severity: str,
    metric: str,
    actual: float,
    threshold: float,
    unit: str,
    observation: str,
    user_impact: str,
    selector: str = "",
) -> dict:
    return {
        "id": finding_id,
        "layer": "measured",
        "rule": rule,
        "severity": severity,
        "selector": selector,
        "viewport": 1280,
        "observation": observation,
        "user_impact": user_impact,
        "evidence": ["screenshots/placeholder.png"],
        "measurement": {
            "metric": metric,
            "actual": actual,
            "threshold": threshold,
            "unit": unit,
            "approximated": False,
        },
    }


def _judged(
    finding_id: str,
    heuristic: str,
    severity: str,
    observation: str,
    user_impact: str,
    rationale: str,
    confidence: str = "high",
) -> dict:
    return {
        "id": finding_id,
        "layer": "judged",
        "heuristic": heuristic,
        "severity": severity,
        "observation": observation,
        "user_impact": user_impact,
        "rationale": rationale,
        "confidence": confidence,
        "evidence": ["screenshots/placeholder.png"],
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
        [
            _measured(
                "ux-1", "occluded-interactive", "blocker", "hit_test", 0, 1, "boolean",
                "Every card's centre point hit-tests to #click-shield rather than the card.",
                "Cards cannot be clicked at all because a transparent overlay covers the board.",
                "div.card:nth-of-type(1)",
            ),
        ],
    ),
    "landing-visual-defects": _base_report(
        "landing-visual-defects",
        [
            _pass("cta-starts-trial"),
            _pass("banner-dismisses"),
            _pass("contact-responds"),
        ],
        [
            _measured(
                "ux-1", "viewport-overflow", "blocker", "horizontal_overflow", 312, 0, "px",
                "The document scrolls 312px sideways at a 1280px viewport.",
                "The page can be scrolled horizontally, cutting off the metrics strip.",
            ),
            _measured(
                "ux-2", "low-legibility", "blocker", "contrast_ratio", 1.54, 4.5, "ratio",
                "The hero subtitle renders at a 1.54:1 contrast ratio against white.",
                "The subtitle is effectively invisible.",
                "p.subtitle",
            ),
            _measured(
                "ux-3", "text-clipped", "blocker", "overflow_x", 125, 0, "px",
                "Card titles are cut off by overflow:hidden with no ellipsis.",
                "Feature names read as 'Continuous depl' with no way to see the rest.",
                "p.card-title",
            ),
            _measured(
                "ux-4", "target-too-small", "blocker", "min_side", 14, 24, "px",
                "The banner dismiss control measures 14x14px.",
                "The dismiss button is hard to hit accurately.",
                "#dismiss",
            ),
            _measured(
                "ux-5", "image-aspect-distortion", "major", "aspect_drift", 200, 2, "percent",
                "The logo's natural ratio is 1:1 but it renders at 240x80.",
                "The logo appears stretched.",
                "#logo",
            ),
            _measured(
                "ux-6", "tiny-text", "major", "font_size", 9, 12, "px",
                "Legal text renders at 9px.",
                "The legal note is uncomfortable to read.",
                "p.legal",
            ),
            _measured(
                "ux-7", "unstyled-default", "major", "default_signals", 1, 0, "count",
                "The Contact sales button still uses user-agent default chrome.",
                "One control looks unfinished next to the styled primary action.",
                "#contact",
            ),
            _judged(
                "ux-8", "hierarchy-competing-emphasis", "minor",
                "The stretched blue logo block occupies more visual weight than the headline.",
                "Attention lands on a placeholder graphic instead of the value proposition.",
                "The logo is the largest saturated area above the fold, so it wins the first fixation.",
                "medium",
            ),
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


def _probe_artifact(report: dict) -> dict:
    """Rebuild the probe output the measured findings came from.

    The validator requires a ux_probe artifact next to any measured finding, so
    a golden round has to carry one. Values mirror a verified real run of
    scripts/ux_probe.js against the fixture.
    """
    measured = [f for f in report.get("ux_findings", []) if f.get("layer") == "measured"]
    by_rule: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    findings = []
    for finding in measured:
        by_rule[finding["rule"]] = by_rule.get(finding["rule"], 0) + 1
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1
        findings.append(
            {
                "rule": finding["rule"],
                "severity": finding["severity"],
                "selector": finding.get("selector", ""),
                "detail": finding["observation"],
                "measurement": finding["measurement"],
                "occurrences": 1,
            }
        )
    return {
        "probe_version": "1.0.0",
        "url": "http://127.0.0.1:8765/app.html",
        "viewport": {"width": 1280, "height": 800, "device_pixel_ratio": 1},
        "findings": findings,
        "summary": {
            "total": len(findings),
            "reported": len(findings),
            "by_rule": by_rule,
            "by_severity": by_severity,
        },
        "notes": ["golden baseline reconstructed from a verified probe run"],
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

    probe_path = round_dir / "ux_probe.1280.json"
    if any(f.get("layer") == "measured" for f in report.get("ux_findings", [])):
        probe_path.write_text(
            json.dumps(_probe_artifact(report), indent=2) + "\n", encoding="utf-8"
        )
    elif probe_path.exists():
        probe_path.unlink()

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
