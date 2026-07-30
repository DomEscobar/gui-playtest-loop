---
name: gui-playtest-loop
description: >-
  Drives a bounded generate-playtest-repair goal loop that verifies AI-generated
  or human-written interactive web UIs against observable expected behaviors
  and measured visual quality, using a separate playtester role and a
  deterministic evidence gate instead of the builder's own self-report. Use
  when the user asks to playtest a web app, verify a generated UI actually
  works, review the visual craft or UX of a rendered page, run a GUI goal
  loop, fix a UI until a goal is met, or invokes "/goal" against a running
  local app.
disable-model-invocation: true
---

# GUI Playtest Goal Loop

## Why this exists

A screenshot, a clean component tree, and a confident agent summary can all
look finished while the interaction is broken. Dead buttons, state that never
resets, timers that never fire, and forms that lose data on validation are
invisible in a single frame. They only show up in a sequence of actions. This
skill replaces "does it look done?" with "can a user complete the expected
behavior, with evidence?"

The core rule that makes this trustworthy: **the agent that built the UI is
not allowed to be the only judge of whether it works.** A separate playtester
role produces a frozen, evidence-backed verdict before any repair happens.

## Roles

Run this as three roles, even if one agent plays all three in sequence. Never
collapse "build" and "judge" into the same step.

- **Builder** — implements or repairs the app. Never plays the app to
  self-certify. Receives only failing checks plus evidence, not a full replay.
- **Playtester** — plays the app like a naive user and freezes a verdict
  before reading any source code. See [reference/portability.md](reference/portability.md)
  for how to approximate role separation when your agent cannot spawn
  subagents.
- **Orchestrator** — expands the user's goal into `goal.json`, freezes it,
  runs the loop, enforces the budget, and mediates between Builder and
  Playtester. The orchestrator is usually you, the top-level agent.

## The loop

```text
1. EXPAND   /goal -> goal.json (9-15 observable checks). Freeze it.
2. BUILD    Builder implements toward goal.json. App runs on a local URL.
3. PLAYTEST Fresh playtester instance plays the app. See "Playtester phases".
4. VALIDATE Run scripts/validate_evidence.py against the run folder.
            exit 1 -> evidence incomplete, repeat step 3, does not count as a round.
            exit 0 -> continue.
5. GATE     All required checks pass, and no gating UX finding remains?
            yes -> DONE. Report final state.
            no  -> build a fail packet (failing checks + gating UX findings,
                   with their evidence only).
6. BUDGET   Stop condition reached? (see "Stop conditions")
            yes -> STOP, report residual failures honestly.
            no  -> round += 1, hand fail packet to Builder, goto 2.
```

Read [reference/contract.md](reference/contract.md) for the exact `goal.json`
and `report.json` schemas before step 1.

## Playtester phases

The playtester has full read access to the codebase. That is deliberate — it
lets checks be derived from real branches and states instead of guesswork.
The access is time-gated, not role-gated:

```text
[1] Initial observation   Load the app. Screenshot the first state before
                           touching anything. Note anything already wrong.
[2] Start                 Enter the flow: auth, seed data, starting action.
[3] Interactive playtest  Run through goal.json's checks. One screenshot per
                           critical state, one action-log line per interaction.
    ─────────────────────────────────────────────────────────────
                  BEHAVIOR VERDICT GATE (see below)
    ─────────────────────────────────────────────────────────────
[4] Visual & UX review     Still rendered-surface only, still no source code.
                           Run scripts/ux_probe.js at each policy viewport,
                           replay the states reached in phase 3, and write
                           measured + judged findings. See
                           reference/ux-review.md.
    ─────────────────────────────────────────────────────────────
                       UX VERDICT GATE
    ─────────────────────────────────────────────────────────────
[5] Diagnosis              NOW read source, console, network, performance.
                           May add temporary instrumentation. Never changes
                           either verdict, only sharpens the reproduction and
                           locates the likely file/line. See
                           reference/instrumentation.md.
[6] Memory capture         Write path knowledge, recurring selectors, wait
                           patterns, and false positives to memory. See
                           reference/memory.md.
```

Behavior is judged first on purpose. A polished-looking surface biases a
reviewer toward assuming the button works, so the functional verdict is
frozen before anyone looks at craft.

### The verdict gate

