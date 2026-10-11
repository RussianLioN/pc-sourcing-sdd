# T008 native cloud handoff

Contract commit: `97fd8b21f8aee68c625a1101df04fc36d9b14625`.
Profile/spec version: `native-cloud-offline/1.0.0`.
Read ADR-0001, specs/003-native-cloud/{spec,plan,acceptance-profile}.md/json
and tasks/T008.json before proceeding. The profile is user-authorized for
future native cloud tasks only. T007 remains unaccepted, unchanged.

## Evidence delivery readiness before launching tasks

The parent owns delivery and consolidation. Choose the finalizer checkout and
an existing approved private transfer capability before expensive role runs.
Check its documented contract and, only where permitted, perform a small
non-sensitive end-to-end transfer to that finalizer. Record the observed result,
not just upload success or returned metadata. No route test is allowed after an
access denial without explicit authorization. If delivery is untested or blocked,
report acceptance delivery as blocked; local role checks may still be preserved
but cannot be called acceptance. Keep original executors/evidence available until
consolidation succeeds where the platform permits retention.

Library can supply a workspace path or a short-lived signed download URL.
Preparation and private storage do not prove the finalizer can download bytes.
Separate executors' absolute paths are not shared storage. A proxy CONNECT 403
is a tunnel denial before the origin response; it does not identify the denying
rule, prove an allowlist omission, or prove an expired URL. Stop on denial,
retain safe metadata, and request platform diagnosis without credentials or URLs.
Do not change proxy, identity, or transport to evade it.

Immediately after each permitted transfer, before shutting down its source,
validate the complete preserved directory locally:

```sh
.venv/bin/python scripts/native_cloud.py evidence-preflight --record "$LOCAL_RECORD"
```

Run this for writer and reviewer in the intended finalizer. It lists missing
referenced files and verifies hashes, with no network access or acceptance
receipt. It cannot authenticate tasks, validate review, or replace finalize/check.
Library is a delivery option, not a profile requirement; all referenced bytes
and the unchanged final gate remain mandatory regardless of approved transport.

## Writer and reviewer commands

The parent supplies the full published code SHA and real cloud task/environment
IDs, verifies there is only one writer, and launches a separate actual reviewer
task with a separate checkout. The reviewer returns findings; it never integrates
patches. IDs are external provenance, not authenticated by this local program.

Start in the chosen checkout; preserve local changes and check remote before any
branch switch. Check out the parent's complete code SHA. Then:

```sh
python3 scripts/bootstrap.py
.venv/bin/python scripts/bootstrap.py --check
.venv/bin/python scripts/verify_scope.py tasks/T008.json .
.venv/bin/python scripts/native_cloud.py collect \
  --role writer --expected-sha "$CODE_SHA" \
  --contract-commit 97fd8b21f8aee68c625a1101df04fc36d9b14625 \
  --task-id "$ACTUAL_WRITER_TASK_ID" --environment-id "$ACTUAL_ENVIRONMENT_ID" \
  --out "$PWD/artifacts/native-cloud/writer-fresh"
```

For the reviewer use `--role reviewer`, its actual IDs and a fresh output path.
Both roles actually run app bootstrap check, all tests, Ruff check/format, T008
scope, synthetic installed pipeline and identical-fingerprint pipeline repeat.
Do not add `--with-codex` or a nested workflow to satisfy this profile.
Local subprocess timeouts terminate process groups; no whole-cloud-task deadline
is claimed. Retain failed records and use new paths for subsequent attempts.

If actual task ID is unavailable, collect may omit `--task-id` to preserve local
check evidence. Such a record cannot be accepted. Once provenance is available,
run fresh collect with the actual ID; never fabricate an ID or promote pending
evidence to independently accepted status.

## Independent review and provenance

After independent code/contract inspection and scratch reproducers, the reviewer
returns a JSON file with these fields (replace placeholders with observed values;
this is a schema example, not an executed review):

```json
{
  "schema": "native-cloud-review/1",
  "task_id": "ACTUAL_REVIEWER_TASK_ID",
  "commit": "FULL_CODE_SHA",
  "contract": "COPY_OBJECT_FROM_REVIEWER_RECORD",
  "writer_record_sha256": "SHA256_OF_EXACT_WRITER_RECORD_BYTES",
  "reviewer_record_sha256": "SHA256_OF_EXACT_REVIEWER_RECORD_BYTES",
  "verdict": "passed|failed|blocked",
  "findings": [],
  "clean_after": true,
  "snapshot_after": "COPY_SNAPSHOT_OBJECT_AFTER_REVIEW_IF_UNCHANGED",
  "summary": "Explain independent inspection, experiments and conclusion",
  "limitations": ["ALL_PROFILE_LIMITATIONS_PLUS_ANY_REVIEW_LIMITATIONS"]
}
```

Passed requires all required checks passed, no findings, exact SHA/spec and
evidence binding. After inspection run this final detection check; report its
observed values in the review JSON, never assume a clean state:

```sh
.venv/bin/python -c 'import sys,json; sys.path.insert(0,"scripts"); import native_cloud as n; print(json.dumps({"clean_after":n.clean(n.ROOT),"snapshot_after":n.snapshot(n.ROOT)}))'
```

A parent claiming verified provenance writes a separate JSON
attestation only after checking real task results and separate checkouts:

