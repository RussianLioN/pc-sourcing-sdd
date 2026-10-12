"""Pinned Spec Kit, fixed T011 validation workflow, exclusive project coordinator lock."""

import fcntl
import hashlib
import json
import os
import signal
import subprocess
from pathlib import Path

from durable_scope import check
from toolchain import require_spec_kit

ROOT = Path(__file__).resolve().parents[1]


def main():
    check()
    if os.environ.get("SPECKIT_INTEGRATION_CODEX_EXTRA_ARGS"):
        raise ValueError("unexpected integration extra args")
    runner = require_spec_kit(ROOT)
    workflow = ROOT / "workflows/durable-validation.yml"
    task = json.loads((ROOT / "tasks/T011.json").read_text())
    if hashlib.sha256(workflow.read_bytes()).hexdigest() != task["workflow_sha256"]:
        raise ValueError("workflow/task hash mismatch")
    lockpath = ROOT / ".specify/workflows/coordinator.lock"
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    with lockpath.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        proc = subprocess.Popen(
            [runner["executable"], "workflow", "run", str(workflow), "--json"],
            cwd=ROOT,
            start_new_session=True,
        )
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
    raise SystemExit(main())
