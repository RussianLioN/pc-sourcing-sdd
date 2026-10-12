"""OPS-01–09: synthetic runtime, persistence, fencing, recovery and portable evidence."""

import json
import multiprocessing
import os
import signal
from datetime import UTC, datetime

import pytest

from pc_sourcing.durable_jobs import Busy, Store

NOW = datetime(2026, 10, 12, tzinfo=UTC).timestamp()
URL = "https://synthetic.example.test/card"
OTHER_URL = "https://other-synthetic.example.test/card"


def receipt(now=NOW, **changes):
    return {
        "url": URL,
        "observed_at": datetime.fromtimestamp(now, UTC).isoformat(),
        "origin": "synthetic_fixture",
        "synthetic": True,
        "facts": {"price_rub": None, "stock": "unknown", "eligible": False},
        **changes,
    }


def setup(root):
    store = Store(root)
    store.configure_source("one", limit=10, interval=5)
    job = store.enqueue("one", URL, {"mpn": "SYNTHETIC", "region": "Москва"})
    return store, job


def complete(store, job, now=NOW, value=None):
    claim = store.claim(now=now, lease_seconds=10)
    assert claim["id"] == job
    store.checkpoint(job, claim["token"], value or receipt(now), now=now)
    store.finish(job, claim["token"], now=now)


def test_reopen_enqueue_canonical_dedup_and_context(tmp_path):
    store, job = setup(tmp_path / "runtime")
    assert store.enqueue("one", URL + "#fragment", {"region": "Москва", "mpn": "SYNTHETIC"}) == job
    other = store.enqueue("one", URL, {"region": "Москва", "mpn": "OTHER"})
    assert other != job
    complete(store, job)
    reopened = Store(store.root)
    assert reopened.enqueue("one", URL, {"mpn": "SYNTHETIC", "region": "Москва"}) == job
    assert len(reopened.report()["current"]) == 1
    assert reopened.report()["current"][0]["receipt"]["facts"]["price_rub"] is None
    assert reopened.report()["current"][0]["receipt"]["synthetic"] is True


def test_expired_lease_fencing_and_checkpoint_recovery(tmp_path):
    store, job = setup(tmp_path / "runtime")
    old = store.claim(now=NOW, lease_seconds=10)
    store.checkpoint(job, old["token"], receipt(), now=NOW)
    assert store.claim(now=NOW + 1, lease_seconds=10) is None
    assert store.recover(now=NOW + 10) == 1
    new = store.claim(now=NOW + 10, lease_seconds=10)
    assert new["receipt"] == receipt()
    with pytest.raises(ValueError, match="lease"):
        store.finish(job, old["token"], now=NOW + 10)
    store.finish(job, new["token"], now=NOW + 10)
    assert len(store.report()["history"]) == 1


def test_source_stop_budget_and_cooldown_are_persistent(tmp_path):
    store, job = setup(tmp_path / "runtime")
    store.configure_source("two", limit=1, interval=0)
    other = store.enqueue("two", OTHER_URL, {})
    claim = store.claim(now=NOW, lease_seconds=10)
    store.stop_source(job, claim["token"], "synthetic HTTP 429", now=NOW)
    reopened = Store(store.root)
    assert reopened.recover(now=NOW + 20) == 0
    claim = reopened.claim(now=NOW + 20, lease_seconds=10)
    assert claim["id"] == other
    reopened.checkpoint(other, claim["token"], receipt(NOW + 20, url=OTHER_URL), now=NOW + 20)
    reopened.finish(other, claim["token"], now=NOW + 20)
    reopened.enqueue("two", OTHER_URL, {}, generation=1)
    assert reopened.claim(now=NOW + 21, lease_seconds=10) is None
    assert reopened.report()["sources"][0]["stopped_reason"] == "synthetic HTTP 429"
    with pytest.raises(ValueError):
        reopened.configure_source("one", limit=999, interval=0)


