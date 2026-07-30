# Instrumentation Contract

The diagnosis phase, which runs after both the behavior and UX verdicts are
frozen, may use temporary logging to explain a failure that has no visible
symptom on screen. This is powerful and easy to misuse, so it runs under a
strict contract.

Note the contrast with `scripts/ux_probe.js`: that probe only reads layout and
computed style, changes nothing, and therefore runs *before* the gate. Anything
that mutates the page or the source is instrumentation and stays behind it.

## The rule that governs everything here

**Instrumentation can only strengthen a FAIL. It can never turn a FAIL into a
PASS, and it can never be the sole basis for a PASS.** The user of the app
never sees console output. If the rendered surface does not show the expected
behavior, the check fails regardless of what any log says.

## Escalation ladder — cheapest first

1. **What already exists.** Console messages, network requests, a
   performance trace. Costs nothing, changes nothing.
2. **Runtime injection.** Wrap a function or read a value from the page's own
   context (e.g. via an init script or an in-page evaluation) without
   touching the repository. Leaves no trace in source control.
3. **Temporary source-level logging.** Only when the value is not reachable
   from the page context — typically server-side route handlers or
   build-time logic. This is the only rung that requires cleanup, so it is
   the only one with a contract below.

## The marker convention

Every line added at rung 3 carries a machine-searchable marker with the run
id:

```js
console.log('[PLAYTEST-TMP run-1-a1b2c3] submit payload', payload); // PLAYTEST-TMP run-1-a1b2c3
```

Additive only. Never modify existing logic to add a log line — if the change
is anything more than inserting a line, it is a code change, not
instrumentation, and belongs to the Builder/Repair role instead.

## Workflow

```text
diagnosis
     |
     +-- capture baseline        git diff > evidence/round-N/instrumentation/pre.patch
     |
     +-- add PLAYTEST-TMP lines  additive only, marker on every line
     |
     +-- reproduce the flow      logs written to
     |                           evidence/round-N/instrumentation/instrumented.log
     |
     +-- archive the diff        evidence/round-N/instrumentation/applied.patch
     |                           plus a one-line reason for each hunk
     |
     +-- REVERT                  remove every PLAYTEST-TMP line
     |
     +-- CLEAN RERUN              reproduce the same failure with no
     |                           instrumentation present
     v
memory capture
```

## Why the clean rerun is mandatory, not optional

`console.log` and similar calls are synchronous and can shift timing enough
to mask or manufacture a race condition. A failure that only appears with
instrumentation present, or only disappears once it is removed, is not a
confirmed bug — it is an artifact of the measurement. If the clean rerun does
not reproduce the failure, set `clean_rerun_reproduced: false` on the
finding, do not report it as confirmed, and record it as a flake suspicion in
`memory/skills.jsonl` instead.

## Recording the finding

Every instrumented finding goes in `report.json`'s `instrumented_findings`
array (see [contract.md](contract.md)), never mixed into `checks`:

```json
{
  "id": "find-1",
  "observation": "The mismatch timer callback is registered twice, so the second call fires after the cards are already reset by the first.",
  "source": "temp-log",
  "visible_symptom": "mismatch-flips-back",
  "clean_rerun_reproduced": true,
  "proposed_check": null
}
```

If the observation has no matching entry in `goal.json` at all — it was only
ever visible through logs — set `visible_symptom` to `null` and fill in
`proposed_check` with a candidate observable statement. Do not let it justify
any check result on its own; it is a suggestion for the orchestrator to
consider adding to a future `goal.json`, not a verdict.

## What the validator enforces here

`scripts/validate_evidence.py` checks that:

- No `PLAYTEST-TMP` marker remains anywhere in the app's working tree after a
  round completes.
- Every entry in `instrumented_findings` has a corresponding archived patch
  under `evidence/round-N/instrumentation/` and an explicit
  `clean_rerun_reproduced` boolean.

It does not and cannot judge whether the diagnosis itself is correct — only
whether the cleanup actually happened and the finding is structurally
complete.
