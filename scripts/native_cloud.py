"""Managed native cloud acceptance; no cloud API, identity auth or OS denial claim."""

import argparse
import hashlib
import json
import os
import platform
import re
import signal
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILES = (
    "docs/adr/0001-native-cloud-acceptance.md",
    "specs/003-native-cloud/spec.md",
    "specs/003-native-cloud/plan.md",
    "specs/003-native-cloud/acceptance-profile.json",
    "tasks/T008.json",
)
REQUIRED = (
    "bootstrap",
    "pytest",
    "ruff_check",
    "ruff_format",
    "pipeline",
    "scope",
    "pipeline_repeat",
)


class AcceptanceError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise AcceptanceError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def full_sha(value):
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value), "full Git SHA required"
    )
    return value


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], timeout=30)


def clean(root):
    return not git(root, "status", "--porcelain", "--untracked-files=all").strip()


def snapshot(root):
    digest = hashlib.sha256()
    for name in sorted(git(root, "ls-files", "-z").decode().rstrip("\0").split("\0")):
        path = Path(root) / name
        digest.update(name.encode() + b"\0" + path.read_bytes())
    return {
        "commit": git(root, "rev-parse", "HEAD").decode().strip(),
        "git_tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
        "tracked_sha256": digest.hexdigest(),
    }


def quality_snapshot(root):
    """Same file-set hashes as the protected quality collector, at this root."""

    def digest(paths):
        h = hashlib.sha256()
        for path in sorted(paths):
            h.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes())
        return h.hexdigest()

    return {
        "commit": git(root, "rev-parse", "HEAD").decode().strip(),
        "spec_hash": digest(
            list((root / "specs").rglob("*.md"))
            + list((root / "specs").rglob("*.json"))
            + [root / ".specify/memory/constitution.md"]
        ),
        "fixtures_hash": digest(list((root / "fixtures").rglob("*.json"))),
        "tests_hash": digest(list((root / "tests").rglob("*.py"))),
        "code_hash": digest(list((root / "src").rglob("*.py"))),
        "tooling_hash": digest(
            list((root / "scripts").glob("*.py"))
            + list((root / "scripts").glob("*.json"))
            + list((root / "scripts").glob("codex-worker"))
            + list((root / "workflows").glob("*.yml"))
        ),
        "lock_hash": digest(list(root.glob("*.lock"))),
    }


def contract(root, commit):
    full_sha(commit)
    frozen = {name: git(root, "show", f"{commit}:{name}") for name in CONTRACT_FILES}
    for name, raw in frozen.items():
        require((Path(root) / name).read_bytes() == raw, "contract changed: " + name)
    task = json.loads(frozen["tasks/T008.json"])
    profile = json.loads(frozen["specs/003-native-cloud/acceptance-profile.json"])
    require(task["id"] == "T008" and task["status"] == "ready", "T008 not ready")
    require(tuple(task["contract_files"]) == CONTRACT_FILES, "contract file set differs")
    require(
        profile["id"] == "native-cloud-offline" and profile["version"] == "1.0.0", "profile differs"
    )
    require(tuple(profile["required_checks"]) == REQUIRED, "required checks differ")
    require(task["base_commit"] == profile["baseline_commit"], "baseline differs")
    for key in ("change_spec", "acceptance_profile"):
        pin = task[key]
        require(sha(Path(root) / pin["path"]) == pin["sha256"], "spec/profile hash differs")
    return (
        task,
        profile,
        {
            "commit": commit,
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "spec_sha256": task["change_spec"]["sha256"],
            "profile_sha256": task["acceptance_profile"]["sha256"],
        },
    )


def verify_project(root, expected, contract_commit):
    full_sha(expected)
    require(
        git(root, "rev-parse", "HEAD").decode().strip() == expected, "STALE expected SHA differs"
    )
    require(clean(root), "STALE checkout is dirty")
    task, profile, binding = contract(root, contract_commit)
    ancestry = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", contract_commit, expected],
        timeout=30,
    )
    require(ancestry.returncode == 0, "contract is not ancestor of target")
    for name in task["protected_files"]:
        require(
            (Path(root) / name).read_bytes() == git(root, "show", f"{task['base_commit']}:{name}"),
            "protected baseline changed: " + name,
        )
    changed = set(
        git(root, "diff", "--name-only", task["base_commit"], expected).decode().splitlines()
    )
    require(not changed - set(task["owned_files"]), "unowned changes")
    return profile, binding, snapshot(root)


def artifact_path(directory, name):
    require(isinstance(name, str) and bool(name), "invalid evidence path")
    path = Path(name)
    require(not path.is_absolute() and ".." not in path.parts, "evidence escapes directory")
    resolved = (Path(directory) / path).resolve()
    require(
        resolved.is_relative_to(Path(directory).resolve()), "evidence symlink escapes directory"
    )
    return resolved


