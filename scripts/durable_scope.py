"""T011 additive scope: every tracked parent blob remains byte-identical."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "bd70f4fceff1199726d89c86dd7e16085f934be2"
OWNED = {
    "specs/006-durable-jobs/spec.md",
    "specs/006-durable-jobs/plan.md",
    "specs/006-durable-jobs/tasks.md",
    "specs/006-durable-jobs/traceability.md",
    "tasks/T011.json",
    "src/pc_sourcing/durable_jobs.py",
    "src/pc_sourcing/durable_cli.py",
    "src/pc_sourcing/durable_product.py",
    "tests/test_durable_product.py",
    "tests/test_durable_jobs.py",
    "tests/test_durable_scope.py",
    "scripts/durable_scope.py",
    "scripts/durable_quality.py",
    "scripts/durable_check_workflow.py",
    "workflows/durable-validation.yml",
    "docs/durable-quickstart.md",
}


def check(root=ROOT):
    task = json.loads((root / "tasks/T011.json").read_text())
    if task["base_commit"] != BASELINE or task["mutable_baseline_files"]:
        raise ValueError("T011 baseline/mutable scope mismatch")
    if set(task["owned_files"]) != OWNED:
        raise ValueError("unauthorized T011 ownership")
    names = set(
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", BASELINE], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    if names != set(task["protected_files"]):
        raise ValueError("T011 protected inventory mismatch")
    for name in names:
        if (root / name).is_symlink() or (root / name).read_bytes() != subprocess.check_output(
            ["git", "show", f"{BASELINE}:{name}"], cwd=root
        ):
            raise ValueError("protected parent changed: " + name)
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", BASELINE], cwd=root, text=True
    ).splitlines()
    other = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=root, text=True
    ).splitlines()
    if (set(changed) | set(other)) - OWNED:
        raise ValueError("unowned T011 changes")
    for name in OWNED:
        if not (root / name).is_file() or (root / name).is_symlink():
            raise ValueError("owned file missing/symlink: " + name)
    if (
        hashlib.sha256((root / "specs/006-durable-jobs/spec.md").read_bytes()).hexdigest()
        != task["spec_sha256"]
    ):
        raise ValueError("T011 spec/task hash mismatch")
    return {
        "status": "passed",
        "baseline": BASELINE,
        "protected_byte_identical": len(names),
        "approved_protected_patches": 0,
    }


if __name__ == "__main__":
    print(json.dumps(check()))
