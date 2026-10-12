"""T018 full unchanged-snapshot checks, task-owned bounds, no legacy edits."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from quality import snapshot
from toolchain import observed_versions

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / "artifacts/T018" / ("quality-" + uuid4().hex)
    out.mkdir(parents=True)
    before = snapshot()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Keep full clone-heavy regressions on the separate /tmp filesystem.
    # Retain this directory on failure as well as success for review.
    pytest_temp = Path(tempfile.mkdtemp(prefix="T018-quality-", dir="/tmp")) / "pytest"
    commands = [
        (
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--junitxml=" + str(out / "tests.xml"),
                "--basetemp=" + str(pytest_temp),
            ],
            240,
        ),
        ([str(ROOT / ".venv/bin/ruff"), "check", "."], 30),
        ([str(ROOT / ".venv/bin/ruff"), "format", "--check", "."], 30),
    ]
    golden = json.loads((ROOT / "fixtures/golden.json").read_text())
    invalid = json.loads((ROOT / "fixtures/invalid.json").read_text())
    inp = out / "input.json"
    inp.write_text(json.dumps([c["offer"] for c in golden["cases"]] + invalid, ensure_ascii=False))
    commands += [
        (
            [
                sys.executable,
                "-m",
                "pc_sourcing.pipeline",
                "--input",
                str(inp),
                "--db",
                str(out / "pilot.sqlite"),
                "--report",
                str(out / "report.md"),
                "--as-of",
                golden["as_of"],
                "--run-id",
                "T018-acceptance",
            ],
            60,
        )
    ]
    checks = []
    for i, (command, timeout) in enumerate(commands):
        timed_out = False
        try:
            completed = subprocess.run(
                command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout
            )
            output, exit_code = completed.stdout + completed.stderr, completed.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            output = (
                "".join(
                    text.decode(errors="replace") if isinstance(text, bytes) else text or ""
                    for text in (exc.stdout, exc.stderr)
                )
                + "\nBounded check timed out; partial output retained.\n"
            )
            exit_code = 124
        except OSError as exc:
            output = "Bounded check could not start: " + str(exc) + "\n"
            exit_code = 127
        (out / ("check-" + str(i) + ".log")).write_text(output)
        checks.append(
            {
                "command": command,
                "timeout_seconds": timeout,
                "exit_code": exit_code,
                "timed_out": timed_out,
            }
        )
    stable = before == snapshot()
    checks_pass = stable and all(c["exit_code"] == 0 for c in checks)
    versions = observed_versions(ROOT)
    pins_pass = all(value["status"] == "passed" for value in versions["tools"].values())
    result = {
        "status": "PASS"
        if checks_pass and pins_pass
        else "CHECKS_PASS_PINS_BLOCKED"
        if checks_pass
        else "FAIL",
        "checks_status": "PASS" if checks_pass else "FAIL",
        "toolchain_pins_status": "PASS" if pins_pass else "BLOCKED",
        "reproducibility_status": "PASS" if checks_pass and pins_pass else "BLOCKED",
        "snapshot": before,
        "unchanged_during_checks": stable,
        "checks": checks,
        "versions": versions,
        "learning_enabled": False,
        "actual_authenticated_coordinator_call": "NOT_RUN",
        "merchant_HTTP": 0,
        "pytest_temp_retained": str(pytest_temp),
    }
    (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "checks_status": result["checks_status"],
                "toolchain_pins_status": result["toolchain_pins_status"],
                "out": str(out),
                "snapshot": before,
            }
        )
    )
    # This workflow checks code/data. Completing it never grants pin acceptance.
    return 0 if checks_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
