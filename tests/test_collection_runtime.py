"""CHAIN-05–08: restart uses committed capture, never refetches a source."""

from datetime import timedelta

import pytest
from test_collection_capture import NOW, fixture_capture

from pc_sourcing.collection_runtime import Journal
from pc_sourcing.durable_jobs import Store
from pc_sourcing.normalized_exports import verify_bundle


def crash(_):
    raise RuntimeError("injected crash")


def test_persistent_import_work_report_restore_idempotency(tmp_path):
    j = Journal(tmp_path / "runtime")
    c = fixture_capture()
    assert j.submit([c]) == j.submit([c])
    assert j.work()["status"] == "done"
    assert j.work()["status"] == "idle"
    j.report(tmp_path / "report", NOW + timedelta(hours=2))
    assert verify_bundle(tmp_path / "report/offers")["formats"] == 5
    j.backup(tmp_path / "backup")
    restored = Journal.restore(tmp_path / "backup", tmp_path / "restored")
    assert restored.status() == j.status()
    assert restored.status()["source_calls"] == 0


def test_capture_fsynced_before_submission_failure_reimport_is_safe(tmp_path):
    j = Journal(tmp_path / "runtime")
    c = fixture_capture()
    with pytest.raises(RuntimeError):
        j.submit([c], hook=crash)
    assert j.status()["jobs"] == []
    j.submit([c])
    assert j.work()["status"] == "done"


def test_claim_crash_and_expired_lease_recover_from_capture(tmp_path):
    j = Journal(tmp_path / "runtime")
    j.submit([fixture_capture()])
    with pytest.raises(RuntimeError):
        j.work(now=100, lease=10, hook=crash)
    assert j.status()["jobs"][0]["state"] == "claimed"
    assert j.recover(now=111) == 1
    assert j.work(now=112)["status"] == "done"
    assert j.status()["source_calls"] == 0


def test_finished_transaction_fault_does_not_claim_success(tmp_path):
    j = Journal(tmp_path / "runtime")
    j.submit([fixture_capture()])

    def hook(phase):
        if phase == "finish_pending":
            crash(phase)

    with pytest.raises(RuntimeError):
        j.work(now=100, lease=10, hook=hook)
    assert j.status()["jobs"][0]["state"] == "claimed"
    j.recover(now=111)
    assert j.work(now=112)["status"] == "done"


def test_new_journal_cannot_relabel_or_use_old_synthetic_root(tmp_path):
    Store(tmp_path / "synthetic")
    with pytest.raises(ValueError, match="separate"):
        Journal(tmp_path / "synthetic")


def test_tampered_blob_and_backup_fail_before_report_publication(tmp_path):
    j = Journal(tmp_path / "runtime")
    j.submit([fixture_capture()])
    j.work()
    j.backup(tmp_path / "backup")
    blob = next((tmp_path / "backup/blobs").glob("*.json"))
    blob.write_text("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        Journal.restore(tmp_path / "backup", tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


@pytest.mark.parametrize("mutation", ["output", "realm", "column", "trigger", "event"])
def test_journal_tamper_rejected_before_report(tmp_path, mutation):
    import json

    j = Journal(tmp_path / "runtime")
    j.submit([fixture_capture()])
    j.work()
    with j.connect() as db:
        if mutation == "output":
            output = json.loads(db.execute("SELECT output FROM jobs").fetchone()[0])
            output["source_match"] = "excluded"
            db.execute("UPDATE jobs SET output=?", (json.dumps(output),))
        elif mutation == "realm":
            db.execute("UPDATE jobs SET realm=0")
        elif mutation == "column":
            db.execute("ALTER TABLE jobs ADD COLUMN unexpected TEXT")
        elif mutation == "trigger":
            db.execute("CREATE TRIGGER unexpected AFTER INSERT ON jobs BEGIN SELECT 1; END")
        else:
            db.execute("INSERT INTO events VALUES ('forged','{}')")
    with pytest.raises(ValueError):
        Journal(tmp_path / "runtime")
    assert not (tmp_path / "report").exists()


def test_unresolved_capture_cannot_export_injected_buyer_ready_offer(tmp_path):
    import json

    from test_normalized_offers import proven, row

    from pc_sourcing.collection_capture import Capture

    c = fixture_capture().model_dump(mode="json")
    c["observation"]["match"] = "unresolved"
    c = Capture.model_validate(c)
    j = Journal(tmp_path / "runtime")
    j.submit([c])
    j.work()
    fake = proven(row())
    fake["synthetic"] = False
    for e in fake["evidence"]:
        e["synthetic"] = False
    with j.connect() as db:
        output = json.loads(db.execute("SELECT output FROM jobs").fetchone()[0])
        output["offer"] = fake
        db.execute("UPDATE jobs SET output=?", (json.dumps(output),))
    with pytest.raises(ValueError, match="bound capture projection"):
        j.report(tmp_path / "report", NOW)
    assert not (tmp_path / "report").exists()
