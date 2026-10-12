# Traceability

Original product §§10–14 → CHAIN-01–04/07/08; methodology §9 → CHAIN-05/06/10.
LIVE-03/04 and original access constraints → CHAIN-09, source-route-plan.md.
OFFER-01–11 remain frozen at T012; this stage consumes those contracts.
No assertion of full product DoD from offline replay or tests.

Preliminary independent rejection: libfile_044a2ceb46f0819183030a125460d742,
SHA256 0144a280980d2c75a18b0ef6d932b17f77f39106509e82f0424ba6101ff6a9af.
F1 output drift → deterministic derive_output equality before report/restore.
F2 fact/witness mismatch → selected JSON value/kind and top observation binding.
F3 empty production state → prior baseline required, separate no-overwrite state
snapshot, marker/ledger and spent-counter validation. F4 schema/realm drift →
exact table/columns/states/fingerprint/realm checks. Tests reproduce output injection,
field/kind changes, empty canonical state, ledger row deletion/counter/column drift,
state snapshot tamper and protected CP rollback.
Live evidence: 28BIT 09:21:11 UTC (ambiguous MHz basis) and REGARD 09:43:54 UTC
(malformed/conditional price; no MPN). Both unresolved and not promoted; source
verification gaps are independent of successful transport/persistent integration.

Second recheck rejection: libfile_7912348709688191afc32d43467b26b6,
SHA256 9afec20d0be666f2c6f748efe90111e74eaa74d6846727a793bce85341ecd29c.
F3 zero-byte ledger -> test_damaged_production_ledger_refuses_without_mutating_any_state
(zero/truncated_header/truncated_pages/malformed/empty_sqlite), exact bytes and
file inventory compare. F4 constraints ->
test_runtime_schema_constraints_types_indexes_reject_identical_columns and
test_source_schema_constraints_and_indexes_are_protected. Positive canonical
reopen and backup/restore remain tested. Initial reproducer: 13 failures retained.
