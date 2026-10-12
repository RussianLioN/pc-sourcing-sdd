# Feature Specification: Reviewed Learning and Regression Experiment

**Feature Branch**: `feature/cloud-portability` (isolated draft checkout; no publication)

**Created**: 2026-10-12

**Status**: Specification accepted for inactive MVP; implementation authorized; independent implementation review and real activation gates pending

**Input**: Agreed combination 1 + 2 + 6: retrieve independently verified lessons, prove critical regression detection with properties and meaningful mutations, and author/run the process experiment through existing Spec Kit. Confirmed base: `f495e5294e93a281f945de6f4e1c6c89d7a6cb1e`.

## Clarifications

### Session 2026-10-12

The following five answers were already supplied in the agreed coordinator requirements, not newly asked of the user. Clarify scanned the actual specification and integrated them before planning.

- Q: What grants promotion authority? → A: Coordinator verification of the actual independent exact-hash verdict outside writer-changeable state; local flags or another-version PASS never suffice (FR-002).
- Q: Can an active lesson issue instructions? → A: No. Even active verified knowledge remains scoped untrusted content; valid hashes do not authorize stop clearing, oracle edits or execution (FR-003).
- Q: What proves actual consumption? → A: Explicit invocation, active lesson, applicability and a new observable test or decision independently reviewed; a formal receipt or already-green implementation is insufficient (FR-004).
- Q: What counts as a killed mutant? → A: A relevant assertion detecting changed semantics in actually imported code after a passing baseline; operational, unapplied and equivalent outcomes do not count (FR-006).
- Q: What does rollback restore? → A: The previous complete active lesson version/hashes after atomic compare-and-switch; current source budgets/stops and audit history are retained (FR-007).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reuse a reviewed lesson without importing authority (Priority: P1)

The sole writer explicitly asks for relevant lessons while preparing a bounded change. The writer receives only independently verified active lessons with applicability and evidence, then either creates a new regression test or records a concrete design decision. An independent reviewer checks that resulting change.

**Why this priority**: Repeated defects should become useful knowledge without allowing a local note to approve itself or override sourcing constraints.

**Independent Test**: In an offline disposable checkout, an explicitly invoked retrieval workflow consumes a specific active lesson and produces a new test or decision that an independent reviewer can inspect. A receipt with no resulting change fails.

**Acceptance Scenarios**:

1. **Given** an independently approved active lesson applicable to a new change, **When** the writer explicitly retrieves it and checks applicability, **Then** the receipt identifies the lesson/version and the resulting new test or decision, bound to the reviewed resulting change. This is AC-01.
2. **Given** a candidate or rejected lesson, **When** retrieval searches the relevant topic, **Then** it returns no active lesson and preserves an explanation. This is AC-02.
3. **Given** a valid lesson containing commands to clear a source stop, alter the oracle, or execute evidence text, **When** the consumer reads it, **Then** no such action is authorized or executed. Applicable knowledge may be recorded as a bounded decision; malicious directives are rejected. This is AC-03.
4. **Given** a non-applicable lesson or a receipt without a new observable result, **When** consumer validation runs, **Then** it reports non-applicability or failed use rather than success. This is AC-04.

### User Story 2 - Prove that critical mistakes would be detected (Priority: P1)

A maintainer runs a bounded offline regression experiment against an unchanged baseline. Properties explore critical variations and shrink failures. Deliberate semantic defects demonstrate whether relevant assertions detect the fault in the code actually imported.

**Why this priority**: Passing tests alone cannot demonstrate sensitivity to the defects that caused repeated repair rounds.

**Independent Test**: A passing baseline and a pinned critical mutant corpus are replayed in disposable checkouts; each mutation receipt links changed imported source, the applicable test, and a relevant assertion. Operational errors never count as a killed semantic defect.

**Acceptance Scenarios**:

1. **Given** a passing baseline, **When** conflicting declarations change order, duplicate keys recur, or evidence is removed, **Then** properties preserve conflicts and cannot increase confidence or activation. This is AC-05.
2. **Given** a mutant that changes the semantics of the imported implementation, **When** a relevant assertion fails, **Then** the result is classified killed with baseline, source, oracle and test-set hashes. This is AC-06.
3. **Given** syntax/import/scope errors, timeouts, unapplied mutants, or an equivalent mutant, **When** the harness reports, **Then** these remain distinct unresolved or invalid categories and are excluded from the killed count. A baseline failure invalidates the experiment. This is AC-07.

### User Story 3 - Promote and roll back without losing operational truth (Priority: P1)

The coordinator checks an actual independent verdict outside writer-changeable files and binds the exact lesson, code, specification, oracle and tests before activation. A version switch is atomic and rejects stale assumptions. Rollback restores the previous active lessons while retaining source restrictions and all audit events.

**Why this priority**: Writer-owned approval flags and stale manifests must never become review authority. Experiment failure must not consume or reset product state.

