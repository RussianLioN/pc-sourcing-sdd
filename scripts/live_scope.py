"""Check additive T009 scope against independently supplied baseline Git blobs."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    task = json.loads((root / "tasks/T009.json").read_text())
    base = task["base_commit"]
    if base != "5e031fcdd2daf7690585ed84f1b731c0972f4dc3":
        raise ValueError("accepted baseline SHA changed")
    names = (
        subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "-z", base], cwd=root)
        .decode()
        .strip("\0")
        .split("\0")
    )
    if set(names) != set(task["protected_files"]):
        raise ValueError("protected inventory changed")
    for name in names:
        expected = subprocess.check_output(["git", "show", f"{base}:{name}"], cwd=root)
        if name == "tests/test_native_cloud.py":
            anchor = b'    shutil.copy2(ROOT / "scripts/native_cloud.py", root / "scripts/native_cloud.py")\n'
            patch = b'    subprocess.run(\n        [\n            "git",\n            "-C",\n            str(root),\n            "checkout",\n            "--detach",\n            "5e031fcdd2daf7690585ed84f1b731c0972f4dc3",\n        ],\n        check=True,\n    )\n'
            if set(task.get("approved_protected_patches", {})) != {name}:
                raise ValueError("approved fixture-only CP binding missing")
            if expected.count(anchor) != 1:
                raise ValueError("unexpected historical fixture anchor")
            expected = expected.replace(anchor, patch + anchor)
        if (root / name).read_bytes() != expected:
            raise ValueError("baseline changed: " + name)
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", "-z", base], cwd=root)
        .decode()
        .strip("\0")
        .split("\0")
    )
    untracked = (
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root
        )
        .decode()
        .strip("\0")
        .split("\0")
    )
    unexpected = set(changed + untracked) - set(task["owned_files"]) - {""}
    if unexpected:
        raise ValueError("unowned changes: " + repr(sorted(unexpected)))
    if (
        hashlib.sha256((root / "specs/004-live-sourcing/spec.md").read_bytes()).hexdigest()
        != task["spec_sha256"]
    ):
        raise ValueError("spec/task hash mismatch")
    return {"status": "passed", "baseline": base, "protected_files": len(names)}


if __name__ == "__main__":
    print(json.dumps(check()))
