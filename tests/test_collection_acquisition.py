"""CHAIN-09: injected transport is always synthetic and never a live permission."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pc_sourcing.collection_acquisition import RAM_MPN, RAM_URL, Acquisition
from pc_sourcing.collection_runtime import Journal
from pc_sourcing.live_models import Request
from pc_sourcing.live_transport import AccessBlocked

ROOT = Path(__file__).resolve().parents[1]


def setup(tmp_path, *, fail=False):
    registry = json.loads((ROOT / "sources/curated-primary.json").read_bytes())
    registry["reviewed_at"] = datetime.now(UTC).isoformat()
    calls = []
    title = "Оперативная память 96 GB 6000 MHz G.Skill (F5-6000J3036F48GX2-TZ5NR)"
    body = f'<div itemscope itemtype="https://schema.org/Product"><h1>{title}</h1><meta itemprop="name" content="{title}"><div itemprop="offers" itemscope itemtype="https://schema.org/Offer"><meta itemprop="price" content="12345"><meta itemprop="priceCurrency" content="RUB"></div></div>'.encode()

    def transport(url):
        calls.append(url)
        if fail:
            raise AccessBlocked("synthetic HTTP 403")
        if url.endswith("robots.txt"):
            return b"User-agent: *\nAllow: /\n", {"content-type": "text/plain"}
        return body, {"content-type": "text/html"}

    a = Acquisition(
        state_dir=tmp_path / "source-state",
        registry=registry,
        transport=transport,
        sleep=lambda _: None,
    )
    return a, calls, Request(name=title, mpn=RAM_MPN, category="ram"), Journal(tmp_path / "runtime")


def test_acquisition_reserves_once_checkpoints_and_reuses_without_http(tmp_path):
    a, calls, r, j = setup(tmp_path)
    result = a.acquire(r, j)
    assert result["synthetic"] is True
    assert calls == ["https://28bit.ru/robots.txt", RAM_URL]
    assert a.status()["budget"]["cards_reserved"] == 1
    assert a.status()["budget"]["http_attempted"] == 2
    assert a.acquire(r, j)["status"] == "checkpoint_reused"
    assert len(calls) == 2
    assert j.work()["status"] == "done"
    assert j.status()["acquisition_http_requests_recorded"] == 2
    assert j.status()["jobs"][0]["capture"]["synthetic"] is True


def test_source_denial_persists_across_constructor_and_never_retries(tmp_path):
    a, calls, r, j = setup(tmp_path, fail=True)
    with pytest.raises(AccessBlocked):
        a.acquire(r, j)
    assert len(calls) == 1
    assert a.status()["budget"]["blocked"]
    again = Acquisition(
        state_dir=a.state_dir, registry=a.registry, transport=a.transport, sleep=lambda _: None
    )
    with pytest.raises(AccessBlocked):
        again.acquire(r, j)
    assert len(calls) == 1


def test_crash_after_reservation_never_refetches_uncertain_acquisition(tmp_path):
    a, calls, r, j = setup(tmp_path)

    def crash(phase):
        if phase == "reserved":
            raise RuntimeError("injected crash")

    with pytest.raises(RuntimeError):
        a.acquire(r, j, hook=crash)
    assert calls == []
    with pytest.raises(AccessBlocked, match="no automatic refetch"):
        a.acquire(r, j)
    assert calls == []


def test_crash_after_source_checkpoint_resumes_journal_without_http(tmp_path):
    a, calls, r, j = setup(tmp_path)

    def crash(phase):
        if phase == "source_checkpointed":
            raise RuntimeError("injected crash")

    with pytest.raises(RuntimeError):
        a.acquire(r, j, hook=crash)
    assert j.status()["jobs"] == []
    assert a.acquire(r, j)["status"] == "checkpoint_reused"
    assert len(calls) == 2
    assert j.work()["status"] == "done"


@pytest.mark.parametrize("target", ["avito", "nix", "gpu", "other_ram"])
def test_no_target_expansion_or_denied_origin_acquisition(tmp_path, target):
    a, calls, r, j = setup(tmp_path)
    req = Request(
        name=target + " product", mpn="OTHER-MPN", category="gpu" if target == "gpu" else "ram"
    )
    with pytest.raises(AccessBlocked):
        a.acquire(req, j)
    assert calls == []
    assert a.status()["budget"]["cards_reserved"] == 0


def test_expired_policy_and_existing_denial_block_before_http(tmp_path):
    a, calls, r, j = setup(tmp_path)
    a.registry["reviewed_at"] = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    with pytest.raises(ValueError, match="stale"):
        a.acquire(r, j)
    assert calls == []
    a.registry["reviewed_at"] = datetime.now(UTC).isoformat()
    (a.state_dir / "28bit-stop.json.denial.json").write_text("{}")
    with pytest.raises(AccessBlocked, match="denial"):
        a.acquire(r, j)
    assert calls == []


def test_production_cannot_override_shared_state_or_review_date(tmp_path):
    with pytest.raises(ValueError, match="cannot be overridden"):
        Acquisition(state_dir=tmp_path)
    with pytest.raises(ValueError, match="cannot be overridden"):
        Acquisition(registry={})


def test_spent_budget_survives_new_runtime_and_missing_ledger_never_resets(tmp_path):
    a, calls, r, j = setup(tmp_path)
    a.acquire(r, j)
    other = Request(name=r.name, mpn=r.mpn, category=r.category, quantity=2)
    with pytest.raises(AccessBlocked, match="budget"):
        a.acquire(other, Journal(tmp_path / "other-runtime"))
    assert len(calls) == 2
    a.dbpath.unlink()
    with pytest.raises(AccessBlocked, match="missing"):
        Acquisition(
            state_dir=a.state_dir, registry=a.registry, transport=a.transport, sleep=lambda _: None
        )
    assert len(calls) == 2


def test_concurrent_identical_acquisition_cannot_double_fetch(tmp_path):
    import threading

    a, calls, r, j = setup(tmp_path)
    reached, release = threading.Event(), threading.Event()
    original = a.transport

    def transport(url):
        if url.endswith("robots.txt"):
            reached.set()
            assert release.wait(timeout=5)
        return original(url)

    a.transport = transport
    errors = []

    def worker():
        try:
            a.acquire(r, j)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    assert reached.wait(timeout=5)
    b = Acquisition(
        state_dir=a.state_dir, registry=a.registry, transport=original, sleep=lambda _: None
    )
    with pytest.raises(AccessBlocked, match="no automatic refetch"):
        b.acquire(r, j)
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive() and not errors
    assert len(calls) == 2 and len(j.status()["jobs"]) == 1


def test_empty_canonical_production_state_never_initializes_budget(tmp_path, monkeypatch):
    import pc_sourcing.collection_acquisition as module

    original = module.PACKAGE_ROOT
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/curated-primary.json").write_bytes(
        (original / "sources/curated-primary.json").read_bytes()
    )
    (tmp_path / "artifacts/source-state").mkdir(parents=True)
    monkeypatch.setattr(module, "PACKAGE_ROOT", tmp_path)
    with pytest.raises(AccessBlocked, match="baseline missing"):
        Acquisition()
    assert not (tmp_path / "artifacts/source-state/28bit-acquisition.sqlite").exists()


@pytest.mark.parametrize("mutation", ["missing_row", "negative_counter", "column"])
def test_source_ledger_drift_never_reinitializes_or_resets(tmp_path, mutation):
    a, calls, r, j = setup(tmp_path)
    a.acquire(r, j)
    with a.connect() as db:
        if mutation == "missing_row":
            db.execute("DELETE FROM budget")
        elif mutation == "negative_counter":
            db.execute("UPDATE budget SET cards_reserved=-1")
        else:
            db.execute("ALTER TABLE budget ADD COLUMN bad TEXT")
    with pytest.raises(ValueError):
        Acquisition(
            state_dir=a.state_dir, registry=a.registry, transport=a.transport, sleep=lambda _: None
        )
    assert len(calls) == 2


def test_production_both_ledger_and_marker_loss_never_resets_with_stops_present(
    tmp_path, monkeypatch
):
    import pc_sourcing.collection_acquisition as module

    original = module.PACKAGE_ROOT
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/curated-primary.json").write_bytes(
        (original / "sources/curated-primary.json").read_bytes()
    )
    state = tmp_path / "artifacts/source-state"
    state.mkdir(parents=True)
    (state / "tavily-stop.json").write_text('{"endpoint":"https://api.tavily.com/search"}')
    (state / "28bit-stop.json").write_text('{"reason":"gaierror"}')
    monkeypatch.setattr(module, "PACKAGE_ROOT", tmp_path)
    with pytest.raises(AccessBlocked, match="no implicit initialization"):
        Acquisition()
    assert not (state / "28bit-acquisition.sqlite").exists()


@pytest.mark.parametrize(
    "damage", ["zero", "truncated_header", "truncated_pages", "malformed", "empty_sqlite"]
)
def test_damaged_production_ledger_refuses_without_mutating_any_state(
    tmp_path, monkeypatch, damage
):
    import sqlite3

    import pc_sourcing.collection_acquisition as module

    a, calls, r, j = setup(tmp_path)
    a.acquire(r, j)
    original = module.PACKAGE_ROOT
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/curated-primary.json").write_bytes(
        (original / "sources/curated-primary.json").read_bytes()
    )
    state = tmp_path / "artifacts/source-state"
    import shutil

    shutil.copytree(a.state_dir, state)
    (state / "tavily-stop.json").write_text('{"endpoint":"https://api.tavily.com/search"}')
    (state / "28bit-stop.json").write_text('{"reason":"gaierror"}')
    ledger = state / "28bit-acquisition.sqlite"
    raw = ledger.read_bytes()
    if damage == "zero":
        ledger.write_bytes(b"")
    elif damage == "truncated_header":
        ledger.write_bytes(raw[:16])
    elif damage == "truncated_pages":
        ledger.write_bytes(raw[: len(raw) // 2])
    elif damage == "malformed":
        ledger.write_bytes(b"not a SQLite database")
    else:
        ledger.unlink()
        with sqlite3.connect(ledger) as db:
            db.execute("PRAGMA user_version=1")
    before = {str(p.relative_to(state)): p.read_bytes() for p in state.rglob("*") if p.is_file()}
    monkeypatch.setattr(module, "PACKAGE_ROOT", tmp_path)
    with pytest.raises((ValueError, AccessBlocked, sqlite3.DatabaseError)):
        Acquisition()
    after = {str(p.relative_to(state)): p.read_bytes() for p in state.rglob("*") if p.is_file()}
    assert before == after
    assert len(calls) == 2


@pytest.mark.parametrize("mutation", ["type", "not_null", "primary_key", "check", "extra_index"])
def test_source_schema_constraints_and_indexes_are_protected(tmp_path, mutation):
    a, calls, r, j = setup(tmp_path)
    with a.connect() as db:
        if mutation == "extra_index":
            db.execute("CREATE INDEX unexpected ON intents(url)")
        else:
            ddl = db.execute("SELECT sql FROM sqlite_master WHERE name='budget'").fetchone()[0]
            ddl = (
                ddl.replace("INTEGER PRIMARY KEY", "TEXT PRIMARY KEY", 1)
                if mutation == "type"
                else ddl.replace(" NOT NULL", "", 1)
                if mutation == "not_null"
                else ddl.replace(" PRIMARY KEY", "", 1)
                if mutation == "primary_key"
                else ddl.replace(" CHECK(id=1)", "")
            )
            db.execute("DROP TABLE budget")
            db.execute(ddl)
            db.execute("INSERT INTO budget VALUES(1,0,0,0,NULL)")
    before = a.dbpath.read_bytes()
    with pytest.raises(ValueError, match="schema"):
        Acquisition(state_dir=a.state_dir, registry=a.registry, transport=a.transport)
    assert a.dbpath.read_bytes() == before and calls == []


def test_canonical_legacy_source_version_zero_preserves_spent_budget_without_migration(tmp_path):
    a, calls, r, j = setup(tmp_path)
    a.acquire(r, j)
    budget = a.status()["budget"]
    with a.connect() as db:
        db.execute("PRAGMA user_version=0")
    before = {
        str(p.relative_to(a.state_dir)): p.read_bytes()
        for p in a.state_dir.rglob("*")
        if p.is_file()
    }
    again = Acquisition(state_dir=a.state_dir, registry=a.registry, transport=a.transport)
    assert again.status()["budget"] == budget
    assert again.acquire(r, Journal(tmp_path / "legacy-runtime"))["http_calls"] == 0
    assert len(calls) == 2
    assert before == {
        str(p.relative_to(a.state_dir)): p.read_bytes()
        for p in a.state_dir.rglob("*")
        if p.is_file()
    }


def test_unknown_source_schema_version_rejected_without_migration(tmp_path):
    a, calls, r, j = setup(tmp_path)
    with a.connect() as db:
        db.execute("PRAGMA user_version=2")
    before = a.dbpath.read_bytes()
    with pytest.raises(ValueError, match="schema version"):
        Acquisition(state_dir=a.state_dir, registry=a.registry, transport=a.transport)
    assert before == a.dbpath.read_bytes() and calls == []
