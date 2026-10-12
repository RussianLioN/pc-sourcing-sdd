# T011 durable sourcing runtime — revision 1.0.0

Authority: coordinator explicitly authorized additive durable jobs, checkpoints,
recovery, inter-run dedup, per-source restrictions and backup/restore. Parent T010
checkpoint bd70f4fceff1199726d89c86dd7e16085f934be2 has limited independent engineering PASS,
reported by the coordinator; full product acceptance and T011 are excluded. All its tracked files are byte protected.

Source basis: product document sections 9, 12–14, 17–18; methodology sections 9,
10, 13–14. This runtime is distinct from the protected Spec Kit development runner.
No network transport, host/service, credentials, Telegram or purchases. Fixtures
and their outputs explicitly synthetic. Existing source stops never reset/imported
as permission. Offline runtime completion is not full product acceptance.

| ID | Binding behavior | Executable acceptance |
|---|---|---|
| OPS-01 | Jobs and canonical listing/context/generation keys durable in SQLite; repeated enqueue idempotent; refresh is explicit new generation | reopen store; duplicate URLs; different request context; history retained |
| OPS-02 | Atomic claim with unpredictable fencing token, finite lease; one active job per source; concurrency conflicts do not change data | simultaneous processes; stale token denied; distinct sources proceed |
| OPS-03 | Per-source persistent stop, minimum interval and bounded claim budget; canonical origin bound once, alias bypass rejected; recovery never clears stop or resets budget | denied source across reopen/recover; unaffected source completes; exhaustion and cooldown |
| OPS-04 | Immutable canonical JSON receipt files with SHA256, UTC, origin, URL, synthetic marker; receipt checkpoint before finalization | tamper/missing evidence fails closed; unknown fields unchanged |
| OPS-05 | Recovery only expired runtime leases; checkpointed work reclaims without transport call; stale worker cannot persist/finish | abrupt kill at every durable write boundary; no duplicate observations or lost committed receipt |
| OPS-06 | Receipt history append-only; one current observation per canonical listing/context, chosen by observed time; older receipt never displaces newer | inter-run refresh/new generation, reopen, temporal order |
| OPS-07 | DB transactions + atomic fsynced evidence publication; leftover temp/orphan evidence preserved, not falsely complete; committed DB must reference valid bytes | partial writes/rollback and post-commit crash cases; startup integrity |
| OPS-08 | Consistent backup captures SQLite and every referenced receipt under mutation lock, hashes manifest; restore fresh root validates before publication | backup while lease active; SQLite/receipt tamper/missing file; restore/rerun equality |
| OPS-09 | Synthetic CLI submit/work/status/recover/backup/restore yields real durable execution/report; report and DB use same current receipts | subprocess e2e and restored CLI lifecycle; no network requests |
| OPS-10 | New stage guard preserves every parent tracked blob; historical scopes reject successor; full quality and independent exact SHA review | scope tamper negatives; 666 legacy tests plus new runtime acceptance |

A lease/budget is claimed before external work; it counts attempted work even if
killed before the synthetic fetch. Recovery cannot promise exactly-once external
reads when interruption precedes durable receipt checkpoint. It prevents duplicate
committed observations and repeats no transport after checkpoint. Real transport
integration/freshness policy requires a later authorized source adapter stage.

Receipt schema: {url, observed_at (offset-aware UTC-normalized), origin,
synthetic:true, facts:{...}}. A fixture transport is never promoted to live evidence.
Unknown values remain JSON null/string unknown. Runtime does not modify product
identity/payment classification. Configured source IDs are opaque nonempty strings;
URL and request context are data, never network capabilities or commands.

Write boundaries (kill-injection hooks, no production command execution): schema,
enqueue, source configuration, claim, evidence temporary fsync, evidence publish,
checkpoint transaction, finish, recovery, source stop, backup SQLite, backup evidence,
backup manifest, backup publication, restore publication, report publication.
Manifest-bearing backup publication is atomic. Incomplete backup/restore paths never
represent success; no existing root/output is overwritten. Running jobs in restored
backups keep their lease/budget state; explicit expiry recovery is required.

Startup schema and integrity share one lock with a maximum two-second local wait;
claim/mutation conflicts remain fail-fast. A source binds to one canonical HTTPS
origin on first enqueue; the same origin cannot obtain a second source namespace.
Independent-source fixtures use genuinely different synthetic origins. This registry
is queue grouping only, never a grant of live permission. Real transport integration
must still enforce reviewed source access and the existing external stop states.

Product bridge acceptance: synthetic fixture request and primary_html are parsed by
existing T010 parse_card, then retained inside a synthetic durable receipt. CLI
submit/work/report/backup/restore must preserve identical product Observation and
evidence hashes. No network or live source permission is introduced. Candidate
curated_registry origin denotes a synthetic fixture seed, not a real source registry;
receipt input_provenance makes this explicit. Complete product request and current
evaluator-source fingerprint are part of context, preventing different requests/code
revisions from sharing a result. Same listing/context/generation binds an immutable
fixture input hash; changed fixture requires explicit new generation, not silent reuse.
