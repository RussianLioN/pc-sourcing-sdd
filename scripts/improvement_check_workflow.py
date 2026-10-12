"""Pinned existing Spec Kit with exclusive lock, no second orchestrator."""

import fcntl
import hashlib
import json
import os
import signal
import subprocess
from pathlib import Path

from improvement_scope import check
from toolchain import require_spec_kit

ROOT = Path(__file__).resolve().parents[1]


def main():
    check()
    if os.environ.get("SPECKIT_INTEGRATION_CODEX_EXTRA_ARGS"):
        raise ValueError("unexpected integration extra args")
    runner = require_spec_kit(ROOT)
    workflow = ROOT / "workflows/improvement-validation.yml"
    task = json.loads((ROOT / "tasks/T017.json").read_bytes())
    if hashlib.sha256(workflow.read_bytes()).hexdigest() != task["workflow_sha256"]:
        raise ValueError("workflow/task mismatch")
    with (ROOT / ".specify/workflows/coordinator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        process = subprocess.Popen(
            [runner["executable"], "workflow", "run", str(workflow), "--json"],
            cwd=ROOT,
            start_new_session=True,
        )
        try:
            return process.wait(timeout=660)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return 124


if __name__ == "__main__":
    raise SystemExit(main())
