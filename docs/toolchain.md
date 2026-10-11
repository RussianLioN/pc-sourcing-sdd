# Toolchain evidence
Spec Kit 1.1.3 installed from official release commit
0282d03eb6fc3091b3deaa3a855d4030dc40cd6c in `.tools/spec-kit-env`.
Sources checked at this tag, not main:
https://github.com/github/spec-kit/releases/tag/v1.1.3
https://github.com/github/spec-kit/blob/v1.1.3/docs/reference/workflows.md
https://github.com/github/spec-kit/blob/v1.1.3/src/specify_cli/integrations/codex/__init__.py
https://github.com/github/spec-kit/blob/v1.1.3/src/specify_cli/integrations/base.py

Installed runner supports prompt/shell/gate/fan-out/fan-in/loops; no second
writer or arbitrary third-party workflow is installed here. Only reviewed
local YAML. No repo-local MCP. Core Spec Kit dependency mcp is transitive,
not a started MCP server. Integration validates args but accepts executable
and extra args from environment, so project wrapper rejects additional args
and pins the actual Codex binary/hash. Streaming subprocess has no built-in
timeout; project supervisor applies one. Codex uses existing ChatGPT login,
--ignore-user-config, explicit workspace-write/read-only, never approval;
no bypass. User global config remains unchanged.

Python 3.13.3 already installed; uv 0.10.2 and Codex CLI 0.157.1 reused.
Pydantic 2.14.0, pytest 8.4.2, Hypothesis 6.142.1 and Ruff 0.14.0 installed
inside `.venv`. `requirements.lock` and `spec-kit.lock` pin transitive versions.
Build backend setuptools 80.9.0 only needed for editable install.
SQLite is Python stdlib; exact runtime version recorded in manifest.

Official references:
https://pydantic.dev/docs/validation/latest/concepts/models/
https://docs.pytest.org/en/stable/how-to/tmp_path.html
https://hypothesis.readthedocs.io/en/latest/settings.html
https://docs.astral.sh/ruff/configuration/
https://docs.python.org/3.13/library/sqlite3.html

Project skills are operational instructions with execution examples, not role
labels. Both are explicitly read by writer and verifier and behavior tested
on the payment corpus and protected-snapshot rejection probes. Official
Spec Kit skills bundled with release are installed repo-locally and relevant
constitution/specify/plan/tasks/implement/converge files explicitly read.
No new third-party plugin, API key, subscription or permanent authorization.