Write `checks` into `report.json` at the end of phase 3 and `ux_findings` at
the end of phase 4 — both before opening any source file, console panel, or
devtools timeline. This ordering is the entire anti-cheat mechanism:

- **Code informs the report. Code never produces a pass.** A handler that
  looks correct is not evidence. A screenshot showing the expected state is.
- **Logs and instrumentation can only strengthen a FAIL, never rescue a
  PASS.** The user never sees console output; if the screen is wrong, the
  check fails regardless of what the code intended.
- Every `pass` needs at least one artifact (screenshot or log excerpt) that
  was captured during phase 3.
- Every `fail` needs reproduction steps a human could follow.
- Do not derive a check's numeric thresholds from the source. If the code
  says `setTimeout(1000)`, the check is "returns within roughly 1.5s of
  visible delay," not "returns within 1000ms."
- `scripts/ux_probe.js` reads layout and computed style without mutating
  anything, so it is observation, not instrumentation, and belongs in phase 4
  rather than behind the diagnosis gate.

### The two verdict tracks

`checks` and `ux_findings` are separate and never merge:

| | `checks` | `ux_findings` |
|---|---|---|
| Question | can the user complete the behavior? | is the surface actually built? |
| Frozen at | end of phase 3 | end of phase 4 |
| Gates DONE | always, for required checks | only measured findings, per `ux_policy.gate_on` |

A judged UX finding can never fail a goal — it is advisory input for the
builder and a candidate for a future `goal.json`. Only measured findings, with
a number and a threshold behind them, are allowed to gate. Without that
asymmetry, "I don't love the spacing" becomes a blocking verdict and the loop
stops being falsifiable. See [reference/ux-review.md](reference/ux-review.md).

## Stop conditions

Define these before round 1 and do not renegotiate them mid-loop:

- All required checks pass → success.
- Round count exceeds the budget (default 5) → stop, report residuals.
- The same failure fingerprint repeats twice in a row → stop, flag as
  stagnation, do not keep retrying the same fix.
- A spend or time cap is hit → stop, report partial progress.

A loop with no stop condition is not a goal loop, it is a runaway cost.

## Anti-cheat summary

| Risk | Mitigation |
|---|---|
| Builder grades its own work | Separate playtester role; builder never plays to self-certify |
| Verdict softened after seeing code | Both verdicts frozen before the diagnosis phase |
| Fake pass with no evidence | `scripts/validate_evidence.py` rejects passes without artifacts |
| Instrumentation leaks into the repo | Marker convention + mandatory revert + clean rerun, see reference/instrumentation.md |
| Same flake reported every round as new | Skill memory records false positives, see reference/memory.md |
| Subjective, unfalsifiable checks | goal.json checks must be observable from the rendered surface and derived from stated intent, not personal taste |
| Taste dressed up as a blocking verdict | Judged UX findings cap at `major` and never gate; only measured findings with a number and a saved probe run can block |
| Design skill grading its own output | The probe measures the painted result, not the token file or the generator's self-score |

## Limits, stated plainly

This loop finds broken flows, dead controls, missing state transitions,
regressions, and measurable visual defects with reproducible evidence. It is
not an accessibility audit and makes no compliance claim. It is not a security
review. Its judged UX layer is one reviewer's opinion, explicitly labelled as
such, and cannot fail a goal on its own. Treat a `PASS` as "the specified
behavior was observed and the surface cleared the measured thresholds," not as
"this is good software."

## Reference material

- [reference/contract.md](reference/contract.md) — `goal.json` / `report.json` schemas and evidence rules
- [reference/checklist.md](reference/checklist.md) — what to actually test, failure archetypes, severity classification
- [reference/ux-review.md](reference/ux-review.md) — the visual/UX track: measured rules, judged heuristics, gating policy
- [reference/memory.md](reference/memory.md) — episode / skill / world memory layers
- [reference/instrumentation.md](reference/instrumentation.md) — temporary logging contract
- [reference/portability.md](reference/portability.md) — running this with agents that lack subagents or browser tools
- [reference/benchmark.md](reference/benchmark.md) — detection + autofix benchmark harness
- [prompts/playtester.md](prompts/playtester.md), [prompts/builder.md](prompts/builder.md), [prompts/repair.md](prompts/repair.md) — role prompts to hand to subagents
