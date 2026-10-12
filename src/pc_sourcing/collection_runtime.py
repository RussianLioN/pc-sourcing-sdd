"""Real-capable retained capture journal, separate from the frozen synthetic Store."""

import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from html import escape
from pathlib import Path

from pc_sourcing.collection_capture import Capture, normalize_capture
from pc_sourcing.durable_jobs import (
    absolute,
    clock,
    digest,
    encoded,
    file_lock,
    fsync_directory,
    publish_directory,
    write_file,
)
from pc_sourcing.normalized_exports import export_bundle

JOURNAL_SCHEMA = "CREATE TABLE jobs(id TEXT PRIMARY KEY, capture_hash TEXT NOT NULL, realm INTEGER NOT NULL, state TEXT NOT NULL, token TEXT, expires REAL, output TEXT, error TEXT);CREATE TABLE events(hash TEXT PRIMARY KEY,data TEXT NOT NULL);CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);"
SOURCE_SCHEMA = "CREATE TABLE budget(id INTEGER PRIMARY KEY CHECK(id=1),cards_reserved INTEGER NOT NULL,http_reserved INTEGER NOT NULL,http_attempted INTEGER NOT NULL,blocked TEXT);CREATE TABLE intents(id TEXT PRIMARY KEY,request TEXT NOT NULL,url TEXT NOT NULL,policy_hash TEXT NOT NULL,realm INTEGER NOT NULL,state TEXT NOT NULL,capture_hash TEXT,error TEXT);"


def schema_fingerprint(db):
    """DDL and SQLite's actual constraints/types/index layouts, not column names alone."""
    objects = [
        (r[0], r[1], r[2], re.sub(r"\s+", " ", r[3]).strip() if r[3] else None)
        for r in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
    ]
    tables = {}
    for kind, name, _table, _sql in objects:
        if kind != "table":
            continue
        # Object names from untrusted state are never interpolated as bare SQL.
        quoted = '"' + name.replace('"', '""') + '"'
        indexes = []
        for row in db.execute("PRAGMA index_list(" + quoted + ")"):
            index = '"' + row[1].replace('"', '""') + '"'
            indexes.append(
                (tuple(row), [tuple(r) for r in db.execute("PRAGMA index_xinfo(" + index + ")")])
            )
        tables[name] = {
            "columns": [tuple(r) for r in db.execute("PRAGMA table_xinfo(" + quoted + ")")],
            "indexes": indexes,
            "foreign_keys": [
                tuple(r) for r in db.execute("PRAGMA foreign_key_list(" + quoted + ")")
            ],
        }
    return digest(
        encoded(
            {
                "objects": objects,
                "tables": tables,
                "version": db.execute("PRAGMA user_version").fetchone()[0],
            }
        )
    )


def require_schema(db, ddl, *, allowed_versions=(1,)):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in allowed_versions:
        raise ValueError("database schema version mismatch")
    with sqlite3.connect(":memory:") as expected:
        expected.executescript(ddl + "PRAGMA user_version=" + str(version) + ";")
        wanted = schema_fingerprint(expected)
    if schema_fingerprint(db) != wanted:
        raise ValueError("database schema fingerprint/constraints/types/indexes mismatch")
    return wanted


