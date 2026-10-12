"""WIT-01–08 new controller synthetic chain, no actual merchant requests."""

import json
from datetime import timedelta

import pytest
from test_product_extraction import MPN, NOW, card, product

from pc_sourcing.collection_runtime import Journal
from pc_sourcing.live_models import Request
from pc_sourcing.live_transport import AccessBlocked
from pc_sourcing.normalized_exports import verify_bundle
from pc_sourcing.witness_controller import Controller
from pc_sourcing.witness_profiles import PROFILES


def setup(tmp_path, key="tdvat", conditional=False, stock="https://schema.org/Discontinued"):
    profile = PROFILES[key]
    calls = []
    gpu = profile.category == "gpu"
    req = Request(
        name="MSI RTX 5090 SUPRIM LIQUID OC"
        if gpu
        else "G.Skill DDR5 96GB 2x48GB 6000 MT/s CL30 EXPO",
        mpn="G5090-32SLC" if gpu else MPN,
        category=profile.category,
    )
    p = product(
        url=profile.url,
        name="SYNTHETIC MSI RTX 5090 SUPRIM LIQUID OC (G5090-32SLC)" if gpu else product()["name"],
        description="рассрочка" if conditional else "",
    )
    p["offers"]["availability"] = stock
    body = card(p, "<footer>ASUS 32GB залог</footer>").encode()

    def transport(url):
        calls.append(url)
        if url == profile.robots_url:
            return b"User-agent: *\nAllow: /\n", {"content-type": "text/plain"}
        assert url == profile.url
        return body, {"content-type": "text/html"}

    c = Controller(
        key,
        state_dir=tmp_path / "state",
        transport=transport,
        sleep=lambda _: None,
        now=lambda: NOW,
    )
    c.bootstrap()
    return c, calls, req, Journal(tmp_path / "runtime")


@pytest.mark.parametrize("key", ["tdvat", "evens", "ram28", "ramregard"])
def test_full_acquisition_journal_all_exports_restore_keeps_witnesses(tmp_path, key):
    c, calls, r, j = setup(tmp_path, key)
    result = c.acquire(r, j)
    assert result["synthetic"] is True and result["http_calls"] == 2
    assert len(calls) == 2 and c.status()["budget"]["cards_reserved"] == 1
    cap = c.checkpoint(result["capture_hash"])
    selected = json.loads(cap.observation.primary["retained_content"])
    assert selected["price_tokens"][0]["raw"] == "118 400,00"
    assert selected["displayed_price_rub"] == "118400.00" and selected["stock"] == "unavailable"
    assert selected["properties"]["availability"] == ["https://schema.org/Discontinued"]
    assert "title-derived" in next(f.selector for f in cap.observation.facts if f.field == "mpn")
    assert j.work()["status"] == "done"
    j.report(tmp_path / "report", NOW)
    assert verify_bundle(tmp_path / "report/offers")["formats"] == 5
    data = json.loads((tmp_path / "report/offers/comparison.json").read_text())
    assert len(data["rows"]) == 1 and data["rows"][0]["offer"]["price"] is None
    assert data["rows"][0]["offer"]["conditional_prices"][0]["kind"] == "unknown"
    assert data["rows"][0]["offer"]["stock"] == "unavailable"
    assert not data["rows"][0]["decision"]["purchase_ready"]
    j.backup(tmp_path / "backup")
    restored = Journal.restore(tmp_path / "backup", tmp_path / "restored")
    restored.report(tmp_path / "restored-report", NOW)
    assert json.loads((tmp_path / "restored-report/coverage.json").read_text()) == json.loads(
        (tmp_path / "report/coverage.json").read_text()
    )
    assert c.acquire(r, restored)["http_calls"] == 0 and len(calls) == 2


