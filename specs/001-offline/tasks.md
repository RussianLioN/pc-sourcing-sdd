# Tasks revision 1.0.0 — execution ledger
Immutable assignments are tasks/T001.json and tasks/T003.json; T002.json is
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
- [x] T004 Bounded runner probes completed, outcomes in runner-probes/results.json.
  Running recovery remains blocked. Historical synthetic steps are labeled.
- [ ] T005 Final independent same-SHA review and acceptance receipt; completes
  only when the actual manifest and check_acceptance.py confirm all required gates.

No additional writer or feature expansion is ready. Next product step requires
a lawful local primary-source route with explicit budget before live smoke.
