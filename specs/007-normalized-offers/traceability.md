# Traceability 1.0.3

| Source requirement | Binding acceptance | Evidence |
|---|---|---|
| Product §§10–11: exact product, quantity, warranty and Moscow fulfillment | OFFER-01–06 | test_normalized_offers.py: primary field, unknown, quantity, warranty and stock cases |
| Product §12: independent sellers | OFFER-07 | canonical listing and evidenced seller entity cases |
| Product §§13–14: verifiable comparable current costs | OFFER-03/08/09 | exact Decimal, missing costs, five-format readback and tamper cases |
| Methodology §§9–14: recorded decisions and reproducibility | OFFER-10/11 | subprocess CLI, durable backup/restore and protected parent scope |

PAY hard rules call src/pc_sourcing/evaluate.py unchanged, including all 19 priced
original golden cards. Unknown price context remains a separate negative case.
Identity uses the accepted T010 functions. No original source price is an input.
Every ranking compares the same request; exact and analogue groups stay separate.
No historical assertion expectation or source stop has been edited. CP-T012-01
now has explicit user authorization and only its exact fixture setup patch is applied.

Independent review evidence: libfile_707b9e9b65dc8191a842a3346ef9738a, version 0,
SHA256 490ae1a1aa76dc31f7cd0fd128e51a10bed0ec84a431742871723b527e3ff36d.
F-SCOPE/F-PAY/F-DECIMAL are covered by explicit context conflicts, known/null
postpay controls and equivalent decimal evidence tests. F-BATCH is covered by
canonical duplicates, reordered/later-as-of idempotency, generation conflict and
second-insert transaction rollback. F-XML is covered by schema-valid control text,
structured subprocess failure, input/runtime preservation and valid CR whitespace.
Alias raw/runtime versus canonical/export cardinality is explicit and tested.

Independent v3 rejection: libfile_25ec21d7085c81919d7bb6f942b70dde, version 0,
SHA256 5b31bff024c415005413fd526b13abcc9bbb583d3f9dc57b68bf1733ace91098.
Collision/precedence repair is covered by canonical/camel/spaced boolean aliases,
contrary/null/unknown/list claims, agreeing controls, manufacturer/brand,
capacity/VRAM, MPN/SKU and profile aliases, nested additionalProperty, an explicit
supported analogue and an absent MPN binding. Assertions and provenance are
preserved in the canonical row and therefore all five exports.

CP acceptance: historical T011 positives/negatives and successor rejection remain
active; T012 separately rejects parent code/test/gate drift, missing or altered
CP hash binding and reverting the approved fixture setup. Final acceptance still
requires independent review of the exact published SHA, separate from WIP PASS.
