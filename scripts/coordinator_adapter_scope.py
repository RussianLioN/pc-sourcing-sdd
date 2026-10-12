"""T018 additive scope; accepted inactive T017 remains byte protected."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "4bc835b57d948c56afc29ceafce671a9ce739099"
DOCS = {
    "spec.md",
    "plan.md",
    "tasks.md",
    "traceability.md",
    "data-model.md",
    "quickstart.md",
    "checklists/requirements.md",
    "CP-T018-01.md",
}
OWNED = {"specs/013-coordinator-adapter/" + n for n in DOCS} | {
    "tasks/T018.json",
    "scripts/coordinator_adapter.py",
    "scripts/coordinator_adapter_scope.py",
    "scripts/coordinator_adapter_quality.py",
    "scripts/coordinator_adapter_check_workflow.py",
    "workflows/coordinator-adapter-validation.yml",
    "tests/test_coordinator_adapter.py",
    "tests/test_coordinator_adapter_scope.py",
}
CP_FILE = "tests/test_improvement_scope.py"
CP_ORIGINAL = "35f896945d8d0fa97dfb3bb876d86d008a3614ccd60ffee87fb9ad3af8df2b1e"
CP_PROPOSED = "90f39fd920523a7679b4f27bdba92b740442f0ef86b3ee7eae6fc37ade6fd8db"
CP_APPROVED = True


def check(root=ROOT):
    root = Path(root)
    task = json.loads((root / "tasks/T018.json").read_text())
    if task["base_commit"] != BASE or set(task["owned_files"]) != OWNED:
        raise ValueError("T018 ownership/base mismatch")
    names = (
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", BASE], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    if set(names) != set(task["protected_files"]):
        raise ValueError("T018 protected inventory mismatch")
    cp = (
        {CP_FILE: {"original_sha256": CP_ORIGINAL, "approved_sha256": CP_PROPOSED}}
        if CP_APPROVED
        else {}
    )
    if task["approved_protected_patches"] != cp:
        raise ValueError("T018 exact CP binding mismatch")
    for name in names:
        p = root / name
        expected = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=root)
        if p.is_symlink():
            raise ValueError("protected symlink")
        if name == CP_FILE and CP_APPROVED:
            if (
                hashlib.sha256(expected).hexdigest() != CP_ORIGINAL
                or hashlib.sha256(p.read_bytes()).hexdigest() != CP_PROPOSED
            ):
                raise ValueError("T018 approved exact CP mismatch")
        elif p.read_bytes() != expected:
            raise ValueError("T018 protected parent changed: " + name)
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", "-z", BASE], cwd=root, text=True)
        .strip("\0")
        .split("\0")
    )
    new = (
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    permitted = OWNED | ({CP_FILE} if CP_APPROVED else set())
    if (set(filter(None, changed)) | set(filter(None, new))) - permitted:
        raise ValueError("T018 unowned files")
    for name in OWNED:
        if (root / name).is_symlink() or not (root / name).is_file():
            raise ValueError("T018 owned missing/symlink")
    if (
        hashlib.sha256((root / "specs/013-coordinator-adapter/spec.md").read_bytes()).hexdigest()
        != task["spec_sha256"]
    ):
        raise ValueError("T018 spec hash mismatch")
    return {
        "status": "PASS",
        "parent_identical": len(names) - int(CP_APPROVED),
        "approved_exact_CP": int(CP_APPROVED),
        "learning_enabled": False,
    }


if __name__ == "__main__":
    print(json.dumps(check()))
