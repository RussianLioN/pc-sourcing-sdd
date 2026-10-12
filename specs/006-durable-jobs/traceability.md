# Traceability 1.0.0

Product §9 → OPS-01/02/04/09, queue→source read→receipt→report.
Product §12 → OPS-01/06, canonical/context dedup; seller independence remains unknown.
Product §13 → OPS-02/03, per-source serialized work/cooldown/budget/stop.
Product §14 → OPS-04/06/08/09, UTC/URL/immutable evidence and portable report.
Methodology §9/10/13/14 → OPS-05/07/10, crash/recovery/explicit blockers/exact snapshot.
All OPS cases → tests/test_durable_jobs.py; scopes → tests/test_durable_scope.py.
No T008–T010 specification, assertion, gate or receipt is changed.

OPS-09 → durable_product.prepare_product_fixture → real T010 parse_card →
durable_cli.fixture_jobs/work_once → Store checkpoint/history/current → report,
backup and restore. tests/test_durable_product.py verifies full CLI/product path,
changed request/code context, immutable generation input and synthetic provenance.
T010 limited engineering verdict supplied by coordinator is recorded in T011 task
with exact SHA/Library evidence/version/hash; this does not accept this runtime.

OPS-02 startup regression: original constructor failed Busy before barrier. Startup
now shares schema/integrity under a bounded two-second lock; claim still fail-fast,
old test assertions preserved. Two-process claim, stale checkpoint, lock timeout,
canonical origin alias and independent-origin progress regressions enforce isolation.
OPS-05/07/08 →31 named write-boundary SIGKILL scenarios, including precommit, partial
blob, atomic publication, backup and restore. CLI SIGKILL checkpoint recovery proves
no fetch after checkpoint and no additional transport budget, not exactly-once reads.
