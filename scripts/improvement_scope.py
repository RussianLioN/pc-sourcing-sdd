"""Additive T017 scope; every accepted parent Git blob remains protected."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "f495e5294e93a281f945de6f4e1c6c89d7a6cb1e"
DOCS = {
    "spec.md",
    "plan.md",
    "tasks.md",
    "traceability.md",
    "research.md",
    "data-model.md",
    "quickstart.md",
    "contracts/process-cli.md",
    "checklists/requirements.md",
    "notices/compound-MIT.txt",
    "CP-T017-01.md",
    "baseline.json",
    "mutant-corpus.json",
    "consumer-case.json",
    "authority-readiness.json",
    "cutover.json",
    "process-evidence.json",
}
OWNED = {"specs/012-reviewed-improvement/" + name for name in DOCS} | {
    "scripts/reviewed_lessons.py",
    "scripts/lesson_consumer.py",
    "scripts/critical_mutations.py",
    "scripts/process_metrics.py",
    "scripts/improvement_scope.py",
    "scripts/improvement_quality.py",
    "scripts/improvement_check_workflow.py",
    "workflows/improvement-validation.yml",
    "tasks/T017.json",
    "tests/test_reviewed_lessons.py",
    "tests/test_lesson_consumer.py",
    "tests/test_critical_mutations.py",
    "tests/test_process_metrics.py",
    "tests/test_improvement_scope.py",
    ".agents/skills/pc-reviewed-lessons/SKILL.md",
    ".agents/skills/pc-reviewed-lessons/agents/openai.yaml",
}
CP_FILE = "tests/test_witness_scope.py"
CP_ORIGINAL = "effdd1008046a909286722a59637e4357747c6338e5384b6fcb0cd9ebede08f1"
CP_CANDIDATE = "fa337fded2e26f9a6bd0c6423c89dfb3e22dd0dc82c6a4617ce5b93b7749843f"
CP_AUTHORIZED = True


def check(root=ROOT):
    root = Path(root)
    task = json.loads((root / "tasks/T017.json").read_bytes())
    if task["base_commit"] != BASE or set(task["owned_files"]) != OWNED:
        raise ValueError("unauthorized T017 baseline/ownership")
    names = (
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", BASE], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    expected_cp = (
        {
            CP_FILE: {
                "change_proposal": "CP-T017-01",
                "original_sha256": CP_ORIGINAL,
                "approved_sha256": CP_CANDIDATE,
            }
        }
        if CP_AUTHORIZED
        else {}
    )
    if task["approved_protected_patches"] != expected_cp:
        raise ValueError("exact CP binding mismatch")
    if set(names) != set(task["protected_files"]):
        raise ValueError("protected inventory mismatch")
    for name in names:
        path = root / name
        expected = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=root)
        if name == CP_FILE and CP_AUTHORIZED:
            if hashlib.sha256(expected).hexdigest() != CP_ORIGINAL:
                raise ValueError("CP original mismatch")
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != CP_CANDIDATE:
                raise ValueError("approved exact CP mismatch")
        elif path.is_symlink() or path.read_bytes() != expected:
            raise ValueError("protected parent changed: " + name)
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", "-z", BASE], cwd=root, text=True)
        .strip("\0")
        .split("\0")
    )
    untracked = (
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root, text=True
        )
        .strip("\0")
        .split("\0")
    )
    allowed = OWNED | ({CP_FILE} if CP_AUTHORIZED else set())
    if (set(filter(None, changed)) | set(filter(None, untracked))) - allowed:
        raise ValueError("unowned T017 files")
    for name in OWNED:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("owned file missing/symlink: " + name)
    if (
        hashlib.sha256((root / "specs/012-reviewed-improvement/spec.md").read_bytes()).hexdigest()
        != task["spec_sha256"]
    ):
        raise ValueError("spec hash mismatch")
    return {
        "status": "PASS",
        "parent_identical": len(names) - int(CP_AUTHORIZED),
        "approved_exact_CP": int(CP_AUTHORIZED),
        "real_learning_enabled": False,
    }


if __name__ == "__main__":
    print(json.dumps(check()))
