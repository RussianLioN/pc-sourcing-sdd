# T011 synthetic durable runtime

This additive runtime provides queue/recovery/backup mechanics, not live sourcing
permission or full product acceptance. T010 parent bd70f4f has limited independent engineering PASS; fresh live smoke,
multiple sources, GPU/mouse primary and operational product e2e remain open. The protected Spec Kit development runner is unchanged.

Use an isolated absolute root under the cloud workspace. Example fixture JSON:

```json
[{"synthetic":true,"source":"fixture-store","url":"https://synthetic.example.test/item","context":{"region":"Москва","mpn":"SYNTHETIC","spec_revision":"1.0.0"},"generation":0,"policy":{"budget":3,"interval":5},"receipt":{"url":"https://synthetic.example.test/item","observed_at":"2026-10-12T00:00:00+00:00","origin":"synthetic_fixture","synthetic":true,"facts":{"price_rub":null,"stock":"unknown","eligible":false}}}]
```

```sh
.venv/bin/python -m pc_sourcing.durable_cli submit --root /workspace/my-runtime --fixtures /workspace/my-fixtures.json
.venv/bin/python -m pc_sourcing.durable_cli work --root /workspace/my-runtime --fixtures /workspace/my-fixtures.json --max-jobs 3
.venv/bin/python -m pc_sourcing.durable_cli status --root /workspace/my-runtime
.venv/bin/python -m pc_sourcing.durable_cli recover --root /workspace/my-runtime
.venv/bin/python -m pc_sourcing.durable_cli report --root /workspace/my-runtime --output /workspace/my-report.json
.venv/bin/python -m pc_sourcing.durable_cli backup --root /workspace/my-runtime --output /workspace/my-backup
.venv/bin/python -m pc_sourcing.durable_cli restore --root /workspace/my-restored-runtime --backup /workspace/my-backup
```

Repeated submit preserves job ID/status. Explicit generation creates a refresh job;
context must distinguish request/specification/region/variant. One latest observation
per listing/context remains, and committed receipt history is append-only. This is
listing dedup; it does not verify that sellers on different domains are independent.

Lease expiry alone does not retry work. `recover` requeues expired runtime leases;
checkpointed receipts resume without fetch and without another transport budget.
Pre-checkpoint interrupted attempts have unknown outcome; recovery can repeat a
synthetic read within remaining budget, never promise exactly-once external reads.
A future real adapter must separately authorize such retry after source-outcome audit.

Source budgets and stops persist; they cannot be reset by configuration/recovery.
Each source binds to one canonical origin; duplicate source aliases cannot obtain
another budget for that origin. Source configuration is queue grouping only; it
cannot grant live permission or override T010 external denial records.

Processes share advisory flock and SQLite FULL synchronous transactions. Startup
waits at most two seconds for initialization/integrity; mutations fail Busy. Leases
use unpredictable fencing tokens; old/expired tokens cannot checkpoint or finalize.
Use one filesystem supporting flock, fsync and atomic rename. Multi-host distributed
locking/hosting is not provided. No daemon, background cadence or deployment is created.

Output paths must be fresh absolute paths, without symlinks. Evidence is canonical
JSON with hashes and synthetic marker. Temporary/orphan blobs from crashes remain
in the original root, not presented as committed observations. Backups include all
committed referenced blobs plus SQLite and a hash manifest; unreferenced temporary
files are excluded. Restore validates before atomic publication, retains lease/budget/
stop state, and never overwrites an existing root. Hashes prove consistency, not a
server signature or authenticated third-party provenance.

Quality: `scripts/durable_check_workflow.py` pins the existing Spec Kit runtime and
runs full regression then the new additive guard. Historical T008–T010 gates continue
to reject successor stages; their artifacts/specifications/assertions are untouched.

Product fixture mode replaces receipt/blocked_reason with request, primary_html and
observed_at. Example request: {"name":"MSI RTX 5090 SUPRIM LIQUID OC",
"mpn":"G5090-32SLC","category":"gpu","quantity":1,"region":"Москва"}.
The supplied primary_html is a synthetic Product card; the bridge invokes the real
T010 parser. Receipt facts.observation preserves its fields, evidence and retained
assertion hash. All results stay synthetic, and eligible stays false. No live search
or card read occurs. Product request plus evaluator/bridge fingerprint distinguishes
contexts; original fixture content is hash-bound per generation. Changed content
requires an explicit refresh generation. Recovered checkpoint work ignores replacement
fixture transport and resumes the immutable saved receipt instead.
