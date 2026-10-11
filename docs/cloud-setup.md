# Current portable setup — offline application and optional workers

**WIP for cloud continuation**, on `feature/cloud-portability`; not integrated
or accepted as main. On Mac, the current changes passed 297 tests, Ruff/scope
and a real fresh worktree bootstrap including pinned runner/Codex. Independent
review, relocated-clone repeat, new runner execution and actual Linux/cloud
verification are still NOT RUN at this handoff; retain WIP until those gates.

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

## Supported cloud environment route and actual blocker

Current official [Cloud environments guide](https://learn.chatgpt.com/docs/environments/cloud-environments)
uses Create environment, repository selection, Get started, setup review and
Publish. The current environment builder can infer repository setup; point it
at the commands above. The older setup-script flow is a separate legacy route.
Keep existing security/network settings and access defaults. No live adapter,
service startup, secret, new OAuth or paid obligation is required by this app.

The requested creation URL is https://chatgpt.com/cloud-environments/new.
No environment was created during this stage: the available executor could
navigate but could not inspect/control the page through its supported UI
capabilities. Parent coordinates the remaining environment-creation step.
No actual Linux/cloud result is claimed; publish the environment only after
its setup is reviewed. Do not change security/network policy to finish setup.

Live primary-source authorization, direct Avito denial and missing local
Tavily access remain separate from this preparation. No alternate access,
orders, seller contact or persistent service is added.
