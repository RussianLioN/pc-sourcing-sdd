# T016 traceability

Original product §§10–14 -> WIT-01/02/04/08/09. Access constraints/LIVE -> WIT-03/05/06/07.
Methodology protected ownership/independent exact-SHA validation -> WIT-10.
Existing contracts CHAIN/EXTRACT remain unchanged and are consumed by composition.
Concrete tests/commands/receipts and snapshot hashes accompany handoff. Cost and
active user time unknown; completed native validation is not full autonomous
repair/recovery proof. New profile bootstrap is explicit authorized bounded search
preparation, not a budget reset or live access authorization by source content.

Coordinator-approved CP-T016-01 exact transition is reconstructed in the T016
scope gate. Old 229+1 assertions, seven negative cases and old checker preserved;
new gate also rejects CP revert and altered authorization hash. LOW Ruff I001
repaired in task-owned test import ordering; no test expectations weakened.

WIT-07 final rejection -> read_profile_body remaining-byte reads and one parent
worker deadline. Tests: test_profile_streaming_never_reads_extra_body_to_reject_oversize,
test_profile_streaming_checks_total_elapsed_after_chunk_not_only_before,
test_total_deadline_terminates_blocking_worker_without_surviving_fetch,
test_dripping_chunked_response_is_cancelled_at_total_deadline,
test_open_time_consumes_body_deadline_in_actual_helper. Reproducer red retained.
