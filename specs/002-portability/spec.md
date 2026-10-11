# Cloud preparation — change specification 1.0.0

Authority: explicit user instruction on 2026-10-11 to prepare the published
project for a real Codex cloud environment and publish reviewed portability
changes. Starting publication SHA: eed6bc7b23b2561df7f3d57f4a8a0e24a17143ef.
The accepted offline product snapshot remains
abf63a5d7e61dfe2d41cce7df0200aaece15cdb4 with its original artifacts.

Goal: reproduce the existing offline collector/tooling in a fresh checkout
without a Mac username, Homebrew path or user-global configuration dependency.
Target host families: Darwin arm64 and Linux x86_64. Other worker platforms
fail closed until reviewed. Linux runtime/cloud verification is a separate
actual-host gate, never inferred from a simulated platform or Mac tests.

Non-goals: live adapters/Avito, purchasing, new product rules, cloud credential
creation, OAuth grants, changed security/network policy, paid obligations,
background services, a second writer or rewriting old acceptance/history.

| ID | Requirement | Verification |
|---|---|---|
| PORT-01 | project-local bootstrap from any checkout, including spaces; pinned Python/uv/runtime/build dependencies, no global writes | fresh relocated checkout install + repeat + offline quality |
| PORT-02 | discover actual Codex by host; verify official binary SHA and exact version before execution; optional project-local official installation | official release archive/member verification + wrong-pin/no-execution regression |
| PORT-03 | launcher selects checkout .venv interpreter without PATH-dependent Python or Mac shebang | executable launcher regression + real runner |
| PORT-04 | retain ignore-user-config/ephemeral/workspace sandbox/never approvals/one thread/600s worker/660s supervisor/exclusive lock/extra-arg rejection | negative controls and actual read-only verifier |
| PORT-05 | verifier project outside all known temporary writable roots; real negative project-write probe required | unsafe-root regression + actual probe |
| PORT-06 | Spec Kit exact package version and official source commit verified before coordinator launch; old absolute-path assignments/workflows are historical and cannot launch as current work | runner identity and historical-workflow rejection |
| PORT-07 | new task binds base SHA, both specs, file ownership and protected files; relative coordinator root is anchored to coordinator script, never shell cwd | scope + relocated task-root tests |
| PORT-08 | quality records observed OS/Python/SQLite/packages/executables/versions with passed/blocked/not_run, not fabricated constants | metadata regression + real fresh quality manifest |
| PORT-09 | preserve src, original tests, golden/contracts/product spec and all old acceptance evidence | coordinator Git blob guard + original artifact hashes |
| PORT-10 | independent actual Codex read-only review at one integrated SHA; publish reviewed commits without force | saved real review + remote SHA/history verification |

Only normal environment creation using existing access is authorized.
If the UI asks for login/new OAuth/token/access/security/billing, record the
specific needed action and continue independent local work. A supported UI
capability failure is distinct from missing account authorization. Never
copy Mac credentials to a new environment. Parent coordinates the first
cloud task after an environment is actually published.
