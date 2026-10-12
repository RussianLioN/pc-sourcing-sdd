import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import improvement_scope as scope  # noqa: E402


def test_parent_scope_unchanged():
    value = scope.check()
    assert value["status"] == "PASS"
    assert value["real_learning_enabled"] is False


@pytest.mark.parametrize("mutation", ["parent", "spec", "owner", "unowned", "symlink"])
def test_scope_rejects_changes(tmp_path, mutation):
    target = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(scope.ROOT), str(target)], check=True
    )
    subprocess.run(
        ["git", "-C", str(target), "checkout", "--quiet", "--detach", scope.BASE], check=True
    )
    for name in scope.OWNED | ({scope.CP_FILE} if scope.CP_AUTHORIZED else set()):
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(scope.ROOT / name, dest)
    assert scope.check(target)["status"] == "PASS"
    if mutation == "parent":
        (target / "src/pc_sourcing/evaluate.py").write_text("changed")
    elif mutation == "spec":
        (target / "specs/012-reviewed-improvement/spec.md").write_text("changed")
    elif mutation == "unowned":
        (target / "unowned.py").write_text("changed")
    elif mutation == "symlink":
        p = target / "scripts/lesson_consumer.py"
        p.unlink()
        p.symlink_to(scope.ROOT / "scripts/lesson_consumer.py")
    else:
        p = target / "tasks/T017.json"
        p.write_text(p.read_text().replace('"scripts/lesson_consumer.py",', '"extra.py",'))
    with pytest.raises(ValueError):
        scope.check(target)
