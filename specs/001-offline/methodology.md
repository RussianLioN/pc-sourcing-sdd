# Section 9 operational methodology
| Stage | Entry | Artifact | Exit / stop |
|---|---|---|---|
| Boundary | supplied sources | constitution + access registry + spec | scope known; dependent live blocked |
| Contract | REQ IDs | model/schema v1.0.0 + decision table + 20 goldens | tests pin expectations; coordinator owns |
| Task | committed contract | JSON SHA/revision/deps/ownership/commands | ready only if base and dependencies match |
| Work | ready task | unique worktree, DB, temp, cache | one writer; bounded worker result + diff |
| Local test | implementation | unit/contract/property reports + exits | failure opens narrow repair |
| Integrate | scope/blob gate passed | common commit | all required tests repeated |
| Review/repair | common snapshot | independent verdict / regression task | continue to acceptance; new hypothesis on stalled progress |
| Pilot | offline passes | SQLite + Markdown + manifest | live primary data blocked without access |
| Accept | tests + independent verdict | spec/test/fixture/tree hashes + SHA | all required offline checks passed |

Coordinator is Spec Kit plus project scripts; collector is deterministic
Python with no Spec Kit/LLM dependency. No perpetual development loop or
background collector. Converge may identify gaps inside frozen scope only.
Budget: one writer, one verifier sequentially, 600s each, supervisor 660s; continuation has no round stop;
no additional paid APIs. Existing ChatGPT Codex authorization is used.
Persist versions, commands, exit codes, stderr/events, failures, SHA, hashes,
reason for stopping, next task; attempts use separate artifact directories.

Required offline acceptance: golden/unit/contract/property, SQLite/report,
idempotency/reject retention, scope gate, lint, same-snapshot independent real
Codex review, observable defect with regression repair. Workflow probes are
separate from product acceptance; synthetic worker verdicts prove only
orchestration. Two-writer combined snapshot, live Avito and full running
crash recovery are explicitly outside demonstrated capability.

Project wrapper takes exclusive nonblocking advisory lock before resume.
It checks exact executable and environment arguments; streaming adapter has
no built-in wall timeout, so supervisor must terminate process group.
Killed worker returning failure can produce failed resumable runner state.
Killed coordinator leaves running state, which Spec Kit cannot resume.
Never edit state to manufacture recovery; inspect processes and start a new
audited task. Shell steps execute with current user rights: use only reviewed
fixed commands, never interpolate offer/agent text into shell commands.

Final verification writes only to a private /tmp scratch; project code remains
read-only to verifier. Direct read-only sandbox was observed to block pytest
temp files; a separate scratch root solved this without making project code
writable. The actual negative project-write probe is required in review.
Use T002 for integrated scope, T001/T003 only for historical worker scopes.
Original golden/schema Git blobs and original test AST assertions remain
protected. Final receipt is validated by scripts/check_acceptance.py; readable
summary is generated from stored Evaluation, not a second eligibility formula.
Final accepted scope can only be this offline pilot, never production readiness.

Continuation policy 1.0.1 supersedes only the former two-round stop, following
the explicit user instruction in tasks/continuation-policy.json. Historical
failed receipts and immutable assignments retain their original limits. The
current coordinator state records progress and next hypothesis; historical
Spec Kit execution state is never edited to manufacture a resume.

Row errors in a syntactically framed, decodable JSON document are isolated:
reject with original raw JSON and a readable reason; valid neighbors survive.
Unpaired Unicode surrogates in keys or nested values must not reach report or
SQLite serialization. Valid Unicode scalar values/pairs are preserved exactly.
Malformed document framing/encoding remains an explicit whole-input error,
as required by the existing syntax tests; never guess boundaries or repair text.

The coordinator drives autonomous repair/review decisions between audited
finite runs; this is not a persistent service or automatic paid retry. A small
Spec Kit do-while scenario checks two real collector passes and idempotency,
with an explicit local experimental bound and exit condition. That bound does
not stop the project repair cycle. Converge is optional gap/task discovery,
not a mandatory acceptance gate or a substitute for tests. No parallel fan-out
capability is claimed. Mandatory offline gates remain those listed above.

The final real collector do-while receipt is mandatory for this continuation
pilot. It binds the exact snapshot and two actual collector passes; it does
not imply autonomous code repair or parallel fan-out. Converge remains optional.
