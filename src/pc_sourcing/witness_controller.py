"""Durable bounded acquisition retaining exact T015 safe witnesses. No implicit reset."""

import json
import multiprocessing
import os
import selectors
import socket
import sqlite3
import struct
import threading
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pc_sourcing.collection_capture import Capture
from pc_sourcing.collection_runtime import require_schema
from pc_sourcing.collection_state import validate_state
from pc_sourcing.curated_primary import NoRedirect, RobotsRules
from pc_sourcing.durable_jobs import (
    absolute,
    digest,
    encoded,
    file_lock,
    fsync_directory,
    write_file,
)
from pc_sourcing.live_models import Candidate, Request
from pc_sourcing.live_transport import DENIAL_MARKERS, AccessBlocked, public_address
from pc_sourcing.product_extraction import extract_card, unique_members
from pc_sourcing.witness_profiles import PROFILES, ROOT, release_gate

SCHEMA = "CREATE TABLE budget(id INTEGER PRIMARY KEY CHECK(id=1),cards_reserved INTEGER NOT NULL,http_reserved INTEGER NOT NULL,http_attempted INTEGER NOT NULL,blocked TEXT);CREATE TABLE intents(id TEXT PRIMARY KEY,request TEXT NOT NULL,url TEXT NOT NULL,state TEXT NOT NULL,capture_hash TEXT,error TEXT);CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);"


class SourceFailure(AccessBlocked):
    def __init__(self, reason, *, status=None, retry_after=None):
        super().__init__(reason)
        self.status = status
        self.retry_after = retry_after


def shared_baseline(root):
    if not root.is_dir() or root.is_symlink():
        raise AccessBlocked("complete shared T013 source state required")
    required = [
        "tavily-stop.json",
        "28bit-stop.json",
        "28bit-acquisition.sqlite",
        "regard-acquisition.sqlite",
        ".28bit-acquisition.initialized",
        ".regard-acquisition.initialized",
    ]
    if any(not (root / n).is_file() for n in required):
        raise AccessBlocked("shared source baseline missing; restore, no reset")
    if (
        json.loads((root / "tavily-stop.json").read_bytes(), object_pairs_hook=unique_members).get(
            "endpoint"
        )
        != "https://api.tavily.com/search"
    ):
        raise AccessBlocked("shared stop provenance invalid")
    validate_state(root)


def read_profile_body(response, *, byte_limit, deadline, clock=time.monotonic):
    """Read only remaining decoded-body allowance; never fetch an overflow byte."""
    if type(byte_limit) is not int or byte_limit <= 0:
        raise AccessBlocked("invalid profile byte limit")
    header = response.headers.get("content-length")
    declared = None
    if header is not None:
        if not isinstance(header, str) or not header.isdigit():
            raise AccessBlocked("ambiguous content length")
        declared = int(header)
        if declared > byte_limit:
            raise AccessBlocked("profile byte limit exceeded by declared length")
    size, parts = 0, []
    while True:
        if clock() >= deadline:
            raise AccessBlocked("profile total deadline exceeded")
        if declared == size and not getattr(response, "chunked", False):
            return b"".join(parts)
        if size == byte_limit:
            if response.isclosed() or declared == size and not getattr(response, "chunked", False):
                return b"".join(parts)
            raise AccessBlocked("profile byte limit reached without proven EOF")
        remaining = byte_limit - size
        if declared is not None:
            remaining = min(remaining, declared - size)
        part = response.read1(min(65536, remaining))
        if clock() >= deadline:
            raise AccessBlocked("profile total deadline exceeded during chunk")
        if not isinstance(part, bytes) or len(part) > min(65536, remaining):
            raise AccessBlocked("response violated bounded read protocol")
        if not part:
            if declared is not None and size != declared:
                raise AccessBlocked("truncated declared response body")
            return b"".join(parts)
        parts.append(part)
        size += len(part)


