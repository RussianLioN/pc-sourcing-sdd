# Tasks: Reviewed Learning and Regression Experiment

**Input**: Design documents in `specs/012-reviewed-improvement/`, draft 0.1.0.

**Prerequisites**: T016 exact SHA is accepted as the limited engineering baseline. Independent T017 specification review and coordinator implementation start are still required; proposed task ownership must be verified externally. Authoring is complete; every implementation task remains unchecked. Tests are explicitly required by FR-011. No parallel writer; task parallelism examples are read-only checks only.

## Phase 1: Setup

- [X] T001 Freeze coordinator-authorized base, owned files and externally protected baselines in tasks/T017.json; refuse implementation if T016 not accepted or start absent.
- [X] T002 Verify licenses and copy pinned MIT attribution into specs/012-reviewed-improvement/notices/compound-MIT.txt without editing protected THIRD_PARTY_NOTICES.md or locks.
- [X] T003 Freeze eligible historical cohort, root-cause taxonomy, independent verdict provenance and unknown/censored metrics in specs/012-reviewed-improvement/baseline.json; no private chat excerpts.

## Phase 2: Foundational Prerequisites

- [X] T004 Add protected-base and sole-owner checks in scripts/improvement_scope.py and tests/test_improvement_scope.py; all parent bytes unchanged, no local hash grants authorization.
- [X] T005 Add strict data validation and immutable incident/candidate/audit records in scripts/reviewed_lessons.py: duplicate keys at every depth refused, documents <=1MB, text <=64KB, IDs <=128 chars, corpus <=32, hashes exactly 64 lowercase hex, unknown null.
- [X] T006 Write trust-boundary rejection cases in tests/test_reviewed_lessons.py: local flags, wrong-version PASS, changed evidence/oracle/tests, missing external authority and synthetic-to-real promotion all refuse before active writes.
- [X] T007 Define coordinator-only external approval verification in scripts/reviewed_lessons.py; actual provenance plus complete lesson/code/spec/oracle/test/outcome hashes outside writer-changeable state, fail closed if permissions/isolation cannot be established.

## Phase 3: User Story 1 — Useful Explicit Consumption

Goal: Verified active lessons produce a new observable independently reviewed result. Independent test: AC-01/02/03/04 with applicable, candidate/rejected, valid-hash hostile text, receipt-only and non-applicable controls.

- [X] T008 [US1] Add active-only retrieval, evidence invalidation and applicability tests in tests/test_reviewed_lessons.py; evidence removal never raises confidence or activation.
- [X] T009 [US1] Implement consistent active snapshot retrieval and quarantine exclusion in scripts/reviewed_lessons.py; scoped text grants no operational authority.
- [X] T010 [US1] Add explicit consumer outcome controls in tests/test_lesson_consumer.py: applicable/new test or decision with bound independent review, unchanged already-green result, receipt-only, unknown and non-applicable negatives.
- [X] T011 [US1] Implement outcome validation in scripts/lesson_consumer.py and install explicit-only future .agents/skills/pc-reviewed-lessons/SKILL.md with .agents/skills/pc-reviewed-lessons/agents/openai.yaml policy allow_implicit_invocation: false only after implementation authorization.
- [ ] T012 [US1] Demonstrate actual explicit skill invocation on a new variant in an isolated consumer; preserve invocation/applicability/new artifact/counterfactual/exact change/independent result-review evidence in specs/012-reviewed-improvement/consumer-case.json; no candidate text execution.

## Phase 4: User Story 2 — Properties and Meaningful Mutations

Goal: Prove semantic detection for a fixed critical corpus. Independent test: AC-05/06/07; every valid non-equivalent mutant killed by relevant assertion, invalid/unresolved outcomes disclosed.

- [X] T013 [US2] Add seeded/shrunk additive Hypothesis properties in tests/test_critical_mutations.py for order/conflict/duplicate/evidence monotonicity, preserving immutable product oracle and synthetic labels.
- [X] T014 [US2] Freeze eight named critical families and source/semantic/assertion mappings in specs/012-reviewed-improvement/mutant-corpus.json; baseline/source/oracle/test hashes, eligibility and denominator are explicit.
- [X] T015 [US2] Add baseline-fail/unapplied/equivalent/syntax/import/scope/timeout and imported-source hash controls in tests/test_critical_mutations.py; these outcomes never count as killed.
- [X] T016 [US2] Implement standard-library semantic harness v1.0.0 in scripts/critical_mutations.py using isolated disposable copies, sanitized environment, import hash receipt and relevant assertion classification; baseline <=120s, mutant <=60s, supervisor <=660s, kill/reap process groups.
- [X] T017 [US2] Run actual offline compatibility and isolation smoke and all eight family cases; record every outcome, seed/shrink and logs in specs/012-reviewed-improvement/mutation-evidence.json; no source state or merchant HTTP, no broad mutation-coverage claim.

