# T012 normalized offers and consistent exports — revision 1.0.3

Authority: coordinator explicitly assigned additive product offer normalization and
comparison/export stage. Parent T011 daabf63 has limited independent engineering PASS only;
T010 bd70f4f has limited engineering PASS only. All parent tracked files are frozen except the exact approved CP-T012-01 setup patch.
Source basis: original product document §9–14,17–18 and methodology §9–14.
No source queries, stop reset, credentials, hosting, Telegram, purchases or contacts.

| ID | Binding requirement | Executable acceptance |
|---|---|---|
| OFFER-01 | Versioned frozen normalized offer/request, exact nullable values for quantity/complete condition/warranty/Moscow fulfillment/seller/price/costs/payment | schema/negative/unknown0/decimal tests |
| OFFER-02 | Money uses Decimal from string/int, never float; unconditional vs conditional/deposit/installment separate; quantity/basis/context explicit; old source-spec prices never read | unit/purchase totals, conditional/non-RUB/unknown cost cases |
| OFFER-03 | Every positive conclusion uses matching primary non-snippet field evidence with URL/UTC/selector/retained fragment hash; conflicting/current/future/stale facts remain gaps | hash tamper, owner/realm/reference, field TTL/conflict tests |
| OFFER-04 | Reuse T010 identity checks; exact/analogue/excluded/unresolved separate, MSI factory liquid mandatory; analogues require differences/compatibility context | raw/model disagreement, OC/SOC, analogue compatibility cases |
| OFFER-05 | Reuse unchanged v1 evaluate for PAY OR and hard global advance/conflict; new route context proves MPN/quantity/item amount/order/Moscow; unknown data retained | all original route combinations, conflict/advance/snippet/context negatives |
| OFFER-06 | Full selection requires confirmed quantity/completeness,new or sealed,warranty,Moscow fulfillment,seller check/current evidence; stock supplier/under_order never in_stock | positive fully evidenced controls and each missing gate |
| OFFER-07 | Listing canonical URL/context dedup; independent sellers only with current evidenced entity/profile key; names/domains alone never prove independence | cross-domain same entity; unknown relations; no denominator inflation |
| OFFER-08 | Compare exact and analogues separately; full total only if all relevant costs known, unknown not free0; conditional prices separate; source gaps visible | cheapest snippet/deposit/unknown shipping can't be ranked as full price |
| OFFER-09 | JSON/CSV/XLSX/Markdown and SQLite generated from one canonical row dataset, evidence retained; formula text literal, monetary precision exact | readback equality, archive/XML validation, export integrity tamper |
| OFFER-10 | Explicit durable bridge stores normalized decisions as synthetic receipts; no fabricated live record or True→False realm conversion; restart/backup preserves full data | actual CLI/durable+report e2e; real import refused by synthetic runtime |
| OFFER-11 | Additive scope preserves every parent blob and old gates; exactSHA full checks, handoff, independent review | protected drift tests/common workflow |

Mandatory synthetic flag is retained at offer/evidence/report. Positive synthetic
controls may satisfy data gates but never represent live purchase readiness.
Real imported records remain real; T011 synthetic-only runtime refuses them rather
than silently relabel them. No live sourcing result is manufactured by this stage.

Private PAY projection calls unchanged models.Offer/evaluate and returns only payment
route gate/result; nonpayment placeholders are explicitly internal, not offer facts.
Nullable public route coverage is interpreted as confirmation predicates for this
adapter, never rewritten in normalized output. OR across independently valid routes
and mandatory external advance/global conflict behavior remain unchanged.

Freshness defaults: price/stock/quantity/fulfillment/costs ≤3600 seconds; other offer
identity/condition/warranty/seller/payment claims ≤24h. Future claims fail. Hashes prove
retained integrity, not authenticity or physical warehouse stock. No implicit refresh.

Schema data includes request, model/MPN/attributes, source/listing URL, timestamps,
requested/available quantity, completeness, condition, warranty, fulfillment,
seller name/verified entity key/check, price alternatives, delivery/other costs,
PAY routes/global flags and field evidence. Unverified shipping/other costs are null.
Stock has in_stock,supplier,under_order,preorder,unavailable,unknown. Whole-item amounts
and requested-quantity context are distinct from full cost including delivery.

