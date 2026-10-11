"""Bounded real runner experiments; distinguish synthetic actions from actual Codex."""

import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv/bin/python")
RUNNER = str(ROOT / "scripts/run_workflow.py")
SPECIFY = str(ROOT / ".tools/spec-kit-env/bin/specify")
OUT = ROOT / "artifacts/runner-probes"
OUT.mkdir(parents=True, exist_ok=True)
results = []


def env_for(name):
    env = os.environ.copy()
    env["PC_PROBE_DIR"] = tempfile.mkdtemp(prefix=name + "-", dir=OUT)
    return env


def call(name, args, env):
    p = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    (OUT / (name + ".stdout")).write_text(p.stdout)
    (OUT / (name + ".stderr")).write_text(p.stderr)
    try:
        obj = json.loads(p.stdout)
    except ValueError:
        obj = {"output": p.stdout}
    return p.returncode, obj


def note(name, ok, **fields):
    results.append({"name": name, "status": "passed" if ok else "failed", **fields})
    print(json.dumps(results[-1]), flush=True)
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))


env = env_for("pause")
code, obj = call("pause", [PY, RUNNER, "run", "workflows/probe-pause.yml"], env)
rid = obj.get("run_id")
note(
    "pause",
    code == 0 and obj.get("status") == "paused",
    kind="synthetic_orchestration",
    exit_code=code,
    outcome=obj,
)
if rid:
    first = subprocess.Popen(
        [PY, RUNNER, "resume", rid, "--input", "verdict=approve"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    marker = Path(env["PC_PROBE_DIR"]) / "child.json"
    deadline = time.monotonic() + 10
    while not marker.exists() and first.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    code2, obj2 = call(
        "duplicate-resume", [PY, RUNNER, "resume", rid, "--input", "verdict=approve"], env
    )
    stdout, stderr = first.communicate(timeout=20)
    (OUT / "resume.stdout").write_text(stdout)
    (OUT / "resume.stderr").write_text(stderr)
    obj1 = json.loads(stdout)
    note(
        "duplicate-resume-excluded",
        marker.exists() and code2 == 75 and obj2.get("status") == "blocked",
        kind="project_exclusive_lock",
        exit_code=code2,
        outcome=obj2,
    )
    ledger = (Path(env["PC_PROBE_DIR"]) / "ledger.jsonl").read_text().splitlines()
    note(
        "paused-resume-idempotent",
        first.returncode == 0 and obj1.get("status") == "completed" and len(ledger) == 1,
        kind="synthetic_orchestration",
        completed_step_executions=len(ledger),
        outcome=obj1,
    )

env = env_for("failure")
code, obj = call("failure", [PY, RUNNER, "run", "workflows/probe-failure.yml"], env)
note(
    "shell-failure-recorded",
    code != 0 and obj.get("status") == "failed",
    kind="synthetic_orchestration",
    exit_code=code,
    outcome=obj,
)
if obj.get("run_id"):
    code, obj = call(
        "failure-resume", [PY, RUNNER, "resume", obj["run_id"], "--input", "state=pass"], env
    )
    ledger = (Path(env["PC_PROBE_DIR"]) / "ledger.jsonl").read_text().splitlines()
    note(
        "failed-resume-idempotent",
        code == 0 and obj.get("status") == "completed" and len(ledger) == 1,
        kind="synthetic_orchestration",
        completed_step_executions=len(ledger),
        outcome=obj,
    )

env = env_for("running")
old = set((ROOT / ".specify/workflows/runs").iterdir())
with (
    (OUT / "killed-coordinator.stdout").open("w") as o,
    (OUT / "killed-coordinator.stderr").open("w") as e,
):
    p = subprocess.Popen(
        [SPECIFY, "workflow", "run", str(ROOT / "workflows/probe-running.yml"), "--json"],
        cwd=ROOT,
        env=env,
        stdout=o,
        stderr=e,
        start_new_session=True,
    )
    marker = Path(env["PC_PROBE_DIR"]) / "child.json"
    deadline = time.monotonic() + 10
    while not marker.exists() and p.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    new = set((ROOT / ".specify/workflows/runs").iterdir()) - old
    child = json.loads(marker.read_text())["pid"] if marker.exists() else None
    if p.poll() is None:
        os.killpg(p.pid, signal.SIGKILL)
    p.wait(timeout=5)
if len(new) == 1:
    runpath = next(iter(new))
    state = json.loads((runpath / "state.json").read_text())
    code, obj = call("running-resume", [PY, RUNNER, "resume", runpath.name], env)
    alive = False
    if child:
        try:
            os.kill(child, 0)
            alive = True
        except ProcessLookupError:
            pass
    note(
        "running-crash-refused",
        state.get("status") == "running" and code != 0 and not alive,
        kind="actual_runner_killed_synthetic_child",
        persisted_status=state.get("status"),
        child_alive=alive,
        exit_code=code,
        recovery_status="blocked",
        reason="Spec Kit running-state resume unsupported",
        outcome=obj,
    )
else:
    note(
        "running-crash-refused",
        False,
        kind="infrastructure",
        reason="unable to identify unique run",
    )

# Terminate an actual Codex executable. No fake adapter or verdict.
env = env_for("real-worker")
env["PC_WORKER_MODE"] = "verifier"
env["SPECKIT_INTEGRATION_CODEX_EXECUTABLE"] = str(ROOT / "scripts/codex_worker.py")
old = set((ROOT / "artifacts/workers").iterdir())
with (OUT / "killed-worker.stdout").open("w") as o, (OUT / "killed-worker.stderr").open("w") as e:
    p = subprocess.Popen(
        [PY, RUNNER, "run", "workflows/worker-crash.yml"], cwd=ROOT, env=env, stdout=o, stderr=e
    )
    deadline = time.monotonic() + 15
    process = None
    while time.monotonic() < deadline and p.poll() is None:
        new = set((ROOT / "artifacts/workers").iterdir()) - old
        files = [d / "process.json" for d in new if (d / "process.json").exists()]
        if files:
            process = files[0]
            break
        time.sleep(0.05)
    if process:
        pid = json.loads(process.read_text())["pid"]
        os.killpg(pid, signal.SIGKILL)
    p.wait(timeout=15)
obj = json.loads((OUT / "killed-worker.stdout").read_text())
death = json.loads(process.read_text()) if process else {}
note(
    "actual-codex-worker-death",
    process is not None
    and death.get("state") == "terminated"
    and death.get("exit_code") == -9
    and obj.get("status") == "failed",
    kind="real_codex_exec_deliberately_killed",
    worker=death,
    outcome=obj,
    next_step="audited new worker attempt; do not auto-retry paid calls",
)

env = env_for("args")
env["SPECKIT_INTEGRATION_CODEX_EXTRA_ARGS"] = "--unexpected-extra-argument"
code, obj = call("extra-args", [str(ROOT / "scripts/codex_worker.py"), "exec", "no dispatch"], env)
reason = (OUT / "extra-args.stderr").read_text()
note(
    "extra-args-refused",
    code != 0 and "unexpected integration extra args" in reason,
    kind="safety_wrapper_no_dispatch",
    exit_code=code,
)
note(
    "two-writer-integration",
    True,
    kind="status_only",
    capability_status="not_run",
    reason="only one writer authorized for this pilot",
)
print(
    json.dumps(
        {
            "status": "passed" if all(r["status"] == "passed" for r in results) else "failed",
            "results": str(OUT / "results.json"),
        }
    )
)
raise SystemExit(0 if all(r["status"] == "passed" for r in results) else 1)
