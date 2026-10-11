# Portability plan — one writer and separate verifier

1. Freeze this additive change spec; preserve product spec 1.0.0/goldens and
accepted baseline. Capture remote HEAD, clean state and old artifact hashes.
2. Bind a coordinator-owned T007 assignment to the contract commit; implement
in one isolated worktree. No second writer or mock multi-agent claim.
3. Add a stdlib bootstrap and toolchain inspector. Default installation is
offline application/test dependencies. Spec Kit/Codex are explicit optional
development tools, with official pins and no credentials setup.
4. Replace active Mac interpreter/binary bindings with root-relative launcher
and platform binary allowlist; keep sandbox and time/resource controls.
Historical assignments/workflows remain traceable but non-dispatchable.
5. Add focused regressions for wrong executable/pin/version/host, unsafe verifier
root, task anchoring, metadata and reproducible installation. Keep original
tests/source/goldens byte-identical. Run fresh relocated checkout (spaces),
repeat bootstrap, complete offline quality, actual pinned runner.
6. Integrate sequentially, then actual independent read-only Codex review
at the common SHA. Narrow repairs if needed; preserve failures. No fake
Linux, cloud environment or auth claims.
7. Publish separate spec/tooling/result commits to authorized existing public
origin without force, after checking remote unchanged and scanning additions.
8. Supply the environment ID/URL only when creation/publishing actually
succeeds; otherwise exact minimal UI/access blocker and prepared commands.

Per-process timeouts and exclusive locks remain. Each install/download has
bounded time and resource limits. New host evidence goes to unique ignored
artifacts, never overwrites artifacts/acceptance or old worker receipts.
