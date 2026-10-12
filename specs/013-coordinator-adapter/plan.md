# Plan — Bounded Coordinator Host Handler

Base: accepted inactive T017 4bc835b57d948c56afc29ceafce671a9ce739099. Existing Python3.13.3, pytest/Hypothesis/Ruff and pinned Spec Kit1.1.3 only. No dependency or service installation.

Implement one new coordinator module and bounded replica transactions. Default/local interface prepares untrusted proposals only. The production coordinator host is a trusted deployment dependency supplied directly by the existing authenticated external executor, never deserialized from request data. This module does not authenticate an arbitrary Python provider or prevent arbitrary writes in a writer-writable filesystem; only the genuine coordinator's externally retained anchor/adjudication grants meaning to an operation. A locally fabricated provider/result is not a verified platform call.

The external executor validates the accepted module/dependency closure before importing it. Every handler call additionally compares current code/spec/oracle/test/closure and source/state hashes to that external pin. Request -> proposal -> external one-use adjudication -> lock/CAS -> verified visible receipt -> external anchor advance. Missing host/start/purpose, wrong tuple or old pointer blocks. No autonomous replay/reconciliation.

All source inventory reads are bounded and read-only. Source payload selection uses accepted witness_transfer validation; fourteen immutable restriction/evidence files must remain byte/mtime-equal. Replica storage is outside source-state/auto-load paths. Knowledge stays untrusted. Original raw Git proof uses accepted neutral ObjectView and one fixed decision recipe; real mode rejects synthetic results and inactive T017 purpose.

Tests use an explicitly simulated externally retaining host. They exercise mechanism and failure controls, not platform authentication. Actual existing-channel invocation, real independently accepted tuple and separate start occur only after independent adapter acceptance. Until then real operation is BLOCKED by the absent production host binding and learning OFF. This precise handoff is not a request for credentials or a new authority platform.

Owned paths: specs/013-coordinator-adapter/, tasks/T018.json, scripts/coordinator_adapter.py, scripts/coordinator_adapter_scope.py, scripts/coordinator_adapter_quality.py, scripts/coordinator_adapter_check_workflow.py, workflows/coordinator-adapter-validation.yml, tests/test_coordinator_adapter.py, tests/test_coordinator_adapter_scope.py. All accepted parent bytes protected, except an exact separately approved historical positive scope setup CP.

Constitution checks: product/evidence/payment/oracles unchanged; single writer; no merchant HTTP/access/credentials/permissions/global hooks; accepted T016 product fallback unchanged. Scope/full/native/fresh transfer and independent exact-SHA review required. No actual real invocation/activation claimed from synthetic tests.

The new task-owned quality runner uses a 240-second full-regression bound within the existing 480-second workflow step and 660-second supervisor. Canonical pre-CP suite took 121.50 seconds; the protected legacy quality runner is unchanged. No assertion/test/expectation is removed or weakened. Failures remain retained.

Clone-heavy pytest temporary directories use unique absolute /tmp paths on the separate filesystem; they and failure logs are retained. Quality logs also retain bounded timeout and executable-start errors as FAIL evidence.
