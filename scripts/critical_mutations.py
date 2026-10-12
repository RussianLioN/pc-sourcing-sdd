"""Curated semantic mutations; source/import proof precedes relevant assertions."""

import argparse
import ast
import hashlib
import importlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import types
from pathlib import Path

from reviewed_lessons import bind, digest, hash_id, projection, read

ROOT = Path(__file__).resolve().parents[1]
CORPUS = [
    {
        "id": "conflict",
        "module": "pc_sourcing.identity_attributes",
        "function": "attributes",
        "file": "src/pc_sourcing/identity_attributes.py",
        "before": "result.setdefault(name, set()).add(value)",
        "after": "result[name] = {value}",
    },
    {
        "id": "duplicate",
        "module": "pc_sourcing.product_extraction",
        "function": "unique_members",
        "file": "src/pc_sourcing/product_extraction.py",
        "before": "if key in result:",
        "after": "if False:",
    },
    {
        "id": "payment_or",
        "module": "pc_sourcing.evaluate",
        "function": "evaluate",
        "file": "src/pc_sourcing/evaluate.py",
        "before": "payment = bool(passed)",
        "after": "payment = len(passed) == 2",
    },
    {
        "id": "unknown",
        "module": "pc_sourcing.identity_claims",
        "function": "number",
        "file": "src/pc_sourcing/identity_claims.py",
        "before": "return None, default_unit",
        "after": "return False, default_unit",
    },
    {
        "id": "evidence_kind",
        "module": "pc_sourcing.evaluate",
        "function": "evaluate",
        "file": "src/pc_sourcing/evaluate.py",
        "before": '{"platform_transaction"}\n            if name',
        "after": '{"platform_transaction", "seller_statement"}\n            if name',
    },
    {
        "id": "budget_reset",
        "module": "pc_sourcing.collection_acquisition",
        "function": "Acquisition.integrity",
        "file": "src/pc_sourcing/collection_acquisition.py",
        "before": 'raise ValueError("source budget row missing/duplicated; no reset")',
        "after": "return None",
    },
    {
        "id": "schema",
        "module": "pc_sourcing.collection_runtime",
        "function": "require_schema",
        "file": "src/pc_sourcing/collection_runtime.py",
        "before": "if schema_fingerprint(db) != wanted:",
        "after": "if False:",
    },
    {
        "id": "stream",
        "module": "pc_sourcing.witness_controller",
        "function": "read_profile_body",
        "file": "src/pc_sourcing/witness_controller.py",
        "before": "if declared > byte_limit:",
        "after": "if declared > byte_limit * 2:",
    },
]


