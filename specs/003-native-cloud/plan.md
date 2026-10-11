# Native cloud acceptance plan 1.0.0

1. Freeze ADR/spec/profile/T008 in a contract commit, retaining every baseline
   tracked file unchanged. Use the separately supplied full contract SHA as trust
   anchor; do not infer approval from a worker-generated current hash.
2. One writer adds a root-relative collect/finalize/check tool, safe handoff and
   negative tests. It runs actual pinned bootstrap/quality/pipeline/repeat on
   Linux, records clean states at the published code SHA, and returns evidence.
3. Parent launches a separate real cloud review at that exact SHA/contract.
   Reviewer independently runs all checks in a separate checkout and examines
   code/contract. Review JSON binds both record hashes and its actual task ID.
4. Findings return to the writer; narrow repairs require new commits and complete
   new review. Preserve failed records. No artificial repair-round cap.
5. Parent verifies task provenance outside the local checker, then finalizes a
   separate ignored T008 manifest. Check it against current HEAD before use.
   Any change needs fresh evidence; do not put a self-referential acceptance
   receipt in a commit or transfer old approval to a documentation commit.

Required checks: app bootstrap --check; quality (pytest, Ruff check/format,
synthetic pipeline); T008 scope; installed pipeline repeat with identical
fingerprint and identical database/report. Both roles run them. Fresh relocated
bootstrap/repeat with spaces remains a writer validation during implementation.
No nested workflow, OS-denial probe or historical do-while receipt is required
by this new profile. Their omission never passes T007 retroactively.
