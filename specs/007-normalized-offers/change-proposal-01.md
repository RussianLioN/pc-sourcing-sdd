# CP-T012-01: historical T011 scope test setup

Status: explicitly authorized by the user through the coordinator on 2026-10-12,
applied exactly as shown below. No protected requirement or assertion expectation
changes. Branch publication is authorized without merge.

The T011 positive scope test currently inspects the current repository. Every
additive successor is intentionally rejected by the historical T011 gate, so its
positive test must run against its own historical stage fixture. The existing
`checkout(tmp_path)` helper already reconstructs that stage and is used by its
negative cases. Keep the historical gate unchanged and reuse this helper.

Exact proposed change in tests/test_durable_scope.py:

```diff
-def test_new_scope_preserves_all_parent_blobs():
-    assert scope.check()["approved_protected_patches"] == 0
+def test_new_scope_preserves_all_parent_blobs(tmp_path):
+    assert scope.check(checkout(tmp_path))["approved_protected_patches"] == 0
```

Acceptance: the historical positive and five negative scope cases pass; the
historical gate still rejects a T012 successor; all T011 parent bytes except this
exact approved setup patch remain identical. T012 scope must bind both original
and approved test hashes and reject any additional drift.

Fixture binding:

- Existing helper: `checkout(tmp_path)` in tests/test_durable_scope.py.
- It checks out `scope.BASELINE` = `bd70f4fceff1199726d89c86dd7e16085f934be2` (accepted T010), then copies exactly the 16 T011 `scope.OWNED` files from ROOT. It does not itself check out T011 HEAD.
- Those copied parent files are currently byte-bound by T012 scope to accepted T011 `daabf63f8fb7ccc429d945490e0d0d6e88da7970`. After approval the sole exception is this exact test setup patch. The helper and historical gate remain unchanged.
- Original protected test SHA256: `ad02c516a0d74b0e849e7292ba1682cc28f872fdd20818b8786ab61a96422d01`.
- Exact proposed patched test SHA256: `895cc5c36a4b73726b862a57bfe15b5b2ba11508d9666606e8aea09e9eda3b99`.

Only the two lines shown in the diff change. All other assertions, five parametrized negative cases and historical rejection tests remain byte-identical. T012 has its own independent byte-bound scope gate and negative drift tests; historical gates are not widened to accept successors.
