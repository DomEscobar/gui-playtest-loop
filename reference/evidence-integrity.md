# Evidence provenance and integrity

Hashes detect later mutation; authority boundaries prevent an implementer from
replacing both a file and its hash. Both are required for meaningful protection.

## Contract manifest

Before implementation, the trusted Orchestrator creates a manifest in a directory
the Builder cannot write. Protect at least:

- `goal.json` as label `goal`;
- `templates/goal.schema.json` as `goal-schema`;
- `templates/report.schema.json` as `report-schema`;
- `scripts/validate_evidence.py` as `validator`;
- `scripts/ux_probe.js` as `ux-probe` when UX measurement is enabled.

Example:

```bash
python scripts/seal_contract.py --manifest /trusted/run-integrity.json \
  --file goal=/app/playtest-runs/demo/goal.json \
  --file goal-schema=/skill/templates/goal.schema.json \
  --file report-schema=/skill/templates/report.schema.json \
  --file validator=/skill/scripts/validate_evidence.py \
  --file ux-probe=/skill/scripts/ux_probe.js
```

The manifest records resolved paths and SHA-256 digests. Storing it inside a
Builder-writable tree provides tamper evidence only, not tamper resistance.

## Evidence manifest

After a playtester finishes a round:

```bash
python scripts/seal_evidence.py --round-dir <round-dir> --origin live-agent
```

The helper hashes `action.log`, all report-referenced evidence, and all UX probe
artifacts. `validate_evidence.py` verifies the hashes and rejects missing coverage.

Allowed origins:

- `live-agent`: newly captured from a running app by the evaluated playtester;
- `human-live`: newly captured by a human tester;
- `replayed`: produced by rerunning an existing deterministic script;
- `synthetic-golden`: constructed reference data for testing the harness.

Only `live-agent` qualifies for standard/release claims about agent detection.
Golden data may validate the harness but must not be aggregated as live-agent recall.
