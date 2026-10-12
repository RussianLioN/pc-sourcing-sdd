"""OFFER-11: every tracked T011 byte remains protected."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "normalized_scope", ROOT / "scripts/normalized_scope.py"
)
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


def test_normalized_stage_preserves_parent_blobs():
    result = scope.check(ROOT)
    assert result["status"] == "passed"
    assert result["protected_byte_identical"] == 182
    assert result["approved_protected_patches"] == 1


def test_historical_durable_scope_rejects_successor():
    oldspec = importlib.util.spec_from_file_location(
        "durable_scope", ROOT / "scripts/durable_scope.py"
    )
    old = importlib.util.module_from_spec(oldspec)
    oldspec.loader.exec_module(old)
    with pytest.raises(ValueError, match="unowned T011 changes"):
        old.check(ROOT)


@pytest.mark.parametrize(
    "mutation",
    [
        "parent_code",
        "parent_test",
        "parent_gate",
        "owner",
        "inventory",
        "spec",
        "extra",
        "cp_binding",
        "cp_hash",
        "cp_reverted",
    ],
)
def test_normalized_scope_rejects_unapproved_changes(tmp_path, mutation):
    import json
    import shutil
    import subprocess

    target = tmp_path / "checkout"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(target)], check=True
    )
    subprocess.run(
        ["git", "-C", str(target), "checkout", "--quiet", "--detach", scope.BASELINE], check=True
    )
    for name in scope.OWNED:
        dst = target / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dst)
    shutil.copyfile(ROOT / scope.CP_FILE, target / scope.CP_FILE)
    assert scope.check(target)["status"] == "passed"
    if mutation.startswith("parent_"):
        name = {
            "parent_code": "src/pc_sourcing/evaluate.py",
            "parent_test": "tests/test_durable_scope.py",
            "parent_gate": "scripts/durable_scope.py",
        }[mutation]
        with (target / name).open("a") as f:
            f.write("\n# unapproved drift\n")
    elif mutation in {"cp_binding", "cp_hash"}:
        path = target / "tasks/T012.json"
        data = json.loads(path.read_text())
        if mutation == "cp_binding":
            del data["approved_protected_patches"]
        else:
            data["approved_protected_patches"][scope.CP_FILE]["approved_sha256"] = "0" * 64
        path.write_text(json.dumps(data))
    elif mutation == "cp_reverted":
        (target / scope.CP_FILE).write_bytes(
            subprocess.check_output(
                ["git", "show", scope.BASELINE + ":" + scope.CP_FILE], cwd=target
            )
        )
    elif mutation in {"owner", "inventory"}:
        path = target / "tasks/T012.json"
        data = json.loads(path.read_text())
        data["owned_files" if mutation == "owner" else "protected_files"].append("unapproved.py")
        path.write_text(json.dumps(data))
    elif mutation == "spec":
        with (target / "specs/007-normalized-offers/spec.md").open("a") as f:
            f.write("\nchanged\n")
    else:
        (target / "unapproved.py").write_text("data")
    with pytest.raises(ValueError):
        scope.check(target)
