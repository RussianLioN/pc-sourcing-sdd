#!/usr/bin/env python3
"""Bounded project-local installation. Existing credentials are never configured."""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

from toolchain import (
    ROOT,
    ToolchainError,
    host_key,
    inspect_python,
    pins,
    require_spec_kit,
    sha256,
    uv_record,
    validated_codex,
)


def local_path(root, path):
    path = Path(path)
    try:
        contained = path.resolve().is_relative_to(Path(root).resolve())
    except (OSError, RuntimeError) as error:
        raise ToolchainError("generated resource path cannot be safely resolved") from error
    if not contained:
        raise ToolchainError("generated resource would leave project root")
    return path


def validate_installer_paths(root):
    """Check existing writable trees before any installer or receipt writes.

    Internal uv cache links are normal. Follow them once, reject external
    destinations, and avoid cycles. Bootstrap Python aliases are read-only
    inputs to pip, never installation destinations in an existing environment.
    """
    root = Path(root).resolve()
    resources = (
        ".tools",
        ".venv",
        "artifacts/bootstrap",
        "src/pc_sourcing_sdd.egg-info",
    )
    pending = [root / name for name in resources]
    visited = set()
    while pending:
        path = pending.pop()
        if (
            path.parent == root / ".tools/bootstrap-env/bin"
            and re.fullmatch(r"python(?:3(?:\.\d+)?)?", path.name)
            and path.is_symlink()
            and path.is_file()
        ):
            # A venv created with the host interpreter normally links outside
            # the checkout. No command recreates an existing bootstrap venv.
            continue
        local_path(root, path)
        resolved = path.resolve()
        if resolved in visited:
            continue
        visited.add(resolved)
        if path.is_dir():
            pending.extend(path.iterdir())


def check_existing_python(root, directory):
    target = local_path(root, Path(root) / directory)
    if not target.exists():
        return False
    python = target / "bin/python"
    if not python.is_file():
        raise ToolchainError("existing environment has no Python; not overwriting")
    data = inspect_python(python)
    if data["python"] != pins()["python"]:
        raise ToolchainError("existing environment Python differs from pin; use a fresh checkout")
    if Path(data["prefix"]).resolve() != target.resolve():
        raise ToolchainError("existing interpreter prefix is outside its project environment")
    return True


def install_commands(root, uv, *, with_runner=False):
    root = Path(root)
    prefix = [str(uv), "--no-config"]
    index = ["--default-index", "https://pypi.org/simple"]
    commands = [
        prefix
        + [
            "pip",
            "sync",
            "--python",
            str(root / ".venv/bin/python"),
            str(root / "requirements.lock"),
            str(root / "requirements-build.lock"),
        ]
        + index,
        prefix
        + [
            "pip",
            "install",
            "--python",
            str(root / ".venv/bin/python"),
            "--no-deps",
            "--no-build-isolation",
            "-e",
            str(root),
        ]
        + index,
    ]
    if with_runner:
        runner_python = str(root / ".tools/spec-kit-env/bin/python")
        build_lock = str(root / "spec-kit-build.lock")
        commands.append(prefix + ["pip", "sync", "--python", runner_python, build_lock] + index)
        commands.append(
            prefix
            + [
                "pip",
                "sync",
                "--python",
                runner_python,
                "--no-build-isolation",
                str(root / "spec-kit.lock"),
                build_lock,
            ]
            + index
        )
    return commands


def required_packages(
    root, lock_names=("requirements.lock", "requirements-build.lock"), application=True
):
    packages = {"pc-sourcing-sdd": "0.1.0"} if application else {}
    for name in lock_names:
        for line in (Path(root) / name).read_text().splitlines():
            match = re.fullmatch(r"([\w-]+)==([^\s]+)", line.strip())
            if match:
                packages[match.group(1)] = match.group(2)
    return packages


def check_environment(root, *, with_runner=False, with_codex=False):
    if not check_existing_python(root, ".venv"):
        raise ToolchainError("project .venv unavailable; run bootstrap installation")
    expected = required_packages(root)
    actual = inspect_python(Path(root) / ".venv/bin/python", list(expected))
    if actual["packages"] != expected:
        raise ToolchainError("installed project packages differ from locked versions")
    tools = {}
    if with_runner:
        check_existing_python(root, ".tools/spec-kit-env")
        tools["spec_kit"] = require_spec_kit(root)
        expected_runner = required_packages(root, ("spec-kit.lock", "spec-kit-build.lock"), False)
        expected_runner["specify-cli"] = pins(root)["spec_kit"]["version"]
        installed_runner = inspect_python(
            Path(root) / ".tools/spec-kit-env/bin/python", list(expected_runner)
        )
        if installed_runner["packages"] != expected_runner:
            raise ToolchainError("installed runner/build dependencies differ from locked versions")
    if with_codex:
        tools["codex"] = validated_codex(root)
    return {
        "status": "passed",
        "scope": "local installed environment",
        "runtime": actual,
        "required_optional_tools": tools,
        "cloud_runtime": "not_run",
    }


def clean_installer_environment(root):
    validate_installer_paths(root)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("UV_", "PIP_"))}
    # Keep the environment's existing network/proxy policy; configure no credentials.
    env.update(
        UV_CACHE_DIR=str(Path(root) / ".tools/uv-cache"),
        UV_PYTHON_INSTALL_DIR=str(Path(root) / ".tools/python"),
        PIP_CONFIG_FILE=os.devnull,
        PYTHONDONTWRITEBYTECODE="1",
        TMPDIR=str(local_path(root, Path(root) / ".tools/tmp")),
        TMP=str(local_path(root, Path(root) / ".tools/tmp")),
        TEMP=str(local_path(root, Path(root) / ".tools/tmp")),
    )
    return env


