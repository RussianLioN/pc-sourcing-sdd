# Cloud handoff — pc-sourcing-sdd

This is a completed **offline pilot**, built and tested on the user's Mac.
It validates sourcing evidence for Moscow, preserves every framed input row
or explains its rejection, evaluates exact SKU/payment/eligibility, writes
SQLite atomically and emits an auditable Markdown report. It has no live
retailer adapter, background service, purchase or seller-contact function.

The collector (`src/pc_sourcing`) is deterministic Python/Pydantic/SQLite.
Spec Kit/Codex (`scripts`, `workflows`, `.agents/skills`) are separate development
tooling. No repo-local MCP or second competing SDD framework is required.

## Verified baseline and publication boundary

Accepted code/spec/test snapshot: `abf63a5d7e61dfe2d41cce7df0200aaece15cdb4`.
Product specification and JSON contracts: **1.0.0**. Continuation policy: **1.0.1**.
Aggregate spec hash: `7577553fdb648b2454529129d180807875f08f6539ed7f4760743888b0aced4e`.
Collector code hash: `65ed050e7fa5867da3d1a5da09f704a85f29c0a3f2799ed94d31fce4b5c508e8`.
Fixture hash: `971929eaa86cc06175656770ca491a429ecbb2bb47431939d24cd2a9367e2b94`.

- 273 unit/contract/property tests passed; Ruff check/format and scope gate passed.
- A fresh actual read-only Codex verifier returned `passed`, `findings=[]` at
  this exact SHA, including 162 independently generated Unicode scenarios.
- `check_acceptance.py` returned exit 0 at the accepted baseline.
- SQLite saved 20 valid and 2 rejected rows; 3 were algorithmically eligible.
  **All offers, prices and stock in that corpus are synthetic test data.**
- A real Spec Kit do-while ran the collector exactly twice, produced identical
  reports and stopped on its condition before the experiment safety cap.
- Installed CLI repeat, rejection retention, idempotency, transaction rollback
  and post-commit report recovery were checked. Numeric overflow, oversized
  integer, payment-conflict evidence and invalid-Unicode defects were found by
  real independent review and fixed with protected regression expectations.

This handoff is added **after** that acceptance as a documentation-only commit.
The collector, tests, goldens and product spec are unchanged. The accepted SHA
above remains the evidence boundary; this publication commit is not presented
as an independently accepted Linux/cloud snapshot.

`artifacts/` is gitignored. Raw worker logs, SQLite results, original manifests,
JUnit reports and `artifacts/acceptance/summary.md` exist on the original Mac,
but **are not included in a clone**. This safe compact summary preserves their
outcomes, not their bytes. `check_acceptance.py` correctly reports NOT RUN when
the receipt is absent, or STALE after a commit change. A clone/new environment
needs new evidence and fresh independent review before its own acceptance.

## Product rules and SDD method

Targets: `G5090-32SLC` (MSI RTX 5090 32G SUPRIM LIQUID **OC**, factory liquid),
`F5-6000J3036F48GX2-TZ5NR` (96 GB), Logitech G PRO X2 SUPERSTRIKE.
OC and SOC stay distinct; exact variants and analogues stay separate. Ignore
prices in the source research. A snippet is a candidate, not price/stock proof;
unknown price stays null and preorder stays outside the verified list.

For Avito under-order payment, one independently confirmed fully applicable
route suffices: platform-protected whole transaction **OR** full payment after
receipt without mandatory external advance. Unknown/conflict on one route
does not veto another suitable route. Purchase-wide mandatory external advance
or unresolved global conflict blocks the gate. Preserve `требует ручной проверки`
and reasons when neither route is confirmed; exclude from verified purchases.
Payment pass establishes neither stock nor overall purchase safety.

The section-9 cycle freezes boundaries/contracts/goldens, issues SHA/spec-bound
owned tasks, uses one writer worktree, tests, checks protected Git blobs, merges
sequentially and independently reviews the common snapshot. Defects get narrow
regressions and repairs. The user superseded the former two-round stop: continue
to required offline acceptance, changing the hypothesis when progress stalls.
Keep 600s worker / 660s supervisor deadlines and exclusive launch protection.
See `specs/001-offline/{spec,plan,methodology,decision-table,traceability}.md`.

Project skills (explicitly read and behavior-tested):
- `.agents/skills/pc-payment-audit/SKILL.md`: payment/evidence audit examples.
- `.agents/skills/pc-snapshot-check/SKILL.md`: scope, protected baselines and
  same-snapshot acceptance, including negative mutation controls.
Official Spec Kit skills are also included. Converge is optional gap/task
discovery, not a substitute for tests. Parallel fan-out is not claimed.

