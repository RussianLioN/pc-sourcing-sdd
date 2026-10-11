# Tasks revision 1.0.0
- [ ] T001 Offline vertical in `.worktrees/offline`: base `a5de9fedff6d413ca2a3b1d9a93be25895402d60`, task JSON
  `tasks/T001.json`, owned evaluate/pipeline/test_worker only. Required tests,
  SQLite and report; no contract changes. One writer. Dependencies: none.
- [ ] T002 Integrate T001 after scope/blob gate, run all checks and independent
  Codex read-only verifier on the exact common commit. Coordinator owns.
- [ ] T003 Bounded repair on a new task at the reviewed SHA if a defect is
  observed; add regression test, never weaken golden. Max two repair rounds.
- [ ] T004 Runner pause/failure/resume/crash/lock probes; coordinator-owned
  unique resource directories, no real second writer. Dependency: T002.
- [ ] T005 Final hash/SHA acceptance record; live sources blocked. T002–T004.
