"""One operation in a trusted external coordinator host; local CLI is proposal-only.

A Python object or JSON does not authenticate a host. The production caller
must come from the existing authenticated coordinator executor, verify the
accepted image before importing it, and retain/adjudicate anchors externally.
No production host/provider is manufactured by this module.
"""

import argparse
import fcntl
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Protocol

from lesson_consumer import ObjectView, prove_recipe
from reviewed_lessons import (
    Rejected,
    atomic,
    bind,
    checked,
    digest,
    encoded,
    hash_id,
    identifier,
    read,
    safe_root,
    validate_lesson,
)

from pc_sourcing.witness_transfer import allowed
from pc_sourcing.witness_transfer import validate as validate_source

ROOT = Path(__file__).resolve().parents[1]
OPS = {"retrieve", "promote", "rollback", "validate_result"}


class CoordinatorHost(Protocol):
    """Trusted deployment dependency; never instantiate from writer request data."""

    def read_anchor(self): ...
    def adjudicate_once(self, proposal): ...
    def commit_verified_result(self, grant, receipt): ...


def loaded_image():
    # The external executor verifies bytes BEFORE import. This catches stale or
    # replaced live functions after that trusted load, not caller authentication.
    from critical_mutations import code_hash, compiled_function, loaded_proof

    code = compile(Path(__file__).read_bytes(), str(Path(__file__)), "exec")
    result = {}
    for name in [
        "loaded_image",
        "closure",
        "source_inventory",
        "request_data",
        "result_proof",
        "Adapter.__init__",
        "Adapter.proposal",
        "Adapter.coordinator_once",
        "Replica.load",
        "Replica.prior",
        "Replica.lesson",
        "Replica.current",
        "Replica.audit",
    ]:
        parts = name.split(".")
        value = globals()[parts[0]]
        for part in parts[1:]:
            value = getattr(value, part)
        actual = code_hash(value.__code__)
        expected = code_hash(compiled_function(code, parts))
        if actual != expected:
            raise Rejected("loaded adapter code differs from accepted source")
        result[name] = actual
    for module, name, alias in [
        *[
            ("reviewed_lessons", n, n)
            for n in [
                "atomic",
                "bind",
                "checked",
                "digest",
                "encoded",
                "hash_id",
                "identifier",
                "read",
                "safe_root",
                "validate_lesson",
            ]
        ],
        ("lesson_consumer", "ObjectView.object", "ObjectView.object"),
        ("lesson_consumer", "prove_recipe", "prove_recipe"),
        ("pc_sourcing.witness_transfer", "allowed", "allowed"),
        ("pc_sourcing.witness_transfer", "validate", "validate_source"),
    ]:
        proof = loaded_proof(module, name, ROOT)
        if proof["actually_loaded_matches_source"] is not True:
            raise Rejected("loaded dependency image mismatch")
        parts = alias.split(".")
        value = globals()[parts[0]]
        for part in parts[1:]:
            value = getattr(value, part)
        if code_hash(value.__code__) != proof["loaded_code_sha256"]:
            raise Rejected("adapter dependency alias differs from accepted loaded image")
        result[module + "." + name] = proof["loaded_code_sha256"]
    return result


def closure(root=ROOT):
    root = Path(root)
    if root.resolve() != ROOT.resolve():
        raise Rejected("adapter supports only its accepted project image")
    from critical_mutations import code_hash, compiled_function

    code = compile(Path(__file__).read_bytes(), str(Path(__file__)), "exec")
    if code_hash(loaded_image.__code__) != code_hash(compiled_function(code, ["loaded_image"])):
        raise Rejected("loaded image validator differs from accepted source")
    image = loaded_image()
    paths = list((root / "src").rglob("*.py")) + list((root / "scripts").glob("*.py"))
    paths += list((root / "specs").rglob("*.md")) + list((root / "specs").rglob("*.json"))
    paths += list((root / "tests").rglob("*.py")) + list(root.glob("*.lock"))
    paths += [
        root / ".specify/memory/constitution.md",
        root / "pyproject.toml",
        root / ".agents/skills/pc-reviewed-lessons/SKILL.md",
        root / ".agents/skills/pc-reviewed-lessons/agents/openai.yaml",
    ]
    for path in paths:
        if path.is_symlink():
            raise Rejected("closure symlink")
    git_sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    hash_id(git_sha, "git")

    def group(items):
        return digest(
            {
                str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(items)
            }
        )

    return {
        "git_sha": git_sha,
        "loaded_image": image,
        "closure_sha256": group(paths),
        "spec_sha256": group(
            list((root / "specs").rglob("*.md")) + list((root / "specs").rglob("*.json"))
        ),
        "oracle_sha256": group(list((root / "fixtures").glob("*.json"))),
        "test_sha256": group(list((root / "tests").rglob("*.py"))),
    }


