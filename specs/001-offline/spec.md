# Offline sourcing pilot — revision 1.0.0
Source: Library libfile_6032ad2fa60081918e1211d8ae62ad59, sections 9–14;
earlier product context libfile_89e134d178e08191b23a0d461814b7a3.

Goal: given a local versioned synthetic corpus, validate, evaluate, preserve
every input in SQLite, and emit a readable report for Moscow sourcing.
Targets: G5090-32SLC (MSI RTX 5090 32G SUPRIM LIQUID OC),
F5-6000J3036F48GX2-TZ5NR (G.Skill 96GB), Logitech G PRO X2 SUPERSTRIKE.
Non-goals: ranking live deals, purchasing, retailer integrations, scheduling,
seller contacts, production migration, fuzzy identity and a second writer.

| ID | Binding requirement | Acceptance evidence |
|---|---|---|
| SKU-01 | Exact identity separate from analogue; SOC excluded, cooling preserved | golden + exact identity tests |
| EVI-01 | Evidence per field: URL, UTC time, origin, offer id, value | model + provenance tests |
| EVI-02 | Snippet never confirms stock, price or eligibility | golden snippet + property |
| PRICE-01 | null unknown; positive RUB only, never source-spec prices | invalid/unknown/currency cases |
| STOCK-01 | preorder stays preorder and outside verified list | preorder golden |
| PAY-01 | independently fully applicable protected OR postpay route | decision table + property |
| PAY-02 | symmetric OR; route conflict differs from global conflict | golden branches |
| PAY-03 | mandatory global advance blocks; optional alternative does not | golden + property |
| OUT-01 | one evaluation drives DB, report and verified list | SQLite/report contract |
| OUT-02 | invalid input retained as rejection with raw JSON and reason | invalid corpus contract |
| OUT-03 | synthetic status and all evidence retained | report + DB tests |
| RUN-01 | idempotent run keyed by input/spec/code/as-of; changed input rejected | rerun contract |
| SDD-01 | task pin, protected golden baseline, scope gate, common snapshot | coordinator audit |
| SDD-02 | bounded repair, failures persisted, actual independent Codex verifier | worker evidence |

JSON contract v1.0.0 is `src/pc_sourcing/models.py`; generated schemas are
`specs/001-offline/contracts/`. Full applicability covers item, entire amount,
region and order terms. Unknown coverage or unknown external advance is
insufficient. Protected route requires platform_transaction evidence;
postpay allows seller_statement. Evidence must belong to this offer, match
the field and value, and be at most 24h old, no future timestamps (pilot
freshness policy; live policy requires separate review).

Verified means: exact SKU, factory cooling where required, positive known RUB
price, in_stock, Moscow, new condition, checked seller, current field evidence,
non-snippet source, and payment pass for Avito. This is a data eligibility
label, not a safety guarantee or purchase authorization. Preorder may be
conditional but never verified. Under-order Avito with failed payment uses
exact `требует ручной проверки` with a specific reason. Valid rows are never
dropped; malformed/duplicate rows are retained separately with error details.

No live data permitted in synthetic fixtures. Public indexed search can only
produce candidates. Avito direct access previously denied: never retry by
changing channel/identity. Local Tavily absent => live blocked.
