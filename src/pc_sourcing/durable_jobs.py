"""Offline durable sourcing jobs. No network, live access or product decisions.

Cooperating processes use one advisory root lock, SQLite transactions, lease fencing
and fsynced immutable receipt blobs. Hooks inject failures in tests only.
"""

import fcntl
import hashlib
import json
import math
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from pc_sourcing.live_models import canonical_url

SCHEMA = """
BEGIN IMMEDIATE;
CREATE TABLE sources (id TEXT PRIMARY KEY, origin TEXT UNIQUE, budget INTEGER NOT NULL,
 interval REAL NOT NULL, spent INTEGER NOT NULL DEFAULT 0,
 next_at REAL NOT NULL DEFAULT 0, stopped_reason TEXT);
CREATE TABLE jobs (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
 source TEXT NOT NULL REFERENCES sources(id), url TEXT NOT NULL, context TEXT NOT NULL,
 listing_key TEXT NOT NULL, generation INTEGER NOT NULL, input_hash TEXT,
 state TEXT NOT NULL DEFAULT 'ready', token TEXT, lease_until REAL,
 receipt_hash TEXT REFERENCES receipts(hash));
CREATE TABLE receipts (hash TEXT PRIMARY KEY, observed_at REAL NOT NULL);
CREATE TABLE history (listing_key TEXT NOT NULL, receipt_hash TEXT NOT NULL REFERENCES receipts(hash),
 PRIMARY KEY(listing_key, receipt_hash));
CREATE TABLE current (listing_key TEXT PRIMARY KEY, receipt_hash TEXT NOT NULL REFERENCES receipts(hash));
PRAGMA user_version=1;
COMMIT;
"""


class Busy(RuntimeError):
    """Another cooperating process is changing the same runtime root."""


def encoded(value):
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
        )
        + "\n"
    ).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def clock(value):
    value = time.time() if value is None else value
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid runtime timestamp")
    return float(value)


