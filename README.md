# GUI Playtest Loop

A portable skill that makes any coding agent playtest its own UI honestly:
build, play it like a user, freeze a verdict, fix only what failed, repeat
until a goal is actually met — or stop and say so.

Works with Cursor, Claude Code, Codex, or any agent that can read a Markdown
skill file and drive a browser (Playwright MCP, Chrome DevTools MCP, or
equivalent). No vendor lock-in, no required subscription, one stdlib-only
Python toolchain plus one read-only browser probe.

## The problem

> KI-generierte Interfaces sehen oft fertig aus, bevor sie sich korrekt
> verhalten. — [Dominic Hückmann](https://huecki.com/blog/ki-generierte-ui-braucht-playtester/)

A screenshot can lie. A clean component tree can lie. A confident agent
summary can lie. A memory game can render cards correctly and still never
flip a wrong pair back. A form can look complete and still lose data on
validation. These bugs live in *sequences of interaction*, not in single
frames — and they multiply as agents generate more UI faster than anyone
reviews it.

The naive fix — "ask the agent if it works" — fails for a structural reason:
**the agent that built the UI is the worst judge of whether it's done.** It
already knows what it intended and will narrate a pass. This skill removes
that option.

## The loop

```text
 user
  |
  |  /goal  "the memory game should be fully playable"
  v
+-----------------------------------------------------------------+
| ORCHESTRATOR                                                     |
|   expand /goal -> goal.json (9-15 observable checks), freeze it |
|   enforce budget: max rounds | stagnation | spend cap            |
+-----------------------------------------------------------------+
                 |
                 v
   +-----------------------------------+
   | BUILDER                           |
   |   implements or repairs           |
   |   never plays the app to certify  |
   +----------------+------------------+
                    |  app runs on a local URL
                    v
   +-----------------------------------+
   | PLAYTESTER  (fresh each round)     |
   |   phases 1-3: observe, act, log    |
   |   >>> BEHAVIOR VERDICT FROZEN <<<  |
   |   phase 4: visual/UX review (probe)|
   |   >>> UX VERDICT FROZEN <<<        |
   |   phase 5: diagnose (code allowed) |
   |   phase 6: memory capture          |
   +----------------+------------------+
                    |  evidence/round-N/report.json
                    v
   +-----------------------------------+
   | validate_evidence.py               |
   |   schema ok? artifacts exist?      |
   |   every check covered? no leftover |
   |   temp-logging markers?            |
   +----------------+------------------+
                    |
        exit 1      |      exit 0
         |           \___________________
         v                               v
   repeat playtest               all required checks pass?
   (doesn't count as              /              \
    a repair round)             yes               no
                                  |                 |
                                  v                 v
                              +--------+   +------------------+
                              |  DONE  |   |   FAIL PACKET    |
                              +--------+   |  only failures + |
                                            |  their evidence  |
                                            +--------+---------+
                                                     |
                                                     v
                                            back to BUILDER
                                            (round += 1, check budget)
```

Full detail, including profile selection, role boundaries, and every design invariant,
is in [`SKILL.md`](SKILL.md).

## Rigor profiles

- **Quick** — required behavior checks and explicit viewports; default 2 repair rounds.
- **Standard** — sealed live evidence, structured phase/action timestamps, complete
  viewport probes, breakpoint-edge checks, and regression gating; default 5 rounds.
- **Release** — Standard plus externally protected contracts, an isolated blinded
  playtester, repeated runs where flakiness matters, and an external final gate.

Profiles are frozen before round 1 and never downgraded after a failure appears.
See [`reference/profiles.md`](reference/profiles.md).

## Protected evidence

Version-2 goals can hash-protect `goal.json`, schemas, validators, and probe code
outside Builder write authority. Each strict round also seals its action log,
screenshots, and probe files in `evidence_manifest.json`. Origins are explicit:
`live-agent`, `human-live`, `replayed`, or `synthetic-golden`. Golden fixtures prove
the harness, not agent detection quality. See
[`reference/evidence-integrity.md`](reference/evidence-integrity.md).

## Why the verdict is frozen before diagnosis

The playtester is deliberately allowed to read the app's source code — that
is what makes it a QA agent rather than a blind clicker, and lets it locate
bugs, not just observe symptoms. The access is **time-gated, not
role-gated**: it happens only *after* `report.json` is written from what was
actually visible on screen.

- **Code informs the report. Code never produces a pass.** A handler that
  looks correct is not evidence; a screenshot showing the expected state is.
- **Logs and temporary instrumentation can only strengthen a FAIL, never
  rescue a PASS.** Users never see console output.
- Any temporary logging added during diagnosis is marked, archived, reverted,
  and re-verified with a clean rerun before a finding counts as confirmed.
  See [`reference/instrumentation.md`](reference/instrumentation.md).

## Visual and UX review

The playtester does not stop at "does it work." After the behavior verdict is
frozen, it reviews the rendered surface in two layers:

- **Measured** — [`scripts/ux_probe.js`](scripts/ux_probe.js) reads layout and
  computed style at each policy viewport and returns numbers: contrast ratios,
  clipped text, sideways scroll, controls covered by an invisible overlay,
  stretched images, off-scale spacing, palette and type-scale sprawl. Read-only,
  so it runs before the diagnosis gate. Severity comes from the numbers, not
  from the reviewer.
- **Judged** — the reviewer's own reading of hierarchy, affordance, feedback,
  missing states, consistency, copy, density, and rhythm. Every judged finding
  must name one of a fixed set of heuristics and carry an observation, a user
  impact, a rationale, and an honest confidence.

**A judged finding can never fail a goal.** Only measured findings gate, and
only at the severities named in `ux_policy.gate_on`. Without that asymmetry,
"I don't love the spacing" becomes a blocking verdict and the loop stops being
falsifiable. Details in [`reference/ux-review.md`](reference/ux-review.md).

Generation-side design skills score their own intent before emitting. This
track measures what the browser actually painted, which is a different
question — a declared 8pt scale means nothing if the rendered gaps are 13px
and 19px.

## Install

This is a plain directory, not a package. Point your agent at it.

**Cursor** — copy or symlink this repo into `~/.cursor/skills/gui-playtest-loop/`
(personal, all projects) or `.cursor/skills/gui-playtest-loop/` inside a
project (shared with the repo):

```bash
./install/install.sh ~/.cursor/skills/gui-playtest-loop
```

```powershell
.\install\install.ps1 -Destination "$HOME\.cursor\skills\gui-playtest-loop"
```

**Claude Code / Codex / other agents** — point the agent at this repo (or a
copy of it) and tell it to read `SKILL.md` before starting. `AGENTS.md` is a
one-line pointer for agents that auto-discover that file.

**No install at all** — you can also just tell any agent: "read
`SKILL.md` in `<path-to-this-repo>` and follow it," and hand it a `/goal`.

## Usage

```text
/goal the checkout flow should handle an empty cart, a full cart, and a failed payment
```

The orchestrating agent (your top-level Cursor/Claude/Codex session) reads
[`SKILL.md`](SKILL.md), expands the goal into `goal.json` following
[`reference/contract.md`](reference/contract.md), and runs the loop using the
role prompts in [`prompts/`](prompts/). After each playtest round, run the
validator by hand or let the agent run it:

```bash
python scripts/seal_evidence.py \
  --round-dir playtest-runs/<goal-id>/evidence/round-1 \
  --origin live-agent
```

```bash
python scripts/validate_evidence.py \
  --round-dir playtest-runs/<goal-id>/evidence/round-1 \
  --goal playtest-runs/<goal-id>/goal.json \
  --app-dir <path-to-your-app-source>

python scripts/evaluate_gate.py \
  --goal playtest-runs/<goal-id>/goal.json \
  --report playtest-runs/<goal-id>/evidence/round-1/report.json
```

Exit code `0` means the evidence package is structurally complete — not that
the app is bug-free, and not that every judgment call was correct. See
[`reference/checklist.md`](reference/checklist.md) for what a thorough
playtest actually covers.

## What this is not

- Not an accessibility audit — the visual track covers craft and ergonomics
  and makes no compliance claim.
- Not a proof that an experience feels good — the judged layer is one
  reviewer's opinion, labelled as such, and cannot fail a goal.
- Not a security review.
- Not perfect: the published study behind this design found GUI playtester
  verdicts agree with blind human annotators on about **84% of criteria**.
  Treat a `PASS` as "the specified behavior was observed," not as "this is
  good software."

Full research basis, citations, and the corrections made along the way are
in [`docs/research.md`](docs/research.md).

## Benchmark

A small HTML fixture library plus a stdlib-only harness scores whether a
playtester actually detects injected UI bugs and (on a subset) whether the
repair loop completes the goal. See [`benchmark/README.md`](benchmark/README.md)
and [`reference/benchmark.md`](reference/benchmark.md).

**Interpretation matters:** `--source golden` is a synthetic harness baseline.
Its reports are generated from known expectations and use placeholder artifacts;
it validates schemas/scoring but is not an agent-effectiveness result. Only
blinded reports declaring `evidence_origin: live-agent` belong in live recall and
precision claims. The current Tier-2 helper applies predefined repair manifests;
it is scaffolding for a future autonomous repair evaluation, not one today.

```bash
python benchmark/harness/seed_golden.py
python benchmark/harness/run_benchmark.py --source golden
```

## Repository layout

```text
SKILL.md              the skill itself — start here
AGENTS.md             pointer for agents that auto-discover this file
skills/               focused behavior, rendered-UX, and repair sub-skills
reference/            contract, checklist, ux-review, memory, instrumentation, portability
prompts/              role prompts for builder / playtester / repair
templates/            goal.json and report.json examples + schema
scripts/              validation, contract/evidence sealing, and rendered UX probe
benchmark/            detection + autofix harness (see benchmark/README.md)
install/              install.sh / install.ps1 for Cursor personal skills
docs/                 research basis and citations
```

## License

MIT — see [`LICENSE`](LICENSE).
