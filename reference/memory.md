# Memory

Three layers, borrowed from research on continual game-generation loops where
a code agent and a GUI playtester iterate with shared memory. Lifecycle
(in-task vs cross-task) and scope (private vs shared) are the two axes.

| Layer | Lifecycle | Scope | Holds |
|---|---|---|---|
| **Episode** | in-task | shared between builder and playtester | this round's summary, fix list, attempts so far |
| **Skill** | cross-task | **playtester-private** | interaction strategies, wait patterns, selector recipes, known false positives |
| **World** | cross-task | shared | app map, routes, auth flow, seed data, domain rules |

## The one rule that keeps memory from becoming a cheat channel

**Memory caches the path to a verdict, never the verdict itself.**

It is fine to remember "the submit button needs a 300ms settle before the
toast appears" or "this selector is `[data-testid=start-btn]`, not the visible
text." It is not fine to remember "check `mismatch-flips-back` passed last
round" and skip re-observing it this round. Every check is re-verified from
fresh evidence every round it is in scope. If this rule is violated, rounds
stop being independent evidence and start being a rubber stamp.

## Why Skill Memory is playtester-private

The builder must never read the playtester's skill memory. If the builder
knows which selectors or timings the playtester relies on, it can shape the
implementation to satisfy the test mechanically instead of the actual
requirement — the same failure mode as a student who has seen the exam
answer key. Keep these on separate files or separate memory namespaces, not
just separate sections of one shared document.

## What goes where, concretely

**`memory/world.md`** (shared, cross-task)

```markdown
## Routes
- / : landing, no auth required
- /app : requires a logged-in session (see Auth below)

## Auth
- Dev login: any email, password "test1234"
- Session persists via localStorage key `session_token`

## Seed data
- `bun run seed` populates 3 demo users and 12 sample items
```

**`memory/skills.jsonl`** (playtester-private, cross-task)

```json
{"type": "wait-pattern", "context": "toast dismiss", "note": "toast auto-dismisses after ~2.5s, wait for it to fully leave the DOM before the next screenshot"}
{"type": "selector-recipe", "context": "start button", "note": "prefer role=button name=Start over text match, label wraps in a span sometimes"}
{"type": "false-positive", "context": "score flicker", "note": "score briefly shows old value for one frame during the match animation, this is not a bug, wait for animation-end before asserting"}
```

**`memory/failures.jsonl`** (shared, in-task, appended every round)

```json
{"round": 1, "check_id": "mismatch-flips-back", "fingerprint": "mismatch-timer-double-registered", "status": "fail"}
{"round": 2, "check_id": "mismatch-flips-back", "fingerprint": "mismatch-timer-double-registered", "status": "fail"}
```

Two consecutive identical fingerprints for the same check is the stagnation
signal referenced in `SKILL.md`'s stop conditions — the orchestrator should
stop retrying the same fix and surface it to a human instead.

## Rehydration at the start of a round

Each playtester invocation is a fresh instance with no memory of the
builder's reasoning or self-narrated intentions from previous rounds. It
rehydrates only from the files above, plus `goal.json` and `APP_GUIDE.md`.
This is what keeps the counterpart adversarial: state persists on disk, not
in a shared conversation the builder can steer.
