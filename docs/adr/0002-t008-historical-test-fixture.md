# CP-T009-01 — historical fixture pin

Status: narrowly approved by coordinator on 2026-10-11 after independent review.
This decision changes only setup fixture `bundle` in tests/test_native_cloud.py.
It does not change product DoD, native checker, T008 contract, criteria or history.

Problem: fixture clones current HEAD, then applies frozen T008 allowlist. Successor
T009 files fail setup before 27 assertions. This is correct behavior for T008
acceptance but wrong input snapshot for its synthetic unit harness.

Approved delta: after clone, checkout detached accepted T008 baseline
5e031fcdd2daf7690585ed84f1b731c0972f4dc3; copy current scripts/native_cloud.py as before;
create synthetic candidate commit and execute every unchanged test body/assertion.
This synthetic receipt remains explicitly non-evidence of real task acceptance.

The only protected-file change is that exact setup insertion. scripts/live_scope.py
checks it against the independently supplied baseline Git blob plus the exact
approved insertion. Other 127 files stay byte-identical; no arbitrary fixture
edit or assertion change is accepted. Task ownership records this exception.

New tests/test_stage_acceptance.py proves: current T009 SHA still rejected by
T008 as unowned; every old test body/assertion/module node except approved fixture
is AST-identical; current T009 scope accepts only owned additions/exact insertion,
rejects foreign files/further fixture changes; native checker/T008 contract bytes
are unchanged. No allowlist widening, skipped/xfail cases or old verdict mutation.

A separate current-stage scope is already used by T009. Routing T009 through
T008 would widen its frozen contract; adding another test alone cannot unblock
old fixture setup. A generic stage dispatcher is unnecessary for this approved
minimal repair. Any future dispatcher requires explicit selectors, rejection of
unknown stages and independent immutable contracts for each stage.

Review fb07134 rejected T009 for robots denial handling, malformed-card isolation,
identity/cooling and conditional-price defects. Repair is traced in T009 tests;
new SHA/full checks/independent review required. Prior rejected receipts preserved.

Exact approved setup insertion, immediately before the existing shutil.copy2:

```python
subprocess.run(
    [
        "git",
        "-C",
        str(root),
        "checkout",
        "--detach",
        "5e031fcdd2daf7690585ed84f1b731c0972f4dc3",
    ],
    check=True,
)
```

All old assertions remain byte-identical; the scope gate allows only this exact
insertion, while the new regression additionally compares every other AST node.