def source_inventory(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise Rejected("canonical source path required")
    validate_source(path)
    result = {}
    for p in sorted(path.rglob("*")):
        if p.is_symlink():
            raise Rejected("source symlink")
        if p.is_file() and allowed(str(p.relative_to(path))):
            result[str(p.relative_to(path))] = {
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "mtime_ns": p.stat().st_mtime_ns,
            }
    if len(result) != 14:
        raise Rejected("complete fourteen source payloads required")
    return result


def request_data(operation, payload):
    if operation not in OPS or not isinstance(payload, (bytes, str)):
        raise Rejected("one known operation and strict JSON bytes required")
    if len(payload if isinstance(payload, bytes) else payload.encode()) > 65536:
        raise Rejected("request bound")
    from reviewed_lessons import bad_constant, pairs

    value = json.loads(payload, object_pairs_hook=pairs, parse_constant=bad_constant)
    fields = {"request_id", "context"} | {
        "retrieve": set(),
        "promote": {"lesson_path", "result_path"},
        "rollback": {"target_hash"},
        "validate_result": {"lesson_path", "result_path"},
    }[operation]
    checked(value, fields)
    identifier(value["request_id"])
    identifier(value["context"])
    return value


class Replica:
    """Untrusted state replica. Only external matching/adjudication grants meaning."""

    def __init__(self, root, synthetic):
        self.root = safe_root(root)
        if type(synthetic) is not bool:
            raise Rejected("explicit realm required")
        self.synthetic = synthetic

    def bootstrap_untrusted(self):
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / "snapshots").mkdir()
        (self.root / "incidents").mkdir()
        snapshot = bind(
            {
                "schema_version": "1.0.0",
                "synthetic": self.synthetic,
                "version": 0,
                "previous_version": None,
                "previous_sha256": None,
                "entries": [],
            },
            "snapshot_sha256",
        )
        atomic(self.root / "snapshots" / (snapshot["snapshot_sha256"] + ".json"), snapshot)
        atomic(self.root / "active.json", {"version": 0, "sha256": snapshot["snapshot_sha256"]})
        return snapshot

    def lesson(self, value):
        validate_lesson(value)
        if value["synthetic"] is not self.synthetic:
            raise Rejected("synthetic evidence cannot be relabeled as real")
        for key in value["incident_ids"]:
            incident = read(self.root / "incidents" / (key + ".json"))
            checked(
                incident,
                {
                    "incident_id",
                    "root_cause",
                    "observed_at",
                    "affected_commit",
                    "evidence",
                    "synthetic",
                },
            )
            from datetime import UTC, datetime

            identifier(incident["incident_id"])
            identifier(incident["root_cause"])
            hash_id(incident["affected_commit"], "git")
            observed = datetime.fromisoformat(incident["observed_at"].replace("Z", "+00:00"))
            if (
                observed.utcoffset() != UTC.utcoffset(observed)
                or not isinstance(incident["evidence"], list)
                or not incident["evidence"]
            ):
                raise Rejected("incident UTC/evidence schema")
            if (
                incident["synthetic"] is not self.synthetic
                or incident["incident_id"] != key
                or digest(incident) != value["incident_sha256s"][key]
                or incident["affected_commit"] != value["code_sha"]
                or not set(incident["evidence"]) <= {e["path"] for e in value["evidence"]}
            ):
                raise Rejected("incident lineage/realm mismatch")
        return value

    def load(self, sha, live=True):
        hash_id(sha)
        value = read(self.root / "snapshots" / (sha + ".json"))
        checked(
            value,
            {
                "schema_version",
                "synthetic",
                "version",
                "previous_version",
                "previous_sha256",
                "entries",
                "snapshot_sha256",
            },
        )
        if (
            value["schema_version"] != "1.0.0"
            or value["synthetic"] is not self.synthetic
            or type(value["version"]) is not int
            or value["version"] < 0
            or bind(value, "snapshot_sha256") != value
            or value["snapshot_sha256"] != sha
        ):
            raise Rejected("replica schema/hash/realm")
        if not isinstance(value["entries"], list) or len(value["entries"]) > 32:
            raise Rejected("bounded replica entries required")
        if value["version"] == 0:
            if (
                value["entries"]
                or value["previous_version"] is not None
                or value["previous_sha256"] is not None
            ):
                raise Rejected("empty bootstrap required")
        elif (
            type(value["previous_version"]) is not int
            or value["previous_version"] != value["version"] - 1
        ):
            raise Rejected("previous replica version")
        else:
            hash_id(value["previous_sha256"])
        seen = set()
        for entry in value["entries"]:
            checked(entry, {"lesson", "result_hash", "grant_id"})
            lesson = (
                self.lesson(entry["lesson"])
                if live
                else validate_lesson(entry["lesson"], verify_evidence=False)
            )
            if lesson["synthetic"] is not self.synthetic or lesson["lesson_id"] in seen:
                raise Rejected("replica duplicate/realm")
            seen.add(lesson["lesson_id"])
            hash_id(entry["result_hash"])
            identifier(entry["grant_id"])
        return value

    def current(self, live=True):
        pointer = read(self.root / "active.json")
        checked(pointer, {"version", "sha256"})
        value = self.load(pointer["sha256"], live)
        if type(pointer["version"]) is not int or value["version"] != pointer["version"]:
            raise Rejected("pointer version mismatch")
        return value

    def prior(self, current, sha):
        target = self.load(sha)
        node, found = current, False
        for _ in range(512):
            found |= node["snapshot_sha256"] == sha and node["version"] < current["version"]
            if node["version"] == 0:
                break
            parent = self.load(node["previous_sha256"], live=False)
            if parent["version"] != node["previous_version"]:
                raise Rejected("replica ancestry version mismatch")
            node = parent
        else:
            raise Rejected("replica ancestry bound")
        if not found:
            raise Rejected("rollback target not previously visible")
        return target

    def audit(self, value):
        path = safe_root(self.root / "audit.jsonl")
        import os

        with path.open("ab") as out:
            out.write(encoded(value) + b"\n")
            out.flush()
            os.fsync(out.fileno())


