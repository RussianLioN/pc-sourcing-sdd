"""Negative controls for coordinator-owned goldens and acceptance binding."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for d in (
        "scripts",
        "specs/001-offline",
        "tests",
        "src/pc_sourcing",
        "fixtures",
        ".specify/memory",
    ):
        (root / d).mkdir(parents=True, exist_ok=True)
    for p in (
        "specs/001-offline/spec.md",
        "fixtures/golden.json",
        "tests/test_a.py",
        "src/pc_sourcing/app.py",
        ".specify/memory/constitution.md",
    ):
        (root / p).write_text("baseline\n")
    for p in ("quality.py", "check_acceptance.py"):
        shutil.copy2(ROOT / "scripts" / p, root / "scripts" / p)
    git(root, "init")
    git(root, "add", ".")
    git(
        root,
        "-c",
        "user.name=Pilot test",
        "-c",
        "user.email=pilot@example.test",
        "commit",
        "-m",
        "baseline",
    )
    return root


def task(root):
    return dict(
        base_commit=git(root, "rev-parse", "HEAD"),
        coordinator_root=str(root),
        status="ready",
        spec_revision="1.0.0",
        dependencies=[],
        spec_sha256=hashlib.sha256((root / "specs/001-offline/spec.md").read_bytes()).hexdigest(),
        owned_files=["src/pc_sourcing/new.py"],
        protected_files=["fixtures/golden.json"],
    )


def scope(root, data, tmp_path):
    path = tmp_path / "task.json"
    path.write_text(json.dumps(data))
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_scope.py"), str(path), str(root)],
        capture_output=True,
        text=True,
    )


def test_protected_golden_mutation_rejected(tmp_path):
    root = repository(tmp_path)
    data = task(root)
    assert scope(root, data, tmp_path).returncode == 0
    (root / "fixtures/golden.json").write_text("weakened expectations")
    result = scope(root, data, tmp_path)
    assert result.returncode != 0
    assert "unowned" in result.stdout + result.stderr
    # Even including the golden in a write set does not disable baseline comparison.
    data["owned_files"].append("fixtures/golden.json")
    result = scope(root, data, tmp_path)
    assert result.returncode != 0
    assert "protected baseline" in result.stdout + result.stderr


@pytest.mark.parametrize("change", ["not_ready", "stale_spec", "dependency"])
def test_unready_task_rejected(tmp_path, change):
    root = repository(tmp_path)
    data = task(root)
    if change == "not_ready":
        data["status"] = "blocked"
    elif change == "stale_spec":
        data["spec_sha256"] = "0" * 64
    else:
        data["dependencies"] = ["T-missing"]
    assert scope(root, data, tmp_path).returncode != 0


@pytest.mark.parametrize(
    "changed",
    [
        "specs/001-offline/spec.md",
        "fixtures/golden.json",
        "tests/test_a.py",
        "src/pc_sourcing/app.py",
        "new_commit",
    ],
)
def test_acceptance_invalidated(tmp_path, changed):
    root = repository(tmp_path)
    record = root / "artifacts/acceptance/manifest.json"
    record.parent.mkdir(parents=True)
    # Ignore only derived run artifacts, as in the real project.
    (root / ".gitignore").write_text("artifacts/\n__pycache__/\n")
    git(root, "add", ".gitignore")
    git(
        root,
        "-c",
        "user.name=Pilot test",
        "-c",
        "user.email=pilot@example.test",
        "commit",
        "-m",
        "ignore artifacts",
    )
    code = "import sys,json;sys.path.insert(0,'scripts');from quality import snapshot;print(json.dumps(snapshot()))"
    snap = json.loads(subprocess.check_output([sys.executable, "-c", code], cwd=root, text=True))
    record.write_text(
        json.dumps(
            dict(
                snapshot=snap,
                status="passed",
                independent_review={"verdict": "passed", "commit": snap["commit"]},
            )
        )
    )
    command = [sys.executable, str(root / "scripts/check_acceptance.py")]
    assert subprocess.run(command, cwd=root, capture_output=True).returncode == 0
    if changed == "new_commit":
        git(
            root,
            "-c",
            "user.name=Pilot test",
            "-c",
            "user.email=pilot@example.test",
            "commit",
            "--allow-empty",
            "-m",
            "changed snapshot",
        )
    else:
        (root / changed).write_text("modified\n")
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert result.returncode != 0
    assert "STALE" in result.stderr + result.stdout