def read_record(path, role, task_id, binding, current, profile, expected_quality):
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    require(
        data["schema"] == profile["record_schema"] and data["role"] == role,
        "record schema/role differs",
    )
    require(isinstance(task_id, str) and bool(task_id.strip()), "actual task ID required")
    require(data["task_id"] == task_id, "record task differs")
    require(
        isinstance(data["environment_id"], str) and bool(data["environment_id"]),
        "environment ID missing",
    )
    require(
        data["contract"] == binding and data["snapshot"] == current, "STALE record SHA/spec differs"
    )
    require(
        data["status"] == "passed" and data["clean_before"] is True and data["clean_after"] is True,
        "record did not pass clean checks",
    )
    require(data["unchanged_during_checks"] is True, "snapshot changed during checks")
    require(data["claims"] == profile["claims"], "unsupported runtime claim")
    require(set(profile["limitations"]) <= set(data["limitations"]), "required limitations missing")
    require(
        all(data["environment"].get(k) == v for k, v in profile["required_environment"].items()),
        "required actual Linux environment differs",
    )
    checks = data["checks"]
    require(
        len(checks) == len(REQUIRED) and {c["id"] for c in checks} == set(REQUIRED),
        "required check missing/duplicate",
    )
    evidence = data["evidence"]
    require(bool(evidence), "evidence missing")
    for name, expected in evidence.items():
        require(sha(artifact_path(path.parent, name)) == expected, "evidence hash differs: " + name)
    for name in (
        "quality/manifest.json",
        "quality/tests.xml",
        "quality/pilot.sqlite",
        "quality/report.md",
        "repeat.json",
    ):
        require(name in evidence, "required evidence missing: " + name)
    for check in checks:
        require(
            type(check["exit_code"]) is int and check["exit_code"] == 0, "required command failed"
        )
        require(
            isinstance(check["command"], list) and bool(check["command"]), "command not recorded"
        )
        require(check["log"] in evidence, "command log missing")
    quality = json.loads(artifact_path(path.parent, "quality/manifest.json").read_text())
    require(
        quality["status"] == "passed" and quality["unchanged_during_checks"] is True,
        "quality failed",
    )
    require(quality["snapshot"] == expected_quality, "quality SHA/spec/corpus differs")
    require(
        len(quality["checks"]) == 4
        and all(type(c["exit_code"]) is int and c["exit_code"] == 0 for c in quality["checks"]),
        "quality commands failed",
    )
    require(data["quality_snapshot"] == quality["snapshot"], "quality snapshot differs")
    repeat = json.loads(artifact_path(path.parent, "repeat.json").read_text())
    require(
        repeat["before"] == repeat["after"] and repeat["exit_code"] == 0, "pipeline repeat differs"
    )
    require(
        repeat["after"]["db_sha256"] == evidence["quality/pilot.sqlite"]
        and repeat["after"]["report_sha256"] == evidence["quality/report.md"],
        "repeat evidence differs",
    )
    return data


