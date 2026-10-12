"""OPS-10: immutable T010 parent and explicit rejection by historical scope."""

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
scope = importlib.import_module("durable_scope")


def checkout(tmp_path):
    target = tmp_path / "checkout"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(target)], check=True
    )
    subprocess.run(
        ["git", "-C", str(target), "checkout", "--quiet", "--detach", scope.BASELINE], check=True
    )
    for name in scope.OWNED:
        dst = target / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dst)
    return target


def test_new_scope_preserves_all_parent_blobs(tmp_path):
    assert scope.check(checkout(tmp_path))["approved_protected_patches"] == 0


@pytest.mark.parametrize("mutation", ["old_app", "old_test", "owner", "spec", "extra"])
def test_scope_rejects_protected_drift_and_new_ownership(tmp_path, mutation):
    root = checkout(tmp_path)
    assert scope.check(root)["status"] == "passed"
    if mutation == "old_app":
        (root / "src/pc_sourcing/live_sourcing.py").write_text("changed")
    elif mutation == "old_test":
        (root / "tests/test_identity_claims.py").write_text("changed")
    elif mutation == "owner":
        p = root / "tasks/T011.json"
        task = json.loads(p.read_text())
        task["owned_files"].append("unapproved.py")
        p.write_text(json.dumps(task))
    elif mutation == "spec":
        (root / "specs/006-durable-jobs/spec.md").write_text("changed")
    else:
        (root / "unapproved.py").write_text("data")
    with pytest.raises(ValueError):
        scope.check(root)


def test_historical_primary_gate_rejects_t011_successor():
    historical = importlib.import_module("primary_scope")
    with pytest.raises(ValueError, match="unowned T010 changes"):
        historical.check(ROOT)
