"""T013 additive scope: every tracked parent blob remains byte-identical."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "35b8141c781cab7a3c72271a98722f5947d93e46"
OWNED = {
    "tasks/T014.json",
    "src/pc_sourcing/collection_runtime.py",
    "src/pc_sourcing/collection_acquisition.py",
    "tests/test_collection_runtime.py",
    "scripts/collection_quality.py",
    "scripts/collection_check_workflow.py",
    "tasks/T013.json",
    "src/pc_sourcing/collection_state.py",
    "specs/009-source-coverage/tasks.md",
    "src/pc_sourcing/collection_capture.py",
    "src/pc_sourcing/collection_cli.py",
    "scripts/collection_scope.py",
    "workflows/collection-validation.yml",
    "tests/test_collection_acquisition.py",
    "specs/009-source-coverage/spec.md",
    "docs/CP-T013-01.md",
    "docs/collection-quickstart.md",
    "specs/009-source-coverage/plan.md",
    "src/pc_sourcing/collection_profiles.py",
    "tests/test_collection_capture.py",
    "tests/test_collection_scope.py",
    "specs/008-collection-integration/tasks.md",
    "tests/test_collection_profiles.py",
    "tests/test_collection_state.py",
    "specs/008-collection-integration/plan.md",
    "specs/008-collection-integration/traceability.md",
    "docs/source-route-plan.md",
    "specs/008-collection-integration/spec.md",
    "specs/009-source-coverage/traceability.md",
}

CP_FILE = "tests/test_normalized_scope.py"
CP_ORIGINAL = "ded9f8364d19040b0c6949ef8c8477285c86d5d23904e71ef90461075a90594f"
CP_APPROVED = "212c3d7e0154c0c3ba1d19c6013bd731b967c1e0563618f651d874282d5e081c"
CP_ANCHOR = b"def test_normalized_stage_preserves_parent_blobs():\n    result = scope.check(ROOT)\n"
CP_REPLACEMENT = b'def test_normalized_stage_preserves_parent_blobs(tmp_path):\n    import subprocess\n\n    checkout = tmp_path / "historical-T012"\n    subprocess.run(\n        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(checkout)], check=True\n    )\n    subprocess.run(\n        [\n            "git",\n            "-C",\n            str(checkout),\n            "checkout",\n            "--quiet",\n            "--detach",\n            "35b8141c781cab7a3c72271a98722f5947d93e46",\n        ],\n        check=True,\n    )\n    result = scope.check(checkout)\n'
CP_BINDING = {
    CP_FILE: {
        "change_proposal": "CP-T013-01",
        "original_sha256": CP_ORIGINAL,
        "approved_sha256": CP_APPROVED,
    }
}


def check(root=ROOT):
    task = json.loads((root / "tasks/T013.json").read_text())
    if task["base_commit"] != BASELINE or task["mutable_baseline_files"]:
        raise ValueError("T013 baseline/mutable scope mismatch")
    if set(task["owned_files"]) != OWNED:
        raise ValueError("unauthorized T013 ownership")
    names = set(
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", BASELINE], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    if names != set(task["protected_files"]):
        raise ValueError("T013 protected inventory mismatch")
    if task.get("approved_protected_patches") != CP_BINDING:
        raise ValueError("exact CP-T013-01 binding missing")
    for name in names:
        expected = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=root)
        if name == CP_FILE:
            if (
                hashlib.sha256(expected).hexdigest() != CP_ORIGINAL
                or expected.count(CP_ANCHOR) != 1
            ):
                raise ValueError("CP-T013-01 original binding mismatch")
            expected = expected.replace(CP_ANCHOR, CP_REPLACEMENT)
            if hashlib.sha256(expected).hexdigest() != CP_APPROVED:
                raise ValueError("CP-T013-01 approved binding mismatch")
        if (root / name).is_symlink() or (root / name).read_bytes() != expected:
            raise ValueError("protected parent changed: " + name)
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", BASELINE], cwd=root, text=True
    ).splitlines()
    other = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=root, text=True
    ).splitlines()
    if (set(changed) | set(other)) - OWNED - {CP_FILE}:
        raise ValueError("unowned T013 changes")
    for name in OWNED:
        if not (root / name).is_file() or (root / name).is_symlink():
            raise ValueError("owned file missing/symlink: " + name)
    if (
        hashlib.sha256((root / "specs/008-collection-integration/spec.md").read_bytes()).hexdigest()
        != task["spec_sha256"]
    ):
        raise ValueError("T013 spec/task hash mismatch")
    return {
        "status": "passed",
        "baseline": BASELINE,
        "protected_byte_identical": len(names) - 1,
        "approved_protected_patches": 1,
    }


if __name__ == "__main__":
    print(json.dumps(check()))
