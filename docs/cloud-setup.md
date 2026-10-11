# Current portable setup — offline application and optional workers

**WIP for cloud continuation**, on `feature/cloud-portability`; not integrated
or accepted as main. Linux execution, relocated-clone repeat and runner launch
were performed on 2026-10-11; independent review remains blocked. See the exact
snapshot and fresh evidence below. Retain WIP until independent acceptance.

## Actual cloud checkpoint — 2026-10-11

Executed snapshot: `879ce3342c807936bc00509d9374869aad7d03d3`.
Observed host: Linux x86_64, Python 3.13.3, SQLite 3.47.1. Mac was not used.
Aggregate spec hash: `caaa2c903ddd68fbf76623cd7dec806bda563d2a4c4490fdfde7eb780e6b647a`.
Product code hash: `65ed050e7fa5867da3d1a5da09f704a85f29c0a3f2799ed94d31fce4b5c508e8`.
Fixture hash: `971929eaa86cc06175656770ca491a429ecbb2bb47431939d24cd2a9367e2b94`.
These are fresh Linux observations, not imported Mac receipts.

| Command / check | Exit / observed result |
|---|---|
| `python3 scripts/bootstrap.py --with-runner --with-codex` | 0; pinned application, Spec Kit and official Linux Codex installed locally |
| `.venv/bin/python scripts/bootstrap.py --check --with-runner --with-codex` | 0; Python/packages/source commit/binary hash verified |
| `.venv/bin/python scripts/quality.py --out artifacts/portability/linux-first` | 0; 297 tests, Ruff check/format and synthetic pipeline passed |
| `.venv/bin/python scripts/verify_scope.py tasks/T007.json .` | 0; protected baseline preserved |
| Fresh clone at `/workspace/pc portability relocated`: bootstrap, check, quality, repeat bootstrap, scope | all 0; 297 tests and synthetic pipeline passed with spaces in checkout path |
| Installed pipeline repeat with original as-of/run-id | 0; one run, 20 valid, 2 rejected, 3 eligible synthetic rows |
| Repeat with a different as-of and the same run-id | 1; expected fingerprint rejection, original data preserved |
| `PC_WORKER_MODE=verifier .venv/bin/python scripts/run_workflow.py run workflows/portability-verifier.yml` | 1; Spec Kit run `443b7821` failed before model review |

Fresh local evidence is gitignored: `artifacts/portability/linux-first/`,
relocated clone `artifacts/portability/relocated-linux/`, and
`artifacts/workers/verifier-1791727587899648117/`. Raw logs and databases are
not published. No fresh acceptance receipt or independent passed verdict exists.
Bootstrap's `cloud_runtime: not_run` describes its installation-only scope;
the separate quality manifest records the actually observed Linux runtime.

The verifier binary matched official Codex 0.157.1 SHA-256
`3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970`.
Spec Kit was 1.1.3 at `0282d03eb6fc3091b3deaa3a855d4030dc40cd6c`.
Nested Codex failed initialization with `Read-only file system (os error 30)`
under the environment-managed `CODEX_HOME`, before the required project-write
denial probe or any independent review. Authorization was therefore not tested.
No permissions, credentials, security/network policy or persistent access were
changed to work around this failure. T007 is **unaccepted**.

Follow-up diagnosis used file-only `strace` and the official Codex 0.157.1
release source, commit `36650394c5b38c2990ccf2a3457165ca3e9d9726`.
Actual rejected operations were `chmod` on `$CODEX_HOME/tmp/arg0` and writable
opens of `$CODEX_HOME/state_5.sqlite` and `$CODEX_HOME/installation_id`.
Supported strict-config overrides `sqlite_home` and `log_dir` successfully
created SQLite state in an already permitted project artifact directory,
without changing `CODEX_HOME` or touching credentials. Initialization still
failed with exit 1 on `installation_id`. Merely relocating SQLite/logs is
therefore insufficient. No file contents from auth were traced or published.

The release's `core/src/installation_id.rs` opens that file read/write/create,
locks it and may set its mode even for an existing identifier;
`app-server/src/in_process.rs` unconditionally calls it during initialization.
No alternate installation-id path is exposed in the release config schema.
The helper alias path is likewise tied to `CODEX_HOME` in `arg0/src/lib.rs`.
These failures occur in the outer cloud filesystem sandbox, before the nested
verifier can execute its own project-write denial probe. `--ephemeral` and
`--ignore-user-config` do not remove these runtime writes.

Minimal operator action, requiring separate confirmation: provide the current
CLI a writable service file at `/run/codex-environment/codex-home/installation_id`
(including its lock/mode operations) and writable helper directory
`/run/codex-environment/codex-home/tmp/arg0`, while keeping `auth.json` read-only
and all project verifier permissions unchanged. SQLite/logs can use private
already-permitted scratch paths through the documented config overrides.
This is a service-state filesystem permission change, not a request for a new
key/login. Authorization and further runtime requirements remain untested;
do not promise this alone completes review. No such change was made here.
Do not copy Mac credentials or bypass sandboxing. Then run a new reviewed
workflow at exact current HEAD and retain the failed runs.

