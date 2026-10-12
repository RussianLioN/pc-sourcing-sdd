# T015 selected Product extraction — revision 1.0.0

Base 79df7e5a04a9a54b4ee2122c4729459bfd512bae has independent limited
engineering PASS (libfile_51ab29779b2081918c9fb509cb7c27aa; hash
e7e6046fe9fe88bd95600357a05504e8c7e7141bb419562759ef144ca8ec3fc0). This additive offline module cannot change the
in-flight review, old observations, acquisition ledger, budgets or gates.
Source: original product §§10–14, PAY applicability and evidence requirements;
T010 typed identity contracts; T013 CHAIN-01–04 and review F2.

| ID | Requirement | Acceptance |
|---|---|---|
| EXTRACT-01 | Select the one JSON-LD Product bound to the candidate URL; multiple unbound/matching Products fail closed | footer/recommendations excluded; two matching Products unresolved |
| EXTRACT-02 | Identity and price conditions come only from selected Product name, description, attributes and its own Offer; internal conflict remains | 32 GB vs 96 GB inside Product blocks; footer prices/specs do not contaminate |
| EXTRACT-03 | Exact original bounded price token, JSON selector, URL, source timestamp and retained hash survive parsing; positive RUB Decimal locale grammar, no float guessing | spaces/NBSP/narrow spaces and decimal comma/dot; malformed/range/zero/foreign/float rejected |
| EXTRACT-04 | A parsed numeric amount is displayed only, never unconditional/full purchase price; installment/deposit/discount tokens remain visible but not regular amounts | credit/deposit context, priceSpecification and multiple offers unresolved |
| EXTRACT-05 | Schema Discontinued maps to unavailable with original schema value retained; unknown availability remains unknown | http/https schema values, unknown token |
| EXTRACT-06 | MPN from title has explicit title-derived selector; bounded supported code grammar, exact token boundaries and structured/title disagreements fail closed | target code in title, neighbouring code, two codes, negation or conflicting Product.mpn |
| EXTRACT-07 | Reuse frozen identity validation; do not convert MHz to MT/s, infer stock/quantity/payment, clear unknowns, or promote original captures | actual retained captures remain untouched; buyer readiness never asserted |
| EXTRACT-08 | PAY-01 applicability follows source=avito; stores can retain unknown route data without failing the payment gate | fully proven synthetic store vs same Avito row |
| EXTRACT-09 | Separate safe user report contains only saved observations, dates, URLs and limitations, no logs/credentials | Library report content review |
| EXTRACT-10 | All parent tracked bytes protected; new task owns only listed additions; exact SHA review and integration remain separate | scope/hash checks; historical T013 fixture CP proposed, not silently applied |

No new HTTP, network configuration, budget initialization/reset, credentials,
seller contact, accounts, deployment or bot. Input HTML is untrusted data.
No primary capture is retroactively relabelled. The first deliverable is a
standalone offline parser and CLI, not a new production acquisition adapter.
Integrating into frozen T013 transport/fingerprint requires a separate reviewed
change. Full product DoD and live coverage remain pending.

Layouts: selected JSON-LD Product (REGARD-style) and nearest-owner scalar microdata
(28BIT-style). Exactly one URL-bound Product wins; one unbound Product may use
the explicit page candidate binding, never an explicit wrong URL. Multiple unbound
Products fail. JSON-LD @id/link-to-related-product edges are not own attributes;
unknown material attributes, owned descriptions/headings and contradictory codes
remain validated. JSON numeric lexemes are retained without binary float conversion;
unsafe credential/control/overlong scalars are not copied to evidence. Ambiguous
input still produces an unresolved coverage record, never an eligible offer.

Frozen Capture -> Journal -> normalized exports/report/backup/restore is tested.
The standalone CLI parses local bytes or reads immutable historical Capture.
Metadata hashes are integrity links, not authenticated source origin. Unsupplied
original HTML/JSON-LD is never reconstructed from partial historical metadata.
Historical capture date and classification remain untouched; current freshness is
not asserted. No transport/profile or old worker fingerprint changes in this stage.

CP-T015-01 was coordinator-approved for the exact historical positive setup hash
transition. Assertions and negative cases/checker remain unchanged; original
historical full-suite failure is retained. GPU smoke is planned only;
see docs/gpu-smoke-plan.md for stops, expiry, explicit new budgets and fixed URLs.

Independent WIP rejection: libfile_fb84996acf8481918dadc82df07245bd, SHA256
8af8394ced695cd9eba36ca5c61fb96d4f8f54a4b7573c3a765e5efe80f9f5e6.
EXTRACT-11: reject all repeated decoded JSON object members before dict creation,
including same-value duplicates, escaped equivalent keys, nested Offers/PropertyValue/
arrays/graphs and both orders. Return unresolved with original date/body hash and
no promoted assertions. Separate objects can repeat their own member names.
New scoped decoder and frozen Capture/Journal bridge are offline-only. Reusing
T013 acquisition sanitizer with T015 witnesses is incompatible (drops price_tokens,
displayed_price_rub and Discontinued stock witness). Future live controller must
retain validated new scalar metadata via a separately reviewed integration; do not
connect the new parser to old sanitizer or perform HTTP in this repair stage.
