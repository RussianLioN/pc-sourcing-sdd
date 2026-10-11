# pc-sourcing-sdd
Offline pilot on the user's Mac. **Every fixture is synthetic.** No real
price, stock, protected transaction or production readiness is confirmed.

The application is installed locally in `.venv` (editable, version 0.1.0).
From `/Users/s060874gmail.com/coding/projects/pc-sourcing-sdd`:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/verify_scope.py tasks/T002.json .
.venv/bin/python scripts/check_acceptance.py
```

Rerun sourcing on the retained acceptance input into **new** output paths:

```bash
mkdir -p artifacts/repeat
.venv/bin/pc-sourcing --input artifacts/acceptance/input.json \
  --db artifacts/repeat/pilot.sqlite --report artifacts/repeat/report.md \
  --as-of 2026-10-11T10:00:00Z --run-id offline-repeat
```

Run the deterministic workflow (its output directory is artifacts/offline-workflow;
a changed snapshot needs new evidence paths):

```bash
.venv/bin/python scripts/run_workflow.py run workflows/offline.yml
```

This validates the offline collector, not a new independent Codex review or
acceptance. Actual worker workflows are `writer.yml`, `repair.yml`, `repair2.yml` and
`verifier.yml`; do not start a second writer or blindly resume a killed run.

Read `specs/001-offline/methodology.md`, `spec.md`, `plan.md`, `traceability.md`
and `docs/pilot-results.md`. Exact final receipt:
`artifacts/acceptance/manifest.json`; readable report:
`artifacts/acceptance/summary.md`; detailed audit: `report.md` alongside it.
Any code, spec, fixture/test, tracked file or commit change invalidates old
acceptance. Historical failures remain in `artifacts/`.

Application is deterministic Python/Pydantic/SQLite. Spec Kit 1.1.3 and Codex
are the separate development coordinator; no runtime LLM, repo-local MCP,
background service or scheduled loop. Dependencies/SDKs stay in `.venv/` and
`.tools/`; exact runtime and transitive pins are in both lockfiles.
Official release Spec Kit skills and two project skills are in `.agents/skills`.
Both project skills were read and behavior-tested on payment and protected
snapshot examples; no third-party plugin is necessary.

One writer at a time. Verifier's writable workspace is private /tmp scratch;
the project remains read-only to it, verified by `verify_readonly.py`.
Runner resume supports paused/failed only. Running-state crash recovery and
local live sources remain blocked. Direct Avito denial is not bypassed.
No publication, remote push, deployment, order, seller contact or new key.

Continuation policy 1.0.1 follows the user instruction to continue autonomously
to successful offline acceptance. Historical 2/2 assignments are archived,
not current stopping rules. See tasks/continuation-policy.json. Each process
retains its timeout, one writer and exclusive launch protection.
