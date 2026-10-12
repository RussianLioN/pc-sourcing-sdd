# Bounded Adapter Data

Request: strict duplicate-free JSON <=64KB; exact operation-specific fields; request_id/context bounded strings. It has no approval, anchor, start or authority fields.

Proposal: operation/request hash, exact runtime tuple, source payload inventory with bytes/mtime, current replica version/hash, lesson/result/target hashes, context. This is untrusted data and always declares learning OFF.

Externally retained anchor: genuine review provenance/package/version/hash/purpose, code/spec/oracle/test/dependency tuple, exact operation context and lesson/new-result tuple, active version/hash, source inventory, explicit start and realm. Supplied only by a coordinator-host integration after independent authentication; no local loader exists.

One-use grant: grant_id, exact proposal hash, operation, request_id, expected version/hash, anchor hash. The external host records consumption/reservation and refuses replay. Local replicas cannot prove grant authenticity.

Replica: immutable canonical snapshots, bounded unique lessons, previous version/hash, pointer and append-only intent/audit. Real versus synthetic realm must consistently match the external host. All evidence/incident/target checks precede writes. Source state never part of a replica rollback.

Receipt: visible pointer/hash, grant/request/proposal bindings, source before/after, audit reference. Even this receipt is untrusted until the coordinator independently verifies it and advances its retained anchor. Failure after local visibility leaves divergence and requires explicit external reconciliation.
