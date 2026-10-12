"""WIT-10 new ownership checker never expands protected T015 scope."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("witness_scope", ROOT / "scripts/witness_scope.py")
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


def test_witness_preserves_every_parent_byte(tmp_path):
    checkout = tmp_path / "historical-T016"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(checkout)], check=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(checkout),
            "checkout",
            "--quiet",
            "--detach",
            "f495e5294e93a281f945de6f4e1c6c89d7a6cb1e",
        ],
        check=True,
    )
    assert scope.check(checkout)["parent_identical"] == 244
    assert scope.check(checkout)["approved_protected_patches"] == 1


@pytest.mark.parametrize(
    "mutation", ["parent", "owner", "baseline", "extra", "spec", "cp_revert", "cp_binding"]
)
def test_witness_scope_rejects_unauthorized_changes(tmp_path, mutation):
    target = tmp_path / "checkout"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(target)], check=True
    )
    subprocess.run(
        ["git", "-C", str(target), "checkout", "--quiet", "--detach", scope.BASE], check=True
    )
    for name in scope.OWNED | {scope.CP_FILE}:
        dst = target / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dst)
    assert scope.check(target)["status"] == "PASS"
    if mutation == "parent":
        (target / "src/pc_sourcing/evaluate.py").write_text("changed")
    elif mutation == "extra":
        (target / "extra.py").write_text("changed")
    elif mutation == "spec":
        (target / "specs/011-witness-controller/spec.md").write_text("changed")
    elif mutation == "cp_revert":
        (target / scope.CP_FILE).write_bytes(
            subprocess.check_output(["git", "show", scope.BASE + ":" + scope.CP_FILE], cwd=target)
        )
    else:
        p = target / "tasks/T016.json"
        d = json.loads(p.read_text())
        if mutation == "owner":
            d["owned_files"].append("extra.py")
        elif mutation == "cp_binding":
            d["approved_protected_patches"][scope.CP_FILE]["approved_sha256"] = "0" * 64
        else:
            d["base_commit"] = "cc5fbc331602f90fa33b529ff4688a106cdf9dc6"
        p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        scope.check(target)
