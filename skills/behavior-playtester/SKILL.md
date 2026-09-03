---
name: behavior-playtester
description: >-
  Executes frozen observable web-UI behavior checks in a fresh browser context
  and records action-level evidence without diagnosing or repairing first.
---

# Behavior Playtester

## Procedure

1. Read only `goal.json`, `APP_GUIDE.md`, permitted playtester memory, and the
   running app. Confirm that benchmark truth, golden reports, and Builder
   conversation are absent from this context.
   **Complete when:** the run id, round, profile, URL, and evidence origin are
   recorded before the first interaction.
2. Load the initial state at the profile's required viewport, wait for declared
   readiness, and capture it before interacting.
   **Complete when:** the initial screenshot and first structured action-log row
   exist.
3. Execute every check from visible behavior only. Record one JSONL action row
   per interaction with sequence, timestamp, action, target, and observation.
   Capture each state needed to adjudicate a check.
   **Complete when:** every check is `pass`, `fail`, or `blocked`; every pass and
   fail references an artifact, and every fail has repro steps and user impact.
4. Persist the behavior verdict and timestamp it before opening source, console,
   network, or performance tools. Never upgrade a verdict with diagnostic data.
   **Complete when:** `phase_timestamps.behavior_verdict_frozen_at` is present
   and precedes any diagnosis timestamp.
5. After the rendered audit is also frozen, diagnose failures if requested.
   Store diagnosis separately and follow the temporary-instrumentation contract.
   **Complete when:** diagnosis changed no frozen status and temporary changes
   were reverted and cleanly reproduced.
6. Run `scripts/seal_evidence.py` after the report and artifacts are final.
   **Complete when:** `evidence_manifest.json` covers the action log, every
   referenced artifact, and every viewport probe with matching hashes.

## Failure boundaries

- A source handler, console line, or DOM property cannot prove a user-visible pass.
- If a prerequisite never occurs, mark dependants `blocked`; do not invent states.
- One screenshot may support several checks only when it visibly proves each one.
- Synthetic, replayed, and live evidence must never share the same origin label.
