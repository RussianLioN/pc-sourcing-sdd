# T012 normalized offer imports

This is an offline import path, not a live fetcher. It does not reset source stops,
obtain source permissions, create tokens or start hosting. Keep real and synthetic
records in separate datasets. Preserve the original evidence and unknown values.

Use a JSON list matching `NormalizedOffer` in normalized_models.py. Every positive
field needs matching retained primary field evidence. Explicit UTC timestamps,
synthetic flags, exact decimals and requested quantity are required. Amounts from
old source specifications are not inputs to this path.

```bash
.venv/bin/python -m pc_sourcing.normalized_cli run \
  --input /absolute/offers.json --output /absolute/fresh-report \
  --as-of 2026-10-12T12:00:00+00:00
.venv/bin/python -m pc_sourcing.normalized_cli verify \
  --output /absolute/fresh-report
```

The report directory contains one canonical JSON dataset, CSV, XLSX, readable
Markdown and SQLite, with SHA256 manifest and readback consistency validation.
Unknown full costs remain null. Conditional prices and deposits cannot replace
unconditional full costs. Synthetic controls never become purchase ready.

For synthetic records only, add `--runtime-root /absolute/runtime`. The bridge
uses T011 leases, budget, stop and immutable generation rules. A changed input
needs an explicit larger `--generation`; restarting never clears a stop or budget.
Use durable_cli backup/restore for cross-environment transfer. Real imports may be
exported offline but cannot enter this synthetic runtime. There is no background
refresh or live source adapter in this stage.

The user approved CP-T012-01: the historical T011 positive scope fixture now checks
its reconstructed stage. T012 binds the exact two-line setup patch and preserves
all other parent bytes. Historical failure receipts remain retained.
No full product or independent T012 acceptance is claimed.

## Raw runtime and canonical comparison

The runtime keeps canonical URL/context observations. Two URL aliases with one
listing ID may remain two runtime current receipts; comparison keeps one row and
retains the other record/evidence in rejections. This is an explicit difference
of layers. Same URL/context duplicates in one batch are coalesced before one
atomic submission; all originals remain in facts.raw_observations. Selection uses
latest timestamp and then descending offer ID in both layers.

A source/input conflict rejects the whole enqueue batch. Input hashes exclude the
evaluation clock, so an identical reordered batch is idempotent. Existing receipt
decisions keep their original as-of; export evaluates at the new explicit as-of.
Changed raw data requires an explicit generation. Older WIP runtimes are not
silently migrated. No cross-resource atomicity between runtime and export is
promised. Unsupported XML text returns a structured failure before runtime or
export changes and preserves the original input; characters are not removed.
