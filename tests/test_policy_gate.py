"""An authorized new policy blob stays protected after continuation."""

from test_control_plane import git, repository, scope, task


def test_authorized_policy_revision_cannot_drift(tmp_path):
    root = repository(tmp_path)
    data = task(root)
    policy = ".specify/memory/constitution.md"
    data["owned_files"].append(policy)
    data["protected_files"].append(policy)
    (root / policy).write_text("authorized continuation; golden immutable\n")
    git(root, "add", policy)
    git(
        root,
        "-c",
        "user.name=Pilot test",
        "-c",
        "user.email=pilot@example.test",
        "commit",
        "-m",
        "authorized policy",
    )
    data["protected_baselines"] = {policy: git(root, "rev-parse", "HEAD")}
    assert scope(root, data, tmp_path).returncode == 0
    (root / policy).write_text("weaken product requirements\n")
    result = scope(root, data, tmp_path)
    assert result.returncode != 0
    assert "protected baseline" in result.stdout + result.stderr


def test_policy_pin_does_not_rebase_goldens(tmp_path):
    root = repository(tmp_path)
    data = task(root)
    data["protected_baselines"] = {".specify/memory/constitution.md": data["base_commit"]}
    data["owned_files"].append("fixtures/golden.json")
    (root / "fixtures/golden.json").write_text("changed golden")
    result = scope(root, data, tmp_path)
    assert result.returncode != 0
    assert "protected baseline" in result.stdout + result.stderr