## Phase 5: User Story 3 — External Promotion and Rollback

Goal: Coordinator-bound atomic activation, consistent readers and rollback without operational-state loss. Independent test: AC-08/09/10/11 under synthetic authority plus independently verified real boundary before actual activation.

- [X] T018 [US3] Add stale previous-version/hash, concurrent readers, interrupted preparation/switch, rollback and retained audit/source-state invariants in tests/test_reviewed_lessons.py.
- [X] T019 [US3] Implement locked compare-and-switch, fsync immutable manifest/atomic pointer and monotonic rollback events in scripts/reviewed_lessons.py; consumers read one snapshot, original current source budgets/stops never rolled back.
- [ ] T020 [US3] Verify actual coordinator authority boundary and rollback smoke externally; store evidence-only references in specs/012-reviewed-improvement/authority-readiness.json; if unavailable mark BLOCKED and keep learning off, no permission configuration changes.
- [X] T021 [US3] Record acceptance/rollback or blocked-learning-off product-resume decision in specs/012-reviewed-improvement/cutover.json; no indefinite experiment pause or pending-source automatic refetch.

## Phase 6: User Story 4 — Measured Process and Existing Framework

Goal: Reproducible metrics and actual Spec Kit execution. Independent test: AC-12/13/14 with absent/censored data and same-event replay.

- [X] T022 [US4] Add metric cohort/denominator/unknown/censored/intervention-category and repeatability tests in tests/test_process_metrics.py; local retries and independent rounds stay distinct.
- [X] T023 [US4] Implement metric summaries in scripts/process_metrics.py preserving null cost/active time without telemetry and forbidding unsupported improvement claims.
- [X] T024 [US4] Add pinned bounded workflow workflows/improvement-validation.yml and scripts/improvement_quality.py plus scripts/improvement_check_workflow.py; retain shared snapshot hashes, actual native commands and all failures, no second orchestrator/global hooks.
- [X] T025 [US4] Replay public historical baseline and fresh eligible experiment events in specs/012-reviewed-improvement/process-evidence.json; no invented dates, independence or improvement.

## Phase 7: Cross-Cutting Acceptance

- [ ] T026 Re-run unit/property/integration/negative/end-to-end/rollback/full regression, Ruff, format and ownership checks on one stable exact SHA; record traceable per-gate evidence in specs/012-reviewed-improvement/acceptance-matrix.json.
- [ ] T027 Secret-scan code and complete evidence/state payload, create exact-SHA Git bundle and immutable lesson/audit snapshots, and verify a fresh consumer/restore in specs/012-reviewed-improvement/transfer-evidence.json; no operational budget rollback.
- [ ] T028 Obtain actual independent exact-SHA verdict outside writer authority; coordinator alone decides activation after useful consumer and rollback proof, preserving acceptance or blockers in specs/012-reviewed-improvement/final-verdict-reference.json.

## Dependencies and Implementation Strategy

T001–T003 -> T004–T007 -> US1 T008–T012. US2 T013–T017 needs frozen baseline and can be validated independently of active lessons. US3 T018–T021 depends on the immutable lesson/authority model and US1 consumer; actual activation also waits for T026–T028. US4 T022–T025 depends on baseline cohort and authoring receipts and can be tested without product access. T026–T028 finalize all stories.

MVP is inactive candidate/rejection/retrieval guards plus one synthetic-authority consumer; it is not sufficient for production activation. Deliver remaining stories before independent acceptance. One writer executes edits sequentially. Read-only examples: after a stable checkpoint, US1 retrieval negatives and US2 corpus inspection can be checked separately; US3 immutable state inspection and US4 metric replay do not share mutable outputs. Each run uses unique absolute output paths. No `[P]` implementation tasks are scheduled in this single-writer pilot.

## Execution Status

Tasks T012/T020/T026–T028 retain pending portions: bootstrap consumer outcome exists but independent resulting-change review is pending; real authority is unavailable; exact CP-T017-01 authorization received and applied; final canonical checks/publication/recheck are in progress. Historical failures and current receipts are retained outside Git in artifacts/T017. These states do not block inactive unit/semantic tests. Actual activation is OFF.
