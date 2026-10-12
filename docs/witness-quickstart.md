# T016 controller quickstart — candidate, live not accepted

Existing RAM is immutable T013 checkpoint consumption, never new acquisition:

```bash
.venv/bin/python -m pc_sourcing.witness_cli ram-replay --source ram28 --request /workspace/ram-request.json --root /workspace/fresh-ram-journal --output /workspace/fresh-ram-report
```

For GPU after independent controller acceptance only, coordinator supplies a small
local release receipt with status `limited_controller_PASS`, independent=true,
reviewed_commit=exact current SHA and profile_hashes for tdvat/evens. Pass the known
receipt SHA256. This is an operator review gate and integrity link, not cryptographic
authentication of reviewer identity; source pages cannot create/enable it.

```bash
.venv/bin/python -m pc_sourcing.witness_cli bootstrap --source tdvat --review-receipt /workspace/controller-review.json --review-sha256 APPROVED_RECEIPT_SHA256
.venv/bin/python -m pc_sourcing.witness_cli acquire --source tdvat --request /workspace/gpu-request.json --root /workspace/fresh-gpu-journal --output /workspace/fresh-gpu-report --review-receipt /workspace/controller-review.json --review-sha256 APPROVED_RECEIPT_SHA256
```

Repeat serially for evens with the same exact target request (MSI RTX 5090 SUPRIM
LIQUID OC, G5090-32SLC); SOC remains an explicit analogue, not the same SKU.
Do not run these live commands until independent acceptance. Production defaults
block before source initialization/HTTP without bound review. Existing root/state
cannot be reset by bootstrap. Only 1 card/2 HTTP per new source, >=10s interval,
<=1MB response, <=15s total request deadline, no redirects/query/API/subresource/retries.
Policy review expires 2026-10-13T10:45:00Z; recheck immediately before both reads.
No DNS/Spectrasoft/Avito/NIX/Tavily routes. Fresh RAM budget is prohibited.

Source state and CPU journal are different transfers. `source-backup` stores
complete minimized old RAM state (spent budgets/stops/capture evidence) plus new
controller state. `source-restore` only publishes to fresh nonexistent canonical
state; CPU backup/restore use collection_cli. Keep the original as-of dates when
comparing reports. Synthetic transport is test-only and cannot use production state.
Unsupported layout, conditional price and malformed JSON remain unresolved coverage.
Selected bytes/tokens/hash/date survive, no full HTML/reviews retained. Displayed
price never becomes unconditional; no full-product DoD or ban-free guarantee.

Request streaming now enforces the profile body cap directly. Unknown-length
response at exact cap without proven EOF is blocked without reading an overflow
byte. POSIX single-thread CLI runs one short-lived HTTP worker; the parent deadline
covers DNS/open/headers/body/IPC and kills/reaps blocking reads at expiry. Full
HTML remains in memory only. This is a request resource guard, not another
development orchestrator. No production HTTP performed during validation.
