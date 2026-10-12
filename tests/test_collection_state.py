"""Shared source stops and spent budget travel without a reset or overwrite."""

import json
import sqlite3

import pytest
from test_collection_acquisition import setup

from pc_sourcing.collection_acquisition import Acquisition
from pc_sourcing.collection_runtime import Journal
from pc_sourcing.collection_state import backup_state, restore_state


def test_spent_source_state_restore_keeps_budget_checkpoint_and_stops(tmp_path):
    a, calls, r, j = setup(tmp_path)
    a.acquire(r, j)
    stop = a.state_dir / "tavily-stop.json"
    raw = b'{"endpoint":"https://api.tavily.com/search","reason":"SYNTHETIC stop"}\n'
    stop.write_bytes(raw)
    backup_state(a.state_dir, tmp_path / "snapshot")
    restore_state(tmp_path / "snapshot", tmp_path / "new-state")
    assert (tmp_path / "new-state/tavily-stop.json").read_bytes() == raw
    restored = Acquisition(
        state_dir=tmp_path / "new-state",
        registry=a.registry,
        transport=a.transport,
        sleep=lambda _: None,
    )
    assert restored.status()["budget"] == a.status()["budget"]
    assert restored.acquire(r, Journal(tmp_path / "new-runtime"))["http_calls"] == 0
    assert len(calls) == 2
    with pytest.raises(ValueError, match="overwritten"):
        restore_state(tmp_path / "snapshot", a.state_dir)


@pytest.mark.parametrize("mutation", ["file", "path", "budget"])
def test_source_snapshot_tamper_rejected_before_publish(tmp_path, mutation):
    a, calls, r, j = setup(tmp_path)
    a.acquire(r, j)
    backup_state(a.state_dir, tmp_path / "snapshot")
    manifest = tmp_path / "snapshot/manifest.json"
    data = json.loads(manifest.read_bytes())
    if mutation == "path":
        data["files"]["../outside.json"] = "0" * 64
        manifest.write_text(json.dumps(data))
    elif mutation == "file":
        (tmp_path / "snapshot/28bit-acquisition.sqlite").write_bytes(b"bad")
    else:
        dbpath = tmp_path / "snapshot/28bit-acquisition.sqlite"
        with sqlite3.connect(dbpath) as db:
            db.execute("DELETE FROM budget")
        from pc_sourcing.durable_jobs import digest

        data["files"]["28bit-acquisition.sqlite"] = digest(dbpath.read_bytes())
        manifest.write_text(json.dumps(data))
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        restore_state(tmp_path / "snapshot", tmp_path / "restored")
    assert not (tmp_path / "restored").exists()
