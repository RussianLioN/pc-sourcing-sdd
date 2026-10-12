"""One reviewed RAM acquisition, durable reservation/checkpoint and no source reset."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pc_sourcing.collection_capture import Capture
from pc_sourcing.curated_primary import CuratedReader, fixed_get
from pc_sourcing.durable_jobs import (
    absolute,
    digest,
    encoded,
    file_lock,
    fsync_directory,
    write_file,
)
from pc_sourcing.live_transport import AccessBlocked

RAM_URL = "https://28bit.ru/operativnaya-pamyat-96-gb-6000-mhz-g-skill-trident-z5-neo-rgb-f5-6000j3036f48gx2-tz5nr/"
RAM_MPN = "F5-6000J3036F48GX2-TZ5NR"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]


class Acquisition:
    source_key = "28bit"
    target_url = RAM_URL

    def canonical_registry(self):
        return json.loads((PACKAGE_ROOT / "sources/curated-primary.json").read_bytes())

    def default_transport(self):
        return fixed_get

    def reader(self, registry, state, **kwargs):
        return CuratedReader(registry, state, **kwargs)

    def __init__(self, *, state_dir=None, registry=None, transport=None, sleep=None):
        canonical_state = PACKAGE_ROOT / "artifacts/source-state"
        if transport is None and state_dir is not None and absolute(state_dir) != canonical_state:
            raise ValueError("production source state cannot be overridden")
        canonical_registry = self.canonical_registry()
        if transport is None and registry is not None and registry != canonical_registry:
            raise ValueError("production reviewed registry cannot be overridden")
        self.state_dir = absolute(state_dir or canonical_state)
        self.synthetic = transport is not None
        self.transport = transport if transport is not None else self.default_transport()
        self.sleep = sleep
        self.registry = registry if registry is not None else canonical_registry
        if not self.synthetic and not self.state_dir.is_dir():
            raise AccessBlocked(
                "source state unavailable; restore prior state before live acquisition"
            )
        if not self.synthetic:
            required = [self.state_dir / "tavily-stop.json", self.state_dir / "28bit-stop.json"]
            if any(not p.is_file() or p.is_symlink() for p in required):
                raise AccessBlocked(
                    "production source-state baseline missing; restore state, never initialize empty"
                )
            if (
                json.loads(required[0].read_bytes()).get("endpoint")
                != "https://api.tavily.com/search"
            ):
                raise AccessBlocked("source-state baseline provenance invalid")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if any(
            (self.state_dir / n).is_symlink()
            for n in [
                self.source_key + "-stop.json",
                self.source_key + "-stop.json.denial.json",
                self.source_key + "-acquisition.sqlite",
                "." + self.source_key + "-acquisition.lock",
            ]
        ):
            raise ValueError("symlink source-state component")
        self.state = self.state_dir / (self.source_key + "-stop.json")
        self.dbpath = self.state_dir / (self.source_key + "-acquisition.sqlite")
        self.lock = self.state_dir / ("." + self.source_key + "-acquisition.lock")
        self.captures = self.state_dir / (self.source_key + "-acquisition-captures")
        if self.captures.is_symlink():
            raise ValueError("symlink source capture directory")
        self.captures.mkdir(exist_ok=True)
        marker = self.state_dir / ("." + self.source_key + "-acquisition.initialized")
        if marker.exists() and not self.dbpath.exists():
            raise AccessBlocked("persistent source budget missing; no automatic recreation/reset")
        with file_lock(self.lock, timeout=2), self.connect() as db:
            objects = db.execute(
                "SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger')"
            ).fetchall()
            if not objects:
                db.executescript(
                    "BEGIN IMMEDIATE;CREATE TABLE budget(id INTEGER PRIMARY KEY CHECK(id=1),cards_reserved INTEGER NOT NULL,http_reserved INTEGER NOT NULL,http_attempted INTEGER NOT NULL,blocked TEXT);INSERT INTO budget VALUES(1,0,0,0,NULL);CREATE TABLE intents(id TEXT PRIMARY KEY,request TEXT NOT NULL,url TEXT NOT NULL,policy_hash TEXT NOT NULL,realm INTEGER NOT NULL,state TEXT NOT NULL,capture_hash TEXT,error TEXT);PRAGMA user_version=1;COMMIT;"
                )
            self.integrity(db)

            if not marker.exists():
                write_file(marker, encoded({"budget": "one-card-two-http", "no_auto_reset": True}))
                fsync_directory(self.state_dir)

    def integrity(self, db):
        expected = {
            "budget": {"id", "cards_reserved", "http_reserved", "http_attempted", "blocked"},
            "intents": {
                "id",
                "request",
                "url",
                "policy_hash",
                "realm",
                "state",
                "capture_hash",
                "error",
            },
        }
        objects = db.execute(
            "SELECT name,type FROM sqlite_master WHERE type IN ('table','view','trigger')"
        ).fetchall()
        if {r["name"] for r in objects} != set(expected) or any(
            r["type"] != "table" for r in objects
        ):
            raise ValueError("source ledger schema invalid; no reset")
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("source ledger corruption")
        for t, columns in expected.items():
            if {r["name"] for r in db.execute("PRAGMA table_info(" + t + ")")} != columns:
                raise ValueError("source ledger columns invalid")
        rows = db.execute("SELECT * FROM budget").fetchall()
        if len(rows) != 1:
            raise ValueError("source budget row missing/duplicated; no reset")
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
            raise ValueError("source budget invariant invalid; no reset")
        intents = db.execute("SELECT * FROM intents").fetchall()
        if len(intents) != b["cards_reserved"]:
            raise ValueError("source intent/budget mismatch")
        for row in intents:
            if (
                row["url"] != self.target_url
                or row["realm"] != int(self.synthetic)
                or row["state"] not in ("reserved", "captured", "submitted", "blocked")
            ):
                raise ValueError("source intent scope/state mismatch")
            if row["capture_hash"]:
                capture = self.checkpoint(row["capture_hash"])
                if capture.synthetic != self.synthetic:
                    raise ValueError("source checkpoint realm mismatch")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.dbpath, timeout=0, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    def admit(self, request):
        if request.category != "ram" or request.mpn != RAM_MPN:
            raise AccessBlocked("only the exact reviewed F5 RAM request is admitted")
        # Frozen reader checks real-time policy expiry, source state and exact URL.
        kwargs = {"transport": self.transport}
        if self.sleep is not None:
            kwargs["sleep"] = self.sleep
        reader = self.reader(self.registry, self.state, **kwargs)
        reader.check_state()
        if self.target_url not in reader.urls:
            raise AccessBlocked("RAM exact capability missing")
        return reader

    def checkpoint(self, h):
        if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError("invalid checkpoint hash")
        p = self.captures / (h + ".json")
        if p.is_symlink() or digest(p.read_bytes()) != h:
            raise ValueError("source checkpoint hash mismatch")
        capture = Capture.model_validate(json.loads(p.read_bytes()))
        metadata_path = self.captures / (h + ".metadata.json")
        selected_path = self.captures / (h + ".selected.json")
        if metadata_path.is_symlink() or selected_path.is_symlink():
            raise ValueError("symlink source audit file")
        metadata = json.loads(metadata_path.read_bytes())
        selected = selected_path.read_bytes()
        if (
            selected != capture.observation.primary["retained_content"].encode()
            or digest(selected) != metadata["selected_bytes_sha256"]
        ):
            raise ValueError("selected source bytes integrity mismatch")
        expected = digest(
            encoded(
                {"http_receipts": metadata["http_receipts"], "selected_sha256": digest(selected)}
            )
        )
        if capture.artifact_sha256 != expected:
            raise ValueError("source HTTP audit integrity mismatch")
        return capture

    def status(self):
        with file_lock(self.lock), self.connect() as db:
            self.integrity(db)
            return {
                "budget": dict(db.execute("SELECT * FROM budget").fetchone()),
                "intents": [dict(r) for r in db.execute("SELECT * FROM intents ORDER BY id")],
            }

    def acquire(self, request, journal, *, hook=lambda phase: None):
        policy_hash = digest(encoded(self.registry))
        intent = digest(
            encoded(
                {
                    "request": request.model_dump(mode="json"),
                    "url": self.target_url,
                    "policy_hash": policy_hash,
                    "synthetic": self.synthetic,
                }
            )
        )
        # A committed source capture is available even if its policy later expires.
        # This is checkpoint consumption, never a fresh source authorization.
        with file_lock(self.lock), self.connect() as db:
            prior = db.execute("SELECT * FROM intents WHERE id=?", (intent,)).fetchone()
            if prior and prior["capture_hash"]:
                capture = self.checkpoint(prior["capture_hash"])
            else:
                capture = None
            if prior and capture is None:
                raise AccessBlocked(
                    "incomplete/blocked acquisition persisted; no automatic refetch"
                )
        if capture is not None:
            metadata = json.loads(
                (self.captures / (prior["capture_hash"] + ".metadata.json")).read_bytes()
            )
            event = {
                "stage": "primary_acquisition",
                "origin": "t013_acquisition_ledger",
                "intent": intent,
                "http_requests": len(metadata["http_receipts"]),
                "receipts": metadata["http_receipts"],
            }
            journal.submit([capture], [event])
            return {"status": "checkpoint_reused", "http_calls": 0, "intent": intent}
        reader = self.admit(request)
        with file_lock(self.lock), self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                # Recheck under reservation lock; concurrent identical caller never fetches.
                prior = db.execute("SELECT * FROM intents WHERE id=?", (intent,)).fetchone()
                if prior:
                    raise AccessBlocked("acquisition already reserved; inspect checkpoint/status")
                budget = db.execute("SELECT * FROM budget").fetchone()
                if (
                    budget["blocked"]
                    or budget["cards_reserved"] >= 1
                    or budget["http_reserved"] >= 2
                ):
                    raise AccessBlocked(
                        "persistent source budget/stop prevents acquisition; no reset"
                    )
                db.execute(
                    "UPDATE budget SET cards_reserved=cards_reserved+1,http_reserved=http_reserved+2 WHERE id=1"
                )
                db.execute(
                    "INSERT INTO intents VALUES(?,?,?,?,?,'reserved',NULL,NULL)",
                    (
                        intent,
                        encoded(request.model_dump(mode="json")).decode(),
                        self.target_url,
                        policy_hash,
                        int(self.synthetic),
                    ),
                )
                db.commit()
            except BaseException:
                db.rollback()
                raise
        hook("reserved")
        receipts = []

        def bounded_transport(url):
            if url not in {self.target_url, self.registry["origin"] + "/robots.txt"}:
                raise AccessBlocked("acquisition transport exact URL boundary")
            self.admit(request)  # fresh policy/state before each actual request
            with file_lock(self.lock), self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                b = db.execute("SELECT * FROM budget").fetchone()
                if b["blocked"] or b["http_attempted"] >= b["http_reserved"]:
                    db.rollback()
                    raise AccessBlocked("persistent HTTP budget/stop")
                db.execute("UPDATE budget SET http_attempted=http_attempted+1 WHERE id=1")
                db.commit()
            body, headers = self.transport(url)
            receipts.append(
                {
                    "url": url,
                    "received_at": datetime.now(UTC).isoformat(),
                    "body_bytes": len(body),
                    "body_sha256": digest(body),
                    "retention": "full response bytes used only in memory; exact selected primary bytes checkpointed",
                }
            )
            return body, headers

        reader.transport = bounded_transport
        candidate = next(
            c
            for c in reader.seed_candidates(datetime.now(UTC), request)
            if c.url == self.target_url
        )
        try:
            observed = reader.observe(request, candidate, datetime.now(UTC))
            # Retain only nonpersonal product facts. Visible prose/reviews and
            # parser raw text are not copied into the durable audit.
            primary = dict(observed.primary)
            original_selected_hash = primary["retained_sha256"]
            parsed = json.loads(primary["retained_content"])
            keep = {
                "name",
                "mpn",
                "sku",
                "price",
                "priceCurrency",
                "availability",
                "itemCondition",
                "manufacturer",
                "brand",
            }
            selected_object = {
                "h1": parsed.get("h1"),
                "product_count": parsed.get("product_count"),
                "properties": {k: v for k, v in parsed.get("properties", {}).items() if k in keep},
                "price_types": parsed.get("price_types", []),
                "identity_conflicts": parsed.get("identity_conflicts", []),
                "identity_assertions": [
                    {k: v for k, v in c.items() if k != "raw"}
                    for c in parsed.get("identity_assertions", [])
                ],
                "source_selected_sha256": original_selected_hash,
                "retention": "selected nonpersonal product facts; visible text/reviews omitted",
            }
            if "price_rub" in parsed:
                selected_object["price_rub"] = parsed["price_rub"]
            retained = encoded(selected_object).decode()
            retained_hash = digest(retained.encode())
            primary.update(retained_content=retained, retained_sha256=retained_hash)
            observed = observed.model_copy(
                update={
                    "primary": primary,
                    "facts": tuple(
                        f.model_copy(update={"content_sha256": retained_hash})
                        for f in observed.facts
                    ),
                }
            )
            # Source-selected metadata bytes are retained exactly; full HTML is not
            # retained under the reviewed minimum-scalar capability.
            selected = observed.primary["retained_content"].encode()
            capture = Capture(
                request=request,
                observation=observed,
                provenance="synthetic_fixture" if self.synthetic else "live_primary",
                synthetic=self.synthetic,
                artifact_sha256=digest(
                    encoded({"http_receipts": receipts, "selected_sha256": digest(selected)})
                ),
            )
            blob = encoded(capture.model_dump(mode="json"))
            h = digest(blob)
            with file_lock(self.lock), self.connect() as db:
                p = self.captures / (h + ".json")
                if not p.exists():
                    temporary = self.captures / ("." + uuid.uuid4().hex)
                    write_file(temporary, blob)
                    temporary.rename(p)
                    fsync_directory(self.captures)
                elif p.is_symlink() or p.read_bytes() != blob:
                    raise ValueError("immutable source checkpoint collision")
                write_file(
                    self.captures / (h + ".metadata.json"),
                    encoded({"http_receipts": receipts, "selected_bytes_sha256": digest(selected)}),
                )
                write_file(self.captures / (h + ".selected.json"), selected)
                fsync_directory(self.captures)
                hook("source_blob_fsynced")
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "UPDATE intents SET state='captured',capture_hash=? WHERE id=?", (h, intent)
                )
                db.commit()
            hook("source_checkpointed")
        except (AccessBlocked, OSError, ValueError, TypeError) as exc:
            with file_lock(self.lock), self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE budget SET blocked=? WHERE id=1", (str(exc)[:500],))
                db.execute(
                    "UPDATE intents SET state='blocked',error=? WHERE id=?",
                    (str(exc)[:500], intent),
                )
                db.commit()
            raise
        event = {
            "stage": "primary_acquisition",
            "origin": "t013_acquisition_ledger",
            "intent": intent,
            "http_requests": len(receipts),
            "receipts": receipts,
        }
        journal.submit([capture], [event])
        with file_lock(self.lock), self.connect() as db:
            db.execute("UPDATE intents SET state='submitted' WHERE id=?", (intent,))
        return {
            "status": "captured_and_submitted",
            "intent": intent,
            "http_calls": len(receipts),
            "synthetic": self.synthetic,
            "capture_hash": h,
        }
