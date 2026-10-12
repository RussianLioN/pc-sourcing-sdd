# T016 plan

Use pinned Python, frozen Capture/Journal/normalized exports, T015 strict decoder
and scoped extractor. No dependency or protected-file changes.
1. Specify new controller and exact small profiles; write tests and keep red receipt.
2. New witness controller explicitly bootstraps only new reviewed GPU state, never
   production RAM. Constructor/status/replay validate existing state read-only.
3. Retain extractor metadata exactly after safe T015 filtering. Bind all receipt,
   selected/capture hashes, source scope/realm, strict canonical SQLite schema.
4. Production gate consumes a local operator-supplied independently reviewed
   exact-SHA receipt with pinned hash; no source-derived instructions or release.
   Hash is integrity, not cryptographic proof of reviewer identity.
5. Injected transport is synthetic; test full acquisition chain and faults. Actual
   RAM data exercises immutable T013 checkpoint consumption, not fresh HTTP.
6. Transfer complete old/new source state separately from CPU journal, preserving
   strict schemas, original stops, spent counters and selected evidence.
7. Propose exact historical T015 positive-fixture CP to coordinator; no protected
   patch before approval. Run scope, meaningful full/negative/e2e tests and native
   workflow on exact commit; publish separate candidate/evidence and request review.
8. After independent controller acceptance only, run serial known GPU routes with
   one robots + one card per source and reproducible CLI; never reset old budgets.