def test_history_and_current_survive_refresh_without_older_displacement(tmp_path):
    store, first = setup(tmp_path / "runtime")
    complete(store, first)
    refreshed = store.enqueue("one", URL, {"mpn": "SYNTHETIC", "region": "Москва"}, generation=1)
    complete(store, refreshed, NOW + 10)
    old = store.enqueue("one", URL, {"mpn": "SYNTHETIC", "region": "Москва"}, generation=2)
    complete(store, old, NOW + 20, receipt(NOW - 10))
    report = store.report()
    assert len(report["current"]) == 1 and len(report["history"]) == 3
    assert report["current"][0]["receipt"] == receipt(NOW + 10)


@pytest.mark.parametrize(
    "field,value",
    [
        ("synthetic", False),
        ("observed_at", "2026-10-12"),
        ("url", "https://synthetic.example.test/other"),
    ],
)
def test_invalid_receipt_cannot_checkpoint(tmp_path, field, value):
    store, job = setup(tmp_path / "runtime")
    claim = store.claim(now=NOW, lease_seconds=10)
    with pytest.raises(ValueError):
        store.checkpoint(job, claim["token"], receipt(**{field: value}), now=NOW)
    assert not store.report()["history"]


def kill_at(root, boundary, operation):
    def hook(name):
        if name == boundary:
            os.kill(os.getpid(), signal.SIGKILL)

    store = Store(root, hook=hook)
    operation(store)


@pytest.mark.parametrize(
    "boundary", ["claim", "evidence_temp", "evidence_publish", "checkpoint", "finish"]
)
def test_sigkill_fetch_boundaries_recover_without_loss_or_duplicates(tmp_path, boundary):
    store, job = setup(tmp_path / "runtime")

    def operation(worker):
        claim = worker.claim(now=NOW, lease_seconds=10)
        worker.checkpoint(job, claim["token"], receipt(), now=NOW)
        worker.finish(job, claim["token"], now=NOW)

    p = multiprocessing.get_context("fork").Process(
        target=kill_at, args=(store.root, boundary, operation)
    )
    p.start()
    p.join(5)
    assert p.exitcode == -signal.SIGKILL
    reopened = Store(store.root)
    reopened.integrity()
    reopened.recover(now=NOW + 10)
    claim = reopened.claim(now=NOW + 10, lease_seconds=10)
    if claim:
        if claim["receipt"] is None:
            reopened.checkpoint(job, claim["token"], receipt(), now=NOW + 10)
        reopened.finish(job, claim["token"], now=NOW + 10)
    assert len(reopened.report()["history"]) == 1
    assert reopened.report()["current"][0]["receipt"] == receipt()
    assert reopened.claim(now=NOW + 100, lease_seconds=10) is None


