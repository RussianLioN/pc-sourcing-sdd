import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import coordinator_adapter_scope as scope  # noqa: E402


def test_accepted_parent_preserved():
    assert scope.check()["status"] == "PASS"
    assert scope.check()["learning_enabled"] is False


@pytest.mark.parametrize("mutation", ["parent", "owner", "spec", "extra", "symlink"])
def test_adapter_scope_refuses_drift(tmp_path, mutation):
    target = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(scope.ROOT), str(target)], check=True
    )
    subprocess.run(
        ["git", "-C", str(target), "checkout", "--quiet", "--detach", scope.BASE], check=True
    )
    for name in scope.OWNED | ({scope.CP_FILE} if scope.CP_APPROVED else set()):
        p = target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(scope.ROOT / name, p)
    assert scope.check(target)["status"] == "PASS"
    if mutation == "parent":
        (target / "scripts/reviewed_lessons.py").write_text("changed")
    elif mutation == "spec":
        (target / "specs/013-coordinator-adapter/spec.md").write_text("changed")
    elif mutation == "extra":
        (target / "extra.py").write_text("changed")
    elif mutation == "symlink":
        p = target / "scripts/coordinator_adapter.py"
        p.unlink()
        p.symlink_to(scope.ROOT / "scripts/coordinator_adapter.py")
    else:
        p = target / "tasks/T018.json"
        data = json.loads(p.read_text())
        data["owned_files"].append("extra.py")
        p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        scope.check(target)
