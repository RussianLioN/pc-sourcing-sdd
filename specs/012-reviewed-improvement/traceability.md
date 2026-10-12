# Traceability: Agreed Input to Acceptance

The proposed acceptance mappings below now have executable inactive tests. Actual independent implementation/result review and real activation remain pending. Draft authoring checks do not substitute for those gates. Parent sourcing requirements, original oracle and accepted source stops/budgets remain immutable.

| Agreed requirement | Spec | Cases | Tasks | Planned evidence |
| --- | --- | --- | --- | --- |
| 1: verified lesson retrieval and quarantine | FR-001, SC-001 | AC-02 | T005–T009 | test_reviewed_lessons: lifecycle/active-only |
| Clarification 1: external independent authority, exact bindings | FR-002, SC-001 | AC-08 | T006–T007, T020, T028 | local flags/different version/authority negatives + actual coordinator verdict |
| Clarification 2: active text still untrusted | FR-003, SC-006 | AC-03 | T008–T012 | otherwise-valid-hash hostile text; budgets/stops/oracle/exec unchanged |
| Clarification 3: actual consumer with new outcome | FR-004, SC-002 | AC-01, AC-04 | T010–T012 | explicit invocation -> active lesson -> applicability -> new test/decision -> independent resulting-change review |
| 2: property variation and shrinking | FR-005, SC-003 | AC-05 | T013 | seed/shrink/order/conflict/duplicate/evidence monotonicity |
| Clarification 4: semantic imported mutation, relevant assertion | FR-006, SC-003 | AC-06, AC-07 | T014–T017 | baseline/import-source/counterfactual/assertion receipts, all invalid categories retained |
| Clarification 5: atomic version comparison/read/rollback | FR-007, SC-004 | AC-09, AC-10 | T018–T020 | stale compare/concurrent reader/interruption/rollback/audit/source invariants |
| 6: Spec Kit from input through all phases | FR-008 | AC-14 | T024, T026, T028 | actual specify/clarify/plan/tasks authoring receipts now; implementation/native/review later |
| Honest metrics and frozen cohorts | FR-009, SC-005 | AC-12, AC-13 | T003, T022–T025 | taxonomy/denominator/independent rounds/censored and unknown controls |
| Cloud-only, one writer, no new access, protected product | FR-010, SC-006 | AC-03, AC-10 | T001, T004, T017, T026–T027 | scope/protected-source inventories/no source HTTP |
| Full meaningful checks and exact review | FR-011, SC-001/006 | AC-01–AC-14 | T026–T028 | exact common snapshot + fresh consumer + external actual review |
| Accepted T016/start first, disabled activation, bounded fallback | FR-012 | AC-11 | T001, T020–T021, T028 | independent T016 verdict/start and cutover/blocked-learning-off receipt |

## Sourcing Requirements Retained

SKU-01 (OC/SOC distinction, MSI factory liquid), EVI-01/02 (field evidence and snippets candidate-only), PRICE-01 (unknown null, source-spec prices ignored), STOCK-01 (preorder), PAY-01/02/03 (independent OR, global/route conflict, advances), OUT-01/02/03 (shared evaluation, rejected input, synthetic labels), RUN-01/SDD-01/02 (idempotency, protected scope, real independent review) remain unchanged. No learning note can amend them. Avito under-order without confirmed suitable route retains `требует ручной проверки`. T007 historical non-acceptance and every source stop remain unchanged.

## Runtime Blockers Distinguished from Draft Readiness

- T016 `f495e529` is independently accepted as a limited engineering baseline. T017 specification was accepted for the inactive MVP and implementation was authorized. The WIP received three MEDIUM findings; repairs are implemented, independent exact-SHA recheck remains pending.
- Actual trusted authority boundary outside writer-changeable state is not established; real promotion remains BLOCKED until coordinator verification.
- Actual inactive harness, explicit synthetic consumer, semantic mutations and rollback have run. OS network isolation and real promotion authority are not established. Independent implementation/result recheck remains pending.
- Full sourcing product DoD remains pending real multi-source user scenario and reproducible operation; no experiment result substitutes for it.

## Executed Inactive Mapping