def reference(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def validate_bundle(root, manifest, expected, contract_commit, writer_task_id, reviewer_task_id):
    profile, binding, current = verify_project(root, expected, contract_commit)
    require(manifest["schema"] == profile["manifest_schema"], "manifest schema differs")
    require(
        manifest["snapshot"] == current and manifest["contract"] == binding,
        "STALE manifest SHA/spec differs",
    )
    require(manifest["claims"] == profile["claims"], "unsupported manifest claim")
    require(manifest["status"] == "passed", "manifest is not accepted")
    require(
        set(profile["limitations"]) <= set(manifest["limitations"]), "manifest limitations missing"
    )
    refs = manifest["references"]
    for ref in refs.values():
        require(sha(ref["path"]) == ref["sha256"], "referenced receipt hash differs")
    expected_quality = quality_snapshot(root)
    writer = read_record(
        refs["writer"]["path"],
        "writer",
        writer_task_id,
        binding,
        current,
        profile,
        expected_quality,
    )
    reviewer = read_record(
        refs["reviewer"]["path"],
        "reviewer",
        reviewer_task_id,
        binding,
        current,
        profile,
        expected_quality,
    )
    require(writer_task_id != reviewer_task_id, "reviewer task is not independent")
    require(
        writer["checkout_identity"] != reviewer["checkout_identity"],
        "reviewer checkout is not separate",
    )
    require(
        writer["quality_snapshot"] == reviewer["quality_snapshot"],
        "writer/reviewer quality differs",
    )
    review = json.loads(Path(refs["review"]["path"]).read_text())
    require(
        review["schema"] == profile["review_schema"] and review["task_id"] == reviewer_task_id,
        "review identity differs",
    )
    require(
        review["commit"] == expected and review["contract"] == binding, "review SHA/spec differs"
    )
    require(
        review["writer_record_sha256"] == refs["writer"]["sha256"]
        and review["reviewer_record_sha256"] == refs["reviewer"]["sha256"],
        "review evidence binding differs",
    )
    require(
        review["verdict"] == "passed" and review["findings"] == [],
        "independent review did not pass",
    )
    require(
        review["clean_after"] is True and review["snapshot_after"] == current,
        "review ended on a changed checkout",
    )
    require(
        isinstance(review["summary"], str) and bool(review["summary"].strip()),
        "review inspection summary missing",
    )
    require(set(profile["limitations"]) <= set(review["limitations"]), "review limitations missing")
    provenance = json.loads(Path(refs["provenance"]["path"]).read_text())
    require(provenance["schema"] == "native-cloud-provenance/1", "provenance schema differs")
    require(
        provenance["commit"] == expected and provenance["contract_commit"] == contract_commit,
        "provenance snapshot differs",
    )
    require(
        provenance["writer_task_id"] == writer_task_id
        and provenance["reviewer_task_id"] == reviewer_task_id,
        "provenance task differs",
    )
    require(
        all(
            provenance.get(k) is True
            for k in (
                "verified_real_tasks",
                "separate_checkouts",
                "reviewer_did_not_integrate_patches",
            )
        ),
        "parent provenance verification missing",
    )
    for key in ("writer", "reviewer", "review"):
        require(provenance[key + "_sha256"] == refs[key]["sha256"], "provenance evidence differs")
    require(
        clean(root) and snapshot(root) == current, "STALE project changed during acceptance checks"
    )
    return {
        "status": "passed",
        "profile": profile["id"],
        "commit": expected,
        "acceptance": "managed process only",
        "T007": "unaccepted",
    }


def run_command(root, command, out, name):
    start = time.monotonic()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with (out / name).open("x") as log:
        proc = subprocess.Popen(
            command, cwd=root, env=env, stdout=log, stderr=log, start_new_session=True
        )
        try:
            code = proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            code = 124
    return {
        "command": command,
        "exit_code": code,
        "log": name,
        "seconds": round(time.monotonic() - start, 3),
        "local_timeout_seconds": 180,
    }


def pipeline_state(directory):
    database = directory / "pilot.sqlite"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as con:
        require(
            con.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity failed"
        )
        require(
            not con.execute("PRAGMA foreign_key_check").fetchall(), "SQLite foreign keys failed"
        )
        counts = {
            t: con.execute("SELECT count(*) FROM " + t).fetchone()[0]
            for t in ("runs", "offers", "evaluations", "rejections")
        }
    return {
        "db_sha256": sha(database),
        "report_sha256": sha(directory / "report.md"),
        "counts": counts,
    }


def collect(root, out, expected, contract_commit, role, task_id, environment_id):
    profile, binding, before = verify_project(root, expected, contract_commit)
    require(role in ("writer", "reviewer"), "unknown role")
    require(bool(environment_id), "actual environment ID required")
    out = Path(out).absolute()
    require(
        out.is_relative_to(root / "artifacts/native-cloud")
        and out.resolve().is_relative_to(root / "artifacts/native-cloud"),
        "new native-cloud artifact path required",
    )
    out.mkdir(parents=True, exist_ok=False)
    stat = (root / ".git").stat()
    identity = hashlib.sha256(
        f"{platform.node()}:{root}:{stat.st_dev}:{stat.st_ino}".encode()
    ).hexdigest()
    record = {
        "schema": profile["record_schema"],
        "role": role,
        "task_id": task_id,
        "environment_id": environment_id,
        "checkout_root": str(root),
        "checkout_identity": identity,
        "contract": binding,
        "snapshot": before,
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
        },
        "clean_before": True,
        "claims": profile["claims"],
        "limitations": profile["limitations"],
        "status": "failed",
        "checks": [],
    }
    python = str(root / ".venv/bin/python")
    commands = [
        ("bootstrap", [python, str(root / "scripts/bootstrap.py"), "--check"]),
        ("quality", [python, str(root / "scripts/quality.py"), "--out", str(out / "quality")]),
        (
            "scope",
            [
                python,
                str(root / "scripts/verify_scope.py"),
                str(root / "tasks/T008.json"),
                str(root),
            ],
        ),
    ]
    try:
        for name, command in commands:
            check = run_command(root, command, out, name + ".log")
            check["id"] = name
            if name != "quality":
                record["checks"].append(check)
            require(check["exit_code"] == 0, "command failed: " + name)
            if name == "quality":
                quality = json.loads((out / "quality/manifest.json").read_text())
                record["quality_snapshot"] = quality["snapshot"]
                require(quality["status"] == "passed", "quality failed")
                for label, original, log in zip(
                    ("pytest", "ruff_check", "ruff_format", "pipeline"),
                    quality["checks"],
                    ("check-0.log", "check-1.log", "check-2.log", "pipeline.log"),
                    strict=True,
                ):
                    record["checks"].append({**original, "id": label, "log": "quality/" + log})
        initial = pipeline_state(out / "quality")
        command = [
            python,
            "-m",
            "pc_sourcing.pipeline",
            "--input",
            str(out / "quality/input.json"),
            "--db",
            str(out / "quality/pilot.sqlite"),
            "--report",
            str(out / "quality/report.md"),
            "--as-of",
            json.loads((root / "fixtures/golden.json").read_text())["as_of"],
            "--run-id",
            "acceptance-pilot",
        ]
        check = run_command(root, command, out, "repeat.log")
        record["checks"].append({**check, "id": "pipeline_repeat"})
        repeated = pipeline_state(out / "quality")
        (out / "repeat.json").write_text(
            json.dumps(
                {"before": initial, "after": repeated, "exit_code": check["exit_code"]}, indent=2
            )
            + "\n"
        )
        require(check["exit_code"] == 0 and initial == repeated, "pipeline repetition failed")
        record["status"] = "passed"
    except (AcceptanceError, OSError, ValueError, subprocess.SubprocessError) as error:
        record["failure"] = str(error)
    record["clean_after"] = clean(root)
    record["unchanged_during_checks"] = before == snapshot(root)
    if not record["clean_after"] or not record["unchanged_during_checks"]:
        record["status"] = "failed"
    # Bind relevant receipts/logs, not pytest's disposable clone trees or Git
    # administrative files. Artifacts are private and never added to Git.
    evidence_names = (
        "bootstrap.log",
        "quality.log",
        "scope.log",
        "repeat.log",
        "repeat.json",
        "quality/manifest.json",
        "quality/tests.xml",
        "quality/input.json",
        "quality/pilot.sqlite",
        "quality/report.md",
        "quality/pipeline.log",
        "quality/check-0.log",
        "quality/check-1.log",
        "quality/check-2.log",
    )
    record["evidence"] = {
        name: sha(out / name) for name in evidence_names if (out / name).is_file()
    }
    path = out / "record.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": record["status"],
                "record": str(path),
                "record_sha256": sha(path),
                "task_identity_supplied": bool(task_id),
                "independent_acceptance": "pending",
            }
        )
    )
    return 0 if record["status"] == "passed" else 1