def test_conditional_price_token_not_dropped_when_no_regular_amount(tmp_path):
    c, calls, r, j = setup(tmp_path, conditional=True)
    result = c.acquire(r, j)
    cap = c.checkpoint(result["capture_hash"])
    selected = json.loads(cap.observation.primary["retained_content"])
    assert selected["price_tokens"][0]["kind"] == "conditional_or_unknown"
    assert selected["price_tokens"][0]["condition_markers"]
    assert cap.observation.price_rub is None and cap.observation.status == "unresolved"
    j.work()
    j.report(tmp_path / "report", NOW)
    assert json.loads((tmp_path / "report/offers/comparison.json").read_text())["rows"] == []


@pytest.mark.parametrize("phase", ["reserved", "source_blob_fsynced", "source_checkpointed"])
def test_crashes_never_automatically_refetch(tmp_path, phase):
    c, calls, r, j = setup(tmp_path)

    def crash(current):
        if current == phase:
            raise RuntimeError("synthetic injected crash")

    with pytest.raises(RuntimeError):
        c.acquire(r, j, hook=crash)
    count = len(calls)
    if phase == "source_checkpointed":
        assert c.acquire(r, j)["http_calls"] == 0
    else:
        with pytest.raises(AccessBlocked):
            c.acquire(r, j)
    assert len(calls) == count


@pytest.mark.parametrize("damage", [b"", b"SQLite format 3\x00", b"malformed"])
def test_existing_damaged_ledger_never_reinitializes_or_mutates(tmp_path, damage):
    c, calls, r, j = setup(tmp_path)
    c.acquire(r, j)
    c.dbpath.write_bytes(damage)
    before = {
        str(p.relative_to(c.state_dir)): p.read_bytes()
        for p in c.state_dir.rglob("*")
        if p.is_file()
    }
    with pytest.raises((ValueError, AccessBlocked, __import__("sqlite3").DatabaseError)):
        Controller(c.key, state_dir=c.state_dir, transport=c.transport, now=lambda: NOW)
    after = {
        str(p.relative_to(c.state_dir)): p.read_bytes()
        for p in c.state_dir.rglob("*")
        if p.is_file()
    }
    assert before == after and len(calls) == 2


def test_unknown_or_wrong_target_and_expired_profile_make_no_calls(tmp_path):
    c, calls, r, j = setup(tmp_path)
    with pytest.raises(AccessBlocked):
        c.acquire(Request(name="Wrong target", mpn="OTHER", category="gpu"), j)
    assert calls == []
    c.now = lambda: NOW + timedelta(days=2)
    with pytest.raises(AccessBlocked, match="policy"):
        c.acquire(r, j)
    assert calls == []


def test_constructor_does_not_initialize_budget_and_bootstrap_is_explicit(tmp_path):
    c, calls, r, j = setup(tmp_path)
    with pytest.raises((ValueError, AccessBlocked)):
        c.bootstrap()
    assert c.status()["budget"]["cards_reserved"] == 0 and calls == []


def test_release_required_before_any_production_bootstrap(tmp_path):
    c = Controller("tdvat")
    with pytest.raises(AccessBlocked, match="review"):
        c.bootstrap()


@pytest.mark.parametrize(
    "body",
    [
        b"<html><h1>Unsupported layout</h1></html>",
        b'<script type="application/ld+json">{"name":"a","name":"b"}</script>',
    ],
)
def test_unsupported_or_ambiguous_source_kept_as_coverage_not_lost(tmp_path, body):
    c, calls, r, j = setup(tmp_path)
    original = c.transport
    c.transport = (
        lambda url: original(url)
        if url == c.profile.robots_url
        else (body, {"content-type": "text/html"})
    )
    result = c.acquire(r, j)
    capture = c.checkpoint(result["capture_hash"])
    assert capture.observation.status == "unresolved" and capture.observation.facts == ()
    j.work()
    j.report(tmp_path / "report", NOW)
    assert len(json.loads((tmp_path / "report/coverage.json").read_text())["jobs"]) == 1
    assert json.loads((tmp_path / "report/offers/comparison.json").read_text())["rows"] == []


