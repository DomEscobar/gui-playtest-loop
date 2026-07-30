# Research Basis

This skill's design invariants were not invented in a vacuum. They come from
a standalone research pass (deep-research workflow, standard depth, 33
sources, 44 URL-backed evidence rows) into the "GUI playtester" pattern for
AI-generated web UIs. The original research artifacts (`plan.yaml`,
`sources.jsonl`, `evidence.jsonl`, validated with `validate`) live in a
separate repository and are not duplicated here; this file is the resulting
report, copied verbatim as the citable basis for this skill.

Three corrections were made to the original draft of this report after a
second evidence pass, and they are the reason several invariants in
`SKILL.md` look the way they do:

- Webwright's completion gate turned out to be **self-reflection** (the
  generator judging itself), not an external verifier — hence this skill's
  insistence on a role-separated playtester plus a stdlib validator that the
  builder cannot influence.
- Play2Code's anti-poisoning mechanism is **input blinding** (no DOM, source,
  console, or internal state), not memory wiping — hence this skill keeps
  cross-round memory but blinds the verdict step from the diagnosis step.
- The GUI judge in that study matched blind human annotators on only 84.2% of
  criteria — hence this skill's explicit "Limits, stated plainly" section
  refusing to claim perfect playtesting.

---

<!-- BEGIN VERBATIM REPORT -->

# GUI Playtester for Web Apps — Research Report

