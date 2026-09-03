---
name: rendered-ux-audit
description: >-
  Audits a rendered web UI at protected viewports and states, separating
  deterministic layout defects from non-gating reviewer judgment.
---

# Rendered UX Audit

## Procedure

1. Read the frozen `ux_policy`, `responsive_policy`, and selected profile.
   Expand configured breakpoints to `-1`, exact, and `+1` widths when edge
   probing is enabled.
   **Complete when:** the required unique viewport list is recorded.
2. At every required width, wait for fonts and layout readiness, disable motion,
   capture the default state, run `scripts/ux_probe.js`, and save
   `ux_probe.<width>.json` even when it has zero findings.
   **Complete when:** every width has a screenshot and probe artifact.
3. Replay authored or goal-relevant loading, empty, error, success, disabled,
   hover, and focus states. Treat one capture as evidence for only its width and
   state.
   **Complete when:** required states are either evidenced or explicitly blocked.
4. Keep universal measurements distinct from project-style lint. Clipping,
   viewport overflow, occlusion, distortion, hit-target size, and configured
   legibility thresholds may gate. Palette, radius, type-scale, spacing-grid,
   rhythm, and aesthetic heuristics are advisory unless the protected goal
   explicitly adopts a project design policy.
   **Complete when:** every gating measurement comes from a protected rule and
   saved probe result.
5. Write judged findings only against named heuristics with observation, impact,
   rationale, confidence, and screenshot. Judged findings never block.
   **Complete when:** `ux_findings` is frozen and
   `phase_timestamps.ux_verdict_frozen_at` is recorded.

## Failure boundaries

- A number is objective only about what it measures; its threshold may still be
  a project convention.
- Approximate contrast over gradients or imagery requires visual confirmation.
- A low global defect count cannot hide one blocker on a primary control.
- This is not an accessibility audit; keep accessibility findings in a separate gate.
