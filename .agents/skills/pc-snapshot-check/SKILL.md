---
name: pc-snapshot-check
description: Verify a pc-sourcing-sdd task diff and common snapshot using the coordinator baseline, scoped ownership and recorded tests.
---
Read the task JSON and `specs/001-offline/plan.md`. Check its base commit,
spec revision, dependencies and owned files. Compare golden, contract and
acceptance-test files against base Git blobs in the coordinator checkout,
outside the worker's writable cwd. Reject scope or protected-file changes;
a worker-written digest is not approval. Run `scripts/verify_scope.py`.
Run unit/contract/property suites on the integrated commit using a unique
temporary DB. Compare the same Evaluation in DB, report and verified list.
Record spec/fixture/test hashes, exact commit, commands and exits. Read-only
reviewer can report a bug and a reproducer but cannot change expectations.
If any required check is failed/blocked/not run, retain an unaccepted status.
Use `scripts/check_acceptance.py` after acceptance; any snapshot change must
invalidate old evidence. Running-state crash recovery is blocked, not resumed.
