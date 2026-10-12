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

CP-T010-02 approved on 2026-10-12 against 2a75952: exact sole expected
literal correction, bound byte-for-byte in primary_scope. Full legacy assertions
otherwise remain unchanged. VRAM, RAM timings/speed/profile/form factor, partial
items, regional/revision MPN and missing model regressions extend PRIMARY-04/05.
Aftermarket factory contradiction remains unresolved pending manufacturer evidence,
rather than excluded: this is more conservative and agrees with the frozen 60-card
oracle; the earlier 25-card oracle used excluded for that same conflict. Both labels
block purchase; this discrepancy is disclosed, not an edited reviewer oracle.

PRIMARY-03 cross-run rate-limit preservation → PersistentSearch CLI wrapper →
429/403/CAPTCHA/timeout persisted-stop regressions. Original observed 429 receipts
remain retained; no new keyless request after stop persistence. Existing primary
card capabilities may be read independently without altering denied search access.

Independent metamorphic repair → identity_attributes.py sets of normalized facts
(capacity/topology/memory type/speed units/CAS aliases/profile negation/full-item
role/factory cooling origin), compared with requested/known target attributes before
MPN exact-match. Product.name/description, visible text and named structured
properties participate; conflicting values never use last-value-wins. Existing
hard exclusions remain explicit; missing model is unresolved. PRIMARY-06/07 →
tests/test_identity_attributes.py (paraphrases, structural/visible conflicts and
positive controls) + frozen60 + independent metamorphic13. No new live receipts.
T011 WIP preserved separately until T010 reviewer authorizes continuation.