def test_backup_restore_and_tamper_fail_closed(tmp_path):
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    backup = tmp_path / "backup"
    store.backup(backup)
    restored = Store.restore(backup, tmp_path / "restored")
    assert restored.report() == store.report()
    assert restored.integrity()["status"] == "passed"
    blob = next((backup / "blobs").glob("*.json"))
    blob.write_text("{}")
    with pytest.raises(ValueError):
        Store.restore(backup, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_tampered_runtime_evidence_is_not_reported(tmp_path):
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    next((store.root / "blobs").glob("*.json")).write_text("{}")
    with pytest.raises(ValueError):
        store.report()


def test_lock_conflict_is_explicit_without_mutation(tmp_path):
    store, job = setup(tmp_path / "runtime")
    import fcntl

    with (store.root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(Busy):
            store.claim(now=NOW, lease_seconds=10)
    assert store.claim(now=NOW, lease_seconds=10)["id"] == job


@pytest.mark.parametrize(
    "boundary", ["claim_pending", "evidence_partial", "checkpoint_pending", "finish_pending"]
)
def test_sigkill_uncommitted_boundaries_keep_only_committed_data(tmp_path, boundary):
    store, job = setup(tmp_path / "runtime")

    def operation(worker):
        claim = worker.claim(now=NOW, lease_seconds=10)
        worker.checkpoint(job, claim["token"], receipt(), now=NOW)
        worker.finish(job, claim["token"], now=NOW)

    p = multiprocessing.get_context("fork").Process(
        target=kill_at, args=(store.root, boundary, operation)
    )
    p.start()
    p.join(5)
    assert p.exitcode == -signal.SIGKILL
    reopened = Store(store.root)
    reopened.recover(now=NOW + 10)
    claim = reopened.claim(now=NOW + 10, lease_seconds=10)
    if claim["receipt"] is None:
        reopened.checkpoint(job, claim["token"], receipt(), now=NOW + 10)
    reopened.finish(job, claim["token"], now=NOW + 10)
    assert len(reopened.report()["history"]) == 1
    assert reopened.report()["current"][0]["receipt"] == receipt()


@pytest.mark.parametrize("boundary", ["schema_pending", "schema"])
def test_schema_crash_reopens_without_manual_database_edit(tmp_path, boundary):
    root = tmp_path / "runtime"
    p = multiprocessing.get_context("fork").Process(
        target=kill_at, args=(root, boundary, lambda worker: None)
    )
    p.start()
    p.join(5)
    assert p.exitcode == -signal.SIGKILL
    assert Store(root).integrity()["status"] == "passed"


@pytest.mark.parametrize(
    "boundary",
    ["source_configuration_pending", "source_configuration", "enqueue_pending", "enqueue"],
)
def test_configuration_and_enqueue_crashes_are_idempotent(tmp_path, boundary):
    root = tmp_path / "runtime"
    Store(root)

    def operation(worker):
        worker.configure_source("one", limit=1, interval=0)
        worker.enqueue("one", URL, {})

    p = multiprocessing.get_context("fork").Process(
        target=kill_at, args=(root, boundary, operation)
    )
    p.start()
    p.join(5)
    assert p.exitcode == -signal.SIGKILL
    reopened = Store(root)
    operation(reopened)
    assert len(reopened.report()["sources"]) == 1
    assert len(reopened.report()["jobs"]) == 1


@pytest.mark.parametrize("boundary", ["source_stop_pending", "source_stop"])
def test_stop_transaction_crash_preserves_committed_policy(tmp_path, boundary):
    store, job = setup(tmp_path / "runtime")
    claim = store.claim(now=NOW, lease_seconds=10)

    def operation(worker):
        worker.stop_source(job, claim["token"], "synthetic CAPTCHA", now=NOW)

    p = multiprocessing.get_context("fork").Process(
        target=kill_at, args=(store.root, boundary, operation)
    )
    p.start()
    p.join(5)
    assert p.exitcode == -signal.SIGKILL
    reopened = Store(store.root)
    if boundary.endswith("pending"):
        # Uncommitted stop rolled back; explicit same denial is replayed under its lease.
        assert reopened.report()["sources"][0]["stopped_reason"] is None
        operation(reopened)
    assert reopened.report()["sources"][0]["stopped_reason"] == "synthetic CAPTCHA"
    reopened.recover(now=NOW + 20)
    assert reopened.claim(now=NOW + 20, lease_seconds=10) is None


@pytest.mark.parametrize("boundary", ["recovery_pending", "recovery"])
def test_recovery_crash_replays_without_extra_fetch(tmp_path, boundary):
    from pc_sourcing.durable_cli import work_once

    store, job = setup(tmp_path / "runtime")
    claim = store.claim(now=NOW, lease_seconds=10)
    store.checkpoint(job, claim["token"], receipt(), now=NOW)
    p = multiprocessing.get_context("fork").Process(
        target=kill_at, args=(store.root, boundary, lambda worker: worker.recover(now=NOW + 10))
    )
    p.start()
    p.join(5)
    assert p.exitcode == -signal.SIGKILL
    reopened = Store(store.root)
    reopened.recover(now=NOW + 10)

    def forbidden_fetch(job):
        raise AssertionError("checkpoint recovery must skip transport")

    assert work_once(reopened, forbidden_fetch, now=NOW + 10)["status"] == "done"
    assert len(reopened.report()["history"]) == 1


@pytest.mark.parametrize(
    "boundary",
    [
        "backup_sqlite_partial",
        "backup_sqlite",
        "backup_evidence_partial",
        "backup_evidence",
        "backup_manifest_partial",
        "backup_manifest",
        "backup_publication",
    ],
)
def test_backup_crash_publishes_only_complete_valid_snapshot(tmp_path, boundary):
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    backup = tmp_path / "backup"
    p = multiprocessing.get_context("fork").Process(
        target=kill_at, args=(store.root, boundary, lambda worker: worker.backup(backup))
    )
    p.start()
    p.join(5)
    assert p.exitcode == -signal.SIGKILL
    if not backup.exists():
        Store(store.root).backup(backup)
    restored = Store.restore(backup, tmp_path / "restored")
    assert restored.report() == store.report()


@pytest.mark.parametrize(
    "boundary", ["restore_copy_partial", "restore_staged", "restore_publication"]
)
def test_restore_crash_does_not_publish_partial_runtime(tmp_path, boundary):
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    backup = tmp_path / "backup"
    store.backup(backup)
    destination = tmp_path / "restored"

    def operation():
        def hook(name):
            if name == boundary:
                os.kill(os.getpid(), signal.SIGKILL)

        Store.restore(backup, destination, hook=hook)

    p = multiprocessing.get_context("fork").Process(target=operation)
    p.start()
    p.join(5)
    assert p.exitcode == -signal.SIGKILL
    restored = Store(destination) if destination.exists() else Store.restore(backup, destination)
    assert restored.report() == store.report()


@pytest.mark.parametrize("boundary", ["report_partial", "report_publication"])
def test_report_crash_does_not_publish_partial_json(tmp_path, boundary):
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    path = tmp_path / "report.json"
    p = multiprocessing.get_context("fork").Process(
        target=kill_at, args=(store.root, boundary, lambda worker: worker.export(path))
    )
    p.start()
    p.join(5)
    assert p.exitcode == -signal.SIGKILL
    if not path.exists():
        store.export(path)
    assert json.loads(path.read_text()) == store.report()


def test_parallel_claims_are_fenced_and_do_not_duplicate(tmp_path):
    store, job = setup(tmp_path / "runtime")
    ctx = multiprocessing.get_context("fork")
    barrier, queue = ctx.Barrier(2), ctx.Queue()

    def racer():
        worker = Store(store.root)
        barrier.wait(timeout=5)
        try:
            result = worker.claim(now=NOW, lease_seconds=10)
            queue.put(result["id"] if result else "idle")
        except Busy:
            queue.put("busy")

    processes = [ctx.Process(target=racer) for _ in range(2)]
    for p in processes:
        p.start()
    for p in processes:
        p.join(5)
        assert p.exitcode == 0
    results = [queue.get(timeout=1) for _ in processes]
    assert results.count(job) == 1
    assert store.report()["sources"][0]["spent"] == 1


def test_active_source_serialization_and_other_source_progress(tmp_path):
    store, first = setup(tmp_path / "runtime")
    store.enqueue("one", URL + "/other", {})
    store.configure_source("two", limit=1, interval=0)
    other = store.enqueue("two", OTHER_URL, {})
    assert store.claim(now=NOW, lease_seconds=10)["id"] == first
    assert store.claim(now=NOW, lease_seconds=10)["id"] == other
    assert store.claim(now=NOW + 100, lease_seconds=10) is None  # explicit recovery required


def test_checkpoint_recovery_does_not_spend_additional_transport_budget(tmp_path):
    from pc_sourcing.durable_cli import work_once

    store = Store(tmp_path / "runtime")
    store.configure_source("one", limit=1, interval=100)
    job = store.enqueue("one", URL, {})
    claim = store.claim(now=NOW, lease_seconds=10)
    store.checkpoint(job, claim["token"], receipt(), now=NOW)
    backup = tmp_path / "backup"
    store.backup(backup)
    restored = Store.restore(backup, tmp_path / "restored")
    restored.recover(now=NOW + 10)
    assert (
        work_once(restored, lambda job: pytest.fail("unexpected fetch"), now=NOW + 10)["status"]
        == "done"
    )
    assert restored.report()["sources"][0]["spent"] == 1


@pytest.mark.parametrize(
    "component", ["jobs.sqlite", "receipt", "missing_receipt", "manifest_path"]
)
def test_backup_database_missing_evidence_and_unsafe_path_rejected(tmp_path, component):
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    backup = tmp_path / "backup"
    store.backup(backup)
    if component == "jobs.sqlite":
        (backup / "jobs.sqlite").write_bytes(b"broken sqlite")
    elif component == "receipt":
        next((backup / "blobs").glob("*.json")).write_text("{}")
    elif component == "missing_receipt":
        next((backup / "blobs").glob("*.json")).unlink()
    else:
        manifest = json.loads((backup / "manifest.json").read_text())
        manifest["files"]["../outside"] = "a" * 64
        (backup / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError)):
        Store.restore(backup, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_cli_submit_work_backup_restore_and_report_e2e(tmp_path):
    import subprocess
    import sys

    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text(
        json.dumps(
            [
                {
                    "synthetic": True,
                    "source": "one",
                    "url": URL,
                    "context": {"region": "Москва"},
                    "receipt": receipt(),
                    "policy": {"budget": 1, "interval": 0},
                }
            ]
        )
    )
    root = tmp_path / "runtime"

    def cli(action, runtime=root, *extra):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pc_sourcing.durable_cli",
                action,
                "--root",
                str(runtime),
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    a = cli("submit", root, "--fixtures", str(fixtures))
    assert cli("submit", root, "--fixtures", str(fixtures))["jobs"] == a["jobs"]
    assert cli("work", root, "--fixtures", str(fixtures))["results"][0]["status"] == "done"
    assert cli("work", root, "--fixtures", str(fixtures))["results"][0]["status"] == "idle"
    backup = tmp_path / "backup"
    cli("backup", root, "--output", str(backup))
    restored = tmp_path / "restored"
    cli("restore", restored, "--backup", str(backup))
    assert cli("status", restored) == cli("status")
    report = tmp_path / "report.json"
    cli("report", restored, "--output", str(report))
    assert json.loads(report.read_text()) == Store(root).report()


def test_startup_lock_timeout_is_explicit_and_bounded(tmp_path):
    import fcntl

    store, job = setup(tmp_path / "runtime")
    before = store.report()
    with (store.root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(Busy):
            Store(store.root, startup_timeout=0)
    assert Store(store.root).report() == before


def test_source_alias_and_origin_switch_cannot_reset_domain_policy(tmp_path):
    store, job = setup(tmp_path / "runtime")
    store.configure_source("alias", limit=100, interval=0)
    with pytest.raises(ValueError, match="alias bypass"):
        store.enqueue("alias", URL, {})
    with pytest.raises(ValueError, match="change canonical origin"):
        store.enqueue("one", OTHER_URL, {})
    assert len(store.report()["jobs"]) == 1


def test_corrupted_job_state_is_rejected_on_reopen(tmp_path):
    import sqlite3

    store, job = setup(tmp_path / "runtime")
    with sqlite3.connect(store.root / "jobs.sqlite") as db:
        db.execute("UPDATE jobs SET state='done' WHERE id=?", (job,))
    with pytest.raises(ValueError, match="checkpoint missing"):
        Store(store.root)


def test_source_cooldown_and_context_refresh_have_independent_keys(tmp_path):
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    refreshed = store.enqueue("one", URL, {"mpn": "SYNTHETIC", "region": "Москва"}, generation=1)
    assert store.claim(now=NOW + 4, lease_seconds=10) is None
    claim = store.claim(now=NOW + 5, lease_seconds=10)
    assert claim["id"] == refreshed
    store.checkpoint(refreshed, claim["token"], receipt(NOW + 5), now=NOW + 5)
    store.finish(refreshed, claim["token"], now=NOW + 5)
    assert len(store.report()["current"]) == 1 and len(store.report()["history"]) == 2


def test_no_overwrite_of_reports_backups_or_restore_roots(tmp_path):
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    report = tmp_path / "report.json"
    store.export(report)
    before = report.read_bytes()
    with pytest.raises(ValueError):
        store.export(report)
    assert report.read_bytes() == before
    backup = tmp_path / "backup"
    store.backup(backup)
    with pytest.raises(ValueError):
        store.backup(backup)
    with pytest.raises(ValueError):
        Store.restore(backup, store.root)
    assert store.integrity()["status"] == "passed"


def test_same_receipt_refresh_keeps_single_history_and_current(tmp_path):
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    new = store.enqueue("one", URL, {"mpn": "SYNTHETIC", "region": "Москва"}, generation=1)
    complete(store, new, NOW + 10, receipt())
    assert len(store.report()["current"]) == 1 and len(store.report()["history"]) == 1
    assert len(store.report()["jobs"]) == 2


def test_backup_concurrent_mutation_is_rejected_before_publish(tmp_path):
    import fcntl

    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    with (store.root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(Busy):
            store.backup(tmp_path / "backup")
    assert not (tmp_path / "backup").exists()
    assert store.report()["current"][0]["receipt"] == receipt()


def test_stale_worker_cannot_checkpoint_after_new_owner_claims(tmp_path):
    store, job = setup(tmp_path / "runtime")
    old = store.claim(now=NOW, lease_seconds=10)
    store.recover(now=NOW + 10)
    new = store.claim(now=NOW + 10, lease_seconds=10)
    with pytest.raises(ValueError, match="lease"):
        store.checkpoint(job, old["token"], receipt(), now=NOW + 10)
    assert not list((store.root / "blobs").glob("*.json"))
    store.checkpoint(job, new["token"], receipt(), now=NOW + 10)
    store.finish(job, new["token"], now=NOW + 10)
    assert len(store.report()["history"]) == 1


def test_cli_recovers_sigkill_checkpoint_without_fetch_or_extra_budget(tmp_path):
    import subprocess
    import sys
    import time

    start = time.time() - 100
    payload = receipt(start - 1)
    store = Store(tmp_path / "runtime")
    store.configure_source("one", limit=1, interval=10)
    job = store.enqueue("one", URL, {"region": "Москва"})
    program = """import os,sys,json,signal
from pathlib import Path
from pc_sourcing.durable_jobs import Store
from pc_sourcing.durable_cli import work_once
root=Path(sys.argv[1]);payload=json.loads(sys.argv[2]);now=float(sys.argv[3])
def hook(name):
 if name=='checkpoint':os.kill(os.getpid(),signal.SIGKILL)
work_once(Store(root,hook=hook),lambda job:payload,now=now,lease_seconds=10)
"""
    killed = subprocess.run(
        [sys.executable, "-c", program, str(store.root), json.dumps(payload), str(start)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert killed.returncode == -signal.SIGKILL
    fixtures = tmp_path / "fixtures.json"
    fixtures.write_text(
        json.dumps(
            [
                {
                    "synthetic": True,
                    "source": "one",
                    "url": URL,
                    "context": {"region": "Москва"},
                    "blocked_reason": "SYNTHETIC: unexpected fetch after checkpoint must fail",
                }
            ]
        )
    )

    def cli(action, *extra):
        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "pc_sourcing.durable_cli",
                action,
                "--root",
                str(store.root),
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert p.returncode == 0, p.stderr
        return json.loads(p.stdout)

    assert cli("recover")["expired_leases_recovered"] == 1
    assert cli("work", "--fixtures", str(fixtures))["results"][0]["status"] == "done"
    status = cli("status")
    assert len(status["history"]) == 1 and status["jobs"][0]["id"] == job
    assert status["sources"][0]["spent"] == 1 and status["sources"][0]["stopped_reason"] is None
    assert status["current"][0]["receipt"] == payload


def test_runtime_and_backup_symlinks_cannot_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "alias").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        Store(tmp_path / "alias")
    store, job = setup(tmp_path / "runtime")
    complete(store, job)
    backup = tmp_path / "backup"
    store.backup(backup)
    blob = next((backup / "blobs").glob("*.json"))
    saved = outside / "receipt.json"
    saved.write_bytes(blob.read_bytes())
    blob.unlink()
    blob.symlink_to(saved)
    with pytest.raises(ValueError, match="symlink"):
        Store.restore(backup, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_missing_runtime_argument_reports_failure_without_creating_root(tmp_path):
    import subprocess
    import sys

    root = tmp_path / "never-created"
    p = subprocess.run(
        [sys.executable, "-m", "pc_sourcing.durable_cli", "submit", "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert p.returncode == 1 and json.loads(p.stderr)["status"] == "failed"
    assert not root.exists()
