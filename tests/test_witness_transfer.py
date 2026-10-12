"""WIT-09 complete synthetic source state and old/new immutable evidence transfer."""

import json

import pytest
from test_witness_controller import setup

from pc_sourcing.collection_runtime import Journal
from pc_sourcing.witness_controller import Controller
from pc_sourcing.witness_transfer import backup, restore


def test_full_source_transfer_keeps_spent_budget_tokens_stops_and_reuses_zero_http(tmp_path):
    c, calls, r, j = setup(tmp_path)
    c.acquire(r, j)
    stop = c.state_dir / "tavily-stop.json"
    raw = b'{"endpoint":"https://api.tavily.com/search","reason":"SYNTHETIC fixture stop"}\n'
    stop.write_bytes(raw)
    backup(c.state_dir, tmp_path / "snapshot")
    restore(tmp_path / "snapshot", tmp_path / "restored-state")
    again = Controller(
        c.key,
        state_dir=tmp_path / "restored-state",
        transport=c.transport,
        now=c.now,
        sleep=lambda _: None,
    )
    assert again.status()["budget"] == c.status()["budget"]
    assert (again.state_dir / "tavily-stop.json").read_bytes() == raw
    assert (
        again.acquire(r, Journal(tmp_path / "fresh-runtime"))["http_calls"] == 0 and len(calls) == 2
    )
    with pytest.raises(ValueError, match="overwritten"):
        restore(tmp_path / "snapshot", c.state_dir)


@pytest.mark.parametrize("mutation", ["file", "path", "missing_marker"])
def test_snapshot_tamper_or_missing_marker_refuses_before_publication(tmp_path, mutation):
    c, calls, r, j = setup(tmp_path)
    c.acquire(r, j)
    backup(c.state_dir, tmp_path / "snapshot")
    root = tmp_path / "snapshot"
    p = root / "manifest.json"
    m = json.loads(p.read_text())
    if mutation == "file":
        (root / (c.key + "-witness.sqlite")).write_bytes(b"bad")
    elif mutation == "path":
        m["files"]["../escape.json"] = "0" * 64
        p.write_text(json.dumps(m))
    else:
        m["files"].pop(c.marker.name)
        p.write_text(json.dumps(m))
    with pytest.raises((ValueError, __import__("sqlite3").DatabaseError)):
        restore(root, tmp_path / "destination")
    assert not (tmp_path / "destination").exists()


def test_unknown_prior_domain_budget_file_cannot_be_omitted_from_backup(tmp_path):
    c, calls, r, j = setup(tmp_path)
    (c.state_dir / "tdvat-acquisition.sqlite").write_bytes(
        b"prior unknown budget must not disappear"
    )
    with pytest.raises(ValueError, match="silently omitted"):
        backup(c.state_dir, tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()
