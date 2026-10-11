# Cloud continuation handoff — WIP

Continue from branch `checkpoint/cloud-portability-20261011` in
https://github.com/RussianLioN/pc-sourcing-sdd. This preparation is WIP, not
independently accepted as main and not verified on Linux or in a cloud task.
Use [cloud-setup.md](cloud-setup.md) and specs/002-portability/{spec,plan}.md.

## Preserved product baseline

Accepted offline snapshot: abf63a5d7e61dfe2d41cce7df0200aaece15cdb4.
Pre-portability publication: eed6bc7b23b2561df7f3d57f4a8a0e24a17143ef.
Product spec/contracts: 1.0.0; continuation policy: 1.0.1.
Original collector, original tests, fixtures and product spec are unchanged.
The accepted baseline had 273 tests, actual independent read-only review and
162 independent Unicode scenarios, with checker exit 0 at that exact SHA.
Synthetic SQLite saved 20 valid and 2 rejected rows; 3 were eligible.
All offers, prices and stock in that corpus are synthetic test data.

Collector hash: 65ed050e7fa5867da3d1a5da09f704a85f29c0a3f2799ed94d31fce4b5c508e8.
Original aggregate spec hash: 7577553fdb648b2454529129d180807875f08f6539ed7f4760743888b0aced4e.
Fixture hash: 971929eaa86cc06175656770ca491a429ecbb2bb47431939d24cd2a9367e2b94.

Raw receipts, SQLite output and worker logs are excluded from Git. They are
not needed to start T007 in a fresh checkout. Historical acceptance is not a
new-host receipt; collect new evidence at one new SHA. Do not fabricate resume.

## Prepared portability change

T007 base contract commit: af908345aca120c1f6d0f5aed05ab6e38bb8bd5b.
Its assignment names owned/protected files and pins both specifications.
One writer worktree was used. A relative coordinator root is anchored to the
coordinator script repository, not a shell working directory.

Prepared components: bounded project-local bootstrap, explicit runtime/build
locks, observed tool metadata, platform Codex hash/version pins, a root-relative
interpreter launcher and a current review workflow. Original sandbox flags,
approval policy, one-thread limit, worker/coordinator deadlines and exclusive
lock remain. Prompts are separated from CLI options. Temporary-root verifier
checkouts fail closed, and actual project-write denial must be demonstrated.

Darwin arm64 and Linux x86_64 official Codex 0.157.1 archives were checked
against release metadata and extracted binary hashes. The Linux binary was
not executed. Spec Kit 1.1.3 remains pinned to official commit
0282d03eb6fc3091b3deaa3a855d4030dc40cd6c; hatchling/build dependencies are locked.

Prior executor-reported Mac checks (not independently verified by this checkpoint): 297 tests passed (273 original + 24 new),
Ruff check/format and T007 scope passed; a fresh worktree-local bootstrap of
runtime, runner and Codex passed. These are preparation checks, not independent
acceptance of this branch. Old 544 evidence artifacts were preserved unchanged.

NOT RUN: independent portability review, relocated-clone repeat, current
runner workflow exercise and actual Linux/cloud runtime verification.

## First cloud continuation

1. Select/check out `checkpoint/cloud-portability-20261011`, preserve the base contract
   commits, then read AGENTS.md, T007 and pc-cloud-setup SKILL.md.
2. From the checkout root, run `python3 scripts/bootstrap.py`, then
   `.venv/bin/python scripts/bootstrap.py --check`.
3. Run `.venv/bin/python scripts/quality.py --out artifacts/fresh-cloud-check`.
   Record actual host/tool versions, commands/exits and fresh SQLite/report.
4. Resolve narrow in-scope failures; protect original golden/model/test bytes.
   Run independent review at one integrated SHA before acceptance or main merge.

Use current reviewed workflows. Old T001–T006 assignments remain historical.
The offline collector needs no external API. Do not transfer local profiles,
environment directories, secrets, caches or raw logs. Do not weaken permissions
to obtain a green worker result. Parent coordinates cloud environment selection.

No live adapters, seller contacts, orders or background services are added.
Direct Avito access restrictions remain binding. Payment pass establishes
neither stock nor overall purchase safety; the original product gates remain.
