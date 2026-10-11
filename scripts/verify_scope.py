"""Coordinator-only scope gate: base commit comes from coordinator task."""

import argparse
import json
import subprocess
from pathlib import Path


def check(task_path, worktree):
    task = json.loads(Path(task_path).read_text())
    base = task["base_commit"]

    def git(*args):
        return subprocess.check_output(["git", "-C", str(worktree), *args], text=True).strip()

    changed = set(git("diff", "--name-only", base).splitlines())
    changed |= set(git("ls-files", "--others", "--exclude-standard").splitlines())
    bad = changed - set(task["owned_files"])
    if bad:
        raise SystemExit("BLOCKED unowned changes: " + ", ".join(sorted(bad)))
    for p in task["protected_files"]:
        expected = subprocess.check_output(
            ["git", "-C", task["coordinator_root"], "show", f"{base}:{p}"]
        )
        if (Path(worktree) / p).read_bytes() != expected:
            raise SystemExit("BLOCKED protected baseline changed: " + p)
    print(json.dumps({"status": "passed", "base_commit": base, "changed_files": sorted(changed)}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("worktree")
    args = ap.parse_args()
    check(args.task, args.worktree)