Readiness remains a data decision, not purchase safety; full product acceptance still
needs real permitted multi-source/user e2e and reproducible authorized operation.

Independent WIP review repairs (revision 1.0.3):

- OFFER-03: an explicit recognized evidence scope must match the offer MPN,
  requested quantity, region and owner/listing when present. Money field scope
  additionally binds amount/currency/price ID and price basis/kind. Missing
  optional scope is distinct from an explicit null or contradictory declaration.
  Scope conflict cannot confirm a positive gate; raw metadata remains retained.
- OFFER-02: economic equality compares validated Decimal amounts in a canonical
  two-decimal representation. Original evidence value spellings remain retained;
  floats, booleans, nonfinite or excessive precision remain invalid money inputs.
- OFFER-05: unknown/blank MPN cannot prove item context by equality with another
  unknown value. The frozen PAY evaluator and independent route OR are unchanged.
- OFFER-09: unsupported XML 1.0 characters cause a structured CLI rejection
  before runtime or export mutation. Input is preserved byte-for-byte; no silent
  deletion/replacement. Valid whitespace is preserved by XML encoding.
- OFFER-10: batch source configuration and enqueues commit in one T011-compatible
  SQLite transaction under its existing cooperating lock. Every input conflict
  and unrelated ready job is checked before mutations. SQL failure rolls back
  the whole submission; receipt/worker crash guarantees remain those of T011.

Runtime/export layer contract:

Runtime is the raw canonical-URL/context observation layer, not the normalized
comparison view. URL aliases of a shared listing ID can yield two runtime current
receipts and one comparison row; the rejected alias and evidence remain in the
canonical report dataset. Same URL/context observations within one batch are
coalesced to one job, with latest timestamp then descending ID as deterministic
selection and all source records retained in receipt facts.raw_observations.
The comparison uses the same timestamp/ID tie-break and retains duplicate records
in rejections. No assertion of equal runtime/export row counts is made.

Input hash binds raw observation declarations and excludes evaluation clock.
Reordered identical batches and a later as-of reuse immutable same-generation
receipts; their original decisions/as-of remain unchanged. Comparison/export
re-evaluates the imported data at its explicit as-of. Changed inputs require an
explicit refresh generation, never an automatic budget or stop reset. Pre-repair
WIP roots with the older hash contract are not silently migrated or rewritten.
There is no atomic transaction joining runtime completion and export publication;
export preflight runs first, while the durable worker retains its independent
restart/lease/checkpoint behavior if export later fails.

Identity collision repair (revision 1.0.3):

OFFER-03/04 independent assertions have no dictionary override precedence.
Offer title, structured attributes and top-level material values are extracted
as separate typed claim streams through the unchanged T010 grammar. All claims,
including explicit unknown/null declarations, retain source and raw value in
identity_assertions; original attributes remain in the offer. Alias reconciliation
uses normalized attribute/scope/unit/polarity, never the original key spelling.
Contradictory positive declarations or a positive/negative collision block identity
readiness even for identity dimensions without a request-specific expectation.
MPN aliases bind to the actual offered item; they cannot override its MPN or
silently supply an absent top-level binding. Request versus offered MPN remains
classified by unchanged identity(), preserving supported explicit analogues.
The frozen validator and PAY rules are not edited. Agreeing aliases remain valid.

CP-T012-01 implementation binding (revision 1.0.3):

The user explicitly authorized the two-line historical T011 fixture setup patch
and publication to feature/cloud-portability without merge. The historical gate,
helper, zero-patches expectation and negative cases remain unchanged. T012 scope
binds original and approved SHA256 values, reconstructs the exact two-line patch,
and rejects missing/altered binding, reverting the required patch, any additional
protected drift or unowned files. 182 parent blobs remain identical; the sole
183rd file equals the explicitly approved bytes. No other protected edit is allowed.
