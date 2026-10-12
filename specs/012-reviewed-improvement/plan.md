# Implementation Plan: Reviewed Learning and Regression Experiment

**Branch**: `feature/cloud-portability`, isolated uncommitted draft | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Spec Kit authored and clarified `specs/012-reviewed-improvement/spec.md`, draft 0.1.0.

## Summary

Add an explicitly invoked repository-local reviewed-lesson workflow, an offline property/semantic-mutation experiment, and a small validation workflow in existing pinned Spec Kit. Preserve all product code and protected acceptance oracles. Draft authoring is complete; T016 is accepted as the limited engineering baseline; implementation is gated by independent T017 specification review and coordinator task authorization. Real activation additionally requires independent exact-SHA acceptance, demonstrated consumer use, rollback proof and externally verified promotion authority.

## Technical Context

**Language/Version**: Existing Python 3.13.3; shell wrappers and document-only skill adapter.

**Primary Dependencies**: Existing pytest 8.4.2, Hypothesis 6.142.1, Pydantic 2.14.0, Ruff 0.14.0; Spec Kit 1.1.3 pinned commit `0282d03eb6fc3091b3deaa3a855d4030dc40cd6c`. No dependency/lock updates.

**Storage**: Immutable bounded JSON candidate/evidence manifests outside skill auto-load paths; append-only audit events; atomic versioned active manifest in a coordinator-controlled state directory. No product database migration. Strict JSON duplicate-key rejection before validation.

**Testing**: Existing pytest/Hypothesis and a planned small standard-library semantic AST harness v1.0.0; no mutmut install. Curated corpus is not general mutation coverage. Fresh isolated consumers and independent exact-SHA review.

**Target Platform**: Cloud Linux CLI; same pinned interpreter. No service, Telegram token or deployment.

**Project Type**: Additive coordinator tooling and explicit skill, not application runtime.

**Performance Goals**: Bounded one experiment: baseline subprocess <=120 seconds, individual mutant <=60 seconds, suite supervisor <=660 seconds, immutable input <=1MB/document, corpus <=8 named critical mutant families. Interrupted work blocked and recorded; never silently resumed. These are process-experiment bounds, not merchant budgets.

**Constraints**: No source HTTP, runtime LLM API calls, new dependencies, credentials, global hooks, root AGENTS changes, protected oracle changes, second orchestrator or concurrent writer. Source budgets/stops byte-identical. No promotion based on writer-generated approval. Draft does not configure permissions or trusted roots.

**Scale/Scope**: Four stories; first pilot one useful lesson and one observable independently reviewed consumer outcome. Eight curated critical mutation families; seeded reproducibility and frozen denominators. Candidate limit 32/experiment and 64KB/scoped text; absence of measured historical data remains unknown.

## Constitution Check

*Before research and after design: PASS as draft design, not implementation acceptance.*

| Gate | Design evidence | Status |
| --- | --- | --- |
| Product/evidence/unknown/payment requirements unchanged | FR-003/010; no application file owned; source restrictions read-only | PASS |
| One writer and independent exact-change review | FR-002/011/012; coordinator authority external to writer | PASS |
| No golden/oracle weakening | Baseline hashes frozen externally; new synthetic cases additive | PASS |
| Bounded execution and failure preservation | Existing Spec Kit + explicit process bounds; no running-state edits | PASS |
| New access/credentials/publication prohibited | Offline subprocess corpus; no source requests/configuration | PASS |
| Change proposal for protected files | None planned; scope drift blocked and escalated separately | PASS |
| Activation authority available | Not established in this draft environment; fail closed | BLOCKED FOR ACTIVATION |

The blocked external authority is a runtime prerequisite, not a permission change or constitutional exception. Writing draft design and later inactive tests does not require it. Product work resumes with learning off if safe activation cannot be established.

## Project Structure

### Documentation (this feature)

```text
specs/012-reviewed-improvement/
  spec.md
  plan.md
  research.md
  data-model.md
  traceability.md
  quickstart.md
  contracts/process-cli.md
  checklists/requirements.md
  tasks.md
```

### Source Code (planned, not created in draft)

```text
scripts/reviewed_lessons.py
scripts/lesson_consumer.py
scripts/critical_mutations.py
scripts/process_metrics.py
scripts/improvement_scope.py
scripts/improvement_quality.py
scripts/improvement_check_workflow.py
workflows/improvement-validation.yml
.agents/skills/pc-reviewed-lessons/SKILL.md
.agents/skills/pc-reviewed-lessons/agents/openai.yaml
specs/012-reviewed-improvement/notices/compound-MIT.txt
tasks/T017.json
tests/test_reviewed_lessons.py
tests/test_lesson_consumer.py
tests/test_critical_mutations.py
tests/test_process_metrics.py
tests/test_improvement_scope.py
```

