# pc-sourcing-sdd
Offline pilot on the user's Mac. Synthetic records demonstrate requirements;
they are not real prices, stock or payment confirmations.

Quick start (project local tools):
```
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pc_sourcing.pipeline --help
.tools/spec-kit-env/bin/specify workflow run workflows/offline.yml --json
```
For module invocation: `PYTHONPATH=src` or install the local package using
`uv pip install --python .venv/bin/python --no-deps -e .`.
Read `specs/001-offline/methodology.md`, `spec.md`, `plan.md`, and the run
manifest in `artifacts/acceptance/manifest.json`. Snapshot acceptance is
checked by `.venv/bin/python scripts/check_acceptance.py`.
Application is deterministic. Spec Kit and Codex are the separate development
coordinator, never required to run sourcing. No repo-local MCP is required.
Local dependencies/SDKs/tools stay in `.venv/` and `.tools/`. Known official
Spec Kit Codex skills are installed in `.agents/skills`; no third-party plugin
is necessary. Read project payment and snapshot skills before their use.
