# Traceability 1.0.0

PRIMARY-01/02/03 → curated_primary.py → tests/test_curated_primary.py.
PRIMARY-04/05/06/07 → curated_primary.py/live_models.py/live_sourcing.py → same suite,
actual fixed-origin 28BIT card receipt (Palit excluded from MSI factory Liquid).
PRIMARY-08 → CLI/state/observation/report equality + transfer tests.
PRIMARY-09 → scripts/primary_scope.py, full quality and independent exact-SHA review.
No prior receipts or immutable old assertions/specifications change.

CP-T010-01 approved: exact setup-only historical T009 checkout pin; every assertion
unchanged. primary_scope byte-checks exact insertion; new regression proves frozen
T009 gate rejects T010 additions. No old allowlist/checker/contracts/receipt changed.

Independent review repair cases → live_sourcing.identity/parse_card and
curated_primary.observe/ProductScope → additive review regressions in
test_curated_primary.py. Conflicting fields remain unknown/unresolved; no oracle
was changed. CP-T010-02 is pending for one protected contradictory assertion.
