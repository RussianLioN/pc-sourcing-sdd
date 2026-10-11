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
Historically repair round 1 used a two-round budget. That stop was later
superseded by continuation policy 1.0.1; historical failures remain preserved.


DEF-005: fresh actual verifier at 19d3fcc0bc0f2ac9167287107623a90f0d69ae71
confirmed all 119 tests, both previous fixes and snapshot immutability, but
reproduced Python's integer-conversion limit on a valid JSON literal of 5000
digits. Decoder aborted the entire batch before rejection retention (OUT-02).
Reproducer and exact result were archived in artifacts/review-round2.
Regression covers both price and a numeric id: oversized literals must not
be silently converted into strings and accepted. Keep raw JSON unchanged,
retain valid rows and a clear rejected-row reason. Do not disable global
Python integer safety limits or change system security settings.
The historical narrow repair round 2/2 owned pipeline.py and an optional
worker test. Its subsequent blocked verdict was preserved. The old stopping
rule was later superseded by the explicit user continuation instruction.

Round 2 writer completed in 160.120s: all 136 tests, Ruff and task scope passed.
The bounded typed integer marker preserves raw tokens and rejects numeric id;
no global digit setting changed. Final common-snapshot review still decides acceptance.

DEF-006: final verifier at 2575afd2482ff817ea18d4f424f494556746263b
found an unpaired Unicode surrogate accepted in Offer.title, then failing
model_dump_json before SQLite opens. Valid neighbors and rejection were lost.
Actual CLI repro and traces are in artifacts/final-review-evidence.
The prior blocked receipt remains unchanged. User explicitly superseded the
2/2 stopping policy; current task T006 repairs the Unicode error class with
protected regression tests, preserving all product/golden expectations.

T006 actual Codex writer completed in 150.275s; 273 tests,
Ruff check/format and task scope passed. Iterative Unicode validation checks
all decoded keys/values before duplicate handling or model diagnostics. It
preserves original raw JSON, UTF-8-safe reasons and valid neighboring offers.
Evidence copied to artifacts/unicode-validation with hashes. Fresh final
independent review remains required; process success alone cannot accept.
