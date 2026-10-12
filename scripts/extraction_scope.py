"""T015 additive ownership; parent bytes stay protected until exact CP review."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "79df7e5a04a9a54b4ee2122c4729459bfd512bae"
OWNED = {
    "specs/010-product-extraction/spec.md",
    "specs/010-product-extraction/plan.md",
    "specs/010-product-extraction/tasks.md",
    "specs/010-product-extraction/traceability.md",
    "tasks/T015.json",
    "src/pc_sourcing/product_extraction.py",
    "src/pc_sourcing/product_extraction_cli.py",
    "tests/test_product_extraction.py",
    "scripts/extraction_scope.py",
    "tests/test_extraction_scope.py",
    "docs/CP-T015-01.md",
    "docs/gpu-smoke-plan.md",
    "scripts/extraction_quality.py",
    "scripts/extraction_check_workflow.py",
    "workflows/extraction-validation.yml",
}

CP_FILE = "tests/test_collection_scope.py"
CP_ORIGINAL = "03a7ff6d16fc840348c10ef0c1bae4d278810e40af62aab36708e2d902e62c79"
CP_APPROVED = "eea35f690719d7444ef3ca91add35f24170c42987b79f8c779ba62b6961b6535"
CP_ANCHOR = b'def test_collection_preserves_all_parent_blobs():\n    assert scope.check()["protected_byte_identical"] == 200\n    assert scope.check()["approved_protected_patches"] == 1\n'
CP_REPLACEMENT = b'def test_collection_preserves_all_parent_blobs(tmp_path):\n    import subprocess\n\n    checkout = tmp_path / "historical-T013"\n    subprocess.run(\n        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(checkout)], check=True\n    )\n    subprocess.run(\n        [\n            "git",\n            "-C",\n            str(checkout),\n            "checkout",\n            "--quiet",\n            "--detach",\n            "79df7e5a04a9a54b4ee2122c4729459bfd512bae",\n        ],\n        check=True,\n    )\n    assert scope.check(checkout)["protected_byte_identical"] == 200\n    assert scope.check(checkout)["approved_protected_patches"] == 1\n'
CP_BINDING = {
    CP_FILE: {
        "change_proposal": "CP-T015-01",
        "original_sha256": CP_ORIGINAL,
        "approved_sha256": CP_APPROVED,
    }
}


def check(root=ROOT):
    task = json.loads((root / "tasks/T015.json").read_text())
    if (
        task["base_commit"] != BASE
        or set(task["owned_files"]) != OWNED
        or task["mutable_baseline_files"]
    ):
        raise ValueError("T015 unauthorized baseline/ownership")
    names = (
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", BASE], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    if set(names) != set(task["protected_files"]):
        raise ValueError("T015 parent inventory mismatch")
    if task.get("approved_protected_patches") != CP_BINDING:
        raise ValueError("T015 exact approved CP binding missing")
    for name in names:
        path = root / name
        expected = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=root)
        if name == CP_FILE:
            if (
                hashlib.sha256(expected).hexdigest() != CP_ORIGINAL
                or expected.count(CP_ANCHOR) != 1
            ):
                raise ValueError("T015 original CP fixture mismatch")
            expected = expected.replace(CP_ANCHOR, CP_REPLACEMENT)
            if hashlib.sha256(expected).hexdigest() != CP_APPROVED:
                raise ValueError("T015 proposed exact CP fixture mismatch")
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
        raise ValueError("unowned T015 change")
    for name in OWNED:
        p = root / name
        if p.is_symlink() or not p.is_file():
            raise ValueError("owned T015 file missing/symlink")
    if (
        hashlib.sha256((root / "specs/010-product-extraction/spec.md").read_bytes()).hexdigest()
        != task["spec_sha256"]
    ):
        raise ValueError("T015 spec hash mismatch")
    return {
        "status": "PASS",
        "parent_identical": len(names) - 1,
        "approved_protected_patches": 1,
        "CP_T015_01": "approved_exact_hash_transition",
    }


if __name__ == "__main__":
    print(json.dumps(check()))
