# Captured primary replay CLI — T013 first slice

This path performs no HTTP/search. It consumes a saved hash-verified primary
artifact, retains real/synthetic origin and original dates, and normalizes unknowns
without making them stock, payment or zero fees. It uses a separate collection
journal; the frozen synthetic runtime is neither changed nor reused for real data.

```bash
PYTHONPATH=src .venv/bin/python -m pc_sourcing.collection_cli import \
  --root /absolute/fresh-collection \
  --artifact /absolute/retained-primary-artifact \
  --request /absolute/original-request.json
PYTHONPATH=src .venv/bin/python -m pc_sourcing.collection_cli work \
  --root /absolute/fresh-collection
PYTHONPATH=src .venv/bin/python -m pc_sourcing.collection_cli report \
  --root /absolute/fresh-collection --output /absolute/fresh-report
```

The report contains offers/comparison.json, offers.csv, offers.xlsx, report.md and
SQLite from T012, plus coverage.json/coverage.md. A displayed price stays an
unknown-kind alternative when unconditional purchase terms are not confirmed.
The historical F5 RAM source quote is not a current executable purchase price.

Use status to inspect persisted jobs; recover requeues only expired CPU leases.
Normalization uses committed captures and makes no source calls. Repeat import
is idempotent. Use backup/restore with --output /fresh/backup or --artifact /backup
and --root /fresh/restored. Receipt bytes and original observations survive transfer.

This is an intermediate offline slice. A bounded live acquisition controller,
source budgets/stops and final operational/fault hardening remain to be completed.
The exact permitted next network step is described in source-route-plan.md; no
network call is implied by these commands. T013 is not independently accepted.

## Narrow acquisition controller

`collection_cli acquire --root /fresh/runtime --request /exact/F5-request.json`
uses only the previously reviewed exact 28BIT route through frozen CuratedReader.
It reserves its shared source budget before HTTP. The current one-card budget is
already spent by the 09:21 UTC capture; repeating its same request consumes the
checkpoint with zero HTTP. Unknown/new intents cannot reset or enlarge the budget.
Use work/report/backup/restore afterwards. Source checkpoints and the global
source-state ledger must travel with runtime data before any future acquisition.
Other source profiles are not implemented/enabled by this command.

## State and code integrity

Runtime output is re-derived from the immutable capture before export. Modified
schema, realm, output or fact/witness values fail closed. Worker fingerprint change
requires a fresh journal with stored captures, not refetch or budget reset. Early
unaccepted WIP journals are not silently migrated; historical evidence remains.

Use source-backup with --output /fresh/source-snapshot to transfer global source
stops, budget ledgers and immutable acquisition checkpoints separately from CPU
journal backup. source-restore publishes only to an absent canonical state directory;
existing state cannot be overwritten. Missing production baseline fails closed.
Do not create empty state folders to regain a budget.

REGARD acquisition supports --source regard only for the exact known F5 page.
Its one-card budget is already spent, so repeated same request consumes checkpoint
with zero HTTP. This capture is unresolved; title/stock claims and source diagnostics
are preserved. GPU/mouse URLs are unknown; ANDPRO profiles/cards are not enabled.
Further live requests are paused pending repair recheck; do not use alternate tools.

Existing source/CPU databases are validated against canonical DDL, types, primary
keys, NOT NULL, indexes, foreign keys and user_version. Empty/truncated source
ledgers fail read-only preflight before state-file creation; restore a validated
complete snapshot rather than opening an empty file. Never reset budgets/stops.
