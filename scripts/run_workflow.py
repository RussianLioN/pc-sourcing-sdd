"""Project-local serialized runner, never a sandbox for shell steps."""

import argparse
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

from toolchain import ToolchainError, pins, require_spec_kit

ROOT = Path(__file__).resolve().parents[1]


def validate_workflow(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT / "workflows") or not path.is_file():
        raise ToolchainError("only reviewed project workflow files")
    if path.relative_to(ROOT / "workflows").as_posix() not in pins(ROOT)["allowed_workflows"]:
        raise ToolchainError("historical or unreviewed workflow is not current dispatch")
    return path


def launch(action, source, inputs=(), cwd=ROOT):
    cwd = Path(cwd).resolve()
    if cwd != ROOT and not cwd.is_relative_to(ROOT / ".worktrees"):
        raise ValueError("unapproved coordinator working directory")
    if os.environ.get("SPECKIT_INTEGRATION_CODEX_EXTRA_ARGS"):
        raise ValueError("unexpected integration extra args")
    if action == "run":
        path = (ROOT / source).resolve()
        source = str(validate_workflow(path))
    elif not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", source):
        raise ValueError("invalid run id")
    runner = require_spec_kit(ROOT)
    lockpath = cwd / ".specify/workflows/coordinator.lock"
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    with lockpath.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                json.dumps(
                    {"status": "blocked", "reason": "another coordinator owns exclusive lock"}
                )
            )
            return 75
        if action == "resume":
            state_path = cwd / ".specify/workflows/runs" / source / "state.json"
            state = json.loads(state_path.read_text())
            allowed_ids = set()
            for name in pins(ROOT)["allowed_workflows"]:
                text = validate_workflow(ROOT / "workflows" / name).read_text()
                match = re.search(r'^  id: "([^"\n]+)"$', text, re.MULTILINE)
                if match:
                    allowed_ids.add(match.group(1))
            if (
                state["workflow_id"] not in allowed_ids
                or Path(state["workflow_dir"]).resolve() != ROOT / "workflows"
            ):
                raise ToolchainError("historical or foreign run cannot resume as current dispatch")
            if state["status"] not in ("paused", "failed"):
                raise ToolchainError(
                    "resume supports paused/failed only; inspect running crash before new task"
                )
        env = os.environ.copy()
        env["SPECKIT_INTEGRATION_CODEX_EXECUTABLE"] = str(ROOT / "scripts/codex-worker")
        args = [runner["executable"], "workflow", action, source, "--json"]
        for value in inputs:
            args += ["--input", value]
        proc = subprocess.Popen(args, cwd=cwd, env=env, start_new_session=True)
        try:
            return proc.wait(timeout=660)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            return 124


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["run", "resume"])
    parser.add_argument("source")
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--cwd", default=str(ROOT))
    args = parser.parse_args()
    sys.exit(launch(args.action, args.source, args.input, args.cwd))
