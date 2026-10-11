---
name: pc-snapshot-check
description: Verify a pc-sourcing-sdd task diff and common snapshot using the coordinator baseline, scoped ownership and recorded tests.
---
Read the task JSON and `specs/001-offline/plan.md`. Check its base commit,
spec revision, dependencies and owned files. Compare golden, contract and
acceptance-test files against base Git blobs in the coordinator checkout,
outside the worker's writable cwd. Reject scope or protected-file changes;
a worker-written digest is not approval. Run `scripts/verify_scope.py tasks/T007.json .` for the current portability snapshot.
T002 is the historical offline acceptance scope and must not approve new tooling.
T007 pins both specs and anchors a relative coordinator root to the script repository.
T001/T003 are historical writer-only scopes; T006 is the Unicode writer scope; apply them only to their
assigned worktrees. Integration includes separately owned coordinator files.
Original golden/schema files are byte-protected; original test behavior
is AST-checked, ignoring only coordinator-approved import ordering.
Run unit/contract/property suites on the integrated commit using a unique
temporary DB. Compare the same Evaluation in DB, report and verified list.
Record spec/fixture/test hashes, exact commit, commands and exits. Read-only
reviewer can report a bug and a reproducer but cannot change expectations.
If any required check is failed/blocked/not run, retain an unaccepted status.
Use `scripts/check_acceptance.py` after acceptance; any snapshot change must
invalidate old evidence. Running-state crash recovery is blocked, not resumed.

Current continuation policy is tasks/continuation-policy.json. The user
superseded the two-round stop only. For constitution, T002 pins the authorized
policy revision to a separate coordinator Git blob via protected_baselines;
all product/golden/schema and original test baselines remain unchanged.
Run tests/test_policy_gate.py to prove later policy/golden drift is rejected.
