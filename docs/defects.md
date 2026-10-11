# Observed defects and bounded repair
No seeded fault or mock verdict was used.

DEF-001: root contract tests were import-sorted before evaluate/pipeline modules
existed. Ruff changed first-party classification after implementation and
reported 3 I001 failures. Coordinator set known-first-party and reordered
imports only. Assertions/golden values unchanged; lint now passes.

Initial independent direct read-only verifier: blocked before pytest
collection by lack of writable temp. Fixed by isolated scratch workspace;
project remains read-only and a negative write probe confirmed enforcement.

Independent verifier at 167d4acfb181189038b2ec0d95ff4d8c9d2ab966:
93 tests passed but additional actual reproducers found:
- DEF-002: valid JSON numeric overflow `1e400` became infinity and aborted
  the whole batch before retaining its rejected row (OUT-02).
- DEF-003: current evidence of global payment conflict was ignored if
  normalized Offer field was false, permitting a payment gate (PAY-03).
- DEF-004: T001 worker scope task was incorrectly reused as common-snapshot
  scope check; coordinator changes made it fail. Separate common-snapshot
  task fixes scope attribution; original test behavior is AST-checked against
  baseline, ignoring only top-level import ordering.

Regressions: tests/test_review_regressions.py, fixed expectations owned by
coordinator. Initial failures retained in artifacts/repair-regressions-before.log.
Actual repair writer: task T003, fresh worktree, only evaluate/pipeline and
optional repair-worker test; cannot alter goldens/contracts/regressions.
Domain repair round 1 of at most 2. Recheck full integrated snapshot and a
fresh independent verifier. Stop if no new hypothesis or budget exhausted.
