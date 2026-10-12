"""T012 additive scope: every parent blob is frozen except exact CP-T012-01."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "daabf63f8fb7ccc429d945490e0d0d6e88da7970"
OWNED = {
    "tests/test_normalized_offers.py",
    "tasks/T012.json",
    "tests/test_normalized_scope.py",
    "specs/007-normalized-offers/traceability.md",
    "src/pc_sourcing/normalized_exports.py",
    "src/pc_sourcing/normalized_offers.py",
    "scripts/normalized_quality.py",
    "scripts/normalized_check_workflow.py",
    "tests/test_normalized_exports.py",
    "specs/007-normalized-offers/change-proposal-01.md",
    "workflows/normalized-validation.yml",
    "specs/007-normalized-offers/spec.md",
    "specs/007-normalized-offers/plan.md",
    "specs/007-normalized-offers/tasks.md",
    "src/pc_sourcing/normalized_cli.py",
    "docs/normalized-quickstart.md",
    "scripts/normalized_scope.py",
    "src/pc_sourcing/normalized_models.py",
}


CP_FILE = "tests/test_durable_scope.py"
CP_ORIGINAL = "ad02c516a0d74b0e849e7292ba1682cc28f872fdd20818b8786ab61a96422d01"
CP_APPROVED = "895cc5c36a4b73726b862a57bfe15b5b2ba11508d9666606e8aea09e9eda3b99"
CP_BINDING = {
    CP_FILE: {
        "change_proposal": "CP-T012-01",
        "original_sha256": CP_ORIGINAL,
        "approved_sha256": CP_APPROVED,
    }
}


def check(root=ROOT):
    task = json.loads((root / "tasks/T012.json").read_text())
    if task["base_commit"] != BASELINE or task["mutable_baseline_files"]:
        raise ValueError("T012 baseline/mutable scope mismatch")
    if set(task["owned_files"]) != OWNED:
        raise ValueError("unauthorized T012 ownership")
    names = set(
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", BASELINE], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    if names != set(task["protected_files"]):
        raise ValueError("T012 protected inventory mismatch")
    if task.get("approved_protected_patches") != CP_BINDING:
        raise ValueError("exact CP-T012-01 binding missing")
    for name in names:
        expected = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=root)
        if name == CP_FILE:
            if hashlib.sha256(expected).hexdigest() != CP_ORIGINAL:
                raise ValueError("CP-T012-01 original hash mismatch")
            anchor = b'def test_new_scope_preserves_all_parent_blobs():\n    assert scope.check()["approved_protected_patches"] == 0\n'
            replacement = b'def test_new_scope_preserves_all_parent_blobs(tmp_path):\n    assert scope.check(checkout(tmp_path))["approved_protected_patches"] == 0\n'
            if expected.count(anchor) != 1:
                raise ValueError("CP-T012-01 exact anchor mismatch")
            expected = expected.replace(anchor, replacement)
            if hashlib.sha256(expected).hexdigest() != CP_APPROVED:
                raise ValueError("CP-T012-01 approved hash mismatch")
        if (root / name).is_symlink() or (root / name).read_bytes() != expected:
            raise ValueError("protected parent changed: " + name)
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", BASELINE], cwd=root, text=True
    ).splitlines()
    other = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=root, text=True
    ).splitlines()
    if (set(changed) | set(other)) - OWNED - {CP_FILE}:
        raise ValueError("unowned T012 changes")
    for name in OWNED:
        if not (root / name).is_file() or (root / name).is_symlink():
            raise ValueError("owned file missing/symlink: " + name)
    if (
        hashlib.sha256((root / "specs/007-normalized-offers/spec.md").read_bytes()).hexdigest()
        != task["spec_sha256"]
    ):
        raise ValueError("T012 spec/task hash mismatch")
    return {
        "status": "passed",
        "baseline": BASELINE,
        "protected_byte_identical": len(names) - 1,
        "approved_protected_patches": 1,
    }


if __name__ == "__main__":
    print(json.dumps(check()))