**Independent Test**: In an isolated offline authority fixture, valid external approval permits a compare-and-switch; local-only approval and different-version approval fail. Concurrent readers observe one complete version. Rollback restores previous lesson hashes and leaves all restriction/audit bytes intact.

**Acceptance Scenarios**:

1. **Given** only writer-local `independent: true`, a local PASS, or an approval for different hashes, **When** promotion is attempted, **Then** it refuses before any active version changes. This is AC-08.
2. **Given** a coordinator-verified external verdict for the complete exact manifest and a matching previous version/hash, **When** promotion runs, **Then** a reader sees either the previous or new complete snapshot; a stale compare refuses. This is AC-09.
3. **Given** a failed activated experiment, **When** rollback runs, **Then** previous active lessons and hashes are restored, current source budgets/stops remain unchanged, and incidents, reviews and rejections remain available. This is AC-10.
4. **Given** missing authority isolation or failed process acceptance, **When** the coordinator ends the bounded experiment, **Then** learning stays off and product work can resume from accepted T016 with the concrete blocker recorded. This is AC-11.

### User Story 4 - Measure the process without inventing improvement (Priority: P2)

The coordinator obtains reproducible process receipts and a baseline of recurring defect categories, independent repair rounds, reproducibility, elapsed acceptance time, and direct human interventions. Missing telemetry stays unknown. Spec Kit participates from initial agreed input through specification, clarification, planning, tasks and executable validation.

**Why this priority**: One pilot can prove guards and a useful consumer; improvement claims require comparable baseline measurements.

**Independent Test**: Replaying the same eligible events produces the same metrics and provenance; missing/censored timestamps remain unknown. Authoring receipts show the installed workflow and artifact order, rather than only familiar filenames.

**Acceptance Scenarios**:

1. **Given** public repository/test/review facts, **When** baseline metrics are computed, **Then** taxonomy and denominators are declared; local attempts differ from independent repair rounds, and human interventions differ from coordinator automation. This is AC-12.
2. **Given** absent usage or timing measurements, **When** reporting runs, **Then** cost and active user time are unknown and no improvement claim appears. This is AC-13.
3. **Given** agreed experiment input, **When** authoring progresses, **Then** specify and clarify precede plan and tasks; actual installed steps, outputs and hashes are retained. Implementation validation and independent review remain separate future gates. This is AC-14.

### Edge Cases

Missing, deleted or stale evidence; changed code/specification/oracle/test-set hashes; conflicting lesson IDs; duplicate declarations at any depth; interrupted promotion; stale previous-version comparison; concurrent retrieval during promotion or rollback; formal consumer receipt without new outcome; inapplicable lesson; expired approval; unsafe text with otherwise valid evidence hashes; invalid or equivalent mutations; non-passing baseline; unavailable external review authority; missing process telemetry. These produce explicit rejection, unknown or blocked categories rather than inferred success.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Preserve a complete incident-to-candidate-to-review-to-promotion/rejection lifecycle. Candidates are quarantined outside any automatically loaded instruction or active lesson path. Only independently verified active versions are returned as usable lessons.
- **FR-002**: Promotion requires coordinator verification of an actual independent verdict outside writer-changeable repository state, bound to lesson, code, specification, oracle and test-set hashes. Local flags or review of another version grant no authority. Missing trusted authority fails closed.
- **FR-003**: All lesson and evidence text, including active lessons, remains untrusted scoped content. It cannot authorize command execution, access changes, stop clearing, oracle alteration, source reclassification or protected-requirement changes.
- **FR-004**: Explicit retrieval must identify an active lesson/version, applicability determination, and a new observable regression test or concrete decision. Consumer acceptance additionally requires independent review of the resulting exact change; an acknowledgement or previously passing implementation is insufficient.
- **FR-005**: Property experiments preserve declaration conflicts, duplicate-key refusal and evidence monotonicity, with reproducible seeds and shrunk failures. All data in offline experiments is marked synthetic; historical real evidence is referenced without reclassification or renewed retrieval.
- **FR-006**: Mutation proof requires a passing baseline, an actual semantic change in imported code, and failure of a relevant assertion. Timeout/import/syntax/scope/unapplied/equivalent outcomes never count as killed mutants. Coverage claims apply only to the predefined critical corpus.
- **FR-007**: Promotion compares previous version and manifest hashes and switches atomically. Each consumer reads one consistent version. Rollback restores the previous verified active lesson snapshot while retaining all incidents/reviews/rejections and current source budgets/stops.
- **FR-008**: Author the experiment from agreed input through the existing specification and clarification workflow, then plan/tasks, implementation checks and independent exact-change review. Preserve actual workflow command receipts and artifact hashes; do not replace the framework or add a second orchestrator.
- **FR-009**: Report recurring defect taxonomy, independent repair rounds versus local retries, reproducibility eligibility/denominators, first-submission-to-acceptance elapsed time, and direct human interventions separately. Missing or censored values are unknown. No improvement claim without a comparable baseline.
- **FR-010**: Remain additive and offline: sole writer, separate task ownership, unchanged protected product requirements/oracles/fixtures and accepted sourcing behavior; no new network access, credentials, subscriptions, global hooks, deployment, purchases, contacts or merchant HTTP.
- **FR-011**: Execute meaningful unit, property, integration, negative, end-to-end, interruption, rollback and fresh-consumer checks. Preserve failures and bind all acceptance evidence to one exact change and test/oracle corpus. Engineering success never implies full sourcing product DoD.
- **FR-012**: Activation remains disabled until accepted T016, coordinator start, independent experiment acceptance and rollback verification. If safe activation is unavailable, record the blocker, keep learning off and resume accepted product work; no indefinite experiment pause.