## Project-local setup and smoke checks

These are bootstrap instructions for a fresh checkout, **not evidence of a
completed Linux/cloud deployment**. Use existing approved environment tools;
do not copy Mac credentials. Current tool pins: Python 3.13.3, uv 0.10.2,
Pydantic 2.14.0, pytest 8.4.2, Hypothesis 6.142.1, Ruff 0.14.0,
setuptools 80.9.0; Mac SQLite runtime was 3.51.2.

```bash
uv venv --python 3.13.3 .venv
uv pip sync --python .venv/bin/python requirements.lock
uv pip install --python .venv/bin/python setuptools==80.9.0
uv pip install --python .venv/bin/python --no-deps --no-build-isolation -e .
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/quality.py --out artifacts/fresh-smoke
```

`fresh-smoke` creates input JSON, `pilot.sqlite`, `report.md`, JUnit/logs and
a quality manifest. It does not supply independent acceptance. Its toolchain
metadata currently includes original Mac pins; verify and adapt that metadata
in the target environment before treating a new manifest as authoritative.
Rerunning with changed code/spec needs fresh resource paths.

Install the separate pinned development runner only when needed:

```bash
uv venv --python 3.13.3 .tools/spec-kit-env
uv pip sync --python .tools/spec-kit-env/bin/python spec-kit.lock
```

Spec Kit is 1.1.3 at official commit
`0282d03eb6fc3091b3deaa3a855d4030dc40cd6c`. Review `docs/toolchain.md`.
**Do not dispatch workers before the host bindings below are adapted and tested.**

## Required adaptation before cloud workers

1. `scripts/codex_worker.py` has an absolute Mac/pyenv shebang. Replace it with
   a reviewed interpreter entry for the target host while preserving sandbox,
   argument validation, timeouts and read-only verifier isolation.
2. `scripts/codex-pin.json` pins the Homebrew/Caskroom Darwin binary path and
   SHA-256, Codex 0.157.1/model gpt-6-astra. Verify the actual target executable,
   version, hash, existing authorization and permissions; do not disable pinning.
3. Historical task JSON `coordinator_root`, workflow prompts/shell commands and
   source manifests contain `/Users/...` paths. Preserve historical assignments;
   issue new target-host tasks/configuration rather than rewriting old history.
4. `.venv`, `.tools`, worktrees, run states and acceptance artifacts are excluded
   from Git. Recreate dependencies/resources; audit transferred evidence separately.
5. `fcntl` locks and process-group signals require Unix semantics; Linux behavior
   and SQLite version must actually be checked. Shell steps are not a sandbox.
6. Source-linked report times and temporary/DB/cache paths must remain explicit
   and isolated. Build a fresh target receipt at one SHA/spec/test corpus after
   integration and a real independent verifier; no mocked review acceptance.

No cloud environment was created during publication. Linux/cloud readiness,
persistent hosting and execution from a phone/Slack have not been validated.

## Remaining access and recovery limits

Local Tavily CLI/module/authorization was unavailable; a parent-chat connector
does not authorize local Codex. Live primary sources need a lawful supported
route and bounded requests/costs. No new key, subscription or persistent access
was created. Indexed links cannot confirm price, stock or payment protection.
Direct Avito access was denied by environment policy: do not retry via another
browser, IP, proxy, hidden API, identity or intermediary to bypass the denial.

Spec Kit 1.1.3 resumes paused/failed runs. A killed coordinator can leave
`running`, which resume rejects; this is a demonstrated tooling limitation,
not missing authorization. Inspect processes/evidence and issue a new audited
task. Do not edit state to manufacture recovery. Paused/failed resume and
exclusive duplicate-resume rejection were tested; a real Codex process death
was recorded separately from synthetic orchestration probes.

Not run: two simultaneous writers/parallel fan-out, Converge command, actual
worker retry after deliberate death, 600s timeout expiry, live primary-source
smoke, 24/7 deployment. They are not claimed by the accepted offline scope.

## Publication review

The user explicitly authorized a public repository and full existing history.
All 20 pre-publication commits / 158 unique blobs, commit metadata, both source
DOCX packages (including relationships/custom metadata) and thumbnails were
reviewed before publication. No credential or unrelated sensitive personal
data was identified. Blank thumbnails contain only dimensions/resolution;
ordinary authorship/recipient/project names, local paths and Library resource
IDs remain under the explicit public-history authorization.

The audit is static pattern inspection plus manual document/metadata review,
not a guarantee or full dependency vulnerability audit. Local credentials,
venvs, worktrees and raw ignored logs are excluded. See the compact
`docs/publication-security-summary.json` and `THIRD_PARTY_NOTICES.md`.
