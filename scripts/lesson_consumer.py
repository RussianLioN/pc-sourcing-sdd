"""Synthetic bootstrap proof tied to a real isolated Git change and bounded recipe."""

import hashlib
import json
import subprocess

from reviewed_lessons import Rejected, checked, encoded, hash_id, read, safe_root

BEFORE = b"def resolve(values):\n    return values[-1]\n"
AFTER = b"def resolve(values):\n    return tuple(dict.fromkeys(values))\n"
COUNTERFACTUAL = {"before": [64, 96], "after": [[96, 64], [64, 96]]}


def git(repo, *args):
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args], stderr=subprocess.PIPE, timeout=10
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise Rejected("actual isolated Git change unavailable") from exc


def commit(repo, message):
    git(repo, "add", "--all")
    git(
        repo,
        "-c",
        "user.name=Synthetic Consumer",
        "-c",
        "user.email=synthetic@example.invalid",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "--quiet",
        "-m",
        message,
    )
    return git(repo, "rev-parse", "HEAD").decode().strip()


def prove_recipe(before, after):
    # Exact fixed bootstrap recipe only; arbitrary Git/lesson/evidence code is never executed.
    if before != BEFORE or after != AFTER:
        raise Rejected("consumer change does not match bounded conflict-preservation recipe")

    def evaluate(source):
        namespace = {"__builtins__": {"tuple": tuple, "dict": dict}}
        exec(compile(source, "synthetic-reviewed-recipe", "exec"), namespace)
        return [namespace["resolve"]([96, 64]), namespace["resolve"]([64, 96])]

    observed = {"before": evaluate(before), "after": [list(x) for x in evaluate(after)]}
    if observed != COUNTERFACTUAL:
        raise Rejected("meaningful counterfactual failed")
    return observed


def validate_use(store, receipt, external_result_review=None):
    checked(
        receipt,
        {
            "explicit_skill",
            "snapshot_sha256",
            "lesson_sha256",
            "context",
            "applicability",
            "outcome_kind",
            "outcome_path",
            "outcome_sha256",
            "base_commit",
            "resulting_commit",
            "change_repository",
            "synthetic",
        },
    )
    if receipt["explicit_skill"] != "$pc-reviewed-lessons" or receipt["synthetic"] is not True:
        raise Rejected("explicit synthetic bootstrap invocation required")
    for key in ["base_commit", "resulting_commit"]:
        hash_id(receipt[key], "git")
    snapshot = store.search(receipt["context"])
    if (
        receipt["applicability"] != "applicable"
        or snapshot["snapshot_sha256"] != receipt["snapshot_sha256"]
        or receipt["lesson_sha256"] not in {x["lesson_sha256"] for x in snapshot["lessons"]}
    ):
        raise Rejected("not applicable or wrong active snapshot")
    if receipt["outcome_kind"] != "design_decision":
        raise Rejected("MVP requires a substantive change-bound decision, not reused evidence/test")
    repo = safe_root(receipt["change_repository"])
    path = safe_root(receipt["outcome_path"])
    if path != repo / "decision.json":
        raise Rejected("outcome must be the new committed decision in its isolated change")
    hash_id(receipt["outcome_sha256"])
    base, result = receipt["base_commit"], receipt["resulting_commit"]
    if (
        git(repo, "cat-file", "-t", base).strip() != b"commit"
        or git(repo, "cat-file", "-t", result).strip() != b"commit"
    ):
        raise Rejected("actual commit objects required")
    if git(repo, "rev-parse", "HEAD").decode().strip() != result or git(
        repo, "status", "--porcelain"
    ):
        raise Rejected("consumer result must be current clean actual change")
    if git(repo, "rev-list", "--parents", "-n", "1", result).decode().split() != [result, base]:
        raise Rejected("consumer change must directly follow recorded baseline")
    if git(repo, "diff", "--name-status", base, result).decode().splitlines() != [
        "A\tdecision.json",
        "M\tresolver.py",
    ]:
        raise Rejected("new decision and actual bounded implementation change required")
    raw = git(repo, "show", result + ":decision.json")
    if (
        not path.is_file()
        or path.read_bytes() != raw
        or hashlib.sha256(raw).hexdigest() != receipt["outcome_sha256"]
    ):
        raise Rejected("observable outcome missing, changed or uncommitted")
    decision = read(path)
    checked(
        decision,
        {
            "schema_version",
            "synthetic",
            "lesson_sha256",
            "context",
            "decision_id",
            "base_commit",
            "change_path",
            "before_sha256",
            "after_sha256",
            "counterfactual",
        },
    )
    before, after = (
        git(repo, "show", base + ":resolver.py"),
        git(repo, "show", result + ":resolver.py"),
    )
    expected = {
        "schema_version": "1.0.0",
        "synthetic": True,
        "lesson_sha256": receipt["lesson_sha256"],
        "context": "declarations",
        "decision_id": "preserve_conflicting_declarations",
        "base_commit": base,
        "change_path": "resolver.py",
        "before_sha256": hashlib.sha256(before).hexdigest(),
        "after_sha256": hashlib.sha256(after).hexdigest(),
        "counterfactual": prove_recipe(before, after),
    }
    if encoded(decision) != encoded(expected) or receipt["context"] != "declarations":
        raise Rejected("substantive decision not bound to actual learned change")
    if external_result_review is not None:
        raise Rejected("writer cannot inject real independent result authority")
    return {
        "status": "BOOTSTRAP_PROOF_ONLY",
        "synthetic": True,
        "outcome_sha256": receipt["outcome_sha256"],
        "actual_base_commit": base,
        "actual_resulting_commit": result,
        "counterfactual": expected["counterfactual"],
        "independent_review": "PENDING",
        "real_learning_enabled": False,
    }


def new_decision(store, context, output):
    snapshot = store.search(context)
    if not snapshot["lessons"]:
        raise Rejected("no applicable active fixture lesson")
    lesson = snapshot["lessons"][0]
    if lesson["lesson_id"] != "conflict" or context != "declarations":
        raise Rejected("consumer recipe not applicable to this lesson")
    output = safe_root(output)
    repo = output.with_name(output.name + ".isolated-change")
    if output.exists() or repo.exists():
        raise Rejected("new observable output required")
    repo.mkdir()
    git(repo, "init", "--quiet")
    (repo / "resolver.py").write_bytes(BEFORE)
    base = commit(repo, "Synthetic baseline: last declaration hides conflict")
    decision = {
        "schema_version": "1.0.0",
        "synthetic": True,
        "lesson_sha256": lesson["lesson_sha256"],
        "context": context,
        "decision_id": "preserve_conflicting_declarations",
        "base_commit": base,
        "change_path": "resolver.py",
        "before_sha256": hashlib.sha256(BEFORE).hexdigest(),
        "after_sha256": hashlib.sha256(AFTER).hexdigest(),
        "counterfactual": prove_recipe(BEFORE, AFTER),
    }
    (repo / "resolver.py").write_bytes(AFTER)
    path = repo / "decision.json"
    path.write_bytes(encoded(decision))
    result = commit(repo, "Synthetic reviewed lesson: retain both conflicting declarations")
    output.write_text(json.dumps(decision, indent=2) + "\n")
    return {
        "explicit_skill": "$pc-reviewed-lessons",
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "lesson_sha256": lesson["lesson_sha256"],
        "context": context,
        "applicability": "applicable",
        "outcome_kind": "design_decision",
        "outcome_path": str(path),
        "outcome_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "base_commit": base,
        "resulting_commit": result,
        "change_repository": str(repo),
        "synthetic": True,
    }