### Key Entities

- **Incident**: root-cause category, observation time, public evidence references, affected exact change, local-attempt and independent-review history.
- **Candidate lesson**: immutable identity/version, bounded applicability, scoped knowledge, source/evidence hashes, status and independent verification links; never an approval authority.
- **External review binding**: coordinator-verified verdict identity, independently reviewed exact hashes and scope, checked outside writer authority; local replicas are evidence only.
- **Active snapshot**: monotonically versioned set of verified lesson hashes plus previous version/hash, allowing one consistent read and atomic comparison.
- **Consumer result**: invocation, lesson snapshot, applicability, new test/decision artifact hash and independent resulting-change review.
- **Experiment result**: baseline, seed, oracle/test/code hashes, changed imported source and mutant outcome category.
- **Metric event**: UTC event type, eligible cohort and provenance; absent cost/time data is explicitly unknown.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every mandatory acceptance scenario AC-01 through AC-14 has reproducible evidence; zero candidates become active from writer-local approval alone.
- **SC-002**: At least one applicable reviewed lesson yields a new independently reviewed test or decision through explicit consumption. Receipt-only and non-applicable controls cannot pass.
- **SC-003**: Every valid non-equivalent critical semantic defect in the frozen corpus is detected by a relevant assertion; all invalid, unresolved and equivalent outcomes are individually disclosed and excluded from the killed denominator. Zero operational failures are counted as detection.
- **SC-004**: Promotion and rollback concurrency/interruption cases reveal no partial active snapshot; rollback preserves 100% of current source restriction bytes and historical audit events.
- **SC-005**: Replaying the same eligible process events yields identical metrics. Missing cost, active user time and censored acceptance time remain unknown; no unsupported improvement claim appears.
- **SC-006**: All protected parent requirements, fixtures, tests and sourcing state remain unchanged except a separately approved exact change proposal. Full regression, fresh-consumer and independent review are required before experiment activation.

## Assumptions

The coordinator has authorized draft authoring only. T016 is independently accepted as a limited engineering baseline; independent T017 specification review and implementation start remain separate external gates. Users need no new technical-choice questions: the five agreed design clarifications resolve the material choices. The first active lesson set is empty unless the coordinator verifies a separate baseline. Public historical Git/test/review facts may be used, private chats and hidden telemetry may not. A trusted review boundary must be supplied and verified by the coordinator before real activation; this draft does not invent one. This experiment proves guards and bounded reuse first, not a quantified productivity gain. Existing product work resumes with learning off if the experiment cannot be activated safely.

## Accepted Baseline Evidence

T016 limited engineering PASS: `f495e5294e93a281f945de6f4e1c6c89d7a6cb1e`, coordinator-supplied independent review `libfile_d5f5b14b1d148191b82699ea3c50bf09`, SHA256 `d35368ccc77974afa2165521314a295735110a3da1e61a4bc2cd7ff813232ad4`. This baseline acceptance does not accept T017 or the full sourcing product. Independent specification review precedes implementation start.

## Narrow Implementation Clarifications

- Bootstrap consumer proof uses an explicitly synthetic isolated active fixture; it never bypasses real activation.
- Canonical hash projections exclude their own hash field. Git commit identifiers are 40 lowercase hex; SHA256 content digests are 64 lowercase hex, validated separately.
- Mutation receipts verify the actually loaded implementation; stale bytecode is a mandatory negative control.
- T016 accepted baseline and the checkpoint disclosure are retained; authoring was not repeated.

## Review Repair Constraints

Consumer bootstrap proves a real isolated committed change and substantive decision, including a bounded semantic counterfactual; arbitrary artifacts or commit strings do not prove use. Mutation reuse validates the complete immutable spec/oracle/test/harness binding and refuses drift. Promotion validates the persisted quarantine payload and incident hash lineage, not filename existence. These clarify existing FR-001/002/004/005/006/011 without widening the inactive MVP.

## Git and Reuse Boundary Repair

Repository metadata never supplies executable validation policy. Original immutable Git objects, raw parents and worktree bytes are checked in a neutral metadata view. Rollback requires a fully valid previously visible snapshot; rehashed unknown targets cannot become active. Mutation proof must match the frozen transformation, loaded/fresh structural code and relevant assertion, not only a checksum or boolean. Existing inactive scope and external-review requirements are unchanged.
