"""Coordinator-only scope gate: base commit comes from coordinator task."""

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path


def check(task_path, worktree):
    task = json.loads(Path(task_path).read_text())
    base = task["base_commit"]
    if task.get("status") != "ready":
        raise SystemExit("BLOCKED task not ready")
    spec = Path(worktree) / "specs/001-offline/spec.md"
    if hashlib.sha256(spec.read_bytes()).hexdigest() != task["spec_sha256"]:
        raise SystemExit("BLOCKED task spec hash stale")
    if task["spec_revision"] != "1.0.0":
        raise SystemExit("BLOCKED task spec revision unsupported")
    for dependency in task["dependencies"]:
        receipt = (
            Path(task["coordinator_root"]) / "artifacts/task-receipts" / (dependency + ".json")
        )
        if not receipt.exists() or json.loads(receipt.read_text()).get("status") != "passed":
            raise SystemExit("BLOCKED unmet task dependency: " + dependency)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(worktree), *args], text=True).strip()

    changed = set(git("diff", "--name-only", base).splitlines())
    changed |= set(git("ls-files", "--others", "--exclude-standard").splitlines())
    bad = changed - set(task["owned_files"])
    if bad:
        raise SystemExit("BLOCKED unowned changes: " + ", ".join(sorted(bad)))
    for p in task["protected_files"]:
        expected = subprocess.check_output(
            [
                "git",
                "-C",
                task["coordinator_root"],
                "show",
                f"{task.get('protected_baselines', {}).get(p, base)}:{p}",
            ]
        )
        if (Path(worktree) / p).read_bytes() != expected:
            raise SystemExit("BLOCKED protected baseline changed: " + p)
    for p in task.get("protected_behavior_files", []):
        before = subprocess.check_output(
            ["git", "-C", task["coordinator_root"], "show", f"{base}:{p}"]
        )

        def behavior(raw):
            tree = ast.parse(raw)
            tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
            return ast.dump(tree, include_attributes=False)

        if behavior(before) != behavior((Path(worktree) / p).read_bytes()):
            raise SystemExit("BLOCKED protected test behavior changed: " + p)
    print(json.dumps({"status": "passed", "base_commit": base, "changed_files": sorted(changed)}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("worktree")
    args = ap.parse_args()
    check(args.task, args.worktree)
