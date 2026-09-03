# Evidence Contract

This defines the two documents that make the loop trustworthy: `goal.json`
(frozen input) and `report.json` (frozen output). Everything the loop and the
validator do is built on these two files having a fixed, checkable shape.

## Run folder layout

Each goal gets its own run folder. Round folders never get overwritten.

```text
playtest-runs/<goal-id>/
├── goal.json                    frozen after step 1, never edited after
├── integrity.json               protected manifest; keep outside Builder write authority
├── APP_GUIDE.md                 how to start the app, seed data, known assumptions
├── memory/
│   ├── world.md                 routes, auth, seed data, domain rules (shared)
│   ├── skills.jsonl             wait patterns, selector recipes, false positives
│   └── failures.jsonl           failure fingerprints seen across rounds
├── evidence/
│   ├── round-1/
│   │   ├── report.json          frozen verdict for this round
│   │   ├── evidence_manifest.json hashes + evidence origin
│   │   ├── action.log           one line per interaction
│   │   ├── screenshots/
│   │   ├── ux_probe.<width>.json  raw probe output, one per reviewed viewport
│   │   └── instrumentation/     archived patches, only if diagnosis used temp logs
│   └── round-2/ ...
└── final_report.md              written once the loop stops
```

## `goal.json`

Produced once by the orchestrator from the user's `/goal`, then frozen. The
playtester and builder may read it but never edit it.

```json
{
  "contract_version": 2,
  "goal_id": "memory-game-playable",
  "source_prompt": "the memory game should be fully playable",
  "profile": "standard",
  "app": {
    "start_command": "bun run dev",
    "url": "http://localhost:5173"
  },
  "checks": [
    {
      "id": "start-begins-game",
      "statement": "Clicking Start begins the game and hides all cards.",
      "required": true
    },
    {
      "id": "match-stays-visible",
      "statement": "A matching pair of cards stays face up after being matched.",
      "required": true
    },
    {
      "id": "mismatch-flips-back",
      "statement": "A non-matching pair flips back face down within roughly 1.5s.",
      "required": true
    },
    {
      "id": "score-increments-on-match",
      "statement": "The score increases by exactly one point per matched pair.",
      "required": true
    },
    {
      "id": "restart-resets-everything",
      "statement": "Restart resets the board, the score, and any in-progress selection.",
      "required": true
    }
  ],
  "ux_policy": {
    "enabled": true,
    "gate_on": ["blocker"],
    "gate_rules": ["low-legibility", "text-clipped", "occluded-interactive", "viewport-overflow"],
    "viewports": [320, 768, 1280]
  },
  "responsive_policy": {
    "breakpoints": [768],
    "probe_breakpoint_edges": true
  },
  "protection": {
    "integrity_required": true
  }
}
```

Version 2 activates strict validation for `standard` and `release`: structured
phase/action timestamps, evidence origin and hashes, complete viewport probes,
contract integrity when required, and full regression checks after repairs. See
[profiles.md](profiles.md) and [evidence-integrity.md](evidence-integrity.md).

`ux_policy` is optional for legacy contracts. `gate_on` selects measured
severities and `gate_rules` selects the rule ids allowed to gate. Judged findings
never gate. Style-system conventions such as palette or radius counts stay
advisory unless a protected project policy explicitly names them. Set
`gate_on: []` when the visual layer is out of scope. See [ux-review.md](ux-review.md).

Rules for writing checks, taken from what makes a rubric usable:

- **Observable**: a tester who only sees the rendered page must be able to
  adjudicate it. "The spawn rate increases each wave" is a check. "The
  difficulty feels right" is not.
- **Faithful**: derive the check from the user's stated intent, not from
  personal preference or from a constant found while reading the code.
- Use the smallest set that covers the user's observable intent. A non-trivial
  flow often needs 5-15 checks, but check count is not a quality metric.
- Mark a check `required: false` for things worth observing but that should
  not block the loop (for example, a nice-to-have animation).

## `report.json`

Written by the playtester in two frozen passes — `checks` at the end of the
behavior playtest, `ux_findings` at the end of the visual review — both before
any code, console, or instrumentation is read.

