"""CP-T009-01: T008 remains frozen; current stage does not borrow its acceptance."""

import ast
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
native = importlib.import_module("native_cloud")
current_scope = importlib.import_module("live_scope")
BASELINE = "5e031fcdd2daf7690585ed84f1b731c0972f4dc3"
CONTRACT = "97fd8b21f8aee68c625a1101df04fc36d9b14625"


def test_t008_gate_rejects_t009_snapshot_as_unowned(tmp_path):
    checkout = tmp_path / "separate current checkout"
    subprocess.run(["git", "clone", "--shared", "--quiet", str(ROOT), str(checkout)], check=True)
    expected = native.git(checkout, "rev-parse", "HEAD").decode().strip()
    with pytest.raises(native.AcceptanceError, match="unowned changes"):
        native.verify_project(checkout, expected, CONTRACT)


def test_every_original_assertion_and_test_body_preserved():
    original = subprocess.check_output(
        ["git", "show", f"{BASELINE}:tests/test_native_cloud.py"], cwd=ROOT
    ).decode()
    old, new = ast.parse(original), ast.parse((ROOT / "tests/test_native_cloud.py").read_text())
    # Fixture setup is the sole approved difference; all module nodes are compared.
    for tree in (old, new):
        tree.body = [
            node
            for node in tree.body
            if not (isinstance(node, ast.FunctionDef) and node.name == "bundle")
        ]
    assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)


def test_current_scope_accepts_only_approved_fixture_patch_and_owned_additions(tmp_path):
    checkout = tmp_path / "scope copy"
    subprocess.run(["git", "clone", "--shared", "--quiet", str(ROOT), str(checkout)], check=True)
    task = json.loads((ROOT / "tasks/T009.json").read_text())
    for name in task["owned_files"]:
        source = ROOT / name
        if source.is_file():
            dest = checkout / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
    assert current_scope.check(checkout)["status"] == "passed"
    foreign = checkout / "unowned.py"
    foreign.write_text("unauthorized\n")
    with pytest.raises(ValueError, match="unowned"):
        current_scope.check(checkout)
    foreign.unlink()
    with (checkout / "tests/test_native_cloud.py").open("a") as stream:
        stream.write("# extra change beyond approved setup\n")
    with pytest.raises(ValueError, match="baseline changed"):
        current_scope.check(checkout)


def test_native_checker_and_t008_contract_bytes_unchanged():
    for name in [
        "scripts/native_cloud.py",
        "tasks/T008.json",
        "specs/003-native-cloud/spec.md",
        "specs/003-native-cloud/acceptance-profile.json",
    ]:
        original = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=ROOT)
        assert (ROOT / name).read_bytes() == original