**Date:** 2026-07-30
**Seed article:** [Deine KI-generierte UI braucht einen Playtester, keinen Screenshot-Review](https://huecki.com/blog/ki-generierte-ui-braucht-playtester/)
**Depth:** standard

## Executive summary

The Huecki article describes a real emerging pattern, not a niche blog idea: as AI makes interactive UIs cheap to generate, verification shifts from "does it look finished?" to "can a naive user complete the expected interaction path?" The strongest open-source match to that pattern is **Microsoft Webwright** (code-as-action → rerunnable Playwright script + screenshots + logs). The closest research twin is **Play2Code / PlaytestArena**, which literally separates a builder agent from a GUI playtester.

There is **no mature product that only sells "GUI playtester for vibe-coded webapps"**, but the market has already split into four useful layers:

1. **Evidence-first coding agents** (Webwright) — best contract for playtest artifacts
2. **Browser CLIs for coding agents** (Playwright CLI, agent-browser, Playwright MCP) — DIY playtester plumbing
3. **NL / vision automation SDKs** (Midscene, Stagehand, Skyvern, browser-use) — strong interaction engines, weaker default evidence contracts
4. **Commercial AI QA** (Momentic, QA.tech, testRigor, ZeroStep) — production regression / exploratory QA, less oriented to ephemeral generated prototypes

**Recommendation:** For AI-generated prototypes and media/demo apps, implement the Huecki loop with **expected behaviors + Webwright or Playwright CLI/agent-browser**, keep Builder ≠ Playtester ≠ Repair, and promote only stable scripts into CI. Use Midscene/Stagehand when you want NL/vision assertions; use Momentic/QA.tech when the app is a shipping product needing continuous coverage.

## What the seed article asks for

From [huecki.com](https://huecki.com/blog/ki-generierte-ui-braucht-playtester/):

| Requirement | Why it matters |
|---|---|
| Separate Playtester from Builder | Self-checking coding agents over-claim |
| Expected behaviors (5–8) | Makes pass/fail objective |
| Rerunnable Playwright script | Turns opinion into regression artifact |
| Screenshots + action log | Evidence for repair |
| No code fixes until evidence complete | Prevents redesign-as-repair |
| Rerun after fix | Closes the loop |

The article explicitly anchors on **Webwright** and related GUI-agent research (Play2Code).

## Landscape map

```text
                    Expected behaviors / rubrics
                              |
                              v
     +-------------------+-------------------+
     | Exploration       | Evidence artifact |
     | (click / observe) | (script+logs+ss)  |
     +---------+---------+---------+---------+
               |                   |
               v                   v
     browser-use, MCP,     Webwright, Spectra,
     Stagehand agent,      QA-agent, Playwright
     Midscene Skills       CLI + coding agent
               |                   |
               +--------+----------+
                        |
                        v
              Repair agent (scoped)
                        |
                        v
              CI / production suite
         (Momentic, Midscene fixtures,
          cleaned Playwright tests)
```

## Findings

### 1. Webwright is the closest OSS "playtester engine"

Primary sources: [Webwright site](https://microsoft.github.io/Webwright/), [MSR article](https://www.microsoft.com/en-us/research/articles/webwright-a-terminal-is-all-you-need-for-web-agents/), [GitHub](https://github.com/microsoft/Webwright) (~5.8k stars).

- Paradigm: **code-as-action** — model writes Playwright/Python, runs it from a terminal, discards browser sessions.
- Durable outputs: `final_script.py`, logs, screenshots, self-reflection result.
- Completion gate: must rerun final script in a fresh folder and pass self-reflection.
- Harness: ~1K LOC (Runner / Model Endpoint / Environment).
- Reported: 60.1% Odysseys and 86.7% Online-Mind2Web per the MSR article and repo (the landing page states 60.8% Odysseys — primary sources disagree).

**Fit to Huecki:** excellent for the artifact contract. The article's workspace contract is almost a direct Webwright usage pattern.

**Critical gap (corrected):** Webwright's done-gate is **self-reflection**, i.e. the generator grading itself: "the agent needs to generate a self-reflection config, run a final script in a fresh folder with logs and screenshots, and **pass its own self-reflection judgement**" ([MSR](https://www.microsoft.com/en-us/research/articles/webwright-a-terminal-is-all-you-need-for-web-agents/)). It mitigates premature "done" but is **not** an agent-external verifier. Any goal loop built on Webwright still needs an independent gate.

**Benchmark caveat:** browser-use claims **#1 on Odysseys at 87.4%** ([repo](https://github.com/browser-use/browser-use)), versus Webwright's 60.1%. Both are vendor self-reports on the same named benchmark; treat "SOTA" claims as unresolved.

### 2. Play2Code is the research proof that playtesters improve generated interactive apps

Primary: [arXiv 2605.28258](https://arxiv.org/abs/2605.28258), [project site](https://continual-game-generation.vercel.app/).

- **PlaytestArena:** 200 browser game generation tasks + rubrics of expected in-play behaviors.
- **Play2Code:** game agent ↔ GUI playtester loop with shared memory.
- Result: **66.8% rubric pass-rate**, +37.1 vs single-pass, +14.6 vs agentic-coding baselines.
- Important caveat from the paper: GUI playtester feedback is more traceable than human reports, but still idiosyncratic.

**How it prevents self-grading (important):** the anti-poison mechanism is **input blinding**, not memory wiping. The GUI agent "has no access to the DOM, source code, internal variables, or console logs," and plays "without access to the code or evaluation rubric." Memory is deliberately **shared and accumulated** across rounds, and rubric scores rise monotonically across rounds.

**Rubric authoring rules (directly reusable):**
- *Observability*: "every criterion can in principle be adjudicated by a tester who only sees the rendered game, without access to source code or internal state."
- *Faithfulness*: criteria follow from the prompt, not personal preference.
- Subjective items are rejected ("the difficulty curve feels right" is not a criterion; "spawn rate increases each wave" is).
- Scale: 375 criteria total, **mean 11.7 per game (min 9, max 15)** — more than the seed article's 5–8.

**Verifier reliability:** the GUI judge matches blind human annotators on **84.2% of criteria** (κ=0.64, within the human–human band of 0.66); game-level Spearman ρ=0.87. Roughly 1 in 6 item verdicts differs from a human.

**Fit:** conceptual twin of Huecki's Builder/Playtester/Repair loop, focused on games but transferable to demos, calculators, onboarding flows, dashboards.

### 3. Browser CLIs make DIY playtesters practical inside Cursor/Claude/Codex

| Tool | Stars (approx.) | Role |
|---|---:|---|
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) | large / official | Persistent exploratory browser for agents |
| [Playwright CLI](https://github.com/microsoft/playwright-cli) | ~12k | Token-efficient discrete commands + skills |
| [agent-browser](https://github.com/vercel-labs/agent-browser) | ~39.5k | Fast CLI for coding agents |

Microsoft itself says coding agents often prefer **CLI+Skills** over MCP for token efficiency; MCP remains useful for long exploratory/self-healing sessions ([Playwright MCP README](https://github.com/microsoft/playwright-mcp)). Ecosystem analysis agrees that CLI tools move state to disk ([N+1 blog](https://nikiforovall.blog/ai/2026/07/05/browser-automation-agents-ecosystem.html), [Better Stack](https://betterstack.com/community/guides/ai/playwright-cli-vs-mcp-browser/)).

**Fit:** best "build your own Huecki loop today" path if you already use coding agents. Prompt the agent as Playtester only; require script + screenshots + log + pass/fail.

### 4. Mature OSS agents excel at driving UIs, not at the evidence contract

| Project | Approx. stars | Paradigm | Playtester fit |
|---|---:|---|---|
| [browser-use](https://github.com/browser-use/browser-use) | ~107k | Autonomous LLM browser loop | Great explorer; weak default rerunnable-script contract |
| [Stagehand](https://github.com/browserbase/stagehand) | ~24k | Hybrid NL + code (`act/extract/observe/agent`) | Strong production automation; can cache actions; not playtest-specific |
| [Midscene](https://github.com/web-infra-dev/midscene) | ~14k | Vision-driven NL testing + Playwright/Vitest | Best OSS for assertion-style playtesting of UIs |
| [Skyvern](https://github.com/Skyvern-AI/skyvern) | large / AGPL | CV + Playwright workflows | Workflow automation; AGPL/commercial hybrid |
| [Spectra](https://github.com/fifijo/spectra) | early | Planner/Generator/Healer → Playwright suite | Conceptually aligned, immature |
| [QA-agent](https://github.com/to7vx/QA-agent) | early | Explore → generate → execute → heal | Aligned pipeline, maturity unclear |
| [CBrowser](https://github.com/alexandriashai/cbrowser) | early | Cognitive/persona UX + MCP tools | Broader UX/a11y than strict expected-behavior checks |

Secondary taxonomies ([candede](https://www.candede.com/articles/webwright-architecture-microsoft/), [Medium](https://ai-engineering-trend.medium.com/microsoft-open-sources-webwright-browser-agents-finally-escape-the-guess-the-next-click-dead-end-f80c236c9da4)) consistently distinguish:

- **Session agents** (browser-use, Stagehand agent mode)
- **CLI micro-action tools** (agent-browser, Playwright CLI)
- **Code-as-action** (Webwright)

Only the last naturally produces the Huecki evidence package.

### 5. Commercial AI QA is adjacent, not identical

| Product | Positioning | Overlap with playtester loop |
|---|---|---|
| [Momentic](https://momentic.ai/) | Plain-English E2E YAML, auto-heal, explore agent, PR gap filling | High for shipping apps; less for ephemeral vibe prototypes |
| [QA.tech](https://qa.tech/) | Exploratory + dynamic regression agents, PR previews | High exploratory metaphor; cloud-hosted |
| [testRigor](https://testrigor.com/) | Plain-English E2E, usage-derived coverage | Mature NL testing; not coding-agent workspace artifacts |
| [ZeroStep](https://zerostep.com/) | `ai()` inside Playwright | Selector resilience, not full playtester role separation |

These products optimize for **maintaining coverage as products change**. Huecki's loop optimizes for **verifying freshly generated interactive artifacts with reproducible evidence**.

### 6. No dominant "open-source GUI playtester product" yet

What exists instead:

- **Pattern** (Huecki / Play2Code): roles + rubrics + evidence
- **Engine** (Webwright): code-as-action harness
- **Plumbing** (Playwright CLI / MCP / agent-browser)
- **Assertion SDKs** (Midscene, Stagehand, ZeroStep)
- **Early generators** (Spectra, QA-agent)
- **Commercial QA clouds** (Momentic, QA.tech)

The open product gap: a thin orchestration layer that takes `expected_behaviors[] + URL`, runs an isolated playtester agent, emits a fixed evidence contract, and feeds a repair agent without letting it redesign. **This skill is one concrete attempt to fill that gap.**

## Decision matrix (for webapp playtesting)

| Option | Rerunnable script | Screenshots/logs | Role separation | Maturity | Best use |
|---|---|---|---|---|---|
| Webwright | Excellent | Excellent | DIY | Emerging research OSS | Prototype playtests, evidence-backed bugs |
| Playwright CLI / agent-browser + coding agent | Good (if prompted) | Good | DIY via prompts | High tooling maturity | Solo builders / Cursor workflows |
| Midscene | Good (NL tests) | Good (vision reports) | Partial | High | Vision/assertion playtests in Playwright |
| Stagehand | Mixed | Mixed | Weak | High | Resilient automation, hybrid NL |
| browser-use | Weak default | Session-dependent | Weak | Very high adoption | Open-ended exploration |
| Spectra / QA-agent | Good intent | Varies | Partial | Low | Experiments only |
| Momentic / QA.tech | Product-managed | Yes | Product-managed | Commercial | Continuous product QA |

## Recommendation

### If you are building AI-generated webapps/demos (closest to Huecki)

1. Adopt the **evidence contract** as the product requirement, not a specific brand.
2. Start with **Webwright** *or* a Cursor/Claude playtester skill over **Playwright CLI / agent-browser**.
3. Keep three roles hard-separated in prompts/tools.
4. Required outputs per run: `plan.md`, `final_script.*`, `action.log`, `screenshots/`, `report.md` with pass/fail per expected behavior.
5. Only then allow Repair; rerun the same script.

### If you need production regression

- Prefer **Midscene** (OSS) or **Momentic / QA.tech** (commercial).
- Promote cleaned playtester scripts into deterministic Playwright CI; do not treat exploratory playtest scripts as production tests.

### If you want open-source leverage without buying a QA cloud

Best stack today:

```text
Expected behaviors
  -> Webwright OR (Playwright CLI + coding agent as Playtester)
  -> evidence package
  -> Repair agent
  -> optional Midscene/Playwright promotion to CI
```

## Goal-loop design evidence (anti-cheat)

Requirements that are actually evidence-backed, for a playtest goal loop:

| Requirement | Evidence |
|---|---|
| Verdict must be external to the generator's self-report | [verification-loop](https://raw.githubusercontent.com/KanakMalpani/Loop-Engineering/main/patterns/verification-loop.md): "Never let the generator mark its own homework—parse tool exit codes and test runners programmatically." |
| Done-check should be one the agent did not write and cannot edit | [Loop Engineering](https://aipatternbook.com/loop-engineering); a loop gated by model optimism is the "Ralph Wiggum Loop" |
| Blind the playtester to implementation | Play2Code: no DOM, source, internals, or console logs |
| Keep playtest memory across rounds | Play2Code shared memory; scores rise monotonically per round |
| Bound the loop | Stop conditions: tests pass, spend cap, iteration cap, human stop; "autonomy ceiling is set by verification reach" |
| Expect specific cheat modes | verification-loop failure modes: test hacking (weakened assertions), false PASS (stub verifier always green), flaky verifier, repair regression, overfitting to tests |
| Mitigations | mutation testing, review test diffs, negative tests, run full suite each round, snapshot best candidate, quarantine flaky checks |

**Unresolved design tension:** Play2Code blinds the playtester to the DOM to keep judgments user-realistic, but Huecki's rerunnable Playwright script depends on DOM selectors for reproducibility. A loop cannot maximize both realism and deterministic replay; choose per check.

**How this skill resolves the tension:** by time, not by role. The playtester keeps full code access (this repo's explicit design choice, made after weighing the tension above) but the verdict is written before that access is used for anything beyond driving the browser. See `SKILL.md`'s "verdict gate" and `reference/instrumentation.md`.

## Caveats and open questions

- Benchmark numbers for Webwright/Play2Code are author-reported; useful for direction, not procurement SLAs.
- Star counts measure popularity, not fitness for playtesting.
- arXiv abstract page and ZeroStep homepage returned empty bodies in one fetch pass; claims for those were cross-checked via HTML/WebFetch/search snippets.
- No reviewed source markets a dedicated "GUI playtester for vibe-coded apps" as a complete product; the pattern is ahead of packaging.
- Agents still miss taste, accessibility quality, and "does this feel good?" — Huecki and Play2Code both acknowledge this.

## Sources

1. [Huecki — KI-generierte UI braucht Playtester](https://huecki.com/blog/ki-generierte-ui-braucht-playtester/)
2. [Webwright project site](https://microsoft.github.io/Webwright/)
3. [MSR — A Terminal Is All You Need For Web Agents](https://www.microsoft.com/en-us/research/articles/webwright-a-terminal-is-all-you-need-for-web-agents/)
4. [microsoft/Webwright](https://github.com/microsoft/Webwright)
5. [GUI Agents for Continual Game Generation (arXiv)](https://arxiv.org/abs/2605.28258)
6. [Play2Code project site](https://continual-game-generation.vercel.app/)
7. [Playwright MCP](https://github.com/microsoft/playwright-mcp)
8. [Playwright CLI](https://github.com/microsoft/playwright-cli)
9. [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)
10. [browser-use](https://github.com/browser-use/browser-use)
11. [Stagehand](https://github.com/browserbase/stagehand) / [Browserbase Stagehand page](https://www.browserbase.com/stagehand)
12. [Midscene](https://github.com/web-infra-dev/midscene) / [docs](https://midscenejs.com/introduction)
13. [Skyvern](https://github.com/Skyvern-AI/skyvern)
14. [Spectra](https://github.com/fifijo/spectra)
15. [QA-agent](https://github.com/to7vx/QA-agent)
16. [CBrowser](https://github.com/alexandriashai/cbrowser)
17. [Momentic](https://momentic.ai/)
18. [QA.tech](https://qa.tech/)
19. [testRigor](https://testrigor.com/)
20. [ZeroStep](https://zerostep.com/)
21. [Browser automation ecosystem roundup](https://nikiforovall.blog/ai/2026/07/05/browser-automation-agents-ecosystem.html)
22. [Webwright architecture secondary](https://www.candede.com/articles/webwright-architecture-microsoft/)
23. [Playwright CLI vs MCP](https://betterstack.com/community/guides/ai/playwright-cli-vs-mcp-browser/)
24. [WinBuzzer Webwright coverage](https://winbuzzer.com/2026/05/25/microsoft-webwright-turns-web-agents-into-reusable-code-xcxwbn/)

<!-- END VERBATIM REPORT -->
