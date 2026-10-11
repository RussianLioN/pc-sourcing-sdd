# T008 native cloud handoff

Contract commit: `97fd8b21f8aee68c625a1101df04fc36d9b14625`.
Profile/spec version: `native-cloud-offline/1.0.0`.
Read ADR-0001, specs/003-native-cloud/{spec,plan,acceptance-profile}.md/json
and tasks/T008.json before proceeding. The profile is user-authorized for
future native cloud tasks only. T007 remains unaccepted, unchanged.

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