def finalize(
    root,
    writer,
    reviewer,
    review,
    provenance,
    out,
    expected,
    contract_commit,
    writer_task_id,
    reviewer_task_id,
):
    profile, binding, current = verify_project(root, expected, contract_commit)
    manifest = {
        "schema": profile["manifest_schema"],
        "status": "passed",
        "snapshot": current,
        "contract": binding,
        "claims": profile["claims"],
        "limitations": profile["limitations"],
        "references": {
            k: reference(p)
            for k, p in {
                "writer": writer,
                "reviewer": reviewer,
                "review": review,
                "provenance": provenance,
            }.items()
        },
    }
    result = validate_bundle(
        root, manifest, expected, contract_commit, writer_task_id, reviewer_task_id
    )
    out = Path(out).absolute()
    require(
        out.is_relative_to(root / "artifacts/native-cloud")
        and out.resolve().is_relative_to(root / "artifacts/native-cloud"),
        "new native-cloud manifest path required",
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as file:
        file.write(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({**result, "manifest": str(out)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("collect", "finalize", "check"):
        command = sub.add_parser(action)
        command.add_argument("--expected-sha", required=True)
        command.add_argument("--contract-commit", required=True)
        if action == "collect":
            command.add_argument("--role", choices=("writer", "reviewer"), required=True)
            command.add_argument(
                "--task-id",
                help="actual ID supplied by parent; missing identity cannot be accepted",
            )
            command.add_argument("--environment-id", required=True)
            command.add_argument("--out", required=True)
        else:
            command.add_argument("--writer-task-id", required=True)
            command.add_argument("--reviewer-task-id", required=True)
            if action == "check":
                command.add_argument("--manifest", required=True)
            else:
                for name in ("writer", "reviewer", "review", "provenance", "out"):
                    command.add_argument("--" + name, required=True)
    args = vars(parser.parse_args())
    action = args.pop("action")
    expected = args.pop("expected_sha")
    try:
        if action == "collect":
            return collect(ROOT, expected=expected, **args)
        if action == "finalize":
            finalize(ROOT, expected=expected, **args)
        else:
            manifest = json.loads(Path(args.pop("manifest")).read_text())
            print(json.dumps(validate_bundle(ROOT, manifest, expected=expected, **args)))
        return 0
    except (
        AcceptanceError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print(json.dumps({"status": "blocked", "reason": str(error), "T007": "unaccepted"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