def absolute(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("absolute runtime/output path required")
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError("symlink runtime/output path")
    return path


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_file(path, data, *, partial=lambda: None):
    with path.open("xb") as stream:
        halfway = len(data) // 2
        stream.write(data[:halfway])
        stream.flush()
        os.fsync(stream.fileno())
        partial()
        stream.write(data[halfway:])
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def file_lock(path, *, timeout=0):
    if path.is_symlink():
        raise ValueError("symlink lock")
    with path.open("a") as lock:
        timeout = clock(timeout)
        if timeout > 2:
            raise ValueError("local lock wait is bounded to two seconds")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Busy("runtime/output lock busy") from exc
                time.sleep(min(remaining, 0.01))
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def publish_directory(staging, destination):
    with file_lock(destination.parent / ("." + destination.name + ".publish.lock")):
        if destination.exists() or destination.is_symlink():
            raise ValueError("output already exists")
        os.rename(staging, destination)
        fsync_directory(destination.parent)


def validate_receipt(payload, url=None, now=None):
    if not isinstance(payload, dict) or payload.get("synthetic") is not True:
        raise ValueError("runtime accepts explicitly synthetic fixtures only")
    if payload.get("origin") != "synthetic_fixture" or not isinstance(payload.get("facts"), dict):
        raise ValueError("synthetic receipt origin/facts invalid")
    result = dict(payload)
    result["url"] = canonical_url(payload["url"])
    if url is not None and result["url"] != url:
        raise ValueError("receipt belongs to different listing")
    try:
        stamp = datetime.fromisoformat(payload["observed_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid receipt timestamp") from exc
    if stamp.tzinfo is None or (now is not None and stamp.timestamp() > now):
        raise ValueError("receipt timestamp naive/future")
    result["observed_at"] = stamp.astimezone(UTC).isoformat()
    encoded(result)  # reject non-JSON values and NaN
    return result, stamp.timestamp()


class Store:
    def __init__(self, root, *, hook=lambda name: None, startup_timeout=2):
        self.root = absolute(root)
        self.hook = hook
        self.root.mkdir(parents=True, exist_ok=True)
        self.blobs = self.root / "blobs"
        self.blobs.mkdir(exist_ok=True)
        for name in ("blobs", "jobs.sqlite", ".lock"):
            if (self.root / name).is_symlink():
                raise ValueError("symlink runtime component")
        with file_lock(self.root / ".lock", timeout=startup_timeout), self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if version == 0 and not tables:
                db.executescript(SCHEMA.rsplit("COMMIT;", 1)[0])
                self.hook("schema_pending")
                db.commit()
                created = True
            elif version != 1:
                raise ValueError("unsupported runtime schema")
            else:
                created = False
            self._integrity(db)
        fsync_directory(self.root)
        if created:
            self.hook("schema")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / "jobs.sqlite", isolation_level=None, timeout=0)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with file_lock(self.root / ".lock"), self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def configure_source(self, source, *, limit, interval):
        if not isinstance(source, str) or not source.strip() or len(source) > 200:
            raise ValueError("invalid source id")
        if type(limit) is not int or limit < 1:
            raise ValueError("invalid source budget")
        interval = clock(interval)
        with self.transaction() as db:
            row = db.execute("SELECT * FROM sources WHERE id=?", (source,)).fetchone()
            if row and (row["budget"] != limit or row["interval"] != interval):
                raise ValueError("source configuration immutable; no budget/stop reset")
            db.execute(
                "INSERT OR IGNORE INTO sources(id,budget,interval) VALUES (?,?,?)",
                (source, limit, interval),
            )
            self.hook("source_configuration_pending")
        self.hook("source_configuration")

    def enqueue(self, source, url, context, *, generation=0, input_hash=None):
        url = canonical_url(url)
        if not isinstance(context, dict) or type(generation) is not int or generation < 0:
            raise ValueError("invalid request context/generation")
        if input_hash is not None and (
            not isinstance(input_hash, str)
            or len(input_hash) != 64
            or any(c not in "0123456789abcdef" for c in input_hash)
        ):
            raise ValueError("invalid immutable fixture input hash")
        ctx = encoded(context).decode()
        listing = digest(encoded({"source": source, "url": url, "context": context}))
        job = digest(encoded({"listing": listing, "generation": generation}))
        with self.transaction() as db:
            prior = db.execute("SELECT input_hash FROM jobs WHERE id=?", (job,)).fetchone()
            if prior and input_hash is not None and prior["input_hash"] != input_hash:
                raise ValueError(
                    "job generation input changed; explicit refresh generation required"
                )
            source_row = db.execute("SELECT * FROM sources WHERE id=?", (source,)).fetchone()
            if not source_row:
                raise ValueError("source not configured")
            origin = "https://" + urlsplit(url).netloc
            if source_row["origin"] and source_row["origin"] != origin:
                raise ValueError("source cannot change canonical origin")
            alias = db.execute(
                "SELECT id FROM sources WHERE origin=? AND id!=?", (origin, source)
            ).fetchone()
            if alias:
                raise ValueError("canonical origin already bound; no source alias bypass")
            db.execute("UPDATE sources SET origin=? WHERE id=?", (origin, source))
            db.execute(
                "INSERT OR IGNORE INTO jobs(id,source,url,context,listing_key,generation,input_hash) "
                "VALUES (?,?,?,?,?,?,?)",
                (job, source, url, ctx, listing, generation, input_hash),
            )
            self.hook("enqueue_pending")
        self.hook("enqueue")
        return job

    def claim(self, *, now=None, lease_seconds=60):
        now = clock(now)
        lease_seconds = clock(lease_seconds)
        if not 0 < lease_seconds <= 3600:
            raise ValueError("lease must be finite and between 0 and 3600 seconds")
        with self.transaction() as db:
            row = db.execute(
                """SELECT j.* FROM jobs j JOIN sources s ON s.id=j.source
                WHERE j.state='ready' AND s.stopped_reason IS NULL
                AND (j.receipt_hash IS NOT NULL OR (s.spent<s.budget AND s.next_at<=?))
                AND NOT EXISTS (SELECT 1 FROM jobs active WHERE active.source=j.source
                    AND active.state IN ('claimed','checkpointed')) ORDER BY j.seq LIMIT 1""",
                (now,),
            ).fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            db.execute(
                "UPDATE jobs SET state='claimed',token=?,lease_until=? WHERE id=?",
                (token, now + lease_seconds, row["id"]),
            )
            if row["receipt_hash"] is None:
                db.execute(
                    "UPDATE sources SET spent=spent+1,next_at=?+interval WHERE id=?",
                    (now, row["source"]),
                )
            result = dict(row)
            result.update(
                token=token,
                lease_until=now + lease_seconds,
                context=json.loads(row["context"]),
                receipt=self.receipt(row["receipt_hash"]) if row["receipt_hash"] else None,
            )
            self.hook("claim_pending")
        self.hook("claim")
        return result

    @staticmethod
    def lease(db, job, token, now):
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
        if (
            not row
            or row["state"] not in {"claimed", "checkpointed"}
            or row["token"] != token
            or row["lease_until"] <= now
        ):
            raise ValueError("stale/expired/missing lease")
        return row

    def receipt(self, sha):
        if (
            not isinstance(sha, str)
            or len(sha) != 64
            or any(c not in "0123456789abcdef" for c in sha)
        ):
            raise ValueError("invalid receipt hash")
        path = self.blobs / (sha + ".json")
        if path.is_symlink():
            raise ValueError("symlink receipt")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ValueError("missing receipt evidence") from exc
        if digest(data) != sha:
            raise ValueError("receipt evidence hash mismatch")
        payload = json.loads(data)
        result, _ = validate_receipt(payload)
        if encoded(result) != data:
            raise ValueError("receipt canonical bytes mismatch")
        return result

    def checkpoint(self, job, token, payload, *, now=None):
        now = clock(now)
        with self.transaction() as db:
            row = self.lease(db, job, token, now)
            result, observed = validate_receipt(payload, row["url"], now)
            data = encoded(result)
            sha = digest(data)
            if row["receipt_hash"] and row["receipt_hash"] != sha:
                raise ValueError("job checkpoint immutable")
            path = self.blobs / (sha + ".json")
            if path.exists() or path.is_symlink():
                self.receipt(sha)
            else:
                temp = self.blobs / ("." + uuid.uuid4().hex + ".tmp")
                write_file(temp, data, partial=lambda: self.hook("evidence_partial"))
                self.hook("evidence_temp")
                os.rename(temp, path)
                fsync_directory(self.blobs)
                self.hook("evidence_publish")
            db.execute(
                "INSERT OR IGNORE INTO receipts(hash,observed_at) VALUES (?,?)", (sha, observed)
            )
            db.execute("UPDATE jobs SET receipt_hash=?,state='checkpointed' WHERE id=?", (sha, job))
            self.hook("checkpoint_pending")
        self.hook("checkpoint")

    def finish(self, job, token, *, now=None):
        now = clock(now)
        with self.transaction() as db:
            row = self.lease(db, job, token, now)
            sha = row["receipt_hash"]
            if not sha:
                raise ValueError("receipt checkpoint required before finish")
            self.receipt(sha)
            db.execute(
                "INSERT OR IGNORE INTO history(listing_key,receipt_hash) VALUES (?,?)",
                (row["listing_key"], sha),
            )
            db.execute(
                """INSERT INTO current(listing_key,receipt_hash) VALUES (?,?)
                ON CONFLICT(listing_key) DO UPDATE SET receipt_hash=excluded.receipt_hash
                WHERE (SELECT observed_at FROM receipts WHERE hash=excluded.receipt_hash)>
                      (SELECT observed_at FROM receipts WHERE hash=current.receipt_hash)""",
                (row["listing_key"], sha),
            )
            db.execute(
                "UPDATE jobs SET state='done',token=NULL,lease_until=NULL WHERE id=?", (job,)
            )
            self.hook("finish_pending")
        self.hook("finish")

    def recover(self, *, now=None):
        now = clock(now)
        with self.transaction() as db:
            count = db.execute(
                """UPDATE jobs SET state='ready',token=NULL,lease_until=NULL
                WHERE state IN ('claimed','checkpointed') AND lease_until<=?""",
                (now,),
            ).rowcount
            self.hook("recovery_pending")
        self.hook("recovery")
        return count

    def stop_source(self, job, token, reason, *, now=None):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("stop reason required")
        with self.transaction() as db:
            row = self.lease(db, job, token, clock(now))
            db.execute(
                "UPDATE sources SET stopped_reason=COALESCE(stopped_reason,?) WHERE id=?",
                (reason, row["source"]),
            )
            db.execute(
                "UPDATE jobs SET state='blocked',token=NULL,lease_until=NULL WHERE id=?", (job,)
            )
            self.hook("source_stop_pending")
        self.hook("source_stop")

    def _integrity(self, db):
        expected = {
            "sources": {"id", "origin", "budget", "interval", "spent", "next_at", "stopped_reason"},
            "jobs": {
                "seq",
                "id",
                "source",
                "url",
                "context",
                "listing_key",
                "generation",
                "input_hash",
                "state",
                "token",
                "lease_until",
                "receipt_hash",
            },
            "receipts": {"hash", "observed_at"},
            "history": {"listing_key", "receipt_hash"},
            "current": {"listing_key", "receipt_hash"},
        }
        schema_objects = db.execute(
            "SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger')"
        ).fetchall()
        if {r["name"] for r in schema_objects} != set(expected) | {"sqlite_sequence"} or any(
            r["type"] != "table" for r in schema_objects
        ):
            raise ValueError("unexpected runtime schema object")
        for table, columns in expected.items():
            if {r[1] for r in db.execute(f"PRAGMA table_info({table})")} != columns:
                raise ValueError("unsupported runtime schema layout")
        for row in db.execute("SELECT * FROM sources"):
            if row["budget"] < 1 or row["spent"] < 0 or row["spent"] > row["budget"]:
                raise ValueError("invalid source budget state")
            clock(row["interval"])
            clock(row["next_at"])
        for row in db.execute("SELECT j.*,s.origin FROM jobs j JOIN sources s ON s.id=j.source"):
            if row["state"] not in {"ready", "claimed", "checkpointed", "done", "blocked"}:
                raise ValueError("invalid durable job state")
            active = row["state"] in {"claimed", "checkpointed"}
            if (active and (row["token"] is None or row["lease_until"] is None)) or (
                not active and (row["token"] is not None or row["lease_until"] is not None)
            ):
                raise ValueError("invalid durable lease state")
            if active:
                clock(row["lease_until"])
            if row["state"] in {"checkpointed", "done"} and not row["receipt_hash"]:
                raise ValueError("durable receipt checkpoint missing")
            context = json.loads(row["context"])
            listing = digest(
                encoded({"source": row["source"], "url": row["url"], "context": context})
            )
            if (
                listing != row["listing_key"]
                or digest(encoded({"listing": listing, "generation": row["generation"]}))
                != row["id"]
            ):
                raise ValueError("durable job identity mismatch")
            if row["origin"] != "https://" + urlsplit(row["url"]).netloc:
                raise ValueError("durable source origin mismatch")
        if db.execute(
            "SELECT 1 FROM jobs j LEFT JOIN history h ON j.listing_key=h.listing_key AND j.receipt_hash=h.receipt_hash WHERE j.state='done' AND h.listing_key IS NULL"
        ).fetchone():
            raise ValueError("completed observation history missing")
        if db.execute(
            "SELECT 1 FROM history h WHERE NOT EXISTS (SELECT 1 FROM jobs j WHERE j.state='done' AND j.listing_key=h.listing_key AND j.receipt_hash=h.receipt_hash)"
        ).fetchone():
            raise ValueError("history lacks completed job")
        if db.execute(
            "SELECT 1 FROM history h LEFT JOIN current c ON h.listing_key=c.listing_key WHERE c.listing_key IS NULL"
        ).fetchone():
            raise ValueError("current observation missing")
        if db.execute(
            "SELECT 1 FROM current c JOIN receipts old ON c.receipt_hash=old.hash JOIN history h ON c.listing_key=h.listing_key JOIN receipts newer ON h.receipt_hash=newer.hash WHERE newer.observed_at>old.observed_at"
        ).fetchone():
            raise ValueError("current observation is not newest history")
        if db.execute(
            "SELECT 1 FROM current c LEFT JOIN history h ON c.listing_key=h.listing_key AND c.receipt_hash=h.receipt_hash WHERE h.listing_key IS NULL"
        ).fetchone():
            raise ValueError("current observation lacks history")
        if (
            db.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            or db.execute("PRAGMA foreign_key_check").fetchall()
        ):
            raise ValueError("runtime SQLite integrity failed")
        refs = db.execute("SELECT hash,observed_at FROM receipts").fetchall()
        for row in refs:
            payload = self.receipt(row["hash"])
            if datetime.fromisoformat(payload["observed_at"]).timestamp() != row["observed_at"]:
                raise ValueError("receipt/SQLite timestamp mismatch")
        for row in db.execute("SELECT url,receipt_hash FROM jobs WHERE receipt_hash IS NOT NULL"):
            if self.receipt(row["receipt_hash"])["url"] != row["url"]:
                raise ValueError("job/receipt URL mismatch")
        return {"status": "passed", "referenced_receipts": len(refs)}

    def integrity(self):
        with file_lock(self.root / ".lock"), self.connect() as db:
            return self._integrity(db)

    def report(self):
        with file_lock(self.root / ".lock"), self.connect() as db:
            self._integrity(db)
            result = {
                "synthetic": True,
                "sources": [dict(r) for r in db.execute("SELECT * FROM sources ORDER BY id")],
                "jobs": [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY seq")],
            }
            for table in ("current", "history"):
                result[table] = [
                    {
                        "listing_key": r["listing_key"],
                        "receipt_hash": r["receipt_hash"],
                        "receipt": self.receipt(r["receipt_hash"]),
                    }
                    for r in db.execute(f"SELECT * FROM {table} ORDER BY listing_key,receipt_hash")
                ]
            return result

    def export(self, path):
        path = absolute(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(path.parent / ("." + path.name + ".publish.lock")):
            if path.exists() or path.is_symlink():
                raise ValueError("report already exists")
            temp = path.parent / ("." + uuid.uuid4().hex + ".tmp")
            write_file(temp, encoded(self.report()), partial=lambda: self.hook("report_partial"))
            os.rename(temp, path)
            fsync_directory(path.parent)
        self.hook("report_publication")

    def backup(self, destination):
        destination = absolute(destination)
        if destination.exists():
            raise ValueError("backup already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.parent / ("." + uuid.uuid4().hex + ".backup")
        staging.mkdir()
        (staging / "blobs").mkdir()
        with file_lock(self.root / ".lock"), self.connect() as db:
            self._integrity(db)
            with sqlite3.connect(staging / "jobs.sqlite") as target:
                db.backup(
                    target,
                    pages=1,
                    progress=lambda status, remaining, total: self.hook("backup_sqlite_partial")
                    if remaining
                    else None,
                )
            with (staging / "jobs.sqlite").open("rb") as stream:
                os.fsync(stream.fileno())
            self.hook("backup_sqlite")
            names = ["jobs.sqlite"]
            for row in db.execute("SELECT hash FROM receipts ORDER BY hash"):
                name = "blobs/" + row["hash"] + ".json"
                write_file(
                    staging / name,
                    (self.root / name).read_bytes(),
                    partial=lambda: self.hook("backup_evidence_partial"),
                )
                names.append(name)
            fsync_directory(staging / "blobs")
            self.hook("backup_evidence")
            manifest = {
                "format": "pc-sourcing-runtime-backup-1",
                "files": {name: digest((staging / name).read_bytes()) for name in names},
            }
            write_file(
                staging / "manifest.json",
                encoded(manifest),
                partial=lambda: self.hook("backup_manifest_partial"),
            )
            fsync_directory(staging)
            self.hook("backup_manifest")
        publish_directory(staging, destination)
        self.hook("backup_publication")

    @staticmethod
    def restore(backup, destination, *, hook=lambda name: None):
        backup, destination = absolute(backup), absolute(destination)
        if destination.exists():
            raise ValueError("restore root already exists")
        manifest_path = backup / "manifest.json"
        if manifest_path.is_symlink():
            raise ValueError("symlink manifest")
        manifest = json.loads(manifest_path.read_bytes())
        if manifest.get("format") != "pc-sourcing-runtime-backup-1":
            raise ValueError("unsupported backup")
        files = manifest.get("files", {})
        if not isinstance(files, dict) or "jobs.sqlite" not in files:
            raise ValueError("backup database missing")
        for name, sha in files.items():
            if name != "jobs.sqlite" and not (
                name.startswith("blobs/")
                and len(name) == 75
                and name.endswith(".json")
                and all(c in "0123456789abcdef" for c in name[6:-5])
            ):
                raise ValueError("unsafe backup path")
            path = absolute(backup / name)
            if digest(path.read_bytes()) != sha:
                raise ValueError("backup hash mismatch")
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.parent / ("." + uuid.uuid4().hex + ".restore")
        staging.mkdir()
        (staging / "blobs").mkdir()
        for name in files:
            write_file(
                staging / name,
                (backup / name).read_bytes(),
                partial=lambda: hook("restore_copy_partial"),
            )
        restored = Store(staging)
        with restored.connect() as db:
            referenced = {"jobs.sqlite"} | {
                "blobs/" + r[0] + ".json" for r in db.execute("SELECT hash FROM receipts")
            }
            if referenced != set(files):
                raise ValueError("backup receipt inventory mismatch")
        fsync_directory(staging / "blobs")
        fsync_directory(staging)
        hook("restore_staged")
        publish_directory(staging, destination)
        hook("restore_publication")
        return Store(destination)
