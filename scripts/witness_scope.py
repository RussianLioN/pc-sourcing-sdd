"""T016 additive ownership; parent bytes stay protected until exact CP review."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "e772a60eb6dbdc5f8019e4a72ddf43a00ebbac18"
OWNED = {
    "scripts/witness_scope.py",
    "scripts/witness_quality.py",
    "tasks/T016.json",
    "scripts/witness_check_workflow.py",
    "specs/011-witness-controller/traceability.md",
    "src/pc_sourcing/witness_cli.py",
    "tests/test_witness_transfer.py",
    "src/pc_sourcing/witness_controller.py",
    "src/pc_sourcing/witness_transfer.py",
    "specs/011-witness-controller/tasks.md",
    "specs/011-witness-controller/spec.md",
    "tests/test_witness_controller.py",
    "src/pc_sourcing/witness_profiles.py",
    "specs/011-witness-controller/plan.md",
    "workflows/witness-validation.yml",
    "docs/witness-quickstart.md",
    "tests/test_witness_scope.py",
    "docs/CP-T016-01.md",
    "tests/test_witness_profiles.py",
}

CP_FILE = "tests/test_extraction_scope.py"
CP_ORIGINAL = "e45e014847853bd4496cb87fcb3dc5b7ac55f3507c52ca8fb3eaf9db6603b537"
CP_APPROVED = "813be738b560703842fcd32a91e26f0a348e81ccb07879e02ad74c553eefbf3a"
CP_ANCHOR = b'def test_extraction_preserves_every_parent_byte():\n    assert scope.check()["parent_identical"] == 229\n    assert scope.check()["approved_protected_patches"] == 1\n'
CP_REPLACEMENT = b'def test_extraction_preserves_every_parent_byte(tmp_path):\n    checkout = tmp_path / "historical-T015"\n    subprocess.run(\n        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(checkout)], check=True\n    )\n    subprocess.run(\n        [\n            "git",\n            "-C",\n            str(checkout),\n            "checkout",\n            "--quiet",\n            "--detach",\n            "e772a60eb6dbdc5f8019e4a72ddf43a00ebbac18",\n        ],\n        check=True,\n    )\n    assert scope.check(checkout)["parent_identical"] == 229\n    assert scope.check(checkout)["approved_protected_patches"] == 1\n'
CP_BINDING = {
    CP_FILE: {
        "change_proposal": "CP-T016-01",
        "original_sha256": CP_ORIGINAL,
        "approved_sha256": CP_APPROVED,
    }
}


def check(root=ROOT):
    task = json.loads((root / "tasks/T016.json").read_text())
    if (
        task["base_commit"] != BASE
        or set(task["owned_files"]) != OWNED
        or task["mutable_baseline_files"]
    ):
        raise ValueError("T016 unauthorized baseline/ownership")
    names = (
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", BASE], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    if set(names) != set(task["protected_files"]):
        raise ValueError("T016 parent inventory mismatch")
    if task.get("approved_protected_patches") != CP_BINDING:
        raise ValueError("exact approved CP-T016-01 binding missing")
    for name in names:
        path = root / name
        expected = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=root)
        if name == CP_FILE:
            if (
                hashlib.sha256(expected).hexdigest() != CP_ORIGINAL
                or expected.count(CP_ANCHOR) != 1
            ):
                raise ValueError("approved CP original baseline mismatch")
            expected = expected.replace(CP_ANCHOR, CP_REPLACEMENT)
            if hashlib.sha256(expected).hexdigest() != CP_APPROVED:
                raise ValueError("approved CP exact replacement mismatch")
        if path.is_symlink() or path.read_bytes() != expected:
            raise ValueError("protected parent changed: " + name)
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", "-z", BASE], cwd=root, text=True)
        .strip("\0")
        .split("\0")
    )
    other = (
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    changed, other = list(filter(None, changed)), list(filter(None, other))
    if (set(changed) | set(other)) - OWNED - {CP_FILE}:
        raise ValueError("unowned T016 change")
    for name in OWNED:
        p = root / name
        if p.is_symlink() or not p.is_file():
            raise ValueError("owned T016 file missing/symlink")
    if (
        hashlib.sha256((root / "specs/011-witness-controller/spec.md").read_bytes()).hexdigest()
        != task["spec_sha256"]
    ):
        raise ValueError("T016 spec hash mismatch")
    return {
        "status": "PASS",
        "parent_identical": len(names) - 1,
        "approved_protected_patches": 1,
        "CP_T016_01": "approved_exact_hash_transition",
    }


if __name__ == "__main__":
    print(json.dumps(check()))