```json
{
  "schema": "native-cloud-provenance/1",
  "commit": "FULL_CODE_SHA",
  "contract_commit": "97fd8b21f8aee68c625a1101df04fc36d9b14625",
  "writer_task_id": "ACTUAL_WRITER_TASK_ID",
  "reviewer_task_id": "ACTUAL_REVIEWER_TASK_ID",
  "verified_real_tasks": true,
  "separate_checkouts": true,
  "reviewer_did_not_integrate_patches": true,
  "writer_sha256": "WRITER_RECORD_SHA256",
  "reviewer_sha256": "REVIEWER_RECORD_SHA256",
  "review_sha256": "REVIEW_JSON_SHA256"
}
```

These booleans are explicit parent attestations, not a cloud API response or
technical proof of identity/isolation. Never generate a successful reviewer or
provenance JSON merely to make the checker pass. Unit fixtures are synthetic and
do not supply real review evidence.

Privately preserve each record with its evidence directory, keeping relative
artifact names and byte hashes. Transfer bundles through existing approved
capabilities if consolidation is needed; do not publish raw logs/DB/credentials.
In a clean checkout of the exact code SHA, with both bundles accessible:

```sh
.venv/bin/python scripts/native_cloud.py finalize \
  --expected-sha "$CODE_SHA" \
  --contract-commit 97fd8b21f8aee68c625a1101df04fc36d9b14625 \
  --writer-task-id "$ACTUAL_WRITER_TASK_ID" --reviewer-task-id "$ACTUAL_REVIEWER_TASK_ID" \
  --writer "$WRITER_RECORD" --reviewer "$REVIEWER_RECORD" \
  --review "$REVIEW_JSON" --provenance "$PARENT_PROVENANCE_JSON" \
  --out "$PWD/artifacts/native-cloud/acceptance-fresh/manifest.json"
.venv/bin/python scripts/native_cloud.py check \
  --expected-sha "$CODE_SHA" \
  --contract-commit 97fd8b21f8aee68c625a1101df04fc36d9b14625 \
  --writer-task-id "$ACTUAL_WRITER_TASK_ID" --reviewer-task-id "$ACTUAL_REVIEWER_TASK_ID" \
  --manifest "$PWD/artifacts/native-cloud/acceptance-fresh/manifest.json"
```

The separately supplied expected SHA/contract/task IDs are trust anchors. Review
or provenance mismatch, changed protected blob/spec/evidence, dirty checkout or
new commit blocks acceptance. Failed/blocked/missing review never creates an
accepted manifest. Existing manifests are not overwritten. A new documentation
commit also invalidates approval; rerun evidence and independent review.

## Continuing from a phone or Slack

Send the parent: “Continue T008 native-cloud-offline at FULL_CODE_SHA in
RussianLioN/pc-sourcing-sdd. Read docs/native-cloud-handoff.md and ADR-0001;
use one writer, a separate actual reviewer checkout and contract 97fd8b21f8aee68c625a1101df04fc36d9b14625.
Preserve original protected files and return a same-SHA evidence manifest.”
The parent performs actual orchestration. This is not a tested Slack command
integration, continuous scheduler or service deployment.

No OS read-only, separate security principal, managed binary/model pin or forced
task deadline is asserted. Clean before/after detects final changes, not temporary
writes. Required server-side checks are not confirmed: acceptance is a managed
process, not an enforced merge block. There are no new credentials, security or
network changes; live Avito, purchasing and seller contact remain out of scope.

## RCA iteration: delivery and evidence lifetime

The verified process gap was late delivery readiness: seven role checks cover
application behavior and checkout integrity, not a finalizer's ability to obtain
bytes from another executor. Successful role checks alone therefore cannot
establish acceptance. Library preparation can return metadata without placing
local bytes; a signed URL is not proof of successful delivery. A reported proxy
tunnel denial does not identify the denying policy. No denied transfer was retried
in this RCA iteration, and no network or credential settings were changed.

A manifest stores absolute paths to records, review and provenance. It is a
receipt for that materialized layout, not a self-contained portable archive.
Preserve the complete evidence directories and receipts privately, including
relative names and hashes. Saving only the manifest does not preserve the bytes
needed by check after an executor closes. Do not edit old records or manifests
to claim recovery. If an approved transfer relocates preserved evidence, use
finalize to create a new manifest against the actual local layout, then run check
at the same exact code SHA and contract with verified parent provenance. Keep the
old receipt as history. This works only with every required byte and valid review;
it cannot transfer acceptance to a different code SHA.

Local evidence-preflight verifies only files already present and their hashes.
It has not demonstrated a real transfer between executors. Real delivery readiness
and later rechecking after environment closure remain unverified until observed
through a permitted route. A blocked route remains blocked; an offline process
fix cannot repair or authorize platform network policy.

RCA patch validation: bootstrap and bootstrap --check passed; 357 pytest tests
passed, including missing bytes, tampering and directory escape regressions;
Ruff check/format, T008 scope and diff whitespace checks passed. These are local
implementation checks, not independent same-SHA acceptance. Every new published
commit needs fresh role evidence and independent review. Original T007 status,
contract/profile and protected baseline are unchanged. Detailed incident IDs,
private artifact identifiers and executor diagnostics are retained privately and
excluded from this public handoff.