def test_source_denial_persists_and_never_retry(tmp_path):
    c, calls, r, j = setup(tmp_path)

    def deny(url):
        calls.append(url)
        raise AccessBlocked("SYNTHETIC HTTP403")

    c.transport = deny
    with pytest.raises(AccessBlocked):
        c.acquire(r, j)
    assert len(calls) == 1 and c.stop.exists()
    with pytest.raises(AccessBlocked):
        c.acquire(r, j)
    assert len(calls) == 1


def test_synthetic_transport_cannot_write_production_state():
    from pc_sourcing.witness_profiles import ROOT

    with pytest.raises(AccessBlocked, match="synthetic"):
        Controller("tdvat", state_dir=ROOT / "artifacts/source-state", transport=lambda _: None)


@pytest.mark.parametrize("mutation", ["receipt", "selected", "capture"])
def test_checkpoint_tamper_never_enters_report(tmp_path, mutation):
    c, calls, r, j = setup(tmp_path)
    result = c.acquire(r, j)
    h = result["capture_hash"]
    suffix = {"receipt": ".metadata.json", "selected": ".selected.json", "capture": ".json"}[
        mutation
    ]
    p = c.captures / (h + suffix)
    p.write_bytes(p.read_bytes() + b"changed")
    with pytest.raises(ValueError):
        c.checkpoint(h)
    assert len(calls) == 2


@pytest.mark.parametrize("mutation", ["id", "realm", "schema", "budget"])
def test_ledger_scope_schema_and_budget_drift_fails_without_reset(tmp_path, mutation):
    c, calls, r, j = setup(tmp_path)
    c.acquire(r, j)
    with c.connection() as db:
        if mutation == "id":
            db.execute("UPDATE intents SET id='wrong'")
        elif mutation == "realm":
            db.execute("UPDATE meta SET value='0' WHERE key='realm'")
        elif mutation == "schema":
            db.execute("ALTER TABLE budget ADD COLUMN bad TEXT")
        else:
            db.execute("DELETE FROM budget")
    before = c.dbpath.read_bytes()
    with pytest.raises(ValueError):
        Controller(c.key, state_dir=c.state_dir, transport=c.transport, now=lambda: NOW)
    assert c.dbpath.read_bytes() == before and len(calls) == 2


def test_concurrent_identical_source_intent_never_double_fetches(tmp_path):
    import threading

    c, calls, r, j = setup(tmp_path)
    arrived = threading.Event()
    release = threading.Event()
    original = c.transport

    def paused(url):
        if url == c.profile.robots_url:
            arrived.set()
            assert release.wait(timeout=5)
        return original(url)

    c.transport = paused
    errors = []

    def run():
        try:
            c.acquire(r, j)
        except BaseException as exc:
            errors.append(exc)

    t = threading.Thread(target=run)
    t.start()
    assert arrived.wait(timeout=5)
    other = Controller(
        c.key, state_dir=c.state_dir, transport=original, now=lambda: NOW, sleep=lambda _: None
    )
    with pytest.raises(AccessBlocked):
        other.acquire(r, j)
    release.set()
    t.join(timeout=5)
    assert not t.is_alive() and not errors and len(calls) == 2


def test_http429_failure_retains_url_time_retry_after_and_attempt(tmp_path):
    from pc_sourcing.witness_controller import SourceFailure

    c, calls, r, j = setup(tmp_path)

    def denied(url):
        calls.append(url)
        raise SourceFailure("SYNTHETIC HTTP429", status=429, retry_after="600")

    c.transport = denied
    with pytest.raises(AccessBlocked):
        c.acquire(r, j)
    stop = json.loads(c.stop.read_text())
    assert stop["failed_receipts"][0]["url"] == c.profile.robots_url
    assert (
        stop["failed_receipts"][0]["status"] == 429
        and stop["failed_receipts"][0]["retry_after"] == "600"
    )
    assert stop["failed_receipts"][0]["started_at"] == NOW.isoformat()
    assert c.operation_attempts == 1 and c.status()["budget"]["http_attempted"] == 1