```json
{
  "goal_id": "memory-game-playable",
  "round": 1,
  "playtester_run_id": "run-1-a1b2c3",
  "evidence_origin": "live-agent",
  "phase_timestamps": {
    "behavior_verdict_frozen_at": "2026-08-01T12:00:00Z",
    "ux_verdict_frozen_at": "2026-08-01T12:05:00Z",
    "diagnosis_started_at": "2026-08-01T12:06:00Z"
  },
  "checks": [
    {
      "id": "mismatch-flips-back",
      "status": "fail",
      "evidence": [
        "screenshots/03_mismatch_still_visible.png"
      ],
      "action_log_lines": [12, 13, 14],
      "repro": [
        "Open http://localhost:5173",
        "Click Start",
        "Click card 1",
        "Click card 4",
        "Wait 2000ms"
      ],
      "user_facing_bug": "Wrong memory-game pairs never flip back, so the board fills up with revealed cards."
    }
  ],
  "ux_findings": [
    {
      "id": "ux-1",
      "layer": "measured",
      "rule": "low-legibility",
      "severity": "major",
      "surface": "board header",
      "selector": "#score",
      "viewport": 1280,
      "observation": "Score text renders at a 3.4:1 contrast ratio against the board background.",
      "user_impact": "The score is hard to read at a glance while playing.",
      "evidence": ["screenshots/ux_1280_board.png"],
      "measurement": {
        "metric": "contrast_ratio",
        "actual": 3.4,
        "threshold": 4.5,
        "unit": "ratio",
        "approximated": false
      }
    },
    {
      "id": "ux-2",
      "layer": "judged",
      "heuristic": "feedback-missing",
      "severity": "major",
      "surface": "board",
      "observation": "Matching a pair changes only the score number; the matched cards look identical to unmatched ones.",
      "user_impact": "Players cannot tell which pairs they have already cleared.",
      "rationale": "The only acknowledgement of a match is a digit change outside the area the player is looking at.",
      "confidence": "high",
      "evidence": ["screenshots/ux_match_no_feedback.png"],
      "proposed_check": "A matched pair is visually distinct from unmatched cards."
    }
  ],
  "instrumented_findings": [
    {
      "id": "find-1",
      "observation": "The mismatch timer callback is registered twice, so the second call fires after the cards are already reset by the first.",
      "source": "temp-log",
      "visible_symptom": "mismatch-flips-back",
      "clean_rerun_reproduced": true,
      "proposed_check": null
    }
  ]
}
```

Field rules:

- `status` is one of `pass`, `fail`, or `blocked` (blocked means the
  precondition for the check never occurred, e.g. the game never started).
- `evidence_origin` distinguishes `live-agent`, `human-live`, `replayed`, and
  `synthetic-golden`. Strict agent runs require `live-agent`; golden fixtures
  test the harness and never count as live detection results.
- Strict profiles use JSONL action rows with `sequence`, timezone-aware
  `timestamp`, `action`, optional `target`, and `observation`.
- Every `pass` **must** reference at least one evidence artifact that exists
  on disk under this round's folder.
- Every `fail` **must** include `repro` steps and at least one artifact.
- `ux_findings` is separate from `checks` and follows the two-layer contract
  in [ux-review.md](ux-review.md). A `measured` finding needs a `rule` and a
  `measurement` with numeric `actual` and `threshold`, and the round folder
  must contain the `ux_probe.<width>.json` it came from. A `judged` finding
  needs a named `heuristic`, a `rationale`, and a `confidence`, and may never
  be `blocker` — a judgment call cannot fail a goal.
- `instrumented_findings` is separate from `checks`. It holds things only
  visible through diagnosis, not through the rendered surface. If a
  finding was only visible in a log, either link it to an existing check via
  `visible_symptom`, or set `proposed_check` to a candidate observable
  statement for the orchestrator to consider adding to `goal.json` in a
  future goal — never let it silently justify a `pass` or a `fail` on its
  own.
- `clean_rerun_reproduced` must be `true` before an instrumented finding is
  treated as a confirmed bug. See
  [instrumentation.md](instrumentation.md).
- After round 1, `regression.previous_passes_rechecked` must exactly cover the
  previous round's passing required checks. Any pass-to-fail or pass-to-blocked
  transition remains a gated regression.
- Run `scripts/seal_evidence.py` after the report is final. Strict validation
  rejects changed, missing, escaping, or unsealed evidence paths.

See [templates/report.schema.json](../templates/report.schema.json) for the
machine-checkable version and
[templates/goal.example.json](../templates/goal.example.json) for a filled
example. `scripts/validate_evidence.py` enforces the rules above
structurally; it does not and cannot judge whether the verdict itself is
correct — that judgment stays with the playtester.

## Fail packets

When the gate finds required failures, the orchestrator hands the builder a
fail packet, not the full report and not the full conversation:

```json
{
  "round": 1,
  "failing_checks": [
    {
      "id": "mismatch-flips-back",
      "user_facing_bug": "Wrong memory-game pairs never flip back, so the board fills up with revealed cards.",
      "repro": ["..."],
      "evidence": ["evidence/round-1/screenshots/03_mismatch_still_visible.png"],
      "likely_location": "src/components/MemoryBoard.tsx (from diagnosis phase, advisory only)"
    }
  ],
  "gating_ux_findings": [
    {
      "id": "ux-3",
      "rule": "occluded-interactive",
      "severity": "blocker",
      "user_impact": "The Start button cannot be clicked because a transparent overlay covers it.",
      "measurement": { "metric": "hit_test", "actual": 0, "threshold": 1, "unit": "boolean" },
      "evidence": ["evidence/round-1/screenshots/ux_1280_initial.png"]
    }
  ],
  "advisory_ux_findings": [
    {
      "id": "ux-2",
      "heuristic": "feedback-missing",
      "user_impact": "Players cannot tell which pairs they have already cleared.",
      "confidence": "high"
    }
  ]
}
```

`gating_ux_findings` carries only measured findings whose severity appears in
`ux_policy.gate_on`; the builder must clear those. `advisory_ux_findings` is
context the builder may act on or ignore — it never blocks the loop, and the
builder is not asked to justify skipping it.

The builder treats `likely_location` as advice, not instruction, and decides
how to fix it. The builder never receives the passing checks' evidence — it
does not need to re-litigate what already works.