PORT-10 requires an independent actual Codex read-only review at one integrated
SHA; it does not explicitly require nesting. A separate cloud executor can
provide additional independent review only after proving project-write denial,
exact SHA, required tests/scope, and applicable isolation/deadlines. That review
alone does not close PORT-03/04/05 launcher and actual sandbox/probe checks or
T007's combined `actual pinned Spec Kit runner + independent read-only Codex
review` command. The current implementation connects those through the pinned
workflow; retain the outstanding runtime gates unless equivalent evidence is
independently demonstrated without weakening their requirements.

From Slack or a phone, send the cloud task: “Continue T007 in
RussianLioN/pc-sourcing-sdd, feature/cloud-portability. Read docs/cloud-setup.md;
check remote SHA and local changes, preserve protected files, use fresh evidence
paths, resolve only the supported nested verifier blocker, and keep one writer.”
This is a task handoff, not a tested Slack command integration or persistent
service. Existing offline bootstrap/quality can be run without model credentials.

This additive stage implements specs/002-portability/spec.md. The accepted
product snapshot remains abf63a5d7e61dfe2d41cce7df0200aaece15cdb4; original
source, product spec, contracts/goldens and original tests remain protected.
Old receipts remain historical and are not overwritten or accepted at a new SHA.

## Reproduce the application/test environment

From any checkout root, with an existing Python 3.11+:

```sh
python3 scripts/bootstrap.py
.venv/bin/python scripts/bootstrap.py --check
.venv/bin/python scripts/quality.py --out artifacts/fresh-host-check
```

Bootstrap selects pinned uv 0.10.2 (existing verified version or local
.tools/bootstrap-env), then Python 3.13.3, requirements.lock and
requirements-build.lock (setuptools 80.9.0), installing the project editable
without an unpinned isolated build. Locks, not source research prices, govern
dependencies. Application dependencies do not require OpenAI/Tavily credentials.
Installer resources/caches/managed Python remain inside the checkout. Unknown
symlink destinations and incompatible existing environments block safely.
Repetition is supported; receipts and logs get unique ignored artifact paths.
Each subprocess is bounded; bootstrap has a 480s total budget and does not
change global configuration. Existing managed network/proxy policy is retained.

Check runs are read-only. Quality runs all unit/contract/property tests, Ruff,
and the synthetic SQLite/report vertical. It records actual runtime/platform
and optional tool status, rather than claiming a tool exists from a constant.
Use new artifact locations for changed snapshots; old evidence stays unchanged.

## Optional pinned development runner and workers

```sh
python3 scripts/bootstrap.py --with-runner --with-codex
.venv/bin/python scripts/bootstrap.py --check --with-runner --with-codex
.venv/bin/python scripts/toolchain.py --json
```

Spec Kit 1.1.3 is pinned to official commit
0282d03eb6fc3091b3deaa3a855d4030dc40cd6c in spec-kit.lock. Its hatchling
build dependencies are separately locked in spec-kit-build.lock and installed
before a build with isolation disabled; installation identity checks require
the exact package version, official Git URL and commit.

Codex 0.157.1/model gpt-6-astra has official release pins for Darwin arm64 and
Linux x86_64. Archives and extracted binary hashes were independently checked
against official release metadata; Linux binaries were not executed on Mac.
The optional installer verifies both hashes and extracts only the expected
regular member. It installs .tools/codex/codex and never creates credentials.
Without local installation, discovery uses explicit PC_CODEX_EXECUTABLE then
PATH, always verifying the host binary hash before its exact version probe.
A wrong executable never falls through to a more permissive worker.
Sources: [Codex release](https://github.com/openai/codex/releases/tag/rust-v0.157.1),
[Spec Kit release](https://github.com/github/spec-kit/releases/tag/v1.1.3),
[uv release](https://github.com/astral-sh/uv/releases/tag/0.10.2).

The tracked scripts/codex-worker shell launcher computes its checkout root
and execs that checkout's .venv interpreter; it requires no Mac shebang.
Workers still ignore user config, are ephemeral, use explicit workspace-write,
never approvals, one thread and 600s wall limit. CLI option parsing ends
before the prompt. Coordinator keeps its 660s limit and exclusive lock.
Verifier uses private scratch and first tests actual project-write denial.
Projects inside temporary writable roots are rejected for verifier mode.
Shell workflow steps themselves are not a sandbox.

Current reviewed workflows are explicitly allowlisted. T001–T006 and their
writer/repair/verifier workflows retain original historical assignments and
paths but cannot be dispatched as current work. Bind a new task to a new SHA
and reviewed workflow before future writes. T007 uses a coordinator-script
anchored relative root and pins both product and portability specifications.
Current review command (only with lawful existing worker authorization):

```sh
PC_WORKER_MODE=verifier .venv/bin/python scripts/run_workflow.py run workflows/portability-verifier.yml
```

Read .agents/skills/pc-cloud-setup/SKILL.md and pc-snapshot-check/SKILL.md.
Cloud task execution does not imply a nested Codex CLI has authorization or
sandbox support. Keep unavailable nested workers blocked, never copy a Mac
profile/key or weaken the wrapper. Pause/failed resume stays bounded;
running crash states are not edited to manufacture recovery.

## Historical environment creation handoff

Current official [Cloud environments guide](https://learn.chatgpt.com/docs/environments/cloud-environments)
uses Create environment, repository selection, Get started, setup review and
Publish. The current environment builder can infer repository setup; point it
at the commands above. The older setup-script flow is a separate legacy route.
Keep existing security/network settings and access defaults. No live adapter,
service startup, secret, new OAuth or paid obligation is required by this app.

The requested creation URL is https://chatgpt.com/cloud-environments/new.
No environment was created during the earlier Mac preparation: the executor could
navigate but could not inspect/control the page through its supported UI
capabilities. Parent coordinates the remaining environment-creation step.
At that earlier stage no Linux/cloud result was claimed; publish only after
its setup is reviewed. Do not change security/network policy to finish setup.

Live primary-source authorization, direct Avito denial and missing local
Tavily access remain separate from this preparation. No alternate access,
orders, seller contact or persistent service is added.