def _request_with_profile_limits(profile, url, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise AccessBlocked("profile total deadline exceeded before request")
    dns_status = "public_precheck_only_not_binding"
    try:
        public_address(urlsplit(url).hostname)
    except socket.gaierror:
        dns_status = "unknown_local_resolver_unavailable"
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise AccessBlocked("profile total deadline exceeded during resolver")
    request = urllib.request.Request(
        url, headers={"User-Agent": "PC-Sourcing-Research/1.0", "Accept-Encoding": "identity"}
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=remaining) as response:
            if time.monotonic() >= deadline:
                raise AccessBlocked("profile total deadline exceeded during headers")
            raw_headers = {k.lower(): v for k, v in response.headers.items()}
            if (
                response.status != 200
                or response.geturl() != url
                or raw_headers.get("content-encoding", "identity") != "identity"
            ):
                raise AccessBlocked("source status/redirect/encoding refusal")
            if (
                hasattr(response.headers, "get_all")
                and len(response.headers.get_all("content-length", [])) > 1
            ):
                raise AccessBlocked("ambiguous repeated content length")
            if getattr(response, "chunked", False) and "content-length" in raw_headers:
                raise AccessBlocked("ambiguous chunked/content-length framing")
            headers = {
                k: str(v)[:1024]
                for k, v in raw_headers.items()
                if k in {"content-type", "date", "age", "cache-control"}
            }
            headers["x-witness-local-dns-status"] = dns_status
            body = read_profile_body(response, byte_limit=profile.byte_limit, deadline=deadline)
            return body, headers
    except urllib.error.HTTPError as exc:
        value = exc.headers.get("retry-after") if exc.headers else None
        raise SourceFailure(
            "source HTTP " + str(exc.code) + "; no retry/fallback",
            status=exc.code,
            retry_after=value if value and value.isdigit() and len(value) < 8 else None,
        ) from exc
    except AccessBlocked:
        raise
    except (OSError, ValueError) as exc:
        raise AccessBlocked(
            "source transport refusal; no retry/fallback: " + type(exc).__name__
        ) from exc


def _bounded_http_child(profile, url, deadline, read_fd, write_fd):
    os.close(read_fd)
    try:
        try:
            body, headers = _request_with_profile_limits(profile, url, deadline)
            metadata = {"status": "ok", "headers": headers}
        except BaseException as exc:
            body = b""
            metadata = {
                "status": "blocked",
                "reason": str(exc)[:500],
                "http_status": getattr(exc, "status", None),
                "retry_after": getattr(exc, "retry_after", None),
            }
        encoded_meta = encoded(metadata)
        if len(encoded_meta) > 16384 or len(body) > profile.byte_limit:
            raise ValueError("bounded worker result invariant")
        payload = struct.pack("!II", len(encoded_meta), len(body)) + encoded_meta + body
        view = memoryview(payload)
        while view:
            count = os.write(write_fd, view)
            view = view[count:]
    finally:
        os.close(write_fd)


def fixed_transport(profile, url):
    """One cancellable HTTP worker; wall deadline covers DNS/open/headers/body."""
    if url not in {profile.url, profile.robots_url}:
        raise AccessBlocked("exact source URL boundary")
    if (
        threading.current_thread() is not threading.main_thread()
        or threading.active_count() != 1
        or not hasattr(os, "fork")
        or multiprocessing.current_process().daemon
    ):
        raise AccessBlocked("bounded HTTP requires isolated single-thread POSIX CLI")
    deadline = time.monotonic() + profile.timeout
    read_fd, write_fd = os.pipe()
    process = multiprocessing.get_context("fork").Process(
        target=_bounded_http_child, args=(profile, url, deadline, read_fd, write_fd)
    )
    try:
        process.start()
    except BaseException:
        os.close(read_fd)
        os.close(write_fd)
        process.close()
        raise
    os.close(write_fd)
    os.set_blocking(read_fd, False)
    data = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(read_fd, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise AccessBlocked("profile total deadline exceeded; HTTP worker terminated")
                part = os.read(read_fd, 65536)
                if not part:
                    break
                data.extend(part)
                if len(data) > profile.byte_limit + 16392:
                    raise AccessBlocked("bounded worker result exceeded byte limit")
        process.join(max(0, deadline - time.monotonic()))
        if process.is_alive() or time.monotonic() >= deadline:
            raise AccessBlocked("profile total deadline exceeded; HTTP worker terminated")
        if process.exitcode != 0 or len(data) < 8:
            raise AccessBlocked("bounded HTTP worker failed; no retry")
        meta_size, body_size = struct.unpack("!II", data[:8])
        if (
            meta_size > 16384
            or body_size > profile.byte_limit
            or len(data) != 8 + meta_size + body_size
        ):
            raise AccessBlocked("bounded HTTP worker framing invalid")
        metadata = json.loads(data[8 : 8 + meta_size], object_pairs_hook=unique_members)
        if metadata["status"] != "ok":
            raise SourceFailure(
                metadata["reason"],
                status=metadata.get("http_status"),
                retry_after=metadata.get("retry_after"),
            )
        body = bytes(data[8 + meta_size :])
        if time.monotonic() >= deadline:
            raise AccessBlocked("profile total deadline exceeded during result transfer")
        return body, metadata["headers"]
    finally:
        os.close(read_fd)
        if process.is_alive():
            process.kill()
            process.join()
        process.close()


class Controller:
    def __init__(
        self,
        key,
        *,
        state_dir=None,
        transport=None,
        sleep=None,
        now=None,
        review_receipt=None,
        review_hash=None,
    ):
        if key not in PROFILES:
            raise AccessBlocked("unknown/denied source")
        self.key = key
        self.profile = PROFILES[key]
        self.synthetic = transport is not None
        canonical = ROOT / "artifacts/source-state"
        if not self.synthetic and (
            state_dir is not None
            and absolute(state_dir) != canonical
            or now is not None
            or sleep is not None
        ):
            raise AccessBlocked("production state/clock/interval cannot be overridden")
        self.state_dir = absolute(state_dir or canonical)
        if self.synthetic and (
            self.state_dir.resolve() == canonical.resolve()
            or canonical.resolve() in self.state_dir.resolve().parents
        ):
            raise AccessBlocked("synthetic acquisition cannot use production source state")
        self.transport = (
            transport if transport is not None else lambda url: fixed_transport(self.profile, url)
        )
        self.sleep = sleep if sleep is not None else time.sleep
        self.now = now if now is not None else lambda: datetime.now(UTC)
        self.review_receipt = review_receipt
        self.review_hash = review_hash
        self.dbpath = self.state_dir / (key + "-witness.sqlite")
        self.marker = self.state_dir / ("." + key + "-witness.initialized")
        self.captures = self.state_dir / (key + "-witness-captures")
        self.lock = self.state_dir / ("." + key + "-witness.lock")
        self.stop = self.state_dir / (key + "-stop.json.denial.json")
        if self.state_dir.exists() and any(p.is_symlink() for p in self.state_dir.rglob("*")):
            raise ValueError("symlink source state")
        if self.dbpath.exists() != self.marker.exists():
            raise AccessBlocked("source ledger/marker missing; no reset")
        if self.dbpath.exists():
            with self.connection(readonly=True) as db:
                self.integrity(db)

    def release(self):
        if not self.synthetic:
            release_gate(self.review_receipt, self.review_hash)

    def admission(self):
        self.profile.fresh(self.now())
        if not self.synthetic:
            self.release()
            shared_baseline(self.state_dir)
            if self.profile.category == "ram":
                raise AccessBlocked(
                    "production RAM is immutable checkpoint replay only; no fresh budget"
                )
        if self.state_dir.exists() and any(
            p.name.startswith(self.key + "-stop.json") for p in self.state_dir.iterdir()
        ):
            raise AccessBlocked("persistent source stop; no retry/clearing")

    @contextmanager
    def connection(self, readonly=False):
        mode = "ro" if readonly else "rw"
        db = sqlite3.connect(
            self.dbpath.as_uri() + "?mode=" + mode, uri=True, timeout=0, isolation_level=None
        )
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def bootstrap(self):
        self.release()
        self.admission()
        if self.dbpath.exists() or self.marker.exists() or self.captures.exists():
            raise AccessBlocked("explicit bootstrap only for genuinely new source; no reset")
        # Domain-wide prior ledger/marker/checkpoints cannot be escaped via namespace.
        if self.state_dir.exists() and any(
            p.name.startswith(self.key + "-acquisition")
            or p.name.startswith("." + self.key + "-acquisition")
            for p in self.state_dir.iterdir()
        ):
            raise AccessBlocked("prior source state exists; restore/integrate, no second budget")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with (
            file_lock(
                self.state_dir.parent / ("." + self.state_dir.name + ".witness-transfer.lock"),
                timeout=2,
            ),
            file_lock(self.lock, timeout=2),
        ):
            if self.dbpath.exists() or self.marker.exists():
                raise AccessBlocked("concurrent bootstrap refusal")
            temporary = self.state_dir / ("." + uuid.uuid4().hex + ".sqlite")
            with sqlite3.connect(temporary) as db:
                db.executescript(
                    SCHEMA + "INSERT INTO budget VALUES(1,0,0,0,NULL);PRAGMA user_version=1;"
                )
                db.execute("INSERT INTO meta VALUES(?,?)", ("profile", self.profile.fingerprint))
                db.execute("INSERT INTO meta VALUES(?,?)", ("realm", str(int(self.synthetic))))
            with temporary.open("rb") as f:
                __import__("os").fsync(f.fileno())
            temporary.rename(self.dbpath)
            write_file(
                self.marker,
                encoded(
                    {
                        "profile": self.profile.fingerprint,
                        "realm": int(self.synthetic),
                        "no_auto_reset": True,
                    }
                ),
            )
            self.captures.mkdir()
            fsync_directory(self.state_dir)
        return self.status()

    def integrity(self, db):
        require_schema(db, SCHEMA)
        marker = json.loads(self.marker.read_bytes(), object_pairs_hook=unique_members)
        if marker != {
            "profile": self.profile.fingerprint,
            "realm": int(self.synthetic),
            "no_auto_reset": True,
        }:
            raise ValueError("marker/profile/realm mismatch")
        if {r["key"]: r["value"] for r in db.execute("SELECT * FROM meta")} != {
            "profile": self.profile.fingerprint,
            "realm": str(int(self.synthetic)),
        }:
            raise ValueError("ledger profile/realm mismatch")
        rows = db.execute("SELECT * FROM budget").fetchall()
        if len(rows) != 1:
            raise ValueError("budget row invariant")
        b = rows[0]
        if (
            b["id"] != 1
            or any(
                type(b[k]) is not int for k in ("cards_reserved", "http_reserved", "http_attempted")
            )
            or b["cards_reserved"] not in (0, 1)
            or b["http_reserved"] != 2 * b["cards_reserved"]
            or not 0 <= b["http_attempted"] <= b["http_reserved"]
        ):
            raise ValueError("budget invariant; no reset")
        intents = db.execute("SELECT * FROM intents").fetchall()
        if b["cards_reserved"] == 0 and self.captures.exists() and any(self.captures.iterdir()):
            raise ValueError("checkpoint files contradict zero budget; no reset")
        if len(intents) != b["cards_reserved"]:
            raise ValueError("intent/budget invariant")
        for row in intents:
            request = Request.model_validate(
                json.loads(row["request"], object_pairs_hook=unique_members)
            )
            self.profile.request_matches(request)
            expected_id = digest(
                encoded(
                    {
                        "request": request.model_dump(mode="json"),
                        "profile": self.profile.fingerprint,
                        "synthetic": self.synthetic,
                    }
                )
            )
            if (
                row["id"] != expected_id
                or row["state"] in {"captured", "submitted"}
                and not row["capture_hash"]
            ):
                raise ValueError("intent identity/checkpoint state invariant")
            if row["url"] != self.profile.url or row["state"] not in {
                "reserved",
                "captured",
                "submitted",
                "blocked",
            }:
                raise ValueError("intent source/state mismatch")
            if row["capture_hash"]:
                c = self.checkpoint(row["capture_hash"])
                if c.request != request:
                    raise ValueError("checkpoint/request mismatch")

    def status(self):
        if not self.dbpath.exists():
            raise AccessBlocked("source not explicitly bootstrapped; no implicit initialization")
        with self.connection(readonly=True) as db:
            self.integrity(db)
            return {
                "budget": dict(db.execute("SELECT * FROM budget").fetchone()),
                "intents": [dict(r) for r in db.execute("SELECT * FROM intents")],
                "synthetic": self.synthetic,
                "profile": self.profile.fingerprint,
            }

    def checkpoint(self, h):
        if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError("invalid checkpoint hash")
        p = self.captures / (h + ".json")
        raw = p.read_bytes()
        if p.is_symlink() or digest(raw) != h:
            raise ValueError("capture hash mismatch")
        c = Capture.model_validate(json.loads(raw, object_pairs_hook=unique_members))
        selected = (self.captures / (h + ".selected.json")).read_bytes()
        metadata = json.loads(
            (self.captures / (h + ".metadata.json")).read_bytes(), object_pairs_hook=unique_members
        )
        if (
            selected != c.observation.primary["retained_content"].encode()
            or digest(selected) != metadata["selected_sha256"]
            or digest(selected) != c.observation.primary.get("retained_sha256")
            or c.artifact_sha256
            != digest(
                encoded({"receipts": metadata["receipts"], "selected_sha256": digest(selected)})
            )
            or c.synthetic != self.synthetic
            or c.observation.candidate.url != self.profile.url
        ):
            raise ValueError("receipt/selected/realm/source capture binding mismatch")
        if len(metadata["receipts"]) != 2 or [r["url"] for r in metadata["receipts"]] != [
            self.profile.robots_url,
            self.profile.url,
        ]:
            raise ValueError("HTTP sequence boundary")
        if (
            any(r.get("synthetic") is not self.synthetic for r in metadata["receipts"])
            or c.observation.candidate.response_sha256 != self.profile.fingerprint
            or c.observation.primary.get("policy_profile_sha256") != self.profile.fingerprint
        ):
            raise ValueError("receipt realm/profile not bound to capture")
        stamp = datetime.fromisoformat(metadata["receipts"][-1]["received_at"])
        if (
            stamp.tzinfo is None
            or c.observation.candidate.observed_at != stamp
            or any(f.observed_at != stamp for f in c.observation.facts)
        ):
            raise ValueError("source field dates not bound to HTTP receipt")
        if (
            c.observation.primary.get("response_body_sha256")
            != metadata["receipts"][-1]["body_sha256"]
            or c.observation.primary.get("retrieved_at") != metadata["receipts"][-1]["received_at"]
        ):
            raise ValueError("original HTTP body/date not bound to selected capture")
        return c

    def submit(self, journal, capture, h, receipts):
        # Existing event-origin string is the frozen accounting interface, not a
        # claim that the controller implementation is T013.
        event = {
            "origin": "t013_acquisition_ledger",
            "controller": "T016/witness-preserving",
            "source": self.key,
            "http_requests": len(receipts),
            "actual_merchant_HTTP": 0 if self.synthetic else len(receipts),
            "synthetic": self.synthetic,
            "receipts": receipts,
        }
        journal.submit([capture], [event])
        with file_lock(self.lock), self.connection() as db:
            db.execute("UPDATE intents SET state='submitted' WHERE capture_hash=?", (h,))

    def acquire(self, request, journal, *, hook=lambda phase: None):
        self.operation_attempts = 0
        self.failed_receipts = []
        self.profile.request_matches(request)
        if not self.dbpath.exists():
            raise AccessBlocked(
                "explicitly established source budget required; no implicit initialization"
            )
        intent = digest(
            encoded(
                {
                    "request": request.model_dump(mode="json"),
                    "profile": self.profile.fingerprint,
                    "synthetic": self.synthetic,
                }
            )
        )
        with self.connection(readonly=True) as db:
            self.integrity(db)
            row = db.execute("SELECT * FROM intents WHERE id=?", (intent,)).fetchone()
        if row:
            if not row["capture_hash"]:
                raise AccessBlocked("uncertain/blocked acquisition; no automatic refetch")
            c = self.checkpoint(row["capture_hash"])
            m = json.loads(
                (self.captures / (row["capture_hash"] + ".metadata.json")).read_bytes(),
                object_pairs_hook=unique_members,
            )
            self.submit(journal, c, row["capture_hash"], m["receipts"])
            return {
                "status": "checkpoint_reused",
                "http_calls": 0,
                "capture_hash": row["capture_hash"],
                "synthetic": self.synthetic,
            }
        self.admission()
        with file_lock(self.lock), self.connection() as db:
            self.integrity(db)
            db.execute("BEGIN IMMEDIATE")
            try:
                b = db.execute("SELECT * FROM budget").fetchone()
                if b["blocked"] or b["cards_reserved"] >= 1:
                    raise AccessBlocked("persistent budget spent/blocked")
                db.execute("UPDATE budget SET cards_reserved=1,http_reserved=2 WHERE id=1")
                db.execute(
                    "INSERT INTO intents VALUES(?,?,?,'reserved',NULL,NULL)",
                    (intent, encoded(request.model_dump(mode="json")).decode(), self.profile.url),
                )
                db.commit()
            except BaseException:
                db.rollback()
                raise
        hook("reserved")
        receipts = []

        def read(url):
            self.admission()
            if url not in {self.profile.url, self.profile.robots_url}:
                raise AccessBlocked("fixed exact URL only")
            with file_lock(self.lock), self.connection() as db:
                self.integrity(db)
                db.execute("BEGIN IMMEDIATE")
                b = db.execute("SELECT * FROM budget").fetchone()
                if b["blocked"] or b["http_attempted"] >= b["http_reserved"]:
                    db.rollback()
                    raise AccessBlocked("HTTP budget blocked/spent")
                db.execute("UPDATE budget SET http_attempted=http_attempted+1 WHERE id=1")
                db.commit()
            self.operation_attempts += 1
            started = self.now()
            try:
                body, headers = self.transport(url)
            except (AccessBlocked, OSError, ValueError, TypeError) as exc:
                self.failed_receipts.append(
                    {
                        "url": url,
                        "started_at": started.isoformat(),
                        "finished_at": self.now().isoformat(),
                        "status": getattr(exc, "status", None),
                        "retry_after": getattr(exc, "retry_after", None),
                        "outcome": "failed_or_blocked",
                        "synthetic": self.synthetic,
                    }
                )
                raise
            if not isinstance(body, bytes) or len(body) > self.profile.byte_limit:
                raise AccessBlocked("bounded response bytes required")
            stamp = self.now()
            receipts.append(
                {
                    "url": url,
                    "received_at": stamp.isoformat(),
                    "body_bytes": len(body),
                    "body_sha256": digest(body),
                    "synthetic": self.synthetic,
                }
            )
            return body, headers, stamp

        try:
            robots, headers, stamp = read(self.profile.robots_url)
            if not headers.get("content-type", "").startswith("text/plain"):
                raise AccessBlocked("robots MIME refusal")
            rules = RobotsRules(robots.decode("utf-8"))
            if not rules.allowed(self.profile.url):
                raise AccessBlocked("robots denies exact path")
            self.sleep(max(self.profile.interval, rules.delay))
            body, headers, stamp = read(self.profile.url)
            if not headers.get("content-type", "").startswith("text/html") or any(
                v in body.decode("utf-8").lower() for v in DENIAL_MARKERS
            ):
                raise AccessBlocked("card MIME/access denial marker")
            candidate = Candidate(
                url=self.profile.url,
                title=request.name,
                queries=(),
                observed_at=stamp,
                response_sha256=self.profile.fingerprint,
                origin="curated_registry",
            )
            extraction = extract_card(
                request, candidate, body.decode("utf-8"), stamp, synthetic=self.synthetic
            )
            primary = dict(extraction.observation.primary)
            if "retained_content" not in primary:
                retained = encoded(
                    {
                        "synthetic": self.synthetic,
                        "selection_status": "unresolved",
                        "reason": extraction.observation.reason,
                        "no_supported_product_facts": True,
                    }
                ).decode()
                primary.update(
                    retained_content=retained,
                    retained_sha256=digest(retained.encode()),
                    content_kind="selected_primary_metadata",
                )
            primary.update(
                requested_url=self.profile.url,
                final_url=self.profile.url,
                policy_profile_sha256=self.profile.fingerprint,
                http_date=headers.get("date"),
                age=headers.get("age"),
                cache_control=headers.get("cache-control"),
                local_dns_status=headers.get("x-witness-local-dns-status"),
                target_ip_binding="unknown behind managed gateway",
            )
            # Exactly retain already-minimized T015 selected metadata. No old sanitizer.
            selected = primary.get("retained_content", "").encode()
            selected_sha = digest(selected)
            observation = extraction.observation.model_copy(update={"primary": primary})
            capture = Capture(
                request=request,
                observation=observation,
                provenance="synthetic_fixture" if self.synthetic else "live_primary",
                synthetic=self.synthetic,
                artifact_sha256=digest(
                    encoded({"receipts": receipts, "selected_sha256": selected_sha})
                ),
            )
            blob = encoded(capture.model_dump(mode="json"))
            h = digest(blob)
            with file_lock(self.lock), self.connection() as db:
                for suffix, data in [
                    (".json", blob),
                    (".selected.json", selected),
                    (
                        ".metadata.json",
                        encoded({"receipts": receipts, "selected_sha256": selected_sha}),
                    ),
                ]:
                    p = self.captures / (h + suffix)
                    if p.exists() and p.read_bytes() != data:
                        raise ValueError("immutable checkpoint collision")
                    if not p.exists():
                        write_file(p, data)
                fsync_directory(self.captures)
                hook("source_blob_fsynced")
                db.execute(
                    "UPDATE intents SET state='captured',capture_hash=? WHERE id=?", (h, intent)
                )
            hook("source_checkpointed")
        except (AccessBlocked, OSError, ValueError, TypeError) as exc:
            with file_lock(self.lock), self.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE budget SET blocked=? WHERE id=1", (str(exc)[:300],))
                db.execute(
                    "UPDATE intents SET state='blocked',error=? WHERE id=?",
                    (str(exc)[:300], intent),
                )
                db.commit()
                if not self.stop.exists():
                    write_file(
                        self.stop,
                        encoded(
                            {
                                "origin": self.profile.origin,
                                "reason": str(exc)[:300],
                                "at": self.now().isoformat(),
                                "synthetic": self.synthetic,
                                "successful_receipts": receipts,
                                "failed_receipts": self.failed_receipts,
                            }
                        ),
                    )
            raise
        self.checkpoint(h)
        self.submit(journal, capture, h, receipts)
        return {
            "status": "captured_and_submitted",
            "capture_hash": h,
            "http_calls": len(receipts),
            "synthetic": self.synthetic,
        }

    def replay_ram(self, request, journal):
        if self.synthetic or self.key not in {"ram28", "ramregard"}:
            raise AccessBlocked("production legacy RAM replay only")
        self.profile.request_matches(request)
        shared_baseline(self.state_dir)
        from pc_sourcing.collection_acquisition import Acquisition
        from pc_sourcing.collection_profiles import RegardAcquisition

        a = (Acquisition if self.key == "ram28" else RegardAcquisition)()
        status = a.status()
        matches = [
            row
            for row in status["intents"]
            if row["capture_hash"] and Request.model_validate(json.loads(row["request"])) == request
        ]
        if len(matches) != 1:
            raise AccessBlocked("one exact immutable historical RAM checkpoint required")
        c = a.checkpoint(matches[0]["capture_hash"])
        metadata = json.loads(
            (a.captures / (matches[0]["capture_hash"] + ".metadata.json")).read_bytes(),
            object_pairs_hook=unique_members,
        )
        journal.submit(
            [c],
            [
                {
                    "origin": "t013_acquisition_ledger",
                    "controller": "T016/legacy-replay",
                    "http_requests": len(metadata["http_receipts"]),
                    "new_merchant_HTTP": 0,
                    "receipts": metadata["http_receipts"],
                }
            ],
        )
        return {
            "status": "retained_original",
            "http_calls": 0,
            "source_timestamp": c.observation.primary["retrieved_at"],
            "not_reclassified": True,
        }
