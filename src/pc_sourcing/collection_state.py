"""Hash-verified source-state transfer. Fresh destination only; never reset stops/budgets."""

import json
import sqlite3
import uuid
from contextlib import ExitStack
from pathlib import Path

from pc_sourcing.collection_runtime import SOURCE_SCHEMA, require_schema
from pc_sourcing.durable_jobs import (
    absolute,
    digest,
    encoded,
    file_lock,
    fsync_directory,
    publish_directory,
    write_file,
)

KEYS = {"28bit", "regard"}


def allowed(name):
    p = Path(name)
    if p.is_absolute() or ".." in p.parts:
        return False
    if len(p.parts) == 1:
        return (
            name in {"tavily-stop.json", "tavily-stop.json.lock"}
            or any(name.startswith(k + "-stop.json") and name.endswith(".json") for k in KEYS)
            or name in {k + "-acquisition.sqlite" for k in KEYS}
            or name in {"." + k + "-acquisition.initialized" for k in KEYS}
        )
    return (
        len(p.parts) == 2
        and p.parts[0] in {k + "-acquisition-captures" for k in KEYS}
        and p.name.endswith(".json")
        and len(p.name.split(".")[0]) == 64
        and all(c in "0123456789abcdef" for c in p.name.split(".")[0])
    )


def validate_state(root):
    root = absolute(root)
    for p in root.rglob("*"):
        if p.is_symlink():
            raise ValueError("symlink source state")
    for k in KEYS:
        dbpath = root / (k + "-acquisition.sqlite")
        marker = root / ("." + k + "-acquisition.initialized")
        if marker.exists() != dbpath.exists():
            raise ValueError("source marker/ledger incomplete; no reset")
        if not dbpath.exists():
            continue
        with sqlite3.connect(dbpath.as_uri() + "?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            require_schema(db, SOURCE_SCHEMA, allowed_versions=(0, 1))
            objects = db.execute(
                "SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger')"
            ).fetchall()
            if {r["name"] for r in objects} != {"budget", "intents"} or any(
                r["type"] != "table" for r in objects
            ):
                raise ValueError("invalid source snapshot schema")
            rows = db.execute("SELECT * FROM budget").fetchall()
            if len(rows) != 1:
                raise ValueError("source budget missing/duplicate")
            b = rows[0]
            if (
                b["cards_reserved"] not in (0, 1)
                or b["http_reserved"] != 2 * b["cards_reserved"]
                or not 0 <= b["http_attempted"] <= b["http_reserved"]
            ):
                raise ValueError("source snapshot budget invariant")
            intents = db.execute("SELECT * FROM intents").fetchall()
            if len(intents) != b["cards_reserved"]:
                raise ValueError("source snapshot intent mismatch")
            for i in intents:
                if i["capture_hash"]:
                    h = i["capture_hash"]
                    p = root / (k + "-acquisition-captures") / (h + ".json")
                    if not allowed(str(p.relative_to(root))) or digest(p.read_bytes()) != h:
                        raise ValueError("source capture hash mismatch")
                    from pc_sourcing.collection_capture import Capture

                    c = Capture.model_validate(json.loads(p.read_bytes()))
                    if int(c.synthetic) != i["realm"]:
                        raise ValueError("source snapshot realm mismatch")
                    metadata = json.loads(p.with_name(h + ".metadata.json").read_bytes())
                    selected = p.with_name(h + ".selected.json").read_bytes()
                    if selected != c.observation.primary[
                        "retained_content"
                    ].encode() or c.artifact_sha256 != digest(
                        encoded(
                            {
                                "http_receipts": metadata["http_receipts"],
                                "selected_sha256": digest(selected),
                            }
                        )
                    ):
                        raise ValueError("source selected/audit mismatch")


def backup_state(source, destination):
    source, destination = absolute(source), absolute(destination)
    if destination.exists():
        raise ValueError("fresh source snapshot destination required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / ("." + uuid.uuid4().hex + ".source-snapshot")
    stage.mkdir()
    with ExitStack() as locks:
        for k in sorted(KEYS):
            locks.enter_context(file_lock(source / ("." + k + "-acquisition.lock")))
        validate_state(source)
        for p in source.rglob("*"):
            if not p.is_file() or not allowed(str(p.relative_to(source))):
                continue
            target = stage / p.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if p.suffix == ".sqlite":
                with sqlite3.connect(p) as db, sqlite3.connect(target) as out:
                    db.backup(out)
            else:
                write_file(target, p.read_bytes())
    validate_state(stage)
    files = {
        str(p.relative_to(stage)): digest(p.read_bytes()) for p in stage.rglob("*") if p.is_file()
    }
    write_file(stage / "manifest.json", encoded({"format": "source-state-1", "files": files}))
    for p in stage.rglob("*"):
        if p.is_dir():
            fsync_directory(p)
        elif p.is_file():
            with p.open("rb") as f:
                __import__("os").fsync(f.fileno())
    fsync_directory(stage)
    publish_directory(stage, destination)


def restore_state(snapshot, destination):
    snapshot, destination = absolute(snapshot), absolute(destination)
    if destination.exists():
        raise ValueError("existing source-state cannot be overwritten/reset")
    manifest = json.loads((snapshot / "manifest.json").read_bytes())
    if manifest.get("format") != "source-state-1" or not isinstance(manifest.get("files"), dict):
        raise ValueError("source snapshot manifest invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / ("." + uuid.uuid4().hex + ".source-restore")
    stage.mkdir()
    for name, h in manifest["files"].items():
        if not allowed(name):
            raise ValueError("unsafe source snapshot path")
        p = snapshot / name
        if p.is_symlink() or digest(p.read_bytes()) != h:
            raise ValueError("source snapshot hash mismatch")
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_file(target, p.read_bytes())
    validate_state(stage)
    for p in stage.rglob("*"):
        if p.is_dir():
            fsync_directory(p)
    fsync_directory(stage)
    publish_directory(stage, destination)
