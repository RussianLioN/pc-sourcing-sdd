# Native cloud acceptance — specification 1.0.0

Profile: native-cloud-offline/1.0.0. Authority and prospective supersession are
specified in docs/adr/0001-native-cloud-acceptance.md. Baseline is
802e001f72bbaf3ae9b6f52081b6361d01736be5; T007 remains unaccepted.
Goal: reproducible offline snapshot validation using real parent-coordinated
native cloud tasks, with truthful process-based independent review.

| ID | Binding requirement | Executable evidence |
|---|---|---|
| CLOUD-01 | full expected SHA and separately supplied contract commit; immutable contract spec/profile/task at that commit | checker rejects SHA/contract/spec drift |
| CLOUD-02 | one writer, separate actual reviewer task and checkout; no reviewer patch integration | distinct task/checkout records, parent provenance verification |
| CLOUD-03 | all baseline tracked files byte-protected; additions limited to T008 ownership | Git blob guard and T008 scope |
| CLOUD-04 | project-local pinned app bootstrap/check, full tests, Ruff, synthetic installed pipeline and idempotent repeat | actual commands/exits, runtime, logs and database/report hashes |
| CLOUD-05 | clean checkout before/after, same snapshot throughout checks/review | recorded clean states and snapshot equality; detection, not write prohibition |
| CLOUD-06 | manifest binds writer/reviewer records, exact SHA, contract/spec/profile hashes, actual environment, task/verdict, evidence hashes and limitations | hashes and cross-record validation |
| CLOUD-07 | missing/failed checks, pending or mismatched reviewer verdict, changed artifact or new commit invalidates acceptance | negative tests and nonzero checker exit |
| CLOUD-08 | preserve T007/old receipts; native-only prospective replacement of nested coordinator and do-while receipt | ADR, scope and separate artifact destination |

A real reviewer first checks out the full SHA in its own checkout, runs collect,
inspects implementation and adds independent scratch reproducers. It completes
the review JSON after inspection: passed requires no findings and all required
checks passed. Failed/blocked findings go back to the writer for a new commit.
The parent verifies real task IDs, separate checkout provenance and the returned
verdict before invoking finalize/check. Locally supplied JSON cannot authenticate
that provenance; the profile deliberately claims only managed acceptance.

No OS read-only/security-principal/model/binary/deadline claim is required or
inferred for the managed cloud runtime. Preserve existing bootstrap pins and
root-relative tooling/negative controls; nested tools are optional historical
checks. Command timeouts remain, but are not claimed as a whole-task deadline.
No credentials, access/security/network changes, paid obligations, live Avito,
orders, contacts, service deployment or automatic product scheduler.