class Installer:
    def __init__(self, root):
        self.root = Path(root)
        self.env = clean_installer_environment(root)
        local_path(root, Path(self.env["TMPDIR"])).mkdir(parents=True, exist_ok=True)
        self.out = local_path(root, Path(root) / "artifacts/bootstrap" / str(time.time_ns()))
        self.out.mkdir(parents=True)
        self.deadline = time.monotonic() + 480
        self.checks = []

    def record(self, status, **fields):
        data = {
            "status": status,
            "checks": self.checks,
            "new_credentials": False,
            "global_configuration_changed": False,
            **fields,
        }
        (self.out / "receipt.json").write_text(json.dumps(data, indent=2))
        return data

    def run(self, command):
        validate_installer_paths(self.root)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ToolchainError("bootstrap total deadline exceeded")
        start = time.monotonic()
        proc = subprocess.Popen(
            command,
            cwd=self.root,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=min(180, remaining))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                stdout, stderr = proc.communicate()
        code = 124 if timed_out else proc.returncode
        log = self.out / f"step-{len(self.checks)}.log"
        log.write_text(stdout + stderr)
        self.checks.append(
            {
                "command": command,
                "exit_code": code,
                "elapsed_seconds": round(time.monotonic() - start, 3),
                "log": str(log),
            }
        )
        self.record("running")
        if code:
            raise ToolchainError(f"bootstrap command failed with exit {code}; inspect {log}")

    def uv(self):
        current = uv_record(self.root)
        if current["status"] == "passed":
            return Path(current["executable"])
        directory = local_path(self.root, self.root / ".tools/bootstrap-env")
        if directory.exists():
            raise ToolchainError(
                "existing project-local uv environment mismatched; not overwriting"
            )
        self.run([sys.executable, "-m", "venv", str(directory)])
        self.run(
            [
                str(directory / "bin/python"),
                "-m",
                "pip",
                "--isolated",
                "install",
                "--no-deps",
                "--no-cache-dir",
                "--index-url",
                "https://pypi.org/simple",
                "uv==" + pins(self.root)["uv"],
            ]
        )
        current = uv_record(self.root)
        if current["status"] != "passed":
            raise ToolchainError("installed uv does not match pin")
        return Path(current["executable"])

    def ensure_venv(self, uv, directory):
        if not check_existing_python(self.root, directory):
            self.run(
                [
                    str(uv),
                    "--no-config",
                    "venv",
                    "--python",
                    pins(self.root)["python"],
                    str(self.root / directory),
                ]
            )
        check_existing_python(self.root, directory)

    def codex(self):
        validate_installer_paths(self.root)
        config = json.loads((self.root / "scripts/codex-pin.json").read_text())
        asset = config["platforms"][host_key()]
        destination = local_path(self.root, self.root / ".tools/codex/codex")
        if destination.exists():
            validated_codex(self.root, executable=destination)
            return
        if not asset["url"].startswith(
            "https://github.com/openai/codex/releases/download/rust-v" + config["version"] + "/"
        ):
            raise ToolchainError("Codex download is outside pinned official release")
        with tempfile.TemporaryDirectory(
            prefix="codex-install-", dir=self.root / ".tools"
        ) as directory:
            archive = Path(directory) / "release.tar.gz"
            with (
                urllib.request.urlopen(asset["url"], timeout=60) as response,
                archive.open("xb") as stream,
            ):
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 150_000_000 or time.monotonic() > self.deadline:
                        raise ToolchainError("Codex download resource/deadline limit")
                    stream.write(chunk)
            if sha256(archive) != asset["archive_sha256"]:
                raise ToolchainError("Codex archive hash mismatch")
            staged = Path(directory) / "codex"
            with tarfile.open(archive, "r:gz") as package:
                member = package.getmember(asset["binary_member"])
                if not member.isfile() or not 0 < member.size <= 400_000_000:
                    raise ToolchainError("unexpected Codex archive member")
                with package.extractfile(member) as source, staged.open("xb") as stream:
                    while chunk := source.read(1024 * 1024):
                        stream.write(chunk)
            if sha256(staged) != asset["binary_sha256"]:
                raise ToolchainError("Codex binary hash mismatch")
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged.chmod(0o755)
            staged.rename(destination)
        validated_codex(self.root, executable=destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--with-runner", action="store_true")
    parser.add_argument("--with-codex", action="store_true")
    args = parser.parse_args()
    installer = None
    try:
        if sys.version_info < (3, 11):  # noqa: UP036 -- bootstrap runs before pinned Python exists
            raise ToolchainError("bootstrap requires an existing Python 3.11+ interpreter")
        host_key()
        validate_installer_paths(ROOT)
        if not args.check:
            installer = Installer(ROOT)
            uv = installer.uv()
            installer.ensure_venv(uv, ".venv")
            if args.with_runner:
                installer.ensure_venv(uv, ".tools/spec-kit-env")
            for command in install_commands(ROOT, uv, with_runner=args.with_runner):
                installer.run(command)
            if args.with_codex:
                installer.codex()
        result = check_environment(ROOT, with_runner=args.with_runner, with_codex=args.with_codex)
        if installer:
            installer.record("passed", environment=result)
            result["receipt"] = str(installer.out / "receipt.json")
        print(json.dumps(result, indent=2))
        return 0
    except (ToolchainError, OSError, ValueError) as error:
        result = {"status": "blocked", "reason": str(error), "cloud_runtime": "not_run"}
        if installer:
            installer.record("blocked", reason=str(error))
            result["receipt"] = str(installer.out / "receipt.json")
        print(json.dumps(result))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
