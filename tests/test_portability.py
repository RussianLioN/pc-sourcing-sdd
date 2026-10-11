"""Host/tool/launcher controls; simulated hosts are not Linux runtime evidence."""

import hashlib
import importlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
toolchain = importlib.import_module("toolchain")
codex_worker = importlib.import_module("codex_worker")
bootstrap = importlib.import_module("bootstrap")


@pytest.mark.parametrize(
    "system,machine,key",
    [
        ("Darwin", "arm64", "Darwin-arm64"),
        ("Linux", "x86_64", "Linux-x86_64"),
        ("Linux", "AMD64", "Linux-x86_64"),
    ],
)
def test_host_mapping(system, machine, key):
    assert toolchain.host_key(system, machine) == key


@pytest.mark.parametrize(
    "system,machine", [("Windows", "AMD64"), ("Linux", "aarch64"), ("Darwin", "x86_64")]
)
def test_unknown_worker_host_rejected(system, machine):
    with pytest.raises(toolchain.ToolchainError, match="unsupported"):
        toolchain.host_key(system, machine)


def fake_codex(tmp_path, version="0.157.1"):
    marker = tmp_path / "executed"
    binary = tmp_path / "codex tool"
    binary.write_text(f'#!/bin/sh\nprintf probe > "{marker}"\nprintf "codex-cli {version}\\n"\n')
    binary.chmod(0o755)
    config = {
        "version": "0.157.1",
        "model": "gpt-6-astra",
        "platforms": {
            toolchain.host_key(): {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
        },
    }
    return binary, marker, config


def test_unpinned_binary_never_executes(tmp_path):
    binary, marker, config = fake_codex(tmp_path)
    config["platforms"][toolchain.host_key()]["binary_sha256"] = "0" * 64
    with pytest.raises(toolchain.ToolchainError, match="hash"):
        toolchain.validated_codex(ROOT, executable=binary, config=config)
    assert not marker.exists()


def test_version_mismatch_rejected_after_identity_check(tmp_path):
    binary, marker, config = fake_codex(tmp_path, "0.158.0")
    with pytest.raises(toolchain.ToolchainError, match="version"):
        toolchain.validated_codex(ROOT, executable=binary, config=config)
    assert marker.exists()


def test_explicit_bad_executable_does_not_fallback(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    monkeypatch.setenv("PC_CODEX_EXECUTABLE", str(missing))
    with pytest.raises(toolchain.ToolchainError, match="unavailable"):
        toolchain.validated_codex(ROOT)


@pytest.mark.parametrize(
    "args",
    [
        ["exec"],
        ["login", "prompt"],
        ["exec", "prompt", "--dangerously-bypass-approvals-and-sandbox"],
        ["exec", "prompt", "--json", "extra"],
    ],
)
def test_invalid_worker_arguments_rejected(args, tmp_path):
    with pytest.raises(toolchain.ToolchainError):
        codex_worker.validate_request(args, "writer", ROOT / ".worktrees/test", ROOT)


def test_extra_integration_arguments_rejected(monkeypatch):
    monkeypatch.setenv("SPECKIT_INTEGRATION_CODEX_EXTRA_ARGS", "--yolo")
    with pytest.raises(toolchain.ToolchainError, match="extra args"):
        codex_worker.validate_request(["exec", "prompt"], "writer", ROOT / ".worktrees/test", ROOT)


def test_writer_requires_project_worktree():
    with pytest.raises(toolchain.ToolchainError, match="worktree"):
        codex_worker.validate_request(["exec", "prompt"], "writer", ROOT, ROOT)


def test_verifier_cannot_claim_readonly_under_temp(tmp_path):
    with pytest.raises(toolchain.ToolchainError, match="temporary writable"):
        codex_worker.validate_verifier_root(tmp_path / "checkout", [tmp_path])


def test_codex_command_keeps_sandbox_and_ends_options(tmp_path):
    tool = {"executable": "/approved/codex", "model": "gpt-6-astra"}
    prompt = "--dangerously-bypass-approvals-and-sandbox"
    cmd = codex_worker.build_command(
        tool, "verifier", tmp_path / "scratch", tmp_path / "logs", prompt, ROOT
    )
    assert cmd[-2] == "--"
    assert prompt in cmd[-1]
    assert "--ignore-user-config" in cmd and "--ephemeral" in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "workspace-write"
    assert 'approval_policy="never"' in cmd
    assert "agents.max_depth=1" in cmd and "agents.max_concurrent_threads_per_session=1" in cmd
    assert "verify_readonly.py" in cmd[-1]
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd[:-1]


def test_relative_task_root_is_coordinator_anchored(tmp_path, monkeypatch):
    import verify_scope

    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert verify_scope.coordinator_path(".") == Path(verify_scope.__file__).resolve().parents[1]


def test_launcher_preserves_spaces_and_literal_prompt(tmp_path):
    root = tmp_path / "checkout with spaces"
    (root / "scripts").mkdir(parents=True)
    (root / ".venv/bin").mkdir(parents=True)
    launcher = root / "scripts/codex-worker"
    shutil.copy2(ROOT / "scripts/codex-worker", launcher)
    fake = root / ".venv/bin/python"
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    fake.chmod(0o755)
    marker = tmp_path / "must-not-exist"
    prompt = f"$(touch {marker}); literal prompt"
    result = subprocess.run(
        [str(launcher), "exec", prompt, "--json"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        str(root / "scripts/codex_worker.py"),
        "exec",
        prompt,
        "--json",
    ]
    assert not marker.exists()


def test_bootstrap_plan_uses_local_resources(tmp_path):
    root = tmp_path / "checkout with spaces"
    plan = bootstrap.install_commands(root, Path("/approved/uv"), with_runner=True)
    assert all(isinstance(command, list) for command in plan)
    assert any(str(root / "requirements-build.lock") in cmd for cmd in plan)
    assert any(str(root / "spec-kit.lock") in cmd for cmd in plan)
    assert all("--no-config" in cmd for cmd in plan)
    assert all("--system" not in cmd for cmd in plan)


def test_uv_observation_reports_actual_mismatch(tmp_path):
    binary = tmp_path / "uv"
    binary.write_text('#!/bin/sh\nprintf "uv 9.9.9\\n"\n')
    binary.chmod(0o755)
    record = toolchain.uv_record(ROOT, executable=binary)
    assert record["status"] == "blocked" and record["observed_version"] == "9.9.9"


def test_existing_wrong_python_environment_is_not_recreated(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    (root / ".venv/bin").mkdir(parents=True)
    (root / ".venv/bin/python").touch()
    monkeypatch.setattr(bootstrap, "inspect_python", lambda path: {"python": "3.14.0"})
    with pytest.raises(toolchain.ToolchainError, match="existing.*Python"):
        bootstrap.check_existing_python(root, ".venv")


def test_legacy_workflow_is_not_current_dispatch():
    import run_workflow

    with pytest.raises(toolchain.ToolchainError, match="historical"):
        run_workflow.validate_workflow(ROOT / "workflows/repair3.yml")


def test_cloud_skill_contains_executable_examples():
    text = (ROOT / ".agents/skills/pc-cloud-setup/SKILL.md").read_text()
    assert "scripts/bootstrap.py --check" in text
    assert "scripts/quality.py" in text
    assert "new credentials" in text
