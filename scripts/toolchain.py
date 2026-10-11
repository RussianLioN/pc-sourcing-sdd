"""Observed, pinned project tools; no credential creation or config changes."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ToolchainError(ValueError):
    pass


def pins(root=ROOT):
    return json.loads((Path(root) / "scripts/toolchain-pins.json").read_text())


def host_key(system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    if system == "Darwin" and machine in ("arm64", "aarch64"):
        return "Darwin-arm64"
    if system == "Linux" and machine in ("x86_64", "amd64"):
        return "Linux-x86_64"
    raise ToolchainError(f"unsupported worker platform: {system}/{machine}")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def version_output(executable):
    try:
        result = subprocess.run(
            [str(executable), "--version"], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ToolchainError("version probe unavailable") from error
    if result.returncode:
        raise ToolchainError("version probe failed")
    return result.stdout.strip()


def validated_codex(root=ROOT, *, executable=None, config=None):
    root = Path(root)
    config = config or json.loads((root / "scripts/codex-pin.json").read_text())
    key = host_key()
    if key not in config["platforms"]:
        raise ToolchainError("unsupported Codex pin platform")
    selected = executable or os.environ.get("PC_CODEX_EXECUTABLE")
    if not selected:
        local = root / ".tools/codex/codex"
        selected = local if local.exists() or local.is_symlink() else shutil.which("codex")
    if not selected:
        raise ToolchainError("Codex executable unavailable; optional bootstrap --with-codex")
    real = Path(selected).resolve()
    if not real.is_file() or not os.access(real, os.X_OK):
        raise ToolchainError("Codex executable unavailable")
    digest = sha256(real)
    if digest != config["platforms"][key]["binary_sha256"]:
        raise ToolchainError("Codex executable hash differs from official platform pin")
    if version_output(real) != "codex-cli " + config["version"]:
        raise ToolchainError("Codex executable version differs from pin")
    return {
        "status": "passed",
        "executable": str(real),
        "version": config["version"],
        "sha256": digest,
        "platform": key,
        "model": config["model"],
    }


def uv_record(root=ROOT, *, executable=None):
    local = Path(root) / ".tools/bootstrap-env/bin/uv"
    selected = executable or (local if local.exists() else shutil.which("uv"))
    expected = pins(root)["uv"]
    if not selected:
        return {"status": "not_run", "expected_version": expected, "reason": "uv unavailable"}
    try:
        real = Path(selected).resolve()
        match = re.fullmatch(r"uv (\d+\.\d+\.\d+)(?: .*)?", version_output(real))
        observed = match.group(1) if match else None
        return {
            "status": "passed" if observed == expected else "blocked",
            "executable": str(real),
            "observed_version": observed,
            "expected_version": expected,
        }
    except ToolchainError as error:
        return {"status": "blocked", "expected_version": expected, "reason": str(error)}


def inspect_python(executable, names=None):
    names = names or ["pydantic", "pytest", "hypothesis", "ruff", "setuptools"]
    program = (
        "import json,platform,sqlite3,sys,importlib.metadata as m;"
        "names=" + repr(names) + ";"
        "packages={};"
        "\nfor name in names:\n"
        " try: packages[name]=m.version(name)\n"
        " except m.PackageNotFoundError: packages[name]=None\n"
        "print(json.dumps(dict(python=platform.python_version(),sqlite=sqlite3.sqlite_version,"
        "executable=sys.executable,prefix=sys.prefix,packages=packages)))"
    )
    try:
        result = subprocess.run(
            [str(executable), "-c", program], capture_output=True, text=True, timeout=15
        )
        if result.returncode:
            raise ToolchainError("project interpreter probe failed")
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise ToolchainError("project interpreter probe unavailable") from error


def spec_kit_record(root=ROOT):
    expected = pins(root)["spec_kit"]
    python = Path(root) / ".tools/spec-kit-env/bin/python"
    cli = Path(root) / ".tools/spec-kit-env/bin/specify"
    if not python.is_file() or not cli.is_file():
        return {
            "status": "not_run",
            "reason": "optional Spec Kit not installed",
            "expected": expected,
        }
    program = (
        "import json,importlib.metadata as m;d=m.distribution('specify-cli');"
        "print(json.dumps(dict(version=d.version,direct_url=json.loads(d.read_text('direct_url.json')))))"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", program], capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout) if result.returncode == 0 else {}
        source = data.get("direct_url", {})
        commit = source.get("vcs_info", {}).get("commit_id")
        valid = (
            data.get("version") == expected["version"]
            and source.get("url") == expected["repository"]
            and commit == expected["commit"]
        )
        return {
            "status": "passed" if valid else "blocked",
            "executable": str(cli.resolve()),
            "observed_version": data.get("version"),
            "observed_commit": commit,
            "expected": expected,
        }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {
            "status": "blocked",
            "reason": "Spec Kit identity probe failed",
            "expected": expected,
        }


def require_spec_kit(root=ROOT):
    record = spec_kit_record(root)
    if record["status"] != "passed":
        raise ToolchainError("Spec Kit version/source pin unavailable or mismatched")
    return record


def observed_versions(root=ROOT):
    packages = {}
    for name in ("pydantic", "pytest", "hypothesis", "ruff", "setuptools"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    try:
        codex = validated_codex(root)
    except ToolchainError as error:
        codex = {"status": "blocked", "reason": str(error)}
    runner = spec_kit_record(root)
    uv = uv_record(root)
    return {
        **packages,
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "os": platform.system(),
        "architecture": platform.machine(),
        "python_executable": sys.executable,
        "spec_kit": runner.get("observed_version"),
        "spec_kit_sha": runner.get("observed_commit"),
        "codex": codex.get("version"),
        "uv": uv.get("observed_version"),
        "tools": {"spec_kit": runner, "codex": codex, "uv": uv},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.parse_args()
    print(json.dumps(observed_versions(), indent=2))
