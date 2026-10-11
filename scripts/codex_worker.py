#!/usr/bin/env python3
"""Pinned real Codex wrapper; called through the project-interpreter launcher."""

import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from toolchain import ROOT, ToolchainError, pins, validated_codex


def validate_verifier_root(root, temp_roots=None):
    root = Path(root).resolve()
    roots = temp_roots or [
        Path("/tmp"),
        Path(tempfile.gettempdir()),
        Path(os.environ.get("TMPDIR", "/tmp")),
    ]
    if any(root.is_relative_to(Path(path).resolve()) for path in roots):
        raise ToolchainError("verifier project is inside a temporary writable root")


def validate_request(args, mode, cwd, root=ROOT):
    if os.environ.get("SPECKIT_INTEGRATION_CODEX_EXTRA_ARGS", ""):
        raise ToolchainError("unexpected integration extra args")
    if len(args) not in (2, 3) or args[0] != "exec" or (len(args) == 3 and args[2] != "--json"):
        raise ToolchainError("only exec + prompt + optional --json allowed")
    if mode not in ("writer", "verifier"):
        raise ToolchainError("invalid worker mode")
    cwd, root = Path(cwd).resolve(), Path(root).resolve()
    if mode == "writer" and not cwd.is_relative_to(root / ".worktrees"):
        raise ToolchainError("writer requires project worktree")
    if mode == "verifier" and cwd != root:
        raise ToolchainError("verifier requires integrated project")
    if mode == "verifier":
        validate_verifier_root(root)


def build_command(tool, mode, scratch, out, prompt, root=ROOT):
    cmd = [
        str(tool["executable"]),
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--sandbox",
        "workspace-write",
        "--model",
        tool["model"],
        "-c",
        'approval_policy="never"',
        "-c",
        "agents.max_depth=1",
        "-c",
        "agents.max_concurrent_threads_per_session=1",
        "--json",
        "--cd",
        str(scratch),
        "--output-last-message",
        str(Path(out) / "final.md"),
    ]
    if mode == "verifier":
        cmd.insert(2, "--skip-git-repo-check")
        prompt = (
            "Your writable workspace is a private scratch directory; the project "
            + str(root)
            + " is read-only outside it. Execute all project commands with cd "
            + str(root)
            + "; put reproducers and temp files only in $TMPDIR. First run "
            + str(Path(root) / ".venv/bin/python")
            + " "
            + str(Path(root) / "scripts/verify_readonly.py")
            + " and include its exit/status in checks. Stop if project write is allowed. "
            + "Do not ask for broader permissions.\n"
            + prompt
        )
    else:
        prompt = (
            "The coordinator repository is $PC_COORDINATOR_ROOT; its task definition "
            "and baseline are read-only outside your worktree. Use only task-owned files.\n"
            + prompt
        )
    # A prompt beginning with -- must never be interpreted as a Codex permission flag.
    return cmd + ["--", prompt]


def main():
    try:
        args = sys.argv[1:]
        mode = os.environ.get("PC_WORKER_MODE", "writer")
        cwd = Path.cwd().resolve()
        validate_request(args, mode, cwd)
        if (
            platform.python_version() != pins()["python"]
            or Path(sys.prefix).resolve() != ROOT / ".venv"
        ):
            raise ToolchainError("worker requires pinned project .venv interpreter")
        tool = validated_codex()
        out = ROOT / "artifacts/workers" / (mode + "-" + str(time.time_ns()))
        out.mkdir(parents=True)
        scratch = (
            Path(tempfile.mkdtemp(prefix="pc-verifier-", dir="/tmp")) if mode == "verifier" else cwd
        )
        cmd = build_command(tool, mode, scratch, out, args[1])
        env = os.environ.copy()
        for name in list(env):
            if name.endswith("API_KEY") or name.startswith("SPECKIT_INTEGRATION_"):
                env.pop(name, None)
        env.update(
            TMPDIR=str(scratch / "tmp")
            if mode == "verifier"
            else tempfile.mkdtemp(prefix="pc-writer-"),
            PYTHONDONTWRITEBYTECODE="1",
            PC_COORDINATOR_ROOT=str(ROOT),
            PC_PROJECT_PYTHON=str(ROOT / ".venv/bin/python"),
        )
        Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        record = {
            "kind": "real_codex_exec",
            "mode": mode,
            "sandbox": "workspace-write",
            **tool,
            "cwd": str(cwd),
            "writable_workspace": str(scratch),
            "project_access": "read-only" if mode == "verifier" else "task-owned writes",
            "argv_without_prompt": cmd[:-1],
            "prompt_sha256": hashlib.sha256(args[1].encode()).hexdigest(),
            "timeout_seconds": 600,
            "new_api": False,
        }
        (out / "invocation.json").write_text(json.dumps(record, indent=2))
        with (out / "events.jsonl").open("w") as events, (out / "stderr.log").open("w") as err:
            proc = subprocess.Popen(cmd, env=env, stdout=events, stderr=err, start_new_session=True)
            (out / "process.json").write_text(json.dumps({"pid": proc.pid, "state": "running"}))
            try:
                code = proc.wait(timeout=600)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                code = 124
        record.update(
            exit_code=code,
            elapsed_seconds=round(time.monotonic() - start, 3),
            next_step="collect diff and validate"
            if code == 0
            else "blocked: inspect worker failure",
        )
        (out / "result.json").write_text(json.dumps(record, indent=2))
        (out / "process.json").write_text(
            json.dumps({"pid": proc.pid, "state": "terminated", "exit_code": code})
        )
        print(json.dumps({"kind": "real_codex_exec", "exit_code": code, "artifacts": str(out)}))
        return code if code >= 0 else 128 - code
    except (ToolchainError, OSError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
