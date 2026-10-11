---
name: pc-cloud-setup
description: Reproduce and verify this project's pinned offline environment without importing Mac authorization or changing cloud security settings.
---
Read specs/002-portability/spec.md, docs/cloud-setup.md and the assigned task.
Work from the checked-out repository root. Keep collector and development
workers separate: offline application setup does not need Codex login.

Example A — fresh checkout with spaces or another host path:
run `python3 scripts/bootstrap.py`, then
`.venv/bin/python scripts/bootstrap.py --check` and
`.venv/bin/python scripts/quality.py --out artifacts/fresh-host-check`.
Expect exact pinned packages, positive exits recorded, synthetic SQLite/report
and actual observed OS/Python/SQLite. A Mac result proves only that Mac run.
The setup command needs an existing Python 3.11+; managed Python/cache and
all dependencies stay project-local. Never overwrite an incompatible .venv.

Example B — workers unavailable or an executable is wrong:
inspect `.venv/bin/python scripts/toolchain.py --json`.
A missing/mismatched Codex is blocked, never silently treated as a verified
worker. The optional install is `python3 scripts/bootstrap.py --with-runner
--with-codex`; it pins official source/archive/binary and does not create login.
Run `.venv/bin/python scripts/bootstrap.py --check --with-runner --with-codex`.
Wrong hash must block before execution; use tests/test_portability.py to
exercise that negative control. These unit fakes are not multi-agent evidence.

Use current task scope for integration; old T001–T006/workflows are historical.
Read-only verifier must pass verify_readonly.py with scratch writable and
project write denied. A checkout under temporary writable roots cannot safely
use that verifier mode; block and issue an approved relocation task.
No new credentials, OAuth, proxy, security/network changes or paid obligation.
Do not copy Mac authorization. Record failed/blocked/not_run distinctly;
preserve old artifacts/acceptance and never report Linux/cloud ready from Mac.
