# Visual & UX Review

The behavior track answers *"can a user complete the flow?"*. This track
answers *"is what they are looking at actually built, or does it just look
built?"* Both are frozen before any source code is read.

This is **not** an accessibility audit and makes no compliance claim. It
covers visual craft and interaction ergonomics — the things that make a
generated interface read as finished or as slop.

## Why this belongs in the loop

Generation-side design skills (Hallmark and friends) already encode good
taste, and they self-score before emitting. That self-score has the same
structural weakness as a builder certifying its own bug fix: the model grades
the intent it just had, not the pixels the browser actually painted. A
declared 8pt spacing scale means nothing if the rendered gaps are 13px and
19px.

So this track measures the **rendered surface**, from outside, after the fact.

## Two layers, different rules

| | Layer 1 — Measured | Layer 2 — Judged |
|---|---|---|
| Produced by | `scripts/ux_probe.js` | the playtester's judgment |
| Basis | numbers from layout and computed style | reasoning about the screenshot |
| Falsifiable | yes — rerun the probe | no — another reviewer may disagree |
| Max severity | `blocker` | `major` |
| Can block the loop | yes, if `ux_policy.gate_on` says so | **never** |
| Required fields | `measurement` with actual + threshold | `heuristic`, `rationale`, `confidence` |

**The rule that governs this track: a judged finding can never fail a goal.**
It is advisory input for the builder and a candidate for promotion into
`goal.json`. Only measured findings — with a number, a threshold, and a
reproducible probe run behind them — are allowed to gate.

That asymmetry is deliberate. Without it, "I don't love the spacing" becomes a
blocking verdict, and the loop stops being falsifiable.

## Layer 1 — the measured rules

`scripts/ux_probe.js` is read-only: it reads layout, computed styles, and
paint order, and mutates nothing. That is why it may run *before* the
diagnosis gate, unlike instrumentation.

| Rule | What it measures | Default severity |
|---|---|---|
| `viewport-overflow` | page scrolls sideways at the tested width | blocker |
| `occluded-interactive` | another element paints over a control's centre, so clicks never land | blocker |
| `text-clipped` | text cut off by `overflow: hidden` with no ellipsis | blocker |
| `low-legibility` | text-to-background contrast ratio below the reading floor | blocker < 3.0, else major |
| `target-too-small` | control's short side under 24px | blocker < 16px, else major |
| `element-overflows-viewport` | element extends past the viewport edge | major |
| `image-aspect-distortion` | rendered ratio differs from the image's natural ratio | major |
| `tiny-text` | computed font size under 12px | major |
| `unstyled-default` | browser default serif body or unstyled buttons | major |
| `two-line-clickable` | button or link label wraps onto multiple lines | minor |
| `missing-hover-affordance` | control gives no pointer cursor | minor |
| `palette-sprawl` | more distinct colours than a coherent palette needs | minor |
| `type-scale-sprawl` | more distinct font sizes than a deliberate scale | minor |
| `font-family-sprawl` | more typefaces than a display + body pairing | minor |
| `radius-sprawl` | inconsistent corner rounding across components | minor |
| `spacing-off-scale` | share of spacing values off the 4px rhythm | minor |
| `near-miss-alignment` | siblings misaligned by 0.5–3px | minor |

Severity is derived from the numbers by fixed rules inside the probe, not
chosen by the reviewer. Thresholds live in one `THRESHOLDS` block at the top
of the probe and are reported back in every result, so a finding always
carries the constants it was judged against.

### Honest limits of the probe

- **Backgrounds are approximated** when text sits on an image or gradient.
  Those findings carry `approximated: true` and must be confirmed visually
  before being reported.
- **Sprawl rules are signals, not verdicts.** A deliberately maximalist design
  can legitimately exceed them. They are always `minor`.
- The probe sees one viewport per run. Run it at each width in
  `ux_policy.viewports` and save one artifact per width.

## Layer 2 — the judged heuristics

A judged finding must name one of these. Freeform aesthetic commentary is not
a finding.

