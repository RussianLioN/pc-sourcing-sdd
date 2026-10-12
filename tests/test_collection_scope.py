"""T013 provisional additive scope; accepted T012 parent is entirely frozen."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "collection_scope", ROOT / "scripts/collection_scope.py"
)
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


def test_collection_preserves_all_parent_blobs(tmp_path):
    import subprocess

    checkout = tmp_path / "historical-T013"
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
            "79df7e5a04a9a54b4ee2122c4729459bfd512bae",
        ],
        check=True,
    )
    assert scope.check(checkout)["protected_byte_identical"] == 200
    assert scope.check(checkout)["approved_protected_patches"] == 1


@pytest.mark.parametrize(
    "mutation", ["parent", "cp_revert", "cp_binding", "owner", "spec", "extra"]
)
def test_collection_scope_rejects_drift(tmp_path, mutation):
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
    for name in scope.OWNED | {scope.CP_FILE}:
        dst = target / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dst)
    assert scope.check(target)["status"] == "passed"
    if mutation == "parent":
        (target / "src/pc_sourcing/evaluate.py").write_text("changed")
    elif mutation == "cp_revert":
        (target / scope.CP_FILE).write_bytes(
            subprocess.check_output(
                ["git", "show", scope.BASELINE + ":" + scope.CP_FILE], cwd=target
            )
        )
    elif mutation in {"cp_binding", "owner"}:
        p = target / "tasks/T013.json"
        data = json.loads(p.read_text())
        if mutation == "cp_binding":
            data["approved_protected_patches"][scope.CP_FILE]["approved_sha256"] = "0" * 64
        else:
            data["owned_files"].append("extra.py")
        p.write_text(json.dumps(data))
    elif mutation == "spec":
        (target / "specs/008-collection-integration/spec.md").write_text("changed")
    else:
        (target / "extra.py").write_text("changed")
    with pytest.raises(ValueError):
        scope.check(target)
