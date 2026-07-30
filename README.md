# GUI Playtest Loop

A portable skill that makes any coding agent playtest its own UI honestly:
build, play it like a user, freeze a verdict, fix only what failed, repeat
until a goal is actually met — or stop and say so.

Works with Cursor, Claude Code, Codex, or any agent that can read a Markdown
skill file and drive a browser (Playwright MCP, Chrome DevTools MCP, or
equivalent). No vendor lock-in, no required subscription, one stdlib-only
Python script as the only piece of code.

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
   |   >>> VERDICT FROZEN <<<           |
   |   phase 4: diagnose (code allowed) |
   |   phase 5: memory capture          |
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

Full detail, including the five playtester phases and every design invariant,
is in [`SKILL.md`](SKILL.md).

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
python scripts/validate_evidence.py \
  --round-dir playtest-runs/<goal-id>/evidence/round-1 \
  --goal playtest-runs/<goal-id>/goal.json \
  --app-dir <path-to-your-app-source>
```

Exit code `0` means the evidence package is structurally complete — not that
the app is bug-free, and not that every judgment call was correct. See
[`reference/checklist.md`](reference/checklist.md) for what a thorough
playtest actually covers.

## What this is not

- Not a full accessibility audit.
- Not a proof that an experience feels good — that's still a human's job.
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

```bash
python benchmark/harness/seed_golden.py
python benchmark/harness/run_benchmark.py --source golden
```

## Repository layout

```text
SKILL.md              the skill itself — start here
AGENTS.md             pointer for agents that auto-discover this file
reference/            contract, checklist, memory, instrumentation, portability
prompts/              role prompts for builder / playtester / repair
templates/            goal.json and report.json examples + schema
scripts/              validate_evidence.py — the one deterministic gate
benchmark/            detection + autofix harness (see benchmark/README.md)
install/              install.sh / install.ps1 for Cursor personal skills
docs/                 research basis and citations
```

## License

MIT — see [`LICENSE`](LICENSE).
