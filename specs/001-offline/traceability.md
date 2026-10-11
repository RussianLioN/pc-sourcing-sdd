# Executable traceability — contract revision 1.0.0
The final manifest binds these checks to one Git SHA and corpus revision.

| Requirement | Concrete check | Supporting artifact |
|---|---|---|
| SKU-01 | soc-analogue, missing-liquid, three exact SKU golden rows | tests/test_payment.py and golden corpus |
| EVI-01 | owner, synthetic, timezone, missing/mismatched/conflicting field evidence | tests/test_contract.py, tests/test_worker.py |
| EVI-02 | snippet cannot confirm or enter verified list | test_snippet_never_promoted, snippet golden |
| PRICE-01 | unknown is null, strict positive RUB; wrong currency excluded | nonpositive property and unknown-price golden |
| STOCK-01 | preorder remains outside verified list despite payment pass | preorder golden cases |
| PAY-01/PAY-02 | symmetric OR, independent route conflict, both routes | test_or_symmetric_independent_route and golden cases |
| PAY-03 | global advance/conflict dominates, optional risk does not | global-block property, review regression, repair-worker tests |
| OUT-01 | same Evaluation in DB/report/verified list; independent SQLite audit | test_pipeline, actual verifier reproducers |
| OUT-02 | malformed/duplicate/1e400 rows retained, valid rows survive | review regression and repair-worker raw-token tests |
| OUT-03 | synthetic flag, evidence URL/time/origin and reasons retained | SQLite/report contract and actual independent audit |
| RUN-01 | repeat is idempotent; input/time/spec/code changes rejected | fingerprint tests, transaction rollback/report recovery |
| SDD-01 | baseline Git blobs, AST assertions, ready task/dependencies, scope | tests/test_control_plane.py, tasks/T002.json scope gate |
| SDD-02 | actual separate Codex review, real defect and repair, capped rounds | workers JSONL/results, defects.md, archived validation |

Runner paused/failed resume and lock tests are separate infrastructure
evidence. Running crash recovery and live access remain blocked; two-writer
support is not claimed. No skipped required offline check can grant acceptance.