def result_proof(replica, lesson, path):
    value = read(safe_root(path))
    checked(
        value,
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
    hash_id(value["snapshot_sha256"])
    if (
        value["synthetic"] is not replica.synthetic
        or value["explicit_skill"] != "$pc-reviewed-lessons"
        or value["applicability"] != "applicable"
        or value["outcome_kind"] != "design_decision"
        or value["context"] != "declarations"
        or value["lesson_sha256"] != lesson["lesson_sha256"]
    ):
        raise Rejected("new result context/realm/lesson mismatch")
    repo = safe_root(value["change_repository"])
    with ObjectView(repo) as objects:
        from lesson_consumer import head_oid, limited_file

        base_tree, _ = objects.commit_header(value["base_commit"])
        after_tree, parents = objects.commit_header(value["resulting_commit"])
        if parents != [value["base_commit"]] or head_oid(repo) != value["resulting_commit"]:
            raise Rejected("new result raw parents/head mismatch")
        before, after = objects.tree(base_tree), objects.tree(after_tree)
        if set(before) != {"resolver.py"} or set(after) != {"resolver.py", "decision.json"}:
            raise Rejected("bounded real-result recipe required")
        before_bytes = objects.object(before["resolver.py"], "blob")
        after_bytes = objects.object(after["resolver.py"], "blob")
        raw = objects.object(after["decision.json"], "blob")
        if set(p.name for p in repo.iterdir() if p.name != ".git") != set(after):
            raise Rejected("new result worktree scope")
        for name in after:
            if limited_file(repo / name) != objects.object(after[name], "blob"):
                raise Rejected("new result worktree mismatch")
    if (
        safe_root(value["outcome_path"]) != repo / "decision.json"
        or hashlib.sha256(raw).hexdigest() != value["outcome_sha256"]
    ):
        raise Rejected("new result hash/path")
    decision = read(repo / "decision.json")
    expected = {
        "schema_version": "1.0.0",
        "synthetic": replica.synthetic,
        "lesson_sha256": lesson["lesson_sha256"],
        "context": "declarations",
        "decision_id": "preserve_conflicting_declarations",
        "base_commit": value["base_commit"],
        "change_path": "resolver.py",
        "before_sha256": hashlib.sha256(before_bytes).hexdigest(),
        "after_sha256": hashlib.sha256(after_bytes).hexdigest(),
        "counterfactual": prove_recipe(before_bytes, after_bytes),
    }
    if encoded(decision) != encoded(expected):
        raise Rejected("new result substantive decision binding")
    return value


class Adapter:
    def __init__(self, replica_path, source_path, synthetic, root=ROOT):
        self.replica = Replica(replica_path, synthetic)
        self.source_path = Path(source_path)
        self.root = Path(root)

    def proposal(self, operation, payload, expected_version, expected_hash):
        request = request_data(operation, payload)
        if type(expected_version) is not int or expected_version < 0:
            raise Rejected("expected version required")
        hash_id(expected_hash)
        current = self.replica.current(live=operation != "rollback")
        if current["version"] != expected_version or current["snapshot_sha256"] != expected_hash:
            raise Rejected("stale anchored state")
        lesson, result = None, None
        if operation in {"promote", "validate_result"}:
            lesson = self.replica.lesson(read(safe_root(request["lesson_path"])))
            result = result_proof(self.replica, lesson, request["result_path"])
            if result["context"] != request["context"]:
                raise Rejected("result applicability mismatch")
        if operation == "rollback":
            self.replica.prior(current, request["target_hash"])
        data = {
            "operation": operation,
            "request": request,
            "request_hash": digest(request),
            "expected_version": expected_version,
            "expected_hash": expected_hash,
            "synthetic": self.replica.synthetic,
            "closure": closure(self.root),
            "source_inventory": source_inventory(self.source_path),
            "replica_path": str(self.replica.root),
            "context": request["context"],
            "lesson_hash": lesson["lesson_sha256"] if lesson else None,
            "result_hash": digest(result) if result else None,
            "consumer_snapshot_hash": result["snapshot_sha256"] if result else None,
            "authority": "PROPOSAL_ONLY",
            "learning_enabled": False,
        }
        return bind(data, "proposal_hash")

    def coordinator_once(
        self, operation, payload, expected_version, expected_hash, *, host=None, fault=None
    ):
        """Only the authenticated external host may supply production mediation.

        This API does not authenticate arbitrary Python providers. Its output
        remains a receipt for external adjudication; no autonomous activation.
        """
        proposal = self.proposal(operation, payload, expected_version, expected_hash)
        if (
            host is None
            or isinstance(host, dict)
            or not all(
                callable(getattr(host, key, None))
                for key in ["read_anchor", "adjudicate_once", "commit_verified_result"]
            )
        ):
            return {
                "status": "BLOCKED",
                "reason": "external coordinator host binding absent",
                "proposal": proposal,
                "learning_enabled": False,
            }
        anchor = host.read_anchor()
        checked(
            anchor,
            {
                "review",
                "version",
                "hash",
                "explicit_start",
                "synthetic",
                "closure",
                "source_inventory",
                "replica_path",
                "context",
                "lesson_hash",
                "result_hash",
                "consumer_snapshot_hash",
            },
        )
        review = anchor["review"]
        checked(
            review,
            {"provenance", "package_id", "package_version", "package_hash", "purpose", "verdict"},
        )
        if (
            review["verdict"] != "PASS"
            or review["purpose"] != "T018_one_operation"
            or not isinstance(review["provenance"], str)
            or not 1 <= len(review["provenance"].encode()) <= 1024
            or not isinstance(review["package_id"], str)
            or not 1 <= len(review["package_id"].encode()) <= 1024
            or type(review["package_version"]) is not int
            or review["package_version"] < 0
            or anchor["explicit_start"] is not True
        ):
            raise Rejected("external purpose/provenance/start mismatch")
        hash_id(review["package_hash"])
        expected = {
            "version": expected_version,
            "hash": expected_hash,
            **{
                key: proposal[key]
                for key in [
                    "synthetic",
                    "closure",
                    "source_inventory",
                    "replica_path",
                    "context",
                    "lesson_hash",
                    "result_hash",
                    "consumer_snapshot_hash",
                ]
            },
        }
        if any(encoded(anchor[key]) != encoded(value) for key, value in expected.items()):
            raise Rejected("external complete tuple/anchor mismatch")
        grant = host.adjudicate_once(proposal)
        checked(
            grant,
            {
                "grant_id",
                "proposal_hash",
                "operation",
                "request_id",
                "version",
                "hash",
                "anchor_hash",
            },
        )
        identifier(grant["grant_id"])
        if encoded(grant) != encoded(
            {
                "grant_id": grant["grant_id"],
                "proposal_hash": proposal["proposal_hash"],
                "operation": operation,
                "request_id": proposal["request"]["request_id"],
                "version": expected_version,
                "hash": expected_hash,
                "anchor_hash": digest(anchor),
            }
        ):
            raise Rejected("external one-operation grant mismatch")
        with (self.replica.root / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            again = self.proposal(operation, payload, expected_version, expected_hash)
            if again != proposal:
                raise Rejected("proposal/closure/source drift after adjudication")
            current = self.replica.current(live=operation != "rollback")
            self.replica.audit({"intent": grant, "synthetic": self.replica.synthetic})
            if fault == "before_switch":
                raise Rejected("interrupted granted operation; no automatic replay")
            entries = current["entries"]
            if operation == "promote":
                lesson = read(proposal["request"]["lesson_path"])
                entries = [
                    entry
                    for entry in entries
                    if entry["lesson"]["lesson_id"] != lesson["lesson_id"]
                ]
                entries += [
                    {
                        "lesson": lesson,
                        "result_hash": proposal["result_hash"],
                        "grant_id": grant["grant_id"],
                    }
                ]
                entries.sort(key=lambda entry: entry["lesson"]["lesson_id"])
            elif operation == "rollback":
                entries = self.replica.prior(current, proposal["request"]["target_hash"])["entries"]
            if operation in {"promote", "rollback"}:
                new = bind(
                    {
                        "schema_version": "1.0.0",
                        "synthetic": self.replica.synthetic,
                        "version": current["version"] + 1,
                        "previous_version": current["version"],
                        "previous_sha256": current["snapshot_sha256"],
                        "entries": entries,
                    },
                    "snapshot_sha256",
                )
                atomic(self.replica.root / "snapshots" / (new["snapshot_sha256"] + ".json"), new)
                self.replica.load(new["snapshot_sha256"])
                if source_inventory(self.source_path) != proposal["source_inventory"]:
                    raise Rejected("source drift before pointer switch")
                atomic(
                    self.replica.root / "active.json",
                    {"version": new["version"], "sha256": new["snapshot_sha256"]},
                )
                current = new
            if fault == "after_switch":
                raise Rejected(
                    "visible pointer may diverge from external anchor; reconcile explicitly"
                )
            if source_inventory(self.source_path) != proposal["source_inventory"]:
                raise Rejected("source drift; external anchor must not advance")
            knowledge = (
                [
                    entry["lesson"]
                    for entry in entries
                    if proposal["context"] in entry["lesson"]["applicability"]
                ]
                if operation == "retrieve"
                else []
            )
            receipt = {
                "grant_id": grant["grant_id"],
                "proposal_hash": proposal["proposal_hash"],
                "version": current["version"],
                "hash": current["snapshot_sha256"],
                "source_inventory": proposal["source_inventory"],
                "knowledge": knowledge,
                "knowledge_is_untrusted": True,
                "synthetic": self.replica.synthetic,
                "learning_enabled": False,
            }
            self.replica.audit(
                {"visible_receipt": digest(receipt), "synthetic": self.replica.synthetic}
            )
        acknowledgement = host.commit_verified_result(grant, receipt)
        if encoded(acknowledgement) != encoded(
            {
                "grant_id": grant["grant_id"],
                "receipt_hash": digest(receipt),
                "version": receipt["version"],
                "hash": receipt["hash"],
            }
        ):
            raise Rejected("external anchor not advanced; reconcile visible state explicitly")
        return {
            "status": "SIMULATED_RECEIPT"
            if self.replica.synthetic
            else "RECEIPT_FOR_EXTERNAL_ADJUDICATION",
            "receipt": receipt,
            "authority": "external coordinator only",
            "learning_enabled": False,
        }


def main():
    parser = argparse.ArgumentParser(description="No local authority loader or real start")
    parser.add_argument("action", choices=["status"])
    parser.parse_args()
    print(
        json.dumps(
            {
                "status": "OFF",
                "production_host_binding": "BLOCKED",
                "learning_enabled": False,
                "merchant_HTTP": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
