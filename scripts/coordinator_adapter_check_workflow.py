"""Pinned Spec Kit, exclusive coordinator lock, bounded T018 checks."""

import fcntl
import hashlib
import json
import os
import signal
import subprocess
from pathlib import Path

from coordinator_adapter_scope import check
from toolchain import require_spec_kit

ROOT = Path(__file__).resolve().parents[1]


def main():
    check()
    if os.environ.get("SPECKIT_INTEGRATION_CODEX_EXTRA_ARGS"):
        raise ValueError("unexpected integration arguments")
    runner = require_spec_kit(ROOT)
    workflow = ROOT / "workflows/coordinator-adapter-validation.yml"
    if (
        hashlib.sha256(workflow.read_bytes()).hexdigest()
        != json.loads((ROOT / "tasks/T018.json").read_text())["workflow_sha256"]
    ):
        raise ValueError("workflow task mismatch")
    with (ROOT / ".specify/workflows/coordinator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = subprocess.Popen(
            [runner["executable"], "workflow", "run", str(workflow), "--json"],
            cwd=ROOT,
            start_new_session=True,
        )
        try:
            return p.wait(timeout=660)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            return 124


if __name__ == "__main__":
    raise SystemExit(main())
