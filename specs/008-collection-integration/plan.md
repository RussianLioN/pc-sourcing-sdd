# T013 execution plan

1. Freeze input/provenance/durable contract and source-route inventory.
2. Build a conservative captured Observation→NormalizedOffer mapper. Validate
   retained hashes and preserve displayed/conditional price semantics and dates.
3. Add a separate real-capable capture journal using shared filesystem primitives;
   never monkeypatch the synthetic Store. Persist capture before CPU normalization.
4. Add CLI import/work/status/report/backup/restore with explicit replay provenance.
5. Reproduce actual retained RAM receipt to five-format report, then test persistent
   recovery/fencing/idempotency/faults and cross-environment handoff.
6. Add a bounded live adapter admission path only after offline integration passes;
   keep existing source denials/permissions. No fresh live step is implied by replay.
7. Exact SHA, native common snapshot and independent review after parent dependency
   and any narrowly required historical fixture setup are resolved.
