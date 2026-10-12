# T010 bounded primary read

Candidate milestone 130d67 is engineering accepted, not full product acceptance.
This prospective iteration adds an explicit exact-URL capability for 28BIT. Source
rules/private routes/prior denials remain binding. Gateway target IP is unknown;
no public-IP-only claim or network/settings change. No arbitrary search URL fetch.

```sh
.venv/bin/python -m pc_sourcing.live_sourcing run --request artifacts/my-run/request.json --out artifacts/my-run/primary-result --primary-registry sources/curated-primary.json --source-state /workspace/pc-sourcing-sdd/artifacts/source-state/28bit-stop.json
.venv/bin/python -m pc_sourcing.live_sourcing verify --out artifacts/my-run/primary-result
```

Registry review expires after 24h; expiry blocks reads and needs a fresh actual
policy/source review, not a fabricated timestamp. A denial/timeout creates persistent
source state; further reads stop. No auto-clearing or provider fallback. One card
per run, at least 10 seconds after robots, original source bytes and bounded metadata.

Initial card is Palit 5090, deliberately excluded from MSI Liquid. Displayed RUB
price and declared availability are preserved separately from unconditional price
and confirmed stock. Moscow site heading isn't fulfillment; delivery/condition/
quantity/seller-review unknown. No verified purchase offer is produced.

Report/SQLite retain selected primary content with final URL, received UTC, exact
retained hash/selectors, original body hash, HTTP Date/Age/Cache-Control, robots and
registry hashes. Original full HTML/session inputs are not stored. Retained hash can
be recomputed; body hash without full body isn't independently reconstructible.
Tavily Extract was tested but changes robots syntax and lacks guaranteed final URL/
cache metadata, so it isn't a replacement primary verification channel.

```sh
.venv/bin/python scripts/primary_scope.py
.venv/bin/python scripts/quality.py --out artifacts/T010/fresh-quality
```

New iteration requires exact SHA, actual bounded smoke, transfer and independent
review. Previous receipts remain immutable; testing a successor under historical
scope is not retrospective acceptance. Full product DoD remains pending.

Local DNS precheck gaierror is infrastructure failure before source HTTP. It is
recorded separately and stops the run, without inventing a site ban. The original
legacy gaierror stop record remains unchanged; a newly initiated bounded run may
probe the same approved route. Actual source denial/timeout stops remain persistent,
with no automated retry, alternate provider or silent reset.
