# Identity assertion extraction contract 1.0.0 — prospective repair

Source: product §10/11, original identity/unknown rules; coordinator instructed a
schema correction after independent holdout rejected abfe280. This changes technical
extraction, not product restrictions, oracle labels or purchase eligibility.

Each assertion records attribute, typed value, original unit, semantic scope,
polarity (positive/negative/unknown), selector/source and literal raw declaration.
Comparisons use compatible scopes and units only. MPN agreement never erases an
explicit conflict or unknown material declaration. Independent assertions persist.

Capacity: total kit/product versus per module; topology derives total only from
explicit module count × module capacity. Speed: effective DDR rate MT/s versus
physical clock MHz/GHz; GHz↔MHz is dimensional conversion, and DDR factor two is
used only for an explicitly physical clock. A named memorySpeed vendor grade in
MHz is labelled advertised grade, never a measured physical clock. Unscoped MHz
is unknown. Latency: CL/CAS cycles versus ns; ns is not CAS cycles without explicit
physical-clock evidence; with one unambiguous physical clock, cycles = ns × MHz /
1000, preserving the original ns assertion and clock provenance. Revision unknown remains unknown.

Supported structural envelope: Product scalar canonical attributes and bounded
additionalProperty PropertyValue entries with names mapped by material concepts:
manufacturer/model/variant/revision/regional code, memory capacity and scope,
rate/clock/latency/profile/form factor, item role/presence and cooling provenance.
Unsupported material declarations become unresolved. Nonmaterial properties are
not manufacturing evidence. No property name creates a network capability.

Text grammar is bounded: number+unit declarations, kit topology, named profile
support, explicit role-only/presence/cooling declarations and clause-local negation.
Negation is scoped to its proposition, not the whole document: 'not SUPERLIGHT'
does not negate SUPERSTRIKE; 'not receiver-only' does not assert receiver-only.
Unknown/unverified material values never become false or true. This is not a
promise to interpret arbitrary prose. Unsupported descriptions/critical modifiers
must remain unresolved rather than be made exact by the product code.

Acceptance: independently frozen60, metamorphic13 and holdout72 are separate generic
JSON-LD route metrics, never pooled with curated microdata probes. Own tests cover
unit/scoping pairs, positive/negative inversion, structured mapping, unknown and
both adapters. No new live reads. Exact SHA full regression and independent review.

Advertised-MHz compares only the nominal grade numeral against the requested DDR
grade. It is a separate expectation, not a unit conversion into MT/s or a physical
clock assertion. A value explicitly in MT/s compares with effective transfer;
a value explicitly labelled clock compares with physical MHz. Raw source unit
remains in retained assertions. No measured clock is inferred from a vendor label.

Boolean scalar correction: explicit JSON/string true/false preserve their value and
source polarity; inverse predicates retain negation rather than inventing a positive
fact. Free-form boolean strings yield all supported propositions with clause-local
prefix and predicate-postfix negation. Positive-word occurrence alone is never True.
Unknown, unconfirmed or unsupported strings yield unknown. Contradictory propositions
are retained. Capacity subject binds to the nearest role marker within its declaration
clause, with separators delimiting scope; prior module labels never capture later totals.

Boolean free strings use a bounded declaration grammar with domain predicate words,
connectors, negation and supported presence/install verbs. Unparsed words/questions
produce unknown, never positive truth from a recognised substring. Explicit module
count in a completeness declaration becomes a separate kit-scoped assertion. This
restricts technical parser capability, not the product rules or frozen oracle.

Numeric polarity correction: all text numeric builders and scalar numeric/enum
PropertyValue parsers use the same prefix/postfix polarity. Frequency/clock never
force positive; copula+negation between a latency label and value is preserved.
Ambiguous qualifiers (maybe, not necessarily, not only) are unknown, not negated
confirmation. Recognised material numeric fragments outside the bounded grammar
become numeric_unknown rather than silently disappear.

Topology and named DDR grade are compound assertions. Only positive compounds
derive component count/capacity/total or independent generation/rate. Negating a
combination does not negate every component or the total. Tuple assertions retain
their unit/scope and are serialised as typed arrays. Numeric subjects bind locally;
a preceding physical-clock declaration cannot capture a later effective rate.
