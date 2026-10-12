# CP-T010-02: correction of contradictory identity assertion

Status: approved by coordinator on 2026-10-12, against proposal commit
2a75952eab506f0dc7da3135d2606be2d8462729.

The independent review identified an OC manufacturer MPN paired with an SOC title.
These declarations conflict; the model must remain unresolved rather than assert
an analogue. This follows existing exact-artikel and unknown-value requirements.

The concrete requested protected-file change is one expected literal in
`tests/test_live_sourcing.py::test_mpn_does_not_hide_soc_conflict`:
`"analogue"` → `"unresolved"`. Preserve the input, function, and every other byte
except that literal. No fixture, contract, historical receipt, source specification,
other assertion or checker changes. Strengthen the check; never suppress it.

Current implementation fixes the conflict, so the unchanged protected assertion
fails. The failed receipt is retained in artifacts/T010/review-repair-tests.txt.
Authorization received; bind the exact byte patch in primary_scope and task T010,
then run full quality checks, commit a precise SHA and request independent review.

Additional review repairs: aftermarket liquid exclusion, contradictory kit capacity,
visible open-box versus NewCondition, deposit versus purchase price, conflicting
manufacturer declarations, Product.name versus h1, and multiple Product scopes.
Their regressions are additive in the T010-owned test_curated_primary.py.
