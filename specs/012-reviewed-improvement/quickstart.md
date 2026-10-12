# Validation Guide: Reviewed Improvement Draft

The inactive MVP is implemented. Real reviewed learning remains OFF; synthetic bootstrap and local semantic experiments are available. Independent implementation/result review and real external authority remain pending. Candidate lessons must stay outside instruction paths.

## Reproduce draft authoring checks

Use the confirmed base `f495e5294e93a281f945de6f4e1c6c89d7a6cb1e` and the provided draft overlay in a fresh isolated clone. Retain existing pinned Spec Kit 1.1.3 and Python 3.13.3. With the feature overlay installed, execute:

```bash
SPECIFY_FEATURE_DIRECTORY=specs/012-reviewed-improvement bash .specify/scripts/bash/check-prerequisites.sh --json --paths-only
SPECIFY_FEATURE_DIRECTORY=specs/012-reviewed-improvement bash .specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
```

Expected: feature/spec/plan/tasks paths resolve to this draft; all design documents detected. These checks demonstrate workflow prerequisites, not implementation behavior or independent acceptance. See authoring evidence for actual template resolver, setup-plan/setup-tasks and hash/order receipts. setup-plan and setup-tasks were run before their respective authoring output.

## Future inactive implementation validation

After accepted T016 and coordinator implementation start, run new unit/property/negative tests, a passing baseline then the curated mutation corpus, promotion/read/rollback interruption cases using explicitly synthetic authority, and a fresh consumer with an explicitly invoked future skill that creates a new test or decision. Preserve the independently reviewed result and counterfactual; receipt-only/non-applicable controls must fail. Never exercise real merchant access.

## Future acceptance and activation

Freeze one exact Git SHA plus code/spec/oracle/test/corpus hashes. Run full regression, Ruff, formatting, owned scope, pinned native Spec Kit validation, secret scan and fresh bundle consumer. Independent reviewer verifies the same exact snapshot and observed new consumer outcome. The coordinator verifies real external review authority and permissions before promotion. If absent, report activation BLOCKED and keep learning off. Verify atomic rollback and source budgets/stops/audit invariants. On acceptance resume product; on safe activation failure resume accepted T016 with learning off and recorded blocker.

Full sourcing product DoD remains separate and pending a real multi-source user scenario and reproducible operation. No process pilot substitutes for it.

## Implemented Inactive Commands and APIs

```bash
.venv/bin/python scripts/reviewed_lessons.py status
.venv/bin/python scripts/reviewed_lessons.py promote
.venv/bin/python scripts/process_metrics.py specs/012-reviewed-improvement/baseline.json
.venv/bin/python scripts/critical_mutations.py --out /absolute/fresh/experiment-output
.venv/bin/python -m pytest -q tests/test_reviewed_lessons.py tests/test_lesson_consumer.py tests/test_critical_mutations.py tests/test_process_metrics.py tests/test_improvement_scope.py
```

Status prints OFF. Promote/search/rollback real CLI attempts print BLOCKED and exit2 without state writes. Isolated synthetic lifecycle is the explicit Python SyntheticAuthority/SyntheticStore API, tested end-to-end; it is never a real promotion bypass. The local skill is installed as a narrow explicit-only adaptation; the upstream Compound plugin and mutmut are not installed. Existing Hypothesis and pinned Spec Kit are the actual installed libraries/framework.

The mutation harness fixes eight semantic families and verifies loaded function bytecode against fresh compiled source. Stale bytecode, nonpassing baseline, imports, syntax, scope escapes and timeout are excluded from semantic kills. No OS network sandbox is claimed; fixed repository corpus plus local socket denial prevents network calls in the exercised tests. Missing external isolation prevents broader untrusted experiments and real activation.

## Repaired Consumer and Receipt Reuse

`new_decision` creates two actual commits in a fresh synthetic isolated repository: last-declaration baseline, then conflict-preserving resolver plus a new structured decision. `validate_use` checks committed content/parents/current clean tree and replays only the exact bounded recipe. This bootstrap does not grant real activation or independent review.

Reuse mutation receipts only with `.venv/bin/python scripts/critical_mutations.py --verify /absolute/experiment-output`; changed Git/spec/oracle/tests/code/harness/corpus invalidates old evidence. Raw historical JSON PASS remains a historical observation, never current acceptance.

## Repository Execution and Semantic Reuse Controls

Git config fsmonitor/include/hooks/diff/textconv/filter.clean and inherited config variables are marker-tested without execution by validation. Object replacement at commit/tree/blob/custom-ref levels cannot change original proof. Rollback refuses schema/entry/verdict/visible-lineage failures before switching. Rehashed mutation contradictions are rejected by frozen-source and structural/assertion checks. See exact external probe XML and current full/native receipts in the review bundle.
