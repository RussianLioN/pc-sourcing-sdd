# Data Model: Reviewed Improvement Draft

All records schema version `1.0.0`, strict duplicate-key refusal at every object depth, extra fields rejected. IDs are nonempty bounded strings <=128 characters; SHA256 values exactly 64 lowercase hexadecimal characters; timestamps explicit UTC. Documents <=1MB, lesson text <=64KB, candidate corpus <=32/experiment. Content is data, never authority. Unknown measured fields are null with a reason, never zero or false.

## Incident

`incident_id`, `root_cause` (frozen taxonomy), `observed_at`, `affected_commit`, `evidence_refs` (immutable URI/hash/provenance), `synthetic`, `local_attempt_ids`, `independent_review_ids`. References may be public historical evidence; private chat bodies are excluded. Missing chronology is recorded rather than reconstructed.

## Candidate Lesson

`lesson_id`, `version` positive integer, `incident_ids`, `applicability` (bounded problem/inputs/exclusions), `knowledge_text`, `evidence_refs`, `lesson_sha256`, `code_sha`, `spec_sha256`, `oracle_sha256`, `test_set_sha256`, `synthetic`, `status` enum candidate/reviewed/rejected/active/retired. Lesson object immutable after creation; status changes are audit events. Text containing imperatives is still untrusted. Applicability never widens product/access scope.

Lifecycle: incident -> candidate -> independent reviewed or rejected -> coordinator-bound active or promotion refused -> retired/rolled back. A candidate may be superseded only by a new immutable version; rejections remain recorded. Evidence loss/hash drift invalidates eligibility and retrieval, with no confidence increase.

## External Review Binding

`review_id`, `reviewer_provenance`, `verdict` PASS/REJECT, `scope`, `reviewed_commit`, `lesson_sha256`, `spec_sha256`, `oracle_sha256`, `test_set_sha256`, `consumer_outcome_sha256`, `reviewed_at`, `synthetic`. Actual independent identity and these values must be verified by coordinator outside writer-changeable state, then matched against the immutable candidate. A writer-local copy never grants permission. Synthetic authority cannot activate real records. Missing/changed authority refuses before mutation.

## Active Snapshot / Pointer

Snapshot: `version` monotonic integer, `previous_version`, `previous_sha256`, sorted unique lesson ID/version/hash entries, complete approval bindings, `snapshot_sha256`, `created_at`, `synthetic`. Pointer: version + immutable snapshot path/hash. Initial pointer version0 references empty set. Compare expected previous version/hash under exclusive lock; rejection on either mismatch. One snapshot per consumer invocation. Rollback creates a new monotonic audit/version transition to prior lesson content; preserves previous snapshots/events and all unrelated source restrictions.

## Consumer Outcome

`invocation_id`, `explicit_skill`, `active_version`, `active_sha256`, `lesson_id`, `lesson_sha256`, `applicability` applicable/not_applicable/unknown, `applicability_reason`, `outcome_kind` new_regression_test/design_decision/none, `outcome_path`, `outcome_sha256`, `resulting_commit`, `independent_result_review_id`, `synthetic`. `none` or non-applicable/unknown is not successful use. New test includes a counterfactual demonstrating relevant distinction; a decision specifies changed behavior/constraint and review evidence. No text execution.

## Mutation Receipt

`experiment_id`, `baseline_commit`, `baseline_code_sha256`, `oracle_sha256`, `test_set_sha256`, `baseline_status`, `seed`, `mutant_id`, `family`, `original_source_sha256`, `mutated_source_sha256`, `imported_path`, `imported_source_sha256`, `semantic_change`, `assertion_id`, `outcome` killed/survived/equivalent/invalid_syntax/import_error/scope_error/timeout/unapplied/blocked, `exit_code`, `log_refs`, `synthetic:true`. Killed requires baseline PASS, distinct imported mutated source, known semantic change and relevant failed assertion. Scores disclose every category, fixed total corpus and eligible valid non-equivalent denominator. Invalids cannot disappear to improve a score.

## Metric Event / Aggregate

`event_id`, `event_type`, `at`, `incident_id`, `commit`, `actor_type` human/coordinator_automatic/writer/reviewer, `evidence_refs`, `eligible_cohort`, optional measured usage/timing. Aggregates separately report root-cause recurrence/cohort, local attempts, independent repair rounds, reproducible eligible runs and blocked runs, UTC first-submission/acceptance with censored/unknown values, and direct human interventions. Cost and active user time are null if not measured. No improvement flag without comparable baseline/cohort.

## Implemented Projection and Bootstrap Boundaries

Canonical lesson and snapshot hashes exclude only their named self-hash field; nested hashes remain part of the projection. Git SHA is 40 lowercase hex, SHA256 digest is 64 lowercase hex. SyntheticStore requires synthetic fixture authority and incident lineage; no real store/promotion is implemented. Real ExternalAuthority always fails closed. Immutable audit records cover incident/candidate/reviewed fixture/promotion/rejection/rollback intents. Consumer output is BOOTSTRAP_PROOF_ONLY until the external reviewer checks the new outcome at the actual resulting commit.

Candidate `incident_sha256s` binds each named strict incident to its canonical payload digest. Consumer receipts name actual isolated repository/base/result Git commits and the committed new structured decision; result must be the current clean direct change and modify the bounded resolver. Mutation manifests carry Git/spec/oracle/test/code/harness/corpus bindings and a `result_sha256` projection excluding only itself; every per-family receipt repeats the binding. Reuse requires `verify_result`, never a raw stored PASS flag.
