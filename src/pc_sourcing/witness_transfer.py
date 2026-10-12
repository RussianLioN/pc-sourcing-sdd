"""Complete minimized old/new source-state transfer; never overwrite/reset state."""

import json
import sqlite3
import uuid
from contextlib import ExitStack
from pathlib import Path

from pc_sourcing.collection_state import allowed as old_allowed
from pc_sourcing.collection_state import validate_state
from pc_sourcing.durable_jobs import (
    absolute,
    digest,
    encoded,
    file_lock,
    fsync_directory,
    publish_directory,
    write_file,
)
from pc_sourcing.product_extraction import unique_members
from pc_sourcing.witness_controller import Controller, shared_baseline
from pc_sourcing.witness_profiles import PROFILES


def allowed(name):
    p = Path(name)
    if p.is_absolute() or ".." in p.parts:
        return False
    if old_allowed(name):
        return len(p.parts) == 1 or p.name[len(p.name.split(".")[0]) :] in {
            ".json",
            ".metadata.json",
            ".selected.json",
        }
    if len(p.parts) == 1:
        return any(
            name in {k + "-witness.sqlite", "." + k + "-witness.initialized"}
            or name.startswith(k + "-stop.json")
            and name.endswith(".json")
            for k in PROFILES
        )
    return (
        len(p.parts) == 2
        and p.parts[0] in {k + "-witness-captures" for k in PROFILES}
        and p.name.endswith(".json")
        and len(p.name.split(".")[0]) == 64
        and all(c in "0123456789abcdef" for c in p.name.split(".")[0])
        and p.name[len(p.name.split(".")[0]) :] in {".json", ".metadata.json", ".selected.json"}
    )


def validate(root):
    root = absolute(root)
    if any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("symlink source snapshot")
    locks = {"." + k + "-witness.lock" for k in PROFILES} | {
        ".28bit-acquisition.lock",
        ".regard-acquisition.lock",
    }
    for p in root.rglob("*"):
        if (
            p.is_file()
            and p.name != "manifest.json"
            and not allowed(str(p.relative_to(root)))
            and str(p.relative_to(root)) not in locks
        ):
            raise ValueError(
                "unknown source file cannot be silently omitted from constraint snapshot"
            )
    validate_state(root)
    live = False
    for key, profile in PROFILES.items():
        dbpath = root / (key + "-witness.sqlite")
        marker = root / ("." + key + "-witness.initialized")
        caps = root / (key + "-witness-captures")
        if dbpath.exists() != marker.exists() or caps.exists() and not dbpath.exists():
            raise ValueError("incomplete source ledger/marker/checkpoint state")
        if not dbpath.exists():
            continue
        m = json.loads(marker.read_bytes(), object_pairs_hook=unique_members)
        if type(m.get("realm")) is not int or m["realm"] not in (0, 1):
            raise ValueError("source snapshot realm invalid")
        c = object.__new__(Controller)
        c.key = key
        c.profile = profile
        c.state_dir = root
        c.dbpath = dbpath
        c.marker = marker
        c.captures = caps
        c.synthetic = bool(m["realm"])
        with c.connection(readonly=True) as db:
            c.integrity(db)
        live = live or not c.synthetic
    if live or (root / "28bit-acquisition.sqlite").exists():
        shared_baseline(root)
    return {
        "status": "PASS",
        "live_baseline_included": live or (root / "28bit-acquisition.sqlite").exists(),
    }


def backup(source, destination):
    source, destination = absolute(source), absolute(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("fresh snapshot destination required")
    validate(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / ("." + uuid.uuid4().hex + ".witness-backup")
    stage.mkdir()
    with ExitStack() as locks:
        locks.enter_context(
            file_lock(source.parent / ("." + source.name + ".witness-transfer.lock"))
        )
        for key in sorted({"28bit", "regard"} | set(PROFILES)):
            if key in PROFILES and not (source / (key + "-witness.sqlite")).exists():
                continue
            locks.enter_context(
                file_lock(
                    source / ("." + key + "-witness.lock")
                    if key in PROFILES
                    else source / ("." + key + "-acquisition.lock")
                )
            )
        validate(source)
        for p in source.rglob("*"):
            name = str(p.relative_to(source))
            if not p.is_file() or not allowed(name):
                continue
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if p.suffix == ".sqlite":
                with (
                    sqlite3.connect(p.as_uri() + "?mode=ro", uri=True) as db,
                    sqlite3.connect(target) as out,
                ):
                    db.backup(out)
            else:
                write_file(target, p.read_bytes())
    validate(stage)
    files = {
        str(p.relative_to(stage)): digest(p.read_bytes()) for p in stage.rglob("*") if p.is_file()
    }
    write_file(stage / "manifest.json", encoded({"format": "witness-source-1", "files": files}))
    for p in stage.rglob("*"):
        if p.is_dir():
            fsync_directory(p)
        elif p.is_file():
            with p.open("rb") as f:
                __import__("os").fsync(f.fileno())
    fsync_directory(stage)
    publish_directory(stage, destination)


def restore(snapshot, destination):
    snapshot, destination = absolute(snapshot), absolute(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("existing source state cannot be overwritten/reset")
    value = json.loads((snapshot / "manifest.json").read_bytes(), object_pairs_hook=unique_members)
    if value.get("format") != "witness-source-1" or not isinstance(value.get("files"), dict):
        raise ValueError("source manifest invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / ("." + uuid.uuid4().hex + ".witness-restore")
    stage.mkdir()
    for name, h in value["files"].items():
        if not allowed(name):
            raise ValueError("unsafe source snapshot path")
        p = snapshot / name
        if p.is_symlink() or digest(p.read_bytes()) != h:
            raise ValueError("source snapshot hash mismatch")
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_file(target, p.read_bytes())
    validate(stage)
    for p in stage.rglob("*"):
        if p.is_dir():
            fsync_directory(p)
    fsync_directory(stage)
    publish_directory(stage, destination)
