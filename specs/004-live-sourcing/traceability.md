# Traceability 1.0.0

LIVE-01/02/06/07/08/09/10/11 → T009 → tests/test_live_sourcing.py.
LIVE-03/04/05 → T009 → tests/test_live_transport.py + test_live_sourcing.py.
LIVE-12 → T009 checks, реальные saved connector responses, independent parent review.
Полное исполнение LIVE-03/05 и DoD coverage требует T010–T012; unit fixtures
проверяют код, но не доказывают разрешение сайта или свежую цену.

## Approved narrow repair after review fb07134

CP-T009-01: docs/adr/0002-t008-historical-test-fixture.md; only protected fixture
setup pins accepted T008 snapshot. tests/test_stage_acceptance.py guards historical
assertions/contract and proves current T009 remains unowned by T008. Full pytest
must execute all 27 former setup failures; no previous error becomes passed by fiat.

LIVE-04: checked robots content/status/denial and conservative unsupported-pattern
stop; managed proxy only fixed keyless search endpoint, generic primary URLs blocked
because proxy destination IP cannot be bound to local DNS. Direct TLS remains pinned.
LIVE-05/06: malformed typed/Unicode/oversized values isolated per card, field unknown;
LIVE-07: token-aware 5090/OC/SOC and explicit cooling conflicts;
LIVE-10: conditional cash/discount/subscription prices remain unknown.
All reproducer regressions are in test_live_transport.py/test_live_sourcing.py.
