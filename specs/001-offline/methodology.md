# Section 9 operational methodology
| Stage | Entry | Artifact | Exit / stop |
|---|---|---|---|
| Boundary | supplied sources | constitution + access registry + spec | scope known; dependent live blocked |
| Contract | REQ IDs | model/schema v1.0.0 + decision table + 20 goldens | tests pin expectations; coordinator owns |
| Task | committed contract | JSON SHA/revision/deps/ownership/commands | ready only if base and dependencies match |
| Work | ready task | unique worktree, DB, temp, cache | one writer; bounded worker result + diff |
| Local test | implementation | unit/contract/property reports + exits | failure opens narrow repair |
| Integrate | scope/blob gate passed | common commit | all required tests repeated |
| Review/repair | common snapshot | independent verdict / regression task | 2 rounds max; no new hypothesis => blocked |
| Pilot | offline passes | SQLite + Markdown + manifest | live primary data blocked without access |
| Accept | tests + independent verdict | spec/test/fixture/tree hashes + SHA | all required offline checks passed |

Coordinator is Spec Kit plus project scripts; collector is deterministic
Python with no Spec Kit/LLM dependency. No perpetual development loop or
background collector. Converge may identify gaps inside frozen scope only.
Budget: one writer, one verifier sequentially, 600s each, two repair rounds;
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
