---
name: repair-verification
description: >-
  Applies scoped repairs from a frozen GUI fail packet and requires a fresh full
  rerun that rejects regressions and protected-input changes.
---

# Repair Verification

## Procedure

1. Receive only the immutable fail packet, application workspace, and allowed
   edit paths. Verify the protected contract before editing.
   **Complete when:** the integrity manifest passes and every requested repair
   maps to a gated failure.
2. Reproduce each failure and make the smallest application-code change that
   addresses it. Do not edit goals, schemas, policies, thresholds, validators,
   manifests, truth data, expected outcomes, or prior evidence.
   **Complete when:** changed files remain within the permitted application scope.
3. Hand the app to a fresh behavior playtester and rendered UX auditor. Rerun the
   complete frozen goal, not only failed checks.
   **Complete when:** the new round contains sealed evidence for all checks and
   required viewports.
4. Compare the new report with the previous one. Every previously passing
   required check must still pass; any pass-to-fail or pass-to-blocked transition
   is a regression and keeps the gate red.
   **Complete when:** `regression.previous_passes_rechecked` covers the previous
   pass set and `regression.regressions` is empty.
5. Stop on success, budget exhaustion, repeated fingerprint, non-improvement, or
   integrity failure. Never weaken a check to force convergence.
   **Complete when:** the orchestrator records success or residual failures and
   the stop reason.

## Failure boundaries

- Repair agents do not mark their own work fixed.
- Advisory judged UX findings do not authorize unrelated redesign.
- A legitimate contract change starts a new goal run; it never edits history.
