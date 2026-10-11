# Tasks revision 1.0.0 — execution ledger
Immutable assignments are tasks/T001.json, tasks/T003.json and tasks/T003-r2.json; T002.json is
the common integration scope assignment. Historical assignment readiness is
not a current product acceptance claim. Exact final status is in the external
SHA-bound receipt `artifacts/acceptance/manifest.json`.

- [x] T001 Initial real writer, base a5de9fedff6d413ca2a3b1d9a93be25895402d60,
  own evaluate/pipeline/test_worker only. Integrated after scope gate.
- [x] T002 Sequential integration and common snapshot scope task; first real
  independent review completed and found defects. Final review status is
  recorded in the acceptance receipt, not assumed from process exit.
- [x] T003 Real repair round 1/2 at 726875ab164c926de8c2d270b9fc5776935a68f8,
  two regression failures fixed; immutable baseline preserved; integrated.
- [x] T003-r2 Final repair round 2/2 at 5ee6496ab72292635cdb71a7f78fa86377f3b7ce,
  oversized numeric raw JSON preserved, numeric id rejected; scope-gated integration.
- [x] T004 Bounded runner probes completed, outcomes in runner-probes/results.json.
  Running recovery remains blocked. Historical synthetic steps are labeled.
T005 status is evaluated dynamically by the external receipt and
`check_acceptance.py`; a static checkbox cannot accept a later Git snapshot.
It is passed only when the final independent same-SHA review and every
required gate pass. Missing or failed receipt means unaccepted.

No additional writer or feature expansion is ready. Next product step requires
a lawful local primary-source route with explicit budget before live smoke.

Continuation 1.0.1: user superseded the former 2/2 stop. Historic tasks remain
immutable evidence; T006 Unicode repair and runner loop verification are
new narrow work. Final acceptance remains receipt-bound, never checkbox-only.

- [x] T006 Actual Unicode writer; protected regression suite and scope gate
  passed (273 tests). Sequentially integrated; final independent review is
  evaluated only by the same-SHA receipt.
