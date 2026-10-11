"""Coordinator-only scope gate: base commit comes from coordinator task."""

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def coordinator_path(value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def check(task_path, worktree):
    task = json.loads(Path(task_path).read_text())
    base = task["base_commit"]
    coordinator = coordinator_path(task["coordinator_root"])
    change = task.get("change_spec")
    if change:
        change_path = (Path(worktree) / change["path"]).resolve()
        if not change_path.is_relative_to((Path(worktree) / "specs").resolve()):
            raise SystemExit("BLOCKED change spec outside specs")
        if (
            change["revision"] != "1.0.0"
            or hashlib.sha256(change_path.read_bytes()).hexdigest() != change["sha256"]
        ):
            raise SystemExit("BLOCKED change spec hash stale")
    if task.get("status") != "ready":
        raise SystemExit("BLOCKED task not ready")
    spec = Path(worktree) / "specs/001-offline/spec.md"
    if hashlib.sha256(spec.read_bytes()).hexdigest() != task["spec_sha256"]:
        raise SystemExit("BLOCKED task spec hash stale")
    if task["spec_revision"] != "1.0.0":
        raise SystemExit("BLOCKED task spec revision unsupported")
    for dependency in task["dependencies"]:
        receipt = coordinator / "artifacts/task-receipts" / (dependency + ".json")
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
                str(coordinator),
                "show",
                f"{task.get('protected_baselines', {}).get(p, base)}:{p}",
            ]
        )
        if (Path(worktree) / p).read_bytes() != expected:
            raise SystemExit("BLOCKED protected baseline changed: " + p)
    for p in task.get("protected_behavior_files", []):
        before = subprocess.check_output(["git", "-C", str(coordinator), "show", f"{base}:{p}"])

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
