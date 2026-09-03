---
name: gui-playtest-loop
description: >-
  Orchestrates bounded, evidence-backed browser playtests and scoped UI repairs
  against protected observable goals. Use for verifying or repairing interactive
  web UIs, rendered UX defects, responsive behavior, or a /goal request. Supports
  quick, standard, and release profiles; it is not an accessibility or security audit.
disable-model-invocation: true
---

# GUI Playtest Loop

Run a protected goal through three independent decision layers: behavior
playtest, rendered-surface audit, and repair verification. Keep detailed role
instructions in the sub-skills; this file only orchestrates them.

## 1. Freeze the contract

1. Expand the request into observable checks in `goal.json` using
   [reference/contract.md](reference/contract.md).
2. Select `quick`, `standard`, or `release` using
   [reference/profiles.md](reference/profiles.md). Do not silently downgrade a
   profile after failures appear.
3. Keep goals, schemas, thresholds, validators, truth data, and integrity
   manifests outside the Builder's edit authority. Seal them with
   `scripts/seal_contract.py` when the selected profile requires it.

**Complete when:** the goal, profile, budget, app URL, required viewports, and
protected-file manifest are fixed before implementation starts.

## 2. Build

Give the Builder the source prompt, app workspace, and
[prompts/builder.md](prompts/builder.md). It may change application code and
`APP_GUIDE.md`; it may not change protected inputs or certify the result.

**Complete when:** the app runs at the frozen URL and `APP_GUIDE.md` states the
start command, assumptions, implemented behaviors, and explicit exclusions.

## 3. Playtest behavior

Use a fresh context and follow
[skills/behavior-playtester/SKILL.md](skills/behavior-playtester/SKILL.md).
Prefer a separate process or workspace with no access to benchmark truth or
Builder conversation. Source access for diagnosis is allowed only after the
behavior and rendered verdicts are persisted.

**Complete when:** every goal check has a visible verdict, action-log lines,
and sealed evidence; failures have reproducible steps and user-facing impact.

## 4. Audit the rendered surface

Follow [skills/rendered-ux-audit/SKILL.md](skills/rendered-ux-audit/SKILL.md).
Keep deterministic findings separate from judged UX commentary. One capture
proves one viewport and one state only. Run every viewport required by the
profile, including breakpoint `-1`, exact, and `+1` probes when configured.

**Complete when:** every required viewport has a saved probe artifact and all
reported findings identify their evidence origin.

## 5. Validate and gate

Run `scripts/validate_evidence.py` with the goal and app directory. For strict
profiles also provide the externally owned integrity manifest. A validator pass
means the evidence package is coherent, not that its judgment is infallible.
Then run `scripts/evaluate_gate.py`; its exit code, not model narration, decides
whether required behavior, selected measured UX rules, and regressions are green.

- Missing or invalid evidence: repeat the playtest; do not spend a repair round.
- All required behavior checks pass and no configured deterministic UX finding
  gates: stop successfully.
- Otherwise create a fail packet containing only failures and their evidence.

**Complete when:** the validator passes and the orchestrator has recorded either
success or an immutable fail packet.

## 6. Repair and regression-test

Follow [skills/repair-verification/SKILL.md](skills/repair-verification/SKILL.md).
The repair agent receives the fail packet, not passing evidence. A fresh
playtester reruns the entire frozen goal. Any previously passing required check
that stops passing is a regression and keeps the gate red.

**Complete when:** a fresh sealed round passes every gate, or a stop condition is
reached and residual failures are reported without softening the contract.

## Stop conditions

- success;
- profile round/time/spend budget exhausted;
- the same failure fingerprint repeats twice;
- two consecutive rounds do not improve the gated result;
- a protected input changes or the evidence origin cannot be established.

## Authority boundaries

- Builder/Repair: application code and narrowly necessary `APP_GUIDE.md` edits.
- Playtester: new round evidence and playtester memory only.
- Orchestrator/Reviewer: goals, schemas, profiles, thresholds, validators,
  integrity manifests, benchmark truth, and approved exceptions.
- Diagnostic models may localize a failure; they may never override a
  deterministic gate or turn missing evidence into a pass.

## References

- [reference/contract.md](reference/contract.md) — versioned goal/report contract
- [reference/profiles.md](reference/profiles.md) — cost and rigor profiles
- [reference/evidence-integrity.md](reference/evidence-integrity.md) — provenance and sealing
- [reference/ux-review.md](reference/ux-review.md) — measured versus judged UX
- [reference/benchmark.md](reference/benchmark.md) — blinded benchmark rules
