# Evidence Contract

This defines the two documents that make the loop trustworthy: `goal.json`
(frozen input) and `report.json` (frozen output). Everything the loop and the
validator do is built on these two files having a fixed, checkable shape.

## Run folder layout

Each goal gets its own run folder. Round folders never get overwritten.

```text
playtest-runs/<goal-id>/
├── goal.json                    frozen after step 1, never edited after
├── APP_GUIDE.md                 how to start the app, seed data, known assumptions
├── memory/
│   ├── world.md                 routes, auth, seed data, domain rules (shared)
│   ├── skills.jsonl             wait patterns, selector recipes, false positives
│   └── failures.jsonl           failure fingerprints seen across rounds
├── evidence/
│   ├── round-1/
│   │   ├── report.json          frozen verdict for this round
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
  "goal_id": "memory-game-playable",
  "source_prompt": "the memory game should be fully playable",
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
    "viewports": [320, 768, 1280]
  }
}
```

`ux_policy` is optional; the values above are the defaults applied when it is
absent. `gate_on` accepts only measured severities — judged findings never
gate, whatever it says. Set `gate_on: []` when the visual layer is explicitly
out of scope for this goal. See [ux-review.md](ux-review.md).

Rules for writing checks, taken from what makes a rubric usable:

- **Observable**: a tester who only sees the rendered page must be able to
  adjudicate it. "The spawn rate increases each wave" is a check. "The
  difficulty feels right" is not.
- **Faithful**: derive the check from the user's stated intent, not from
  personal preference or from a constant found while reading the code.
- **9-15 checks** is a reasonable range for a non-trivial interactive
  artifact. Fewer than 5 usually means the goal was not decomposed enough.
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
  "checks": [
    {
      "id": "mismatch-flips-back",
      "status": "fail",
      "evidence": [
        "evidence/round-1/screenshots/03_mismatch_still_visible.png"
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
