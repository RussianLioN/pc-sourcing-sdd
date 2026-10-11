# ADR-0001 — native cloud snapshot acceptance

Status: approved by the user on 2026-10-11; applies prospectively to T008.
Authority: the user explicitly agreed to the methodology after being told that
separate checkouts and clean-state checks do not establish OS write denial.
Baseline: 802e001f72bbaf3ae9b6f52081b6361d01736be5.

Use one writer cloud task and a separate reviewer cloud task with a separate
checkout. The parent coordinates actual tasks through available capabilities;
there is no repo scheduler, simulated cloud API, runtime LLM or live adapter.
Reviewer findings return to the writer; the reviewer does not integrate patches.
Every repair creates a new commit and requires new same-SHA evidence/review.

For future native cloud runs only, this profile replaces the nested Spec Kit /
Codex coordinator, nested binary/model pin and OS read-only verifier requirements.
It also replaces the old mandatory two-iteration collector do-while receipt with
actual installed pipeline execution and idempotent repetition on the same input,
as-of, run-id and database. This checks collector repetition, not do-while
orchestration, supervisor termination, crash recovery or a scheduler.

The procedural parts of historical AGENTS/constitution/SDD instructions are
superseded only where the explicitly agreed native execution profile differs.
Product requirements, protected original tests/spec/contracts/goldens, evidence,
access restrictions and no-live scope remain binding. Historical files and
receipts are immutable; neither T007 nor old acceptance is reclassified as
passed. T007 stays unaccepted under its original PORT requirements.

Manifest checks detect inconsistent SHA, spec, protected bytes, evidence and
review. They do not authenticate a cloud service, a security principal, binary
or model identity, or prove absence of temporary writes. Task/environment IDs and
separate-checkout provenance are supplied/checked by the parent against real task
results. No OS read-only or forced cloud-task deadline is claimed. Recorded
per-subprocess timeouts are local tooling behavior only.

Without confirmed repository required checks, acceptance is a managed process,
not an enforced prohibition on merge. Git/evidence hashes detect drift but do not
provide signatures or make a dishonest author unable to forge a receipt. Keep
raw logs/databases ignored; publish only reviewed safe summaries.
