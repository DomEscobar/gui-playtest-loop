# Portability Across Agents

This skill is agent-agnostic by design: it depends on files on disk and one
stdlib-only Python script, not on any single vendor's subagent API or MCP
server. But agents differ in what they can actually do, and pretending
otherwise produces fake confidence. Be honest about which tier you are
running in.

## Tier A — subagents plus browser control

The agent can spawn isolated subagents (a fresh context per invocation) and
drive a browser (via Playwright MCP, Chrome DevTools MCP, or an equivalent).

- Full role separation: Builder and Playtester are genuinely separate
  contexts. The playtester subagent never inherits the builder's reasoning
  or self-narrated intentions.
- Run the loop exactly as described in `SKILL.md`.
- This is the only tier where the anti-cheat property ("the builder cannot
  talk the playtester into a pass") is structurally guaranteed rather than
  merely requested.

## Tier B — browser control, no subagents

The agent can drive a browser but is a single continuous session (for
example, a CLI coding agent without a subagent API).

- Role separation becomes a **discipline**, not a structural guarantee.
  Before switching from Builder to Playtester, the agent must explicitly
  declare a context reset in its own output, e.g.:

  ```text
  --- ROLE SWITCH: BUILDER -> PLAYTESTER ---
  Discarding prior reasoning about what I just implemented.
  Reading only: goal.json, APP_GUIDE.md, memory/.
  ```

- Do not read the diff you just wrote before finishing the visual review.
  Read `goal.json` and `APP_GUIDE.md` only, then play the app.
- State the weaker guarantee in the final report: "role separation was
  simulated within a single session, not structurally enforced."
- The evidence gate (`validate_evidence.py`) still runs and still matters —
  it is the one check that Tier B cannot fake, since it verifies files exist
  on disk rather than trusting the agent's narration.

## Tier C — no browser control

The agent cannot drive a browser or capture screenshots at all.

- **Refuse to run the loop.** Do not approximate a playtest with static code
  reading or a description of expected behavior — that is exactly the
  self-report failure mode this skill exists to prevent.
- Say so explicitly: "This environment has no browser automation available
  (no Playwright MCP, Chrome DevTools MCP, or equivalent). I cannot produce
  evidence-backed playtest verdicts here. Options: add browser tooling, or
  fall back to a manual human playtest using `reference/checklist.md` as a
  guide."
- It is better to report zero verdicts than fabricated ones.

## Driver interchangeability

The skill does not require Playwright or Chrome DevTools specifically — it
requires something that can navigate, click, type, wait, screenshot, and read
console/network output. If your agent only has one of Playwright MCP or
Chrome DevTools MCP available, use it for both interaction and diagnosis; the
role and phase boundaries in `SKILL.md` still apply unchanged.

## What the visual review needs

`scripts/ux_probe.js` needs two things beyond the behavior playtest:

- **In-page JavaScript evaluation.** Playwright's `page.evaluate`, CDP's
  `Runtime.evaluate` with `returnByValue`, or any equivalent. The probe is a
  self-contained IIFE that returns a plain object.
- **Viewport control**, to review more than one width. Playwright's
  `setViewportSize` or CDP `Emulation.setDeviceMetricsOverride` both work.

If viewport control is unavailable, run the probe at whatever width you have,
record that width in every finding, and say in the final report that the
narrow-viewport rules were not exercised. Do not claim a width you did not
actually render. If in-page evaluation is unavailable, skip the measured layer
entirely and report only judged findings — never hand-estimate a contrast
ratio.

## What never changes across tiers

- The behavior verdict is still frozen before the visual review, and both are
  frozen before diagnosis, regardless of whether role separation is structural
  (Tier A) or disciplined (Tier B).
- A judged UX finding still never gates, at any tier.
- `goal.json` is still frozen before round 1.
- `scripts/validate_evidence.py` still gates every round the same way. It
  checks files on disk, so it is the one part of this system whose guarantee
  does not degrade between tiers.
