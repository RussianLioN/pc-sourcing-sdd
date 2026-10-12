# Feature Specification: One Explicit Coordinator Operation

**Branch**: `feature/cloud-portability`
**Created**: 2026-10-12
**Status**: Inactive implementation specification, independent review pending
**Base**: Accepted inactive T017 `4bc835b57d948c56afc29ceafce671a9ce739099`.
**Input**: The authenticated coordinator requested the bounded adapter in COORDINATOR-CONTRACT.txt from independent package `libfile_09e6e42eaf288191b84f396cb9fc2cda`, SHA256 `69e61b64f07df6b7fa445e928aab5daf3a073cdf3d5eca3f5b44ad8022661362`.

## User Scenarios & Testing

### User Story 1 — Prepare a proposal without acquiring authority (P1)

The writer submits bounded data for one operation. The helper reports a proposal and hashes, or rejection/blocking. A local file, environment flag or assertion never grants permission or starts learning.

**Independent test**: Local-only calls, injected approval fields, duplicate JSON keys and wrong scopes cannot switch the pointer. A valid request yields untrusted PROPOSAL data. AC-01.

### User Story 2 — Execute one externally adjudicated operation (P1)

An authenticated coordinator-controlled executor retains the actual verdict and current hash anchor outside writer control. It verifies the accepted execution image before loading it, adjudicates one proposal, and calls the bounded handler. The handler rechecks the pinned tuple, current state and source inventory; writes only through CAS when the coordinator grants that exact operation; and returns a receipt that the coordinator must verify before advancing its external anchor.

**Independent test**: An explicitly simulated external host proves promotion/retrieval/rollback/result validation and the complete before/after tuple. Synthetic host tests remain synthetic and cannot demonstrate real platform authentication. A real invocation requires independently accepted adapter code and a separate explicit start in the existing external coordinator channel. AC-02/03.

### User Story 3 — Refuse drift and reconcile interruption explicitly (P1)

Wrong provenance, old grants, changed evidence/code/source state, mismatched anchors and interrupted pointer/anchor updates stop the operation. Historical source restrictions remain intact. The coordinator may explicitly reconcile a verified visible result; the adapter never retries a grant automatically.

**Independent test**: Negative tuple/closure/evidence/anchor cases preserve pointer; before/after-switch failures preserve intent and expose divergence; a subsequent call with an old external anchor refuses. Genuine rollback preserves prior snapshots/audit and all 14 restriction payloads. AC-04 through AC-09.

## Requirements

- **FR-01**: Keep the local interface proposal-only. No anchor/grant loader from writer JSON, environment flags, CLI assertions or file permissions; no local data grants authority. Knowledge and receipts remain untrusted data.
- **FR-02**: The coordinator-controlled executor must obtain and retain actual authenticated verdict/provenance outside writer control. Before importing the adapter/dependency closure it verifies exact code/spec/oracle/tests/runtime hashes; the adapter also rechecks current closure before every operation. This callable is not an authenticator of an arbitrary Python caller/provider.
- **FR-03**: Accept only one inspect/retrieve, promote, rollback or validate_result request per call, with strict duplicate-free bounded JSON, known fields, explicit context and resolved references. No commands or broadened scope. Unknown inputs never infer approval.
- **FR-04**: Match the complete externally retained package/provenance/purpose/code/spec/oracle/test/lesson/new-result tuple, explicit start and active version/hash. An inactive T017 PASS alone does not approve the adapter or real consumption. Synthetic results cannot become real by relabeling local data.
- **FR-05**: Apply promotion/rollback only after external adjudication of that exact proposal/grant ID, under the existing lock/CAS and immutable snapshot/fsync/atomic-pointer pattern. Revalidate current/target schema, lineage, evidence and verdict before switching.
- **FR-06**: Verify post-operation pointer/version/hash, intent/audit and complete source inventory before the coordinator advances its external anchor. Refuse stale/replayed grant and mismatched pointer. Interruption never creates an automatic replay, stop clearing or source budget rollback.
- **FR-07**: Result validation requires explicit invocation, applicability, anchored consistent lesson/snapshot and an independently accepted exact new substantive Git decision using the single bounded conflict-preservation recipe. Original raw objects and worktree bytes must match. A reviewed synthetic bootstrap does not prove real use.
- **FR-08**: Retrieval returns untrusted scoped knowledge from exactly one externally anchored snapshot; embedded text is never executed or treated as permission.
- **FR-09**: Preserve all 14 source restriction payloads, budgets/stops, original bytes/mtime and CPU/report transfer invariants. Merchant HTTP remains zero. No new credentials, service, permission/security/network change, global hook, general authority platform or second writer.
- **FR-10**: Learning stays OFF until independent adapter acceptance and a separate verified coordinator invocation. Default/missing host is BLOCKED. A writer-created provider/JSON/receipt is not a genuine external coordinator channel; arbitrary filesystem writes in a writer-writable directory do not become trusted activation.

## Key Entities

Request: operation ID/context/reference data only. Proposal: exact request/tuple/closure/source/state hashes and no authority. External host: trusted deployment dependency in the existing coordinator execution context, not supplied through request data. Anchor: independently retained verdict/provenance/package tuple plus current version/hash and one-operation state. Grant: externally adjudicated, operation-specific, one-use proposal binding. Replica: local immutable snapshots/pointer/audit, untrusted unless independently matched to the external anchor. Receipt: verified visible state/source inventory references for external adjudication, not a local permission.

## Acceptance Cases and Outcomes

- **AC-01**: Local JSON/flags/forged approval and duplicate/unknown fields reject or remain PROPOSAL/OFF without pointer switch.
- **AC-02**: Simulated external host performs exactly one bounded operation with explicit synthetic tagging; all tuple/closure/state checks and returned receipt agree.
- **AC-03**: Real operation is BLOCKED without independently accepted adapter purpose, genuine external host and separate explicit start. No synthetic bootstrap is relabeled.
- **AC-04**: Wrong provenance, package/version/hash, code/spec/oracle/test/lesson/result/context or changed closure refuses before switch.
- **AC-05**: Stale external version/hash, reused grant or unfinished grant refuses; no blind replay.
- **AC-06**: Promotion/rollback revalidates evidence, full snapshots, visible ancestry and independently granted exact lesson/result.
- **AC-07**: Hostile active text and Git callbacks/replacements cannot execute or virtualize result proof.
- **AC-08**: Before/after pointer failures retain audit; pointer/anchor divergence blocks further calls until explicit external reconciliation.
- **AC-09**: Verified rollback and transfer preserve all source payload bytes/mtime/budgets/stops, and prior lesson/audit history.
- **AC-10**: Full/native/fresh-consumer exact-SHA evidence and independent review are separate from real channel/start evidence; unavailable host integration is disclosed and accepted T016 with learning OFF remains the product fallback.

## Assumptions and Explicit Boundary

The implementation can provide a bounded coordinator-side handler and local proposal helper. The actual authenticated coordinator provider/executor is supplied outside the writer workspace through the existing platform, and is never inferred from class names, directories, chmod, callback return flags or JSON. Before deployment the coordinator verifies and loads the accepted closure in its trusted execution context. Tests use a clearly simulated host; they do not establish real authentication. This task will not manufacture an actual real-operation verdict or claim that the existing platform has been exercised before independent acceptance and a verified start.