class Journal:
    def __init__(self, root):
        self.root = absolute(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.blobs = self.root / "blobs"
        package = Path(__file__).resolve().parent
        self.fingerprint = digest(
            encoded(
                {
                    n: digest((package / n).read_bytes())
                    for n in (
                        "collection_capture.py",
                        "normalized_models.py",
                        "normalized_offers.py",
                        "identity_claims.py",
                        "live_models.py",
                    )
                }
            )
        )
        existing = self.root / "collection.sqlite"
        if existing.is_symlink():
            raise ValueError("symlink collection component")
        if existing.exists():
            with sqlite3.connect(existing.as_uri() + "?mode=ro", uri=True) as db:
                db.row_factory = sqlite3.Row
                self.integrity(db)
        with file_lock(self.root / ".lock", timeout=2):
            if any(
                p.name not in {".lock", "blobs", "collection.sqlite", "collection.sqlite-journal"}
                for p in self.root.iterdir()
            ):
                raise ValueError(
                    "fresh separate collection root required; synthetic runtime is untouched"
                )
            if any(p.is_symlink() for p in self.root.iterdir()):
                raise ValueError("symlink collection component")
            self.blobs.mkdir(exist_ok=True)
            with self.connect() as db:
                objects = db.execute(
                    "SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger')"
                ).fetchall()
                if not objects:
                    db.executescript(
                        "BEGIN IMMEDIATE;" + JOURNAL_SCHEMA + "PRAGMA user_version=1;COMMIT;"
                    )
                    db.execute(
                        "INSERT INTO meta VALUES ('worker_fingerprint',?)", (self.fingerprint,)
                    )
                self.integrity(db)
        fsync_directory(self.root)

    def integrity(self, db):
        require_schema(db, JOURNAL_SCHEMA)
        expected = {
            "jobs": {"id", "capture_hash", "realm", "state", "token", "expires", "output", "error"},
            "events": {"hash", "data"},
            "meta": {"key", "value"},
        }
        objects = db.execute(
            "SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger')"
        ).fetchall()
        if {r["name"] for r in objects} != set(expected) or any(
            r["type"] != "table" for r in objects
        ):
            raise ValueError("unexpected collection schema; no silent WIP migration")
        if (
            db.execute("PRAGMA user_version").fetchone()[0] != 1
            or db.execute("PRAGMA quick_check").fetchone()[0] != "ok"
        ):
            raise ValueError("collection database integrity failure")
        for table, columns in expected.items():
            if {r["name"] for r in db.execute("PRAGMA table_info(" + table + ")")} != columns:
                raise ValueError("collection schema column mismatch")
        meta = db.execute("SELECT value FROM meta WHERE key='worker_fingerprint'").fetchone()
        if meta is None or meta[0] != self.fingerprint:
            raise ValueError(
                "worker fingerprint changed; replay stored captures into a new journal, no refetch"
            )
        realms = set()
        for row in db.execute("SELECT * FROM jobs"):
            capture = self.capture(row["capture_hash"])
            if row["id"] != row["capture_hash"] or row["realm"] != int(capture.synthetic):
                raise ValueError("job capture/realm mismatch")
            realms.add(row["realm"])
            if row["state"] not in {"ready", "claimed", "done", "failed"}:
                raise ValueError("job state invalid")
            active = row["state"] == "claimed"
            if (active and (row["token"] is None or row["expires"] is None)) or (
                not active and (row["token"] is not None or row["expires"] is not None)
            ):
                raise ValueError("job lease state invalid")
            if active:
                clock(row["expires"])
            if row["state"] == "done":
                output = json.loads(row["output"])
                if encoded(output) != encoded(self.derive_output(capture)):
                    raise ValueError("job output differs from bound capture projection")
            elif row["output"] is not None:
                raise ValueError("unfinished job has output")
        if len(realms) > 1:
            raise ValueError("journal realms mixed")
        for event in db.execute("SELECT * FROM events"):
            if digest(event["data"].encode()) != event["hash"]:
                raise ValueError("event integrity mismatch")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / "collection.sqlite", timeout=0, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with file_lock(self.root / ".lock"), self.connect() as db:
            self.integrity(db)
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def capture(self, h):
        if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError("capture hash invalid")
        path = self.blobs / (h + ".json")
        if path.is_symlink() or digest(path.read_bytes()) != h:
            raise ValueError("capture blob integrity mismatch")
        return Capture.model_validate(json.loads(path.read_bytes()))

    def submit(self, captures, events=(), *, hook=lambda phase: None):
        captures = list(captures)
        if len({c.synthetic for c in captures}) > 1:
            raise ValueError("real and synthetic journal batches must be separate")
        prepared = [
            (digest(encoded(c.model_dump(mode="json"))), encoded(c.model_dump(mode="json")), c)
            for c in captures
        ]
        with self.transaction() as db:
            existing = {r[0] for r in db.execute("SELECT DISTINCT realm FROM jobs")}
            if captures and existing and existing != {int(captures[0].synthetic)}:
                raise ValueError("journal realm cannot change")
            for h, blob, c in prepared:
                path = self.blobs / (h + ".json")
                if path.exists():
                    if path.is_symlink() or path.read_bytes() != blob:
                        raise ValueError("immutable capture collision")
                else:
                    temporary = self.blobs / ("." + uuid.uuid4().hex)
                    write_file(temporary, blob)
                    temporary.rename(path)
                    fsync_directory(self.blobs)
                hook("capture_fsynced")
                db.execute(
                    "INSERT OR IGNORE INTO jobs VALUES (?,?,?,'ready',NULL,NULL,NULL,NULL)",
                    (h, h, int(c.synthetic)),
                )
            for event in events:
                raw = encoded(event).decode()
                db.execute("INSERT OR IGNORE INTO events VALUES (?,?)", (digest(raw.encode()), raw))
            hook("submit_pending")
        return [h for h, _blob, _c in prepared]

    @staticmethod
    def derive_output(capture):
        normalized = normalize_capture(capture)
        return {
            "offer": normalized.model_dump(mode="json") if normalized else None,
            "source_status": capture.observation.status,
            "source_match": capture.observation.match,
            "source_reason": capture.observation.reason,
            "provenance": capture.provenance,
            "synthetic": capture.synthetic,
        }

    def work(self, *, now=None, lease=60, hook=lambda phase: None):
        provided_now = now
        now = clock(now)
        lease = clock(lease)
        if not 0 < lease <= 3600:
            raise ValueError("invalid clock/lease")
        with self.transaction() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE state='ready' ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                return {"status": "idle"}
            token = uuid.uuid4().hex
            db.execute(
                "UPDATE jobs SET state='claimed',token=?,expires=? WHERE id=?",
                (token, now + lease, row["id"]),
            )
        hook("claimed")
        capture = self.capture(row["capture_hash"])
        output = self.derive_output(capture)
        hook("normalized")
        finished_at = clock(provided_now)
        with self.transaction() as db:
            active = db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
            if (
                active["state"] != "claimed"
                or active["token"] != token
                or active["expires"] <= finished_at
            ):
                raise ValueError("stale collection worker fence")
            db.execute(
                "UPDATE jobs SET state='done',token=NULL,expires=NULL,output=? WHERE id=?",
                (encoded(output).decode(), row["id"]),
            )
            hook("finish_pending")
        return {"status": "done", "job": row["id"], "source_calls": 0}

    def recover(self, *, now=None):
        now = clock(now)
        with self.transaction() as db:
            count = db.execute(
                "SELECT count(*) FROM jobs WHERE state='claimed' AND expires<=?", (now,)
            ).fetchone()[0]
            db.execute(
                "UPDATE jobs SET state='ready',token=NULL,expires=NULL WHERE state='claimed' AND expires<=?",
                (now,),
            )
        return count

    def status(self):
        with file_lock(self.root / ".lock"), self.connect() as db:
            self.integrity(db)
            jobs = [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY id")]
            for row in jobs:
                row["capture"] = self.capture(row["capture_hash"]).model_dump(mode="json")
                if row["output"]:
                    row["output"] = json.loads(row["output"])
            events = [json.loads(r[0]) for r in db.execute("SELECT data FROM events ORDER BY hash")]
        return {
            "jobs": jobs,
            "events": events,
            "source_calls": 0,
            "mode": "retained_capture_replay"
            if all(j["capture"]["provenance"] == "cached_primary_import" for j in jobs)
            else "captured_primary_pipeline",
            "acquisition_http_requests_recorded": sum(
                e.get("http_requests", 0)
                for e in events
                if e.get("origin") == "t013_acquisition_ledger"
            ),
        }

    def backup(self, destination):
        destination = absolute(destination)
        if destination.exists():
            raise ValueError("fresh backup path required")
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = destination.parent / ("." + uuid.uuid4().hex + ".collection-backup")
        stage.mkdir()
        (stage / "blobs").mkdir()
        with file_lock(self.root / ".lock"), self.connect() as db:
            self.integrity(db)
            with sqlite3.connect(stage / "collection.sqlite") as target:
                db.backup(target)
            for row in db.execute("SELECT DISTINCT capture_hash FROM jobs"):
                self.capture(row[0])
                write_file(
                    stage / "blobs" / (row[0] + ".json"),
                    (self.blobs / (row[0] + ".json")).read_bytes(),
                )
        paths = [p for p in stage.rglob("*") if p.is_file()]
        for p in paths:
            with p.open("rb") as handle:
                os.fsync(handle.fileno())
        write_file(
            stage / "manifest.json",
            encoded(
                {
                    "format": "collection-backup-1",
                    "files": {str(p.relative_to(stage)): digest(p.read_bytes()) for p in paths},
                }
            ),
        )
        fsync_directory(stage / "blobs")
        fsync_directory(stage)
        publish_directory(stage, destination)

    @classmethod
    def restore(cls, backup, destination):
        backup, destination = absolute(backup), absolute(destination)
        manifest = json.loads((backup / "manifest.json").read_bytes())
        if manifest.get(
            "format"
        ) != "collection-backup-1" or "collection.sqlite" not in manifest.get("files", {}):
            raise ValueError("collection backup manifest invalid")
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = destination.parent / ("." + uuid.uuid4().hex + ".collection-restore")
        stage.mkdir()
        for name, h in manifest["files"].items():
            if name != "collection.sqlite" and (
                not name.startswith("blobs/")
                or len(name.split("/")) != 2
                or not name.endswith(".json")
            ):
                raise ValueError("unsafe backup path")
            source = backup / name
            if source.is_symlink() or digest(source.read_bytes()) != h:
                raise ValueError("collection backup hash mismatch")
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            write_file(target, source.read_bytes())
        restored = cls(stage)
        restored.status()
        actual = {"collection.sqlite"} | {
            "blobs/" + j["capture_hash"] + ".json" for j in restored.status()["jobs"]
        }
        if actual != set(manifest["files"]):
            raise ValueError("backup inventory differs from referenced captures")
        fsync_directory(stage / "blobs")
        fsync_directory(stage)
        publish_directory(stage, destination)
        return cls(destination)

    def report(self, destination, as_of):
        from pc_sourcing.normalized_models import NormalizedOffer

        destination = absolute(destination)
        if destination.exists():
            raise ValueError("fresh report directory required")
        state = self.status()
        state["as_of"] = as_of.isoformat()
        for row in state["jobs"]:
            capture = Capture.model_validate(row["capture"])
            row["source_freshness"] = [
                {
                    "field": f.field,
                    "observed_at": f.observed_at.isoformat(),
                    "age_seconds": (as_of - f.observed_at).total_seconds(),
                    "status": "future"
                    if as_of < f.observed_at
                    else "stale"
                    if (as_of - f.observed_at).total_seconds() > 3600
                    else "current",
                }
                for f in capture.observation.facts
            ]
        if any(j["state"] != "done" for j in state["jobs"]):
            raise ValueError("pending captures: work or recover first")
        offers = [
            NormalizedOffer.model_validate(j["output"]["offer"])
            for j in state["jobs"]
            if j["output"]["offer"]
        ]
        stage = destination.parent / ("." + uuid.uuid4().hex + ".collection-report")
        stage.mkdir(parents=True)
        export_bundle(offers, stage / "offers", as_of)
        write_file(stage / "coverage.json", encoded(state))
        lines = [
            "# Источники и ограничения",
            "",
            "Режим: " + state["mode"] + ". Origin и исходные даты каждого capture сохранены.",
            "",
            f"Наблюдений: {len(state['jobs'])}; записанных HTTP acquisition: {state['acquisition_http_requests_recorded']}; новых запросов при построении отчёта: 0.",
        ]
        for j in state["jobs"]:
            o = j["output"]
            lines.append(
                f"- {j['id']}: {o['source_status']} / {o['source_match']}; {o['provenance']}; {o['source_reason']}"
            )
            observation = j["capture"]["observation"]
            lines.append(
                "  URL: "
                + escape(observation["candidate"]["url"])
                + "; исходный title: "
                + escape(observation.get("title") or "unknown")
                + "; MPN: "
                + escape(observation.get("mpn") or "unknown")
            )
            lines.append(
                "  Отличия/неопределённость: "
                + escape(json.dumps(observation["differences"], ensure_ascii=False))
            )
            for f in observation["facts"]:
                lines.append(
                    "  Факт "
                    + escape(f["field"])
                    + ": "
                    + escape(str(f["value"]))
                    + "; исходная дата "
                    + f["observed_at"]
                    + ". Отображённая цена не означает безусловную полную цену."
                )
        lines.append("")
        lines.append(
            "Срез отчёта: "
            + as_of.isoformat()
            + ". Исходные даты не обновлены; replay не подтверждает текущую цену."
        )
        lines.extend("- " + json.dumps(e, ensure_ascii=False) for e in state["events"])
        write_file(stage / "coverage.md", ("\n".join(lines) + "\n").encode())
        files = {
            str(p.relative_to(stage)): digest(p.read_bytes())
            for p in stage.rglob("*")
            if p.is_file()
        }
        write_file(
            stage / "manifest.json", encoded({"format": "collection-report-1", "files": files})
        )
        fsync_directory(stage)
        publish_directory(stage, destination)
        return {
            "status": "reported",
            "offers": len(offers),
            "captures": len(state["jobs"]),
            "source_calls": 0,
        }
