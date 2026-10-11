# Pilot evidence and acceptance boundary
This is an offline pilot on the user's Mac, not production readiness.
The collector is deterministic Python. Spec Kit/Codex are development tooling,
not runtime dependencies. No repo-local MCP, service deployment, publication,
orders, seller messages, accounts, new credentials or subscription.

The final receipt is `artifacts/acceptance/manifest.json`, validated using
`scripts/check_acceptance.py`. It binds exact Git SHA, spec/fixture/test/code
hashes and real independent review. Current receipt is authoritative; historical
green reports do not accept a changed snapshot. The readable sourcing report
is `artifacts/acceptance/summary.md`; detailed audit is `report.md` in the same
directory. Both use the same stored Offer and Evaluation as SQLite; eligibility is not recomputed.

Actual initial writer: Codex CLI 0.157.1, 243.580s, 84 tests passed; protected
baseline/scope passed. Ruff found an import classification issue; coordinator
fixed imports without changing assertions or golden expectations.
Actual read-only review initially blocked pytest temporary file creation.
Verifier was moved to private writable /tmp scratch; project stayed outside
its writable roots. A negative project-write test confirmed the restriction.
Fresh actual verifier ran 93 tests and additional reproducers, then reported
numeric-overflow row loss, ignored global-conflict evidence and mismatched
worker/common scope task. Failures were retained, not converted to passed.
Actual repair writer: fresh worktree, repair round 1/2, 187.742s, 118 tests
passed. The regression pair failed before repair and passed after it.
Coordinator's additional protected-expectation control brings the integrated
suite to 119 tests. No golden expectation was weakened. Repair was integrated
sequentially after worker scope gate. A Mac transport outage interrupted the
first integration attempt; reconnect confirmed it had not partially executed.
Original repair files were actually present and copied to
`artifacts/repair-validation`, with an archive SHA-256 manifest.

Second actual verifier at 19d3fcc0bc0f2ac9167287107623a90f0d69ae71
ran 119 tests successfully but failed an independent 5000-digit integer
reproducer. This failed verdict is retained. Final repair round 2/2 used
a new writer/worktree (160.120s): 136 tests, lint, format and scope passed.
The fixed regressions reject large numeric price/id without string coercion,
retain raw JSON and valid neighbors, and preserve Python global digit limits.
Evidence is durably copied to artifacts/repair2-validation with hashes.
This was the old budget; the subsequent explicit user continuation instruction
supersedes the round stop, recorded in tasks/continuation-policy.json.

Final acceptance requires a new real verifier on the final common SHA and
full regression/lint/format/scope/SQLite checks; the receipt records their
actual outcomes. Verifier CLI process success alone does not mean review pass.
All synthetic prices and stock are test values, not shopping confirmations.

Runner experiments:
- passed: deterministic paused resume, failed resume, completed-step executes
  once, project lock excludes a second concurrent resume (exit 75).
- passed: actual Codex process deliberately killed (SIGKILL), recorded worker
  exit -9 / wrapper 137 and Spec Kit failed state. This is not a fake adapter.
- passed refusal / blocked recovery: killed coordinator left running state;
  resume refused it and its synthetic child was confirmed dead. No state edit
  was used to manufacture recovery. Use a new audited task after inspection.
- not run: actual worker retry after death, resource timeout expiry at 600s,
  two simultaneous writers/combined snapshot, fan-out/fan-in, loops, Converge.
Synthetic action probes prove orchestration, not agent product performance.

Live blocked: local tvly/tavily CLI, Python module, configured Tavily MCP and
environment API key were absent. The current Tavily search skill mentions
capped keyless search, but its referenced setup resource was unavailable;
installation/auth were not guessed. Parent-chat Tavily does not authorize
local Codex automatically. Direct Avito access was previously denied and
never retried by another browser/IP/proxy/hidden API. Indexed search is not run
in this pilot and could only create candidates, not verified price or stock.
No new paid API was started. Token usage exists in actual worker JSONL;
monetary cost was not measured. Worker wall limit is 600s, coordinator 660s,
no project round stop after the explicit continuation instruction. Each worker
keeps a 600s wall limit and no perpetual background service is scheduled.

Continuation from 2575afd: actual final review blocked on DEF-006 despite
136 passing tests. Historical receipt remains archived. Current acceptance
requires Unicode-class regression repair, finite real collector loop check,
and fresh independent review. Converge remains optional under the frozen
product specification; no untested parallel fan-out is promised.