def source_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def code_hash(code):
    def constant(value):
        if isinstance(value, types.CodeType):
            return {"code": code_hash(value)}
        if isinstance(value, bytes):
            return {"bytes": value.hex()}
        if isinstance(value, tuple):
            return {"tuple": [constant(x) for x in value]}
        if isinstance(value, frozenset):
            return {
                "frozenset": sorted(
                    (constant(x) for x in value), key=lambda x: json.dumps(x, sort_keys=True)
                )
            }
        return {"type": type(value).__name__, "value": repr(value)}

    # Structural canonicalization avoids marshal intern/reference-layout artifacts.
    payload = {
        "bytecode": code.co_code.hex(),
        "constants": [constant(x) for x in code.co_consts],
        "names": code.co_names,
        "varnames": code.co_varnames,
        "freevars": code.co_freevars,
        "cellvars": code.co_cellvars,
        "flags": code.co_flags,
        "args": [code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount],
        "exceptions": code.co_exceptiontable.hex(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def compiled_function(code, names):
    for item in code.co_consts:
        if isinstance(item, types.CodeType) and item.co_name == names[0]:
            return item if len(names) == 1 else compiled_function(item, names[1:])
    raise ValueError("target function absent from compiled source")


def loaded_proof(module_name, function_name, root):
    module = importlib.import_module(module_name)
    path = Path(module.__file__).resolve()
    if Path(root).resolve() not in path.parents:
        raise ValueError("import escaped disposable root")
    value = module
    names = function_name.split(".")
    for name in names:
        value = getattr(value, name)
    fresh = compiled_function(compile(path.read_bytes(), str(path), "exec"), names)
    loaded, expected = code_hash(value.__code__), code_hash(fresh)
    return {
        "imported_path": str(path),
        "source_sha256": source_hash(path),
        "loaded_code_sha256": loaded,
        "fresh_source_code_sha256": expected,
        "actually_loaded_matches_source": loaded == expected,
    }


def semantic_assertion(case, module, root):
    if case == "duplicate":
        try:
            module.unique_members([("x", 1), ("x", 2)])
        except ValueError:
            return
        raise AssertionError("SEMANTIC: duplicate declarations must be rejected")
    elif case == "conflict":
        result = module.attributes("DDR5 96GB (2x48GB) DDR5 64GB (2x32GB)", category="ram")
        assert len(result["capacity"]) == 2, "SEMANTIC: earlier conflicting capacity retained"
    elif case == "unknown":
        assert module.number("unknown", "GB")[0] is None, "SEMANTIC: unknown must remain None"
    elif case in {"payment_or", "evidence_kind"}:
        from datetime import datetime

        from pc_sourcing.models import Offer

        data = json.loads((Path(root) / "fixtures/golden.json").read_bytes())
        offer = Offer.model_validate(data["cases"][3]["offer"])
        if case == "evidence_kind":
            offer = offer.model_copy(
                update={
                    "evidence": [
                        e.model_copy(update={"origin": "seller_statement"})
                        if e.field == "protected_route"
                        else e
                        for e in offer.evidence
                    ]
                }
            )
        value = module.evaluate(offer, datetime.fromisoformat(data["as_of"].replace("Z", "+00:00")))
        assert value.payment_gate_passed is (case == "payment_or"), (
            "SEMANTIC: route OR and evidence kind"
        )
    elif case in {"schema", "budget_reset"}:
        import sqlite3

        from pc_sourcing.collection_runtime import SOURCE_SCHEMA

        with sqlite3.connect(":memory:") as db:
            db.row_factory = sqlite3.Row
            ddl = (
                SOURCE_SCHEMA.replace("cards_reserved INTEGER NOT NULL", "cards_reserved INTEGER")
                if case == "schema"
                else SOURCE_SCHEMA
            )
            db.executescript(ddl + "PRAGMA user_version=1;")
            try:
                if case == "schema":
                    module.require_schema(db, SOURCE_SCHEMA)
                else:
                    module.Acquisition.integrity(object(), db)
            except ValueError:
                return
            raise AssertionError("SEMANTIC: schema drift/missing budget cannot pass")
    elif case == "stream":

        class Response:
            headers = {"content-length": "1200000"}
            chunked = False

            def read1(self, _size):
                return b""

        try:
            module.read_profile_body(Response(), byte_limit=1_000_000, deadline=99, clock=lambda: 0)
        except ValueError as exc:
            assert "declared length" in str(exc), (
                "SEMANTIC: refuse declared overflow before body read"
            )
            return
        raise AssertionError("SEMANTIC: profile declared body overflow refused")


def worker(root, item):
    # Local guard, not an OS sandbox. Corpus is fixed repository code, no arbitrary inputs.
    def denied(*_args, **_kwargs):
        raise RuntimeError("offline mutation socket guard")

    class OfflineSocket(socket.socket):
        connect = denied
        connect_ex = denied
        sendto = denied

    socket.socket = OfflineSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(Path(root) / "src"), str(Path(root) / "scripts")]
    proof = loaded_proof(item["module"], item["function"], root)
    if not proof["actually_loaded_matches_source"]:
        return {
            "outcome": "unapplied",
            "reason": "stale or substituted loaded bytecode",
            "proof": proof,
        }
    try:
        semantic_assertion(item["id"], importlib.import_module(item["module"]), root)
        return {"outcome": "survived", "proof": proof}
    except AssertionError as exc:
        if not str(exc).startswith("SEMANTIC:"):
            raise
        return {"outcome": "killed", "assertion": str(exc), "proof": proof}


def bounded(command, cwd, timeout=60):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        return {"outcome": "timeout", "killed": False}
    if process.returncode:
        return {
            "outcome": (
                "invalid_syntax"
                if b"SyntaxError" in err
                else "import_error"
                if b"ImportError" in err or b"ModuleNotFoundError" in err
                else "scope_error"
                if b"import escaped disposable root" in err
                else "operational_error"
            ),
            "exit_code": process.returncode,
            "stderr": err.decode()[:2000],
        }
    return json.loads(out)


def tree_hash(root, paths):
    root = Path(root)
    entries = {}
    for path in sorted(set(paths)):
        if path.is_symlink() or not path.is_file():
            raise ValueError("experiment binding input missing/symlink")
        entries[str(path.relative_to(root))] = source_hash(path)
    if not entries:
        raise ValueError("experiment binding input corpus empty")
    return digest(entries)


def experiment_binding(root):
    root = Path(root)
    git_commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    hash_id(git_commit, "git")
    return {
        "schema_version": "1.0.0",
        "git_commit": git_commit,
        "spec_sha256": tree_hash(
            root,
            list((root / "specs").rglob("*.md"))
            + list((root / "specs").rglob("*.json"))
            + [root / ".specify/memory/constitution.md"],
        ),
        "oracle_sha256": tree_hash(
            root,
            list((root / "fixtures").glob("*.json"))
            + list((root / "specs/001-offline/contracts").glob("*.json"))
            + [root / "specs/001-offline/decision-table.md"],
        ),
        "test_set_sha256": tree_hash(root, list((root / "tests").rglob("*.py"))),
        "code_sha256": tree_hash(
            root, list((root / "src").rglob("*.py")) + list((root / "scripts").glob("*.py"))
        ),
        "harness_sha256": source_hash(root / "scripts/critical_mutations.py"),
        "corpus_sha256": digest(CORPUS),
        "python_version": sys.version.split()[0],
    }


def require_stable_binding(root, expected):
    if experiment_binding(root) != expected:
        raise ValueError("experiment input drift; stale result must not be reused")


def verify_result(output, root=ROOT):
    output = Path(output)
    result = read(output / "manifest.json")
    if result.get("result_sha256") != digest(projection(result, "result_sha256")):
        raise ValueError("mutation result payload/hash mismatch")
    require_stable_binding(root, result["bindings"])
    if result["fixed_corpus"] != len(CORPUS) or len(result["outcomes"]) != len(CORPUS):
        raise ValueError("mutation corpus changed")
    for item, entry in zip(CORPUS, result["outcomes"], strict=True):
        if (
            entry["family"] != item["id"]
            or entry["bindings"] != result["bindings"]
            or read(output / (entry["family"] + ".json")) != entry
            or entry["baseline"]["outcome"] != "survived"
        ):
            raise ValueError("mutation entry/baseline binding mismatch")
        proof = entry["result"].get("proof", {})
        if entry["result"]["outcome"] == "killed" and (
            not entry["result"].get("assertion", "").startswith("SEMANTIC:")
            or proof.get("source_sha256") != entry["mutated_sha256"]
            or not proof.get("actually_loaded_matches_source")
            or proof.get("loaded_code_sha256") == entry["baseline"]["proof"]["loaded_code_sha256"]
        ):
            raise ValueError("mutation semantic kill proof invalid")
    killed = sum(x["result"]["outcome"] == "killed" for x in result["outcomes"])
    if result["meaningfully_killed"] != killed or result["status"] != (
        "PASS" if killed == len(CORPUS) else "FAIL"
    ):
        raise ValueError("mutation score/status mismatch")
    return result


def execute(output, root=ROOT):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    bindings = experiment_binding(root)
    outcomes = []
    for item in CORPUS:
        with tempfile.TemporaryDirectory(prefix="pc-semantic-") as directory:
            clone = Path(directory) / "copy"
            clone.mkdir()
            for name in ["src", "scripts", "fixtures"]:
                shutil.copytree(
                    Path(root) / name,
                    clone / name,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            target = clone / item["file"]
            original = target.read_text()
            command = [
                sys.executable,
                str(clone / "scripts/critical_mutations.py"),
                "--worker",
                str(clone),
                item["id"],
            ]
            baseline = bounded(command, clone, 120)
            if baseline.get("outcome") != "survived":
                (output / "baseline_failure.json").write_text(json.dumps(baseline, indent=2) + "\n")
                raise ValueError(
                    "nonpassing baseline invalidates mutation experiment: " + json.dumps(baseline)
                )
            if original.count(item["before"]) != 1:
                raise ValueError("mutation anchor not unique")
            mutated = original.replace(item["before"], item["after"])
            ast.parse(mutated)
            target.write_text(mutated)
            mutant = bounded(command, clone)
            require_stable_binding(root, bindings)
            if (
                mutant.get("outcome") == "killed"
                and mutant["proof"]["loaded_code_sha256"] == baseline["proof"]["loaded_code_sha256"]
            ):
                mutant = {
                    "outcome": "unapplied",
                    "reason": "target loaded semantics unchanged",
                    "proof": mutant["proof"],
                }
            entry = {
                "family": item["id"],
                "bindings": bindings,
                "synthetic": True,
                "baseline": baseline,
                "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "mutated_sha256": source_hash(target),
                "result": mutant,
            }
            if (
                mutant.get("outcome") == "killed"
                and mutant["proof"]["source_sha256"] != entry["mutated_sha256"]
            ):
                raise ValueError("mutated imported source mismatch")
            outcomes.append(entry)
            (output / (item["id"] + ".json")).write_text(json.dumps(entry, indent=2) + "\n")
    require_stable_binding(root, bindings)
    result = {
        "bindings": bindings,
        "status": "PASS" if all(x["result"]["outcome"] == "killed" for x in outcomes) else "FAIL",
        "harness_version": "1.0.0",
        "semantic_equivalence": "survivors are unresolved until independent equivalence review; never counted killed",
        "fixed_corpus": 8,
        "meaningfully_killed": sum(x["result"]["outcome"] == "killed" for x in outcomes),
        "coverage": "eight curated families only; not general mutation coverage",
        "OS_network_sandbox": "not established; fixed corpus + local socket guard only",
        "seed": 0,
        "real_learning_enabled": False,
        "merchant_HTTP": 0,
        "outcomes": outcomes,
    }
    result = bind(result, "result_sha256")
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return verify_result(output, root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=2)
    parser.add_argument("--out")
    parser.add_argument("--verify")
    args = parser.parse_args()
    if args.worker:
        root, case = args.worker
        print(json.dumps(worker(root, next(x for x in CORPUS if x["id"] == case))))
    elif args.verify:
        print(json.dumps(verify_result(args.verify)))
    else:
        print(json.dumps(execute(args.out)))


if __name__ == "__main__":
    main()
