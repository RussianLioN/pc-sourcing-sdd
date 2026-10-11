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

ROOT = Path(__file__).resolve().parents[1]


def launch(action, source, inputs=(), cwd=ROOT):
    cwd = Path(cwd).resolve()
    if cwd != ROOT and not cwd.is_relative_to(ROOT / ".worktrees"):
        raise ValueError("unapproved coordinator working directory")
    if os.environ.get("SPECKIT_INTEGRATION_CODEX_EXTRA_ARGS"):
        raise ValueError("unexpected integration extra args")
    if action == "run":
        path = (ROOT / source).resolve()
        if not path.is_relative_to(ROOT / "workflows") or not path.is_file():
            raise ValueError("only reviewed project workflow files")
        source = str(path)
    elif not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", source):
        raise ValueError("invalid run id")
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
        env = os.environ.copy()
        env["SPECKIT_INTEGRATION_CODEX_EXECUTABLE"] = str(ROOT / "scripts/codex_worker.py")
        args = [str(ROOT / ".tools/spec-kit-env/bin/specify"), "workflow", action, source, "--json"]
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