| Acceptance | Executable checks | Remaining gate |
| --- | --- | --- |
| AC-01/04 | test_lesson_consumer: explicit new decision, applicability and receipt-only controls | Actual independent resulting-change review pending; bootstrap synthetic only |
| AC-02/03/08 | test_reviewed_lessons: quarantine, active retrieval, wrong/local authority, valid-hash hostile text; test_lesson_consumer hostile data | Real external authority BLOCKED |
| AC-05 | Hypothesis declaration-order/duplicate variation, evidence deletion refusal | None for inactive guards |
| AC-06/07 | test_critical_mutations: eight semantic kills, actual loaded/source binding, stale bytecode, baseline/invalid/import/scope/timeout/equivalent survivor controls | Curated coverage only; broader isolation not established |
| AC-09/10 | test_reviewed_lessons: concurrent CAS, before/after-switch interruption, rollback and retained audit/source restrictions | Real activation OFF |
| AC-11 | authority-readiness.json, cutover.json and real OFF/BLOCKED CLI | Coordinator resumes product after independent review |
| AC-12/13 | test_process_metrics: fixed cohort, chronology, censored/unknown and replay/intervention controls | Historical telemetry incomplete, no improvement claim |
| AC-14 | Existing authoring receipts plus planned pinned implementation validation workflow | Exact committed native run and independent review pending |

## WIP Review Repairs (Historical Receipts Retained)

Reviewer reference: libfile_31896ca4e9ec8191bd30f3f8345063e6, SHA256 43dd4e7a20974588da4895073fe5759ae78745e43f364379b756b362cc0d7e97.

| Finding | Contract | New executable evidence |
| --- | --- | --- |
| M1 old evidence/ACK/nonexistent commit accepted | FR-004, AC-01/04 | Actual isolated Git base/result objects and direct parent, committed new decision plus changed resolver, bounded semantic counterfactual; old evidence, ACK, nonexistent/stale/no-change commits and changed source refuse |
| M2 stale unbound mutation PASS | FR-005/006/011, AC-05/06/07 | Git/spec/oracle/tests/code/harness/corpus bindings, canonical receipt self-hash; reuse validator and mid-run checks refuse spec/oracle/test/harness drift and tampered result |
| M3 corrupt quarantine promoted | FR-001/002, AC-02/08 | Strict persisted candidate schema/hash/payload equality, typed incident schema and canonical incident hash lineage; malformed/different/duplicate candidate and missing/corrupt/validly reencoded changed incident refuse before switch |
| LOW obsolete NOT_RUN status | FR-008/009 | Current status corrected here; original authoring/WIP receipts unchanged |

CP-T017-01 was explicitly approved and applied only at exact protected-file hashes documented in CP-T017-01.md. Original assertions244/1, seven negatives and historical checker remain unchanged.

## Additional Independent Findings Repaired

- HIGH R5 and filter.clean neighbor: ObjectView never reads the supplied repository config/index/attributes. Controlled temporary metadata and explicit environment are used; no repository-driven callbacks run. Actual before/after marker controls are preserved.
- MEDIUM R6: original commit/tree/blob object IDs and payloads are verified without replace refs/grafts or inherited Git environment. Raw parent/file sets and worktree bytes are checked; false replacement commits are refused. Valid packed original objects and symbolic HEAD are covered.
- MEDIUM R7: rollback revalidates full target schema, unique bounded entries, lesson/incident/verdict and visible ancestry before pointer mutation. Interrupted but never-visible orphan targets refuse; valid empty historical rollback after evidence loss remains supported.
- MEDIUM R8: verifier reconstructs each frozen original-to-mutant transformation and expected structural code. Contradictory loaded/fresh hashes, unchanged source, false baseline/origin/assertion refuse after rehashing.

Review evidence: libfile_3397f9050b608191a9cf153dacd8e6ba SHA2560dfbf89f064551fd65f0489ba4b13701c27c9fb5dcbe4b43dc67d2e6fe3ba56a; recovered independent package libfile_a7656d01bbe48191b067ecbe6c88d900 SHA25632c19e978d8aff2a51a0d283670c094125ae626358d6e38afd8d0e4ee1c91249 was materialized and its exact seven probes checked, red4/green7. Historical receipts are not rewritten.
