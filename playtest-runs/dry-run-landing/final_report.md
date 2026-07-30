# Dry Run: dry-run-landing

Manual dry run of the loop's evidence contract and validator, performed
during initial implementation of this skill against the `media4agents`
landing page (`frontend-react`, `bun run dev`, `http://localhost:3001`).

## What this proves

1. **Genuine evidence passes.** Two checks (`landing-loads`,
   `media-url-example-visible`) were verified with real browser screenshots
   captured via the browser MCP, then `scripts/validate_evidence.py` exited
   `0` against `evidence/round-1/report.json`.
2. **A faked pass is rejected.** `report.json` was edited to reference a
   screenshot path that does not exist. The validator exited `1` with:
   `check 'media-url-example-visible' references evidence that does not
   exist: screenshots/02_media_url_example_DOES_NOT_EXIST.png`.
3. **A leftover instrumentation marker is rejected.** A scratch file
   containing a `PLAYTEST-TMP` marker was placed in an isolated directory
   and scanned as `--app-dir`. The validator exited `1` with: `leftover
   instrumentation marker 'PLAYTEST-TMP' found in ...\Example.tsx`.
4. **Clean rerun recovers.** After removing the scratch marker file, the
   validator exited `0` again against the unmodified, genuine report —
   confirming the contract in `reference/instrumentation.md` behaves as
   specified end to end.

## Notes

- This was a manual verification of the contract and validator, not a full
  agent-driven loop run (no Builder/Repair round was needed since both
  checks passed on the first observation).
- The scratch marker directory was created in isolation and fully removed;
  the `media4agents` product source tree was never modified.
