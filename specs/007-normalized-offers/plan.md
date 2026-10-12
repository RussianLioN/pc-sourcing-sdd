# Plan 1.0.0

1. Freeze task/spec and acceptance before implementation; additive ownership only.
2. New normalized_models.py with strict Decimal/null/evidence contract. Reuse Request,
identity, v1 Route/Offer/evaluate; no fork of PAY decision logic.
3. normalized_offers.py: field confirmation/freshness/context checks, price totals,
listing/seller dedup, separate exact/analogue/conditional comparison rows.
4. normalized_exports.py: canonical SQLite/JSON/CSV/Markdown plus minimal standards
XLSX via stdlib zip/XML (no new dependency or protected lock edit).
5. normalized_cli.py: offline import/evaluate/export and explicit synthetic durable
receipt bridge. Existing live/durable CLI files remain frozen.
6. Unit/negative/integration/e2e, full common snapshot, additive gate, exact commit,
secret scan and private handoff; independent review by coordinator.
