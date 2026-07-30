# What To Actually Test

This is the catalog the playtester draws checks from during goal expansion
and keeps in mind during phase 3. It is not a script to run mechanically —
judge which items apply to the app in front of you.

## Failure archetypes common in AI-generated UIs

These are disproportionately common in freshly generated interfaces and are
invisible in a static screenshot:

- **Dead button** — element renders, handler was never wired up.
- **State never returns** — a temporary state (a wrong pair, an open toast,
  a hover highlight) never reverts.
- **Timer never fires** — a delay, auto-save, or auto-dismiss is coded but
  never actually triggers.
- **Miscounted state** — a counter double-increments (common with strict
  re-render modes) or only updates on the next unrelated action.
- **Missing end state** — a win, game-over, success, or completion screen is
  never reached even when the underlying condition is met.
- **Fake dynamism** — a dashboard renders charts but changing a filter does
  nothing because the data is hardcoded.
- **Modal with no exit** — opens fine, but Escape, backdrop click, and the
  close button do not all work.
- **Optimistic UI without reconciliation** — an item appears immediately but
  silently disappears on reload because the write never actually happened.
- **Endless spinner** — a loading state has no timeout and no error path.
- **Input loses focus or value** — a re-render on every keystroke resets the
  field.

## Systematic sweep

Work through these categories for any nontrivial interactive surface:

1. **Entry** — Does it load? Is the initial state correct before any click?
   Is there a layout shift right after first render?
2. **Affordance sweep** — Touch every visible interactive element once and
   confirm *something* observable changes. Cheapest way to catch dead
   controls; do this before the happy path.
3. **Happy path, twice** — Run the core flow start to finish once cleanly,
   then run it again. Many bugs only appear on the second pass (stale state
   from the first run, listeners that were not cleaned up).
4. **State transitions over time** — Does a state change on the expected
   trigger, and does it revert when it is supposed to? What is visible
   during the wait?
5. **Invalid input** — Empty, whitespace-only, very long, wrong type,
   special characters, emoji, boundary values (0, -1, max+1). The bar is not
   "it blocks," it is "the user understands why."
6. **Data retention** — Does input survive a validation error, a reload, the
   back button, or a tab switch? Silent data loss after validation is one of
   the most common hidden bugs.
7. **Reset and repeatability** — Does restart actually reset everything
   (board, score, timers, selection), or only what is visible?
8. **Navigation** — Browser back mid-flow, a deep link straight to step
   three, a reload during a modal, opening in a new tab.
9. **Race conditions** — Double-click submit, rapid repeated clicks, an
   action fired while a previous one is still loading. Is there a disabled
   state?
10. **Edge states** — Zero items, one item, many items, very long text
    (overflow), an error response from the backend.
11. **Feedback** — Silent failure is the worst category: the action did not
    happen, but nothing indicates that.
12. **Viewport and keyboard** — Narrow width, resizing mid-flow, tab order,
    Enter to submit, Escape to close, focus trapped correctly inside a
    modal.
13. **Runtime hygiene** — Uncaught exceptions in the console, failed
    requests, 404s on assets, obvious jank, a heap that keeps growing across
    repeated identical actions.

## Severity classification

Not every observation belongs in `report.json` as a check result. Classify
before writing anything down:

| Observation | Classification |
|---|---|
| Expected behavior does not occur | **FAIL** — blocking |
| Uncaught exception during a flow, even if the UI looks fine | **FAIL** — blocking, the exception is the evidence |
| Console warning with no observable effect | Advisory note, not a FAIL |
| Reproduces on only one of three attempts | **Flake suspicion** — record in `memory/skills.jsonl`, do not report as a confirmed FAIL yet |
| "Feels slow," "color is ugly," "layout could be nicer" | **Not a finding** — outside this loop's scope, do not put it in the report |

Subjective, unfalsifiable statements do not belong in `goal.json` either.
"The difficulty curve feels right" is not checkable by a tester who only
sees the rendered surface; "the spawn rate increases each wave" is.
