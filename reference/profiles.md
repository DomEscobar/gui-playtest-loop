# Playtest profiles

Choose once before round 1. A profile controls cost and evidence rigor; it never
changes the meaning of an individual goal check.

## `quick`

Use for small, low-risk UI changes. Run all required behavior checks, preserve an
action log, and capture evidence for pass/fail. Run only explicitly configured UX
viewports. Evidence sealing and integrity verification are recommended, not required.
Default repair budget: 2 rounds.

## `standard` (default)

Use for interactive features, demos, forms, dashboards, and ordinary releases.
Require structured phase timestamps, `evidence_origin: live-agent`, a sealed evidence
manifest, every configured viewport probe, breakpoint edge probes, and full-goal
regression checks after repairs. Require a contract integrity manifest when the
Builder and Orchestrator share a writable workspace. Default repair budget: 5 rounds.

## `release`

Use for high-impact flows and benchmark claims. Require all `standard` controls plus
an integrity manifest stored outside Builder write authority, an isolated fresh
playtester with no truth/golden access, all declared states and viewports, repeated
live runs when flakiness matters, and an externally owned final gate. Default repair
budget: 5 rounds with an explicit time/spend cap.

## Profile invariants

- Never relabel synthetic or replayed evidence as live.
- Never downgrade after seeing failures.
- A missing strict-profile artifact is `blocked`, not a reason to fall back silently.
- Accessibility and security require their own declared gates; neither is implied.
