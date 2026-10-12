"""T010 additive scope; immutable product/previous stage preserved at accepted SHA."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "130d67acd07b68a942dd62daf9127723556916e3"


def check(root=ROOT):
    task = json.loads((root / "tasks/T010.json").read_text())
    if task["base_commit"] != BASELINE:
        raise ValueError("wrong T010 accepted baseline")
    allowed_mutations = {"src/pc_sourcing/live_models.py", "src/pc_sourcing/live_sourcing.py"}
    if set(task["mutable_baseline_files"]) != allowed_mutations:
        raise ValueError("unauthorized mutable baseline scope")
    names = (
        subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "-z", BASELINE], cwd=root)
        .decode()
        .strip("\0")
        .split("\0")
    )
    if set(names) != set(task["protected_files"]):
        raise ValueError("baseline inventory differs")
    for name in names:
        if name in allowed_mutations:
            continue
        expected = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=root)
        if name == "tests/test_stage_acceptance.py":
            anchor = b'    task = json.loads((ROOT / "tasks/T009.json").read_text())\n'
            patch = b'    subprocess.run(\n        [\n            "git",\n            "-C",\n            str(checkout),\n            "checkout",\n            "--detach",\n            "130d67acd07b68a942dd62daf9127723556916e3",\n        ],\n        check=True,\n    )\n'
            if (
                set(task.get("approved_protected_patches", {})) != {name}
                or expected.count(anchor) != 1
            ):
                raise ValueError("approved CP-T010-01 binding missing")
            expected = expected.replace(anchor, patch + anchor)
        if (root / name).read_bytes() != expected:
            raise ValueError("protected prior stage changed: " + name)
    changed = subprocess.check_output(["git", "diff", "--name-only", "-z", BASELINE], cwd=root)
    other = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root
    )
    files = set((changed + other).decode().strip("\0").split("\0")) - {""}
    if files - set(task["owned_files"]):
        raise ValueError("unowned T010 changes")
    if (
        hashlib.sha256((root / "specs/005-primary-verification/spec.md").read_bytes()).hexdigest()
        != task["spec_sha256"]
    ):
        raise ValueError("T010 spec/task mismatch")
    return {
        "status": "passed",
        "baseline": BASELINE,
        "protected_byte_identical": len(names) - 3,
        "approved_setup_patch": 1,
    }


if __name__ == "__main__":
    print(json.dumps(check()))