| Heuristic | Fires when |
|---|---|
| `hierarchy-primary-action` | the main action does not visually dominate |
| `hierarchy-competing-emphasis` | several elements compete for the same attention |
| `affordance-unclear` | a user cannot tell what is interactive |
| `feedback-missing` | an action produces no visible acknowledgement |
| `state-missing` | no empty, loading, error, success, or disabled state exists |
| `consistency-drift` | the same concept is styled differently across surfaces |
| `copy-unclear` | a label, error, or empty state does not tell the user what to do |
| `density-cramped` | elements crowd each other and lose grouping |
| `density-bloated` | space is so loose that relationships break |
| `rhythm-templated` | the layout reads as a generic generated template |
| `motion-excessive` | animation delays the user without adding information |
| `motion-missing` | a state change happens abruptly enough to be missed |
| `tone-mismatch` | the visual voice contradicts the stated intent in `goal.json` |
| `flow-friction` | the flow requires steps that carry no value |

Every judged finding needs four things, or the validator rejects it:

1. **`observation`** — what is on screen. Descriptive, not evaluative.
2. **`user_impact`** — the concrete consequence for someone using this.
3. **`rationale`** — why the observation causes the impact.
4. **`confidence`** — `high`, `medium`, or `low`, honestly set.

### Forbidden as findings

- "Looks ugly", "feels cheap", "I would have used a different colour."
- Anything the reviewer cannot point at in a screenshot.
- Any restatement of a behavior check that already lives in `checks`.
- Any preference that contradicts an explicit instruction in `goal.json`.

If the observation is real but does not fit a heuristic, write it to
`memory/skills.jsonl` as a note. Do not inflate the report.

## Procedure

Run after the behavior verdict is frozen, before reading any source.

```text
1. Reset to a clean load of the app at the default viewport.
2. For each width in ux_policy.viewports (default 320, 768, 1280):
     resize -> settle -> screenshot -> run scripts/ux_probe.js
     save evidence/round-N/ux_probe.<width>.json
3. Walk the measured findings. Discard any that the screenshot contradicts
   (approximated backgrounds especially). Keep the rest verbatim — do not
   soften a number.
4. Replay the key states you already reached during the behavior playtest
   (empty, loading, error, success, disabled) and screenshot each one.
5. Write judged findings against the heuristic table, each anchored to a
   screenshot.
6. Freeze: append ux_findings to report.json.
```

Step 4 matters. Most `state-missing` findings are only visible because the
behavior playtest already drove the app into those states — which is exactly
why this track runs second rather than in isolation.

## Gating

`goal.json` carries an optional policy. Defaults apply when it is absent:

```json
"ux_policy": {
  "enabled": true,
  "gate_on": ["blocker"],
  "viewports": [320, 768, 1280]
}
```

- `gate_on: ["blocker"]` — measured blockers must be fixed before the goal is
  done. This is the default and the recommended setting.
- `gate_on: []` — review is reported but never blocks. Use when the visual
  layer is explicitly out of scope for this goal.
- `gate_on: ["blocker", "major"]` — strict mode for design-critical work.

Judged findings are never in `gate_on`, regardless of configuration.

## Promotion

A judged finding that keeps recurring is a sign the goal was underspecified.
Set `proposed_check` on it with an observable statement, and the orchestrator
may add that statement to a **future** `goal.json` — never the frozen current
one. This is the same rule instrumented findings follow: a diagnosis can
propose a check, it cannot become one mid-loop.

```json
{
  "id": "ux-7",
  "layer": "judged",
  "heuristic": "state-missing",
  "severity": "major",
  "observation": "Submitting with an empty cart shows the same blank panel as a loaded cart.",
  "user_impact": "A user cannot tell whether the cart is empty or still loading.",
  "rationale": "The empty and loading states render identical markup, so the panel carries no information.",
  "confidence": "high",
  "evidence": ["screenshots/08_empty_cart.png"],
  "proposed_check": "An empty cart shows a labelled empty state distinct from the loading state."
}
```

## Relationship to generation-side design skills

They are complementary and should not be merged:

- A design skill decides **what to build** and scores its own intent.
- This track measures **what was actually painted**, from outside, with no
  knowledge of that intent beyond `goal.json`.

If a project uses a design skill, its tokens and scale are the natural source
for tightening this probe's `THRESHOLDS` — but the probe still measures the
rendered result, never the token file.
