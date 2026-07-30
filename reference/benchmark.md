# Benchmark harness

Reference for the detection + autofix benchmark. Ground truth lives in
`benchmark/truth/` and must never be copied into an agent workspace during
evaluation.

## Tiers

| Tier | Question | Fixtures |
|------|----------|----------|
| **Tier 1 — Detection** | Did the playtester find the injected bug? | All `tier1: true` entries in `catalog.json` |
| **Tier 2 — Autofix** | After a fail packet, can repair + re-playtest complete the goal? | Entries with `tier2_autofix: true` |

## Layout

```text
benchmark/
├── catalog.json           fixture registry + thresholds
├── fixtures/<id>/         agent-visible app.html + goal.json
├── truth/<id>.json        ground truth (orchestrator-only)
├── golden/<id>/round-1/   reference playtest reports for CI
├── golden/<id>-repaired/ post-fix reference reports (tier 2)
├── harness/               scripts (serve, score, benchmark runner)
├── runs/                  live playtest evidence
└── results/<ts>/          scored aggregates
```

## Commands

Seed golden evidence (CI baseline):

```bash
python benchmark/harness/seed_golden.py
```

Tier 1 — score all fixtures against golden reports:

```bash
python benchmark/harness/run_benchmark.py --source golden
```

Single spike (manual playtest → score):

```bash
python benchmark/harness/serve.py --fixture memory-dead-start-button
python benchmark/harness/run_spike.py \
  --fixture memory-dead-start-button \
  --round-dir benchmark/runs/memory-dead-start-button/round-1
```

Tier 2 — autofix loop (detection + repair + goal completion):

```bash
python benchmark/harness/run_autofix_loop.py --fixture memory-dead-start-button
```

Headless agent probe (requires working CLI + browser MCP):

```bash
python benchmark/harness/agent_runner.py --agent codex --fixture memory-dead-start-button \
  --round-dir benchmark/runs/memory-dead-start-button/round-1 --dry-run
```

Unit tests:

```bash
python -m unittest discover -s benchmark/harness/tests -v
```

## Scoring semantics

`score.py` compares a frozen `report.json` to a truth manifest:

- **`must_fail`** — playtester must report `fail` (or `blocked` when `accept_blocked_as_fail` is true).
- **`must_pass`** — playtester must report `pass`.
- **`primary_fail` + `cascade_fail_if_primary`** — when the primary check fails, dependent checks count as expected failures even if the playtester marks them `blocked`.

Detection recall/precision are computed over expected vs reported failures.

Tier 2 success is separate: after applying a repair manifest, all **required** checks in `goal.json` must be `pass` in the post-fix report.

## Anti-cheat

1. Never place `benchmark/truth/` or `benchmark/golden/` in the agent workspace during live evaluation.
2. Playtester writes `report.json` from rendered behavior before reading source.
3. `validate_evidence.py` enforces artifact existence; it does not judge correctness.
4. Instrumentation findings cannot upgrade a pass — see `reference/instrumentation.md`.

## Fixture classes

| Class | Purpose |
|-------|---------|
| `control` | Working app; all required checks must pass |
| `injected` | Single intentional mutation; specific checks must fail |
| `trap` | Code looks plausible; broken via overlay, timing, or invisible blocker |

Train vs held-out splits are in `catalog.json`. Tune prompts/skills on **train** only; report held-out scores without iteration.

## Thresholds

Default gates in `catalog.json`:

- Tier 1: avg detection recall ≥ 0.85, precision ≥ 0.85, zero integrity violations
- Tier 2: autofix pass rate ≥ 0.75 across tier-2 fixtures

## Headless automation status

| CLI | Status |
|-----|--------|
| `codex exec` | Try `-c features.multi_agent_v2=false` if config.toml breaks parsing |
| `claude -p` | Requires sufficient API credits |

Until headless browser MCP is reliable, run the playtester via IDE browser tools and pipe evidence through `run_spike.py` or replace golden reports after manual runs.
