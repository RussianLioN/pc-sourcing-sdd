"""Inactive reviewed-knowledge MVP. Only isolated synthetic snapshots can switch."""

import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_DOCUMENT = 1_000_000


class Rejected(ValueError):
    pass


def pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise Rejected("duplicate JSON key")
        result[key] = value
    return result


def read(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > MAX_DOCUMENT:
        raise Rejected("symlink or oversized document")
    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=bad_constant)


def bad_constant(_value):
    raise Rejected("nonfinite JSON value")


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def projection(value, self_field):
    return {key: val for key, val in value.items() if key != self_field}


def bind(value, self_field):
    result = dict(value)
    result[self_field] = digest(projection(result, self_field))
    return result


def hash_id(value, kind="sha256"):
    length = 40 if kind == "git" else 64
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{" + str(length) + "}", value):
        raise Rejected("invalid " + kind + " identifier")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", value):
        raise Rejected("invalid bounded identifier")


def checked(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise Rejected("unknown/missing fields")


def bound_document(value):
    if len(encoded(value)) > MAX_DOCUMENT:
        raise Rejected("oversized document")


def safe_root(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
        raise Rejected("absolute canonical nonsymlink path required")
    if any(part in {".agents", ".specify", "source-state"} for part in path.parts):
        raise Rejected("instruction/source state path forbidden")
    return path


def atomic(path, value):
    path = Path(path)
    if path.is_symlink():
        raise Rejected("symlink output")
    data = encoded(value)
    bound_document(value)
    temp = path.with_name(path.name + ".pending")
    with temp.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


LESSON_FIELDS = {
    "schema_version",
    "incident_ids",
    "incident_sha256s",
    "lesson_id",
    "version",
    "applicability",
    "knowledge_text",
    "evidence",
    "code_sha",
    "spec_sha256",
    "oracle_sha256",
    "test_set_sha256",
    "synthetic",
    "lesson_sha256",
}


def validate_lesson(value, *, verify_evidence=True):
    checked(value, LESSON_FIELDS)
    if value["schema_version"] != "1.0.0" or type(value["synthetic"]) is not bool:
        raise Rejected("schema/synthetic label")
    identifier(value["lesson_id"])
    if not isinstance(value["incident_ids"], list) or not value["incident_ids"]:
        raise Rejected("incident lineage required")
    for incident in value["incident_ids"]:
        identifier(incident)
    if len(set(value["incident_ids"])) != len(value["incident_ids"]):
        raise Rejected("duplicate incident lineage")
    checked(value["incident_sha256s"], value["incident_ids"])
    for value_hash in value["incident_sha256s"].values():
        hash_id(value_hash)
    if type(value["version"]) is not int or value["version"] < 1:
        raise Rejected("invalid version")
    if (
        not isinstance(value["knowledge_text"], str)
        or len(value["knowledge_text"].encode()) > 65536
    ):
        raise Rejected("knowledge text bound")
    if not isinstance(value["applicability"], list) or not value["applicability"]:
        raise Rejected("explicit applicability required")
    for item in value["applicability"]:
        identifier(item)
    hash_id(value["code_sha"], "git")
    for key in ["spec_sha256", "oracle_sha256", "test_set_sha256", "lesson_sha256"]:
        hash_id(value[key])
    if value["lesson_sha256"] != digest(projection(value, "lesson_sha256")):
        raise Rejected("lesson canonical hash mismatch")
    if not isinstance(value["evidence"], list) or not value["evidence"]:
        raise Rejected("evidence required")
    for evidence in value["evidence"]:
        checked(evidence, {"path", "sha256"})
        path = safe_root(evidence["path"])
        hash_id(evidence["sha256"])
        if verify_evidence and (
            not path.is_file()
            or path.stat().st_size > MAX_DOCUMENT
            or hashlib.sha256(path.read_bytes()).hexdigest() != evidence["sha256"]
        ):
            raise Rejected("evidence missing or changed")
    bound_document(value)
    return value


def review_binding(lesson, outcome_sha256):
    hash_id(outcome_sha256)
    return {
        key: lesson[key]
        for key in [
            "lesson_sha256",
            "code_sha",
            "spec_sha256",
            "oracle_sha256",
            "test_set_sha256",
            "synthetic",
        ]
    } | {"consumer_outcome_sha256": outcome_sha256}


class ExternalAuthority:
    """No writer-local receipt can establish a real coordinator trust boundary."""

    def verify(self, _lesson, _approval):
        raise Rejected("BLOCKED: external coordinator authority/isolation not configured")


class SyntheticAuthority:
    """Explicit test fixture only; never authorizes real lessons or real state."""

    def __init__(self, registry):
        self.registry = dict(registry)

    def verify(self, lesson, approval):
        if lesson["synthetic"] is not True:
            raise Rejected("synthetic authority cannot approve real lesson")
        checked(approval, {"review_id", "binding", "verdict", "synthetic"})
        identifier(approval["review_id"])
        if approval["synthetic"] is not True or approval["verdict"] != "PASS":
            raise Rejected("synthetic exact PASS required")
        if approval != self.registry.get(approval["review_id"]):
            raise Rejected("unregistered writer-local approval")
        expected = review_binding(lesson, approval["binding"]["consumer_outcome_sha256"])
        if approval["binding"] != expected:
            raise Rejected("approval exact hash binding mismatch")


def validate_incident(value):
    checked(
        value,
        {
            "incident_id",
            "root_cause",
            "observed_at",
            "affected_commit",
            "evidence",
            "synthetic",
        },
    )
    identifier(value["incident_id"])
    identifier(value["root_cause"])
    hash_id(value["affected_commit"], "git")
    if value["synthetic"] is not True or not value["evidence"]:
        raise Rejected("isolated synthetic incident evidence required")
    from datetime import UTC, datetime

    at = datetime.fromisoformat(value["observed_at"].replace("Z", "+00:00"))
    if at.utcoffset() != UTC.utcoffset(at):
        raise Rejected("UTC incident observation required")
    bound_document(value)
    return value


class SyntheticStore:
    """All write operations are explicitly synthetic and unrelated to source state."""

    def __init__(self, path, authority):
        if not isinstance(authority, SyntheticAuthority):
            raise Rejected("real activation disabled; fixture authority required")
        self.root = safe_root(path)
        self.authority = authority

    def bootstrap(self):
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / "candidates").mkdir()
        (self.root / "incidents").mkdir()
        (self.root / "snapshots").mkdir()
        self._snapshot(0, None, None, [])

    def _snapshot(self, version, previous_version, previous_hash, entries, fault=None):
        snapshot = bind(
            {
                "schema_version": "1.0.0",
                "synthetic": True,
                "version": version,
                "previous_version": previous_version,
                "previous_sha256": previous_hash,
                "entries": entries,
            },
            "snapshot_sha256",
        )
        self.validate_snapshot(snapshot, snapshot["snapshot_sha256"])
        snap_path = self.root / "snapshots" / (snapshot["snapshot_sha256"] + ".json")
        atomic(snap_path, snapshot)
        if fault == "before_switch":
            raise Rejected("interrupted preparation; old pointer retained")
        atomic(
            self.root / "active.json", {"version": version, "sha256": snapshot["snapshot_sha256"]}
        )
        if fault == "after_switch":
            raise Rejected("interrupted after switch; visible immutable snapshot retained")
        return snapshot

    def validate_snapshot(self, snapshot, expected_hash, *, validate_entries=True):
        checked(
            snapshot,
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
        hash_id(expected_hash)
        if (
            snapshot["schema_version"] != "1.0.0"
            or snapshot["synthetic"] is not True
            or type(snapshot["version"]) is not int
            or snapshot["version"] < 0
            or snapshot["snapshot_sha256"] != expected_hash
            or digest(projection(snapshot, "snapshot_sha256")) != expected_hash
        ):
            raise Rejected("inconsistent snapshot schema/hash/version")
        if not isinstance(snapshot["entries"], list) or len(snapshot["entries"]) > 32:
            raise Rejected("snapshot corpus bound")
        if snapshot["version"] == 0:
            if (
                snapshot["previous_version"] is not None
                or snapshot["previous_sha256"] is not None
                or snapshot["entries"]
            ):
                raise Rejected("initial snapshot must be the empty bootstrap")
        else:
            if (
                type(snapshot["previous_version"]) is not int
                or snapshot["previous_version"] != snapshot["version"] - 1
            ):
                raise Rejected("snapshot previous version lineage mismatch")
            hash_id(snapshot["previous_sha256"])
        seen = set()
        for entry in snapshot["entries"]:
            checked(entry, {"lesson", "approval"})
            lesson = validate_lesson(entry["lesson"], verify_evidence=validate_entries)
            if validate_entries:
                self.lineage(lesson)
            self.authority.verify(lesson, entry["approval"])
            if lesson["lesson_id"] in seen:
                raise Rejected("duplicate active lesson")
            seen.add(lesson["lesson_id"])
        return snapshot

    def load_snapshot(self, expected_hash, *, validate_entries=True):
        hash_id(expected_hash)
        value = read(safe_root(self.root / "snapshots" / (expected_hash + ".json")))
        return self.validate_snapshot(value, expected_hash, validate_entries=validate_entries)

    def snapshot(self, *, validate_entries=True):
        safe_root(self.root)
        pointer = read(self.root / "active.json")
        checked(pointer, {"version", "sha256"})
        if type(pointer["version"]) is not int or pointer["version"] < 0:
            raise Rejected("invalid pointer version")
        snapshot = self.load_snapshot(pointer["sha256"], validate_entries=validate_entries)
        if snapshot["version"] != pointer["version"]:
            raise Rejected("pointer/snapshot version mismatch")
        return snapshot

    def rollback_target(self, current, expected_hash):
        previous = self.load_snapshot(expected_hash)
        if previous["version"] >= current["version"]:
            raise Rejected("rollback must target a prior visible version")
        node, found = current, False
        for _ in range(512):
            if node["snapshot_sha256"] == expected_hash:
                found = True
            if node["version"] == 0:
                break
            parent = self.load_snapshot(node["previous_sha256"], validate_entries=False)
            if parent["version"] != node["previous_version"]:
                raise Rejected("visible snapshot lineage version mismatch")
            node = parent
        else:
            raise Rejected("snapshot lineage exceeds bound")
        if not found:
            raise Rejected("rollback target was never in visible snapshot lineage")
        return previous

    def incident(self, value):
        validate_incident(value)
        path = self.root / "incidents" / (value["incident_id"] + ".json")
        if path.exists():
            raise Rejected("immutable incident exists")
        atomic(path, value)
        self.audit("incident", digest(value))
        return path

    def lineage(self, lesson):
        for incident_id in lesson["incident_ids"]:
            record = validate_incident(read(self.root / "incidents" / (incident_id + ".json")))
            if (
                record["incident_id"] != incident_id
                or digest(record) != lesson["incident_sha256s"][incident_id]
                or record["affected_commit"] != lesson["code_sha"]
                or not set(record["evidence"]) <= {e["path"] for e in lesson["evidence"]}
            ):
                raise Rejected("incident-to-candidate lineage/hash mismatch")

    def candidate(self, lesson):
        validate_lesson(lesson)
        self.lineage(lesson)
        if lesson["synthetic"] is not True:
            raise Rejected("fixture cannot store real lesson")
        if len(list((self.root / "candidates").glob("*.json"))) >= 32:
            raise Rejected("candidate corpus limit")
        path = self.root / "candidates" / (lesson["lesson_sha256"] + ".json")
        with path.open("xb") as handle:
            handle.write(encoded(lesson))
        self.audit("candidate", lesson["lesson_sha256"])
        return path

    def audit(self, action, subject):
        # Audit exists before visibility switch; interruption leaves intent evidence.
        path = self.root / "audit.jsonl"
        if path.is_symlink():
            raise Rejected("symlink audit")
        with path.open("ab") as handle:
            handle.write(encoded({"action": action, "subject": subject, "synthetic": True}) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    def switch(
        self,
        expected_version,
        expected_hash,
        *,
        lesson=None,
        approval=None,
        rollback=None,
        fault=None,
    ):
        if type(expected_version) is not int or expected_version < 0:
            raise Rejected("typed expected version required")
        hash_id(expected_hash)
        with (self.root / "lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            current = self.snapshot(validate_entries=rollback is None)
            if (
                current["version"] != expected_version
                or current["snapshot_sha256"] != expected_hash
            ):
                raise Rejected("stale compare-and-switch")
            if rollback is not None:
                hash_id(rollback)
                previous = self.rollback_target(current, rollback)
                entries = previous["entries"]
            else:
                validate_lesson(lesson)
                candidate_path = self.root / "candidates" / (lesson["lesson_sha256"] + ".json")
                if not candidate_path.is_file():
                    raise Rejected("quarantined candidate required")
                persisted = validate_lesson(read(candidate_path))
                if encoded(persisted) != encoded(lesson):
                    raise Rejected("quarantine payload does not match reviewed candidate")
                self.lineage(persisted)
                try:
                    self.authority.verify(lesson, approval)
                except Rejected:
                    self.audit("promotion_rejected", lesson["lesson_sha256"])
                    raise
                self.audit("reviewed_fixture", lesson["lesson_sha256"])
                entries = [
                    entry
                    for entry in current["entries"]
                    if entry["lesson"]["lesson_id"] != lesson["lesson_id"]
                ]
                entries.append({"lesson": lesson, "approval": approval})
                entries.sort(key=lambda entry: entry["lesson"]["lesson_id"])
            self.audit("rollback_intent" if rollback else "promotion_intent", expected_hash)
            return self._snapshot(
                current["version"] + 1, current["version"], expected_hash, entries, fault
            )

    def search(self, context):
        identifier(context)
        snapshot = self.snapshot()
        result = []
        for entry in snapshot["entries"]:
            lesson = validate_lesson(entry["lesson"])
            self.authority.verify(lesson, entry["approval"])
            if context in lesson["applicability"]:
                result.append(lesson)
        return {
            "synthetic": True,
            "version": snapshot["version"],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "lessons": result,
            "authority": "synthetic isolated fixture; real learning OFF",
        }


def main():
    parser = argparse.ArgumentParser(description="Real reviewed learning remains OFF")
    parser.add_argument("action", choices=["status", "promote", "search", "rollback"])
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "status": "BLOCKED" if args.action != "status" else "OFF",
                "reason": "real external coordinator authority not configured",
                "real_learning_enabled": False,
                "merchant_HTTP": 0,
            }
        )
    )
    return 0 if args.action == "status" else 2


if __name__ == "__main__":
    raise SystemExit(main())