**Structure Decision**: Coordinator scripts are never imported by `src/pc_sourcing`. Existing application/tests/skills/locks remain protected. Candidate storage uses explicit absolute paths outside `.agents`, `.specify`, AGENTS and other auto-loaded instructions. New skill installation in `.agents` occurs only after coordinator implementation start; implicit invocation disabled. No active skill files are created during this draft.

## Phase 0: Research Decisions

Research is complete from the separately preserved version/license/source manifest; no new uncertain technology choices require delegated research. [research.md](research.md) records decisions/alternatives and provenance. Read-only original template/skill resolution receipts accompany this draft. The research phase did not contact merchants or install plugins/dependencies.

## Phase 1: Design and Contracts

See [data-model.md](data-model.md), [contracts/process-cli.md](contracts/process-cli.md), [quickstart.md](quickstart.md), [traceability.md](traceability.md). Technical constants and lifecycle validation are in the data model, not in the functional specification. All command interfaces are planned contracts: they are not claimed runnable until implementation.

### Review authority boundary

The coordinator must verify real independent reviewer provenance in its own environment and pin the approval's complete hash tuple outside writer-changeable state. Repository approval JSON is evidence, never authority. Production promotion executes only in a coordinator-controlled boundary whose state and approval registry the writer cannot alter. The coordinator must verify actual permissions/sandbox separation; pathname or writer-declared read-only flags do not prove it. Current shared `/workspace` is writer-writable and cannot provide this boundary by naming another directory. No permission changes are performed by this task.

Implementation can prove rejection and lifecycle behavior with explicitly synthetic isolated authority fixtures. Such fixtures carry `synthetic: true` and cannot promote a real active set. If actual external authority is unavailable, production promotion is blocked, useful offline testing proceeds, and product work resumes with learning off. No new cryptographic service is introduced. The platform/coordinator independent-review channel supplies identity, rather than locally self-asserted signer names.

### Atomic snapshot and rollback

The coordinator uses an exclusive local process lock, checks previous version/hash under that lock, validates every referenced immutable lesson/evidence file, writes and fsyncs a new immutable snapshot, then atomically replaces a small active pointer and fsyncs the directory. Consumers resolve one pointer once, validate the named immutable manifest and use only that snapshot. No in-place lesson writes. Interrupted preparation leaves old active state; interrupted after pointer replacement records recovery intent and audits the visible version before a new coordinator task. Rollback appends an event and points to the previous verified immutable set through the same compare-and-switch; version/event sequence remains monotonic. It never rolls product databases back to pre-spend state.

### Critical corpus and meaningful mutation proof

Families: declaration override/conflict, duplicate-key rejection, payment OR symmetry, unknown-to-false coercion, evidence-kind mismatch, budget reset/implicit initialization, schema-constraint weakening, stream byte/deadline drift. Freeze exact baseline/source/oracle/test hashes before mutation. Mutation targets may be protected files only inside a disposable experiment copy; originals never change. Verify the mutated bytes are loaded using import origin/source hash receipts. Run semantic assertions before broad scope checks; a scope failure is not a kill. A baseline failure blocks all scores. A surviving or equivalent/invalid mutant does not grant acceptance by reducing the denominator: disclose it and independently justify corpus repair/equivalence; every defined valid non-equivalent critical mutant must be meaningfully killed.

The harness writes a mutation plan/result and bounded stdout/stderr/exit classification, preserves seeds and shrunk failures, kills/reaps timed-out process groups, and has no source state, inherited secret values or application network tools. Disposable mutations are never committed. Process scripts use an explicit sanitized minimal environment. Network prohibition is enforced by the coordinator's existing execution boundary plus local socket rejection; local monkeypatch alone is not advertised as an OS sandbox. Missing isolation is a disclosed BLOCKED category.

### Explicit lesson consumer

Invoke the new skill explicitly, identify a lesson snapshot and applicability, and produce a new bounded regression test or concrete decision artifact. The observable artifact and resulting change hashes are independently reviewed. A test is meaningful only if it distinguishes the covered bad behavior; an unchanged already-green implementation/receipt is not proof. One pilot uses a new property/regression from a reviewed historical root cause on a fresh variant, not a verbatim restatement of an existing test. Candidates/lesson bodies cannot inject execution instructions. Coordinator commands and approved contracts carry authority, evidence does not.

### Metrics and bounded cutover

Public historical facts seed the baseline; missing independent-verdict chronology remains censored/unknown. Defect taxonomy and eligible cohorts are frozen before comparison. Count independent rejection-to-repair rounds separately from local failed test retries. Distinguish human user intervention from coordinator automatic gates. Usage and active user time stay unknown without actual telemetry. Acceptance ends one bounded additive pilot; on safe failure keep learning off and resume accepted T016 instead of retrying indefinitely.

## Complexity Tracking

No constitutional violations requested. The small curated semantic harness avoids dependency closure and protected-lock changes at the cost of explicitly limited mutation coverage. General mutmut adoption would require a separate reviewed proposal.
