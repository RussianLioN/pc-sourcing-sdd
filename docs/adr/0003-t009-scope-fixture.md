# CP-T010-01 — historical T009 scope unit setup

Status: pending explicit coordinator approval. One protected baseline file:
tests/test_stage_acceptance.py, setup inside
`test_current_scope_accepts_only_approved_fixture_patch_and_owned_additions`.

Reproducer: quality at T010 contract commit 557c855 plus current writer code:
482 passed, one failed. The test clones successor HEAD then invokes frozen T009
scope; new specs/005 + T010 assignment are correctly unowned in T009. No product
failure/assertion expectations should be relaxed to hide this.

Exact proposed insertion, immediately after clone and before task loading:

```python
subprocess.run(
    ["git", "-C", str(checkout), "checkout", "--detach",
     "130d67acd07b68a942dd62daf9127723556916e3"],
    check=True,
)
```

Then existing copy of T009 task-owned files and every existing assertion/negative
case remain unchanged. Only historical unit checkout context is pinned. Current
T010 is tested by new primary_scope and its negatives; T008 checker/fixtures,
T009 scope code/contracts/receipts unchanged. T008/T009 gate still reject successor
scope; no skip/deselect/xfail, widened allowlist or retroactive acceptance.

Needs explicit approved T010 ownership exception for this exact setup insertion.
Until then keep full check failed and preserve original failure receipt.
