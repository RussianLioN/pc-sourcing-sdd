#!/Users/s060874gmail.com/.pyenv/versions/3.13.3/bin/python3
"""Reviewed Spec Kit executable wrapper; actual Codex, never a mock."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT / "scripts/codex-pin.json").read_text())
real = Path(PIN["executable"])
if hashlib.sha256(real.read_bytes()).hexdigest() != PIN["sha256"]:
    raise SystemExit("BLOCKED Codex executable changed")
if os.environ.get("SPECKIT_INTEGRATION_CODEX_EXTRA_ARGS", ""):
    raise SystemExit("BLOCKED unexpected integration extra args")
args = sys.argv[1:]
if len(args) not in (2, 3) or args[0] != "exec" or (len(args) == 3 and args[2] != "--json"):
    raise SystemExit("BLOCKED only exec + prompt + optional --json allowed")
mode = os.environ.get("PC_WORKER_MODE", "writer")
if mode not in ("writer", "verifier"):
    raise SystemExit("BLOCKED invalid worker mode")
sandbox = "workspace-write"
cwd = Path.cwd().resolve()
if mode == "writer" and not cwd.is_relative_to(ROOT / ".worktrees"):
    raise SystemExit("BLOCKED writer requires project worktree")
if mode == "verifier" and cwd != ROOT:
    raise SystemExit("BLOCKED verifier requires integrated project")
stamp = str(time.time_ns())
out = ROOT / "artifacts" / "workers" / (mode + "-" + stamp)
out.mkdir(parents=True)
scratch = Path(tempfile.mkdtemp(prefix="pc-verifier-", dir="/tmp")) if mode == "verifier" else cwd
cmd = [
    str(real),
    "exec",
    "--ignore-user-config",
    "--ephemeral",
    "--sandbox",
    sandbox,
    "--model",
    PIN["model"],
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
    str(out / "final.md"),
    args[1],
]
if mode == "verifier":
    cmd.insert(2, "--skip-git-repo-check")
    cmd[-1] = (
        "Your writable workspace is a private scratch directory; the project "
        + str(ROOT)
        + " is read-only outside it. Execute all project commands with cd "
        + str(ROOT)
        + "; put reproducers and temp files only in $TMPDIR. First run "
        + str(ROOT / ".venv/bin/python")
        + " "
        + str(ROOT / "scripts/verify_readonly.py")
        + " and include its exit/status in checks. Do not ask for broader permissions.\n"
        + args[1]
    )
env = os.environ.copy()
for name in list(env):
    if name.endswith("API_KEY") or name.startswith("SPECKIT_INTEGRATION_"):
        env.pop(name, None)
env["TMPDIR"] = (
    str(scratch / "tmp") if mode == "verifier" else tempfile.mkdtemp(prefix="pc-writer-")
)
Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
env["PYTHONDONTWRITEBYTECODE"] = "1"
start = time.monotonic()
record = {
    "kind": "real_codex_exec",
    "mode": mode,
    "sandbox": sandbox,
    "executable": str(real),
    "version": PIN["version"],
    "model": PIN["model"],
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
    next_step="collect diff and validate" if code == 0 else "blocked: inspect worker failure",
)
(out / "result.json").write_text(json.dumps(record, indent=2))
(out / "process.json").write_text(
    json.dumps({"pid": proc.pid, "state": "terminated", "exit_code": code})
)
print(json.dumps({"kind": "real_codex_exec", "exit_code": code, "artifacts": str(out)}))
raise SystemExit(code if code >= 0 else 128 - code)
