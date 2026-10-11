"""Record machine evidence for one unchanged common snapshot."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(ROOT)).encode())
        h.update(b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()


def snapshot():
    return {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "spec_hash": digest(
            list((ROOT / "specs").rglob("*.md"))
            + list((ROOT / "specs").rglob("*.json"))
            + [ROOT / ".specify/memory/constitution.md"]
        ),
        "fixtures_hash": digest(list((ROOT / "fixtures").rglob("*.json"))),
        "tests_hash": digest(list((ROOT / "tests").rglob("*.py"))),
        "code_hash": digest(list((ROOT / "src").rglob("*.py"))),
    }


def run(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    before = snapshot()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    commands = [
        [
            str(ROOT / ".venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "--junitxml=" + str(out / "tests.xml"),
            "--basetemp=" + str(out / "pytest"),
        ],
        [str(ROOT / ".venv/bin/ruff"), "check", "."],
        [str(ROOT / ".venv/bin/ruff"), "format", "--check", "."],
    ]
    checks = []
    for i, command in enumerate(commands):
        start = time.monotonic()
        result = subprocess.run(
            command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120
        )
        log = out / f"check-{i}.log"
        log.write_text(result.stdout + result.stderr)
        checks.append(
            {
                "command": command,
                "exit_code": result.returncode,
                "status": "passed" if result.returncode == 0 else "failed",
                "seconds": round(time.monotonic() - start, 3),
                "log": str(log),
            }
        )
    data = json.loads((ROOT / "fixtures/golden.json").read_text())
    inp = out / "input.json"
    invalid = json.loads((ROOT / "fixtures/invalid.json").read_text())
    inp.write_text(json.dumps([c["offer"] for c in data["cases"]] + invalid, ensure_ascii=False))
    command = [
        str(ROOT / ".venv/bin/python"),
        "-m",
        "pc_sourcing.pipeline",
        "--input",
        str(inp),
        "--db",
        str(out / "pilot.sqlite"),
        "--report",
        str(out / "report.md"),
        "--as-of",
        data["as_of"],
        "--run-id",
        "acceptance-pilot",
    ]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    (out / "pipeline.log").write_text(result.stdout + result.stderr)
    checks.append(
        {
            "command": command,
            "exit_code": result.returncode,
            "status": "passed" if result.returncode == 0 else "failed",
        }
    )
    versions = {
        p: importlib.metadata.version(p) for p in ("pydantic", "pytest", "hypothesis", "ruff")
    }
    versions.update(
        python=platform.python_version(),
        sqlite=sqlite3.sqlite_version,
        spec_kit="1.1.3",
        spec_kit_sha="0282d03eb6fc3091b3deaa3a855d4030dc40cd6c",
        codex="0.157.1",
        uv="0.10.2",
    )
    stable = before == snapshot()
    evidence = {
        "snapshot": before,
        "unchanged_during_checks": stable,
        "versions": versions,
        "checks": checks,
        "status": "passed" if stable and all(c["exit_code"] == 0 for c in checks) else "failed",
        "live": {"status": "blocked", "reason": "local Tavily unavailable; Avito direct denied"},
        "next_step": "independent verifier on same snapshot",
    }
    (out / "manifest.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(json.dumps({"status": evidence["status"], "out": str(out), "snapshot": before}))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    raise SystemExit(run(args.out))
