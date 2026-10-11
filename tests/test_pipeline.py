import json
import sqlite3

import pytest
from pc_sourcing.pipeline import run


def inputs(tmp_path, corpus, invalid=False):
    data = [c["offer"] for c in corpus["cases"]]
    if invalid:
        from pathlib import Path

        data += json.loads(
            (Path(__file__).resolve().parents[1] / "fixtures/invalid.json").read_text()
        )
        data.append(data[0])
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    return path


def test_sqlite_report_and_idempotency(tmp_path, corpus, as_of):
    inp = inputs(tmp_path, corpus)
    db, report = tmp_path / "pilot.sqlite", tmp_path / "report.md"
    first = run(inp, db, report, as_of=as_of, run_id="contract")
    assert first["valid"] == 20
    assert first["eligible"] == 3
    assert first["rejected"] == 0
    with sqlite3.connect(db) as con:
        rows = con.execute("SELECT data FROM evaluations WHERE run_id='contract'").fetchall()
        assert len(rows) == 20
        for (raw,) in rows:
            result = json.loads(raw)
            assert result["synthetic"]
            assert result["offer_id"] in report.read_text()
            assert result["label"] in report.read_text()
        assert con.execute("SELECT count(*) FROM evidence").fetchone()[0] > 100
        assert sum(json.loads(raw)["eligible"] for (raw,) in rows) == first["eligible"]
    before = report.read_bytes()
    assert run(inp, db, report, as_of=as_of, run_id="contract") == first
    assert report.read_bytes() == before
    assert "ТЕСТОВЫЕ" in report.read_text()
    assert "https://fixture.example.test/" in report.read_text()
    assert "2026-10-11" in report.read_text()
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT count(*) FROM offers").fetchone()[0] == 20
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_invalid_rows_retained(tmp_path, corpus, as_of):
    inp = inputs(tmp_path, corpus, invalid=True)
    db, report = tmp_path / "rejections.sqlite", tmp_path / "rejections.md"
    result = run(inp, db, report, as_of=as_of, run_id="rejects")
    assert result["valid"] == 20
    assert result["rejected"] == 3
    with sqlite3.connect(db) as con:
        rows = con.execute("SELECT data, reason FROM rejections").fetchall()
        assert len(rows) == 3
        assert all(reason for _, reason in rows)
        assert any(json.loads(raw).get("id") == "broken-input" for raw, _ in rows)
    assert "broken-input" in report.read_text()
    assert "invalid-zero" in report.read_text()


def test_changed_input_same_run_rejected(tmp_path, corpus, as_of):
    inp = inputs(tmp_path, corpus)
    db, report = tmp_path / "pilot.sqlite", tmp_path / "report.md"
    run(inp, db, report, as_of=as_of, run_id="fixed")
    data = json.loads(inp.read_text())
    data[0]["title"] = "changed"
    inp.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="fingerprint"):
        run(inp, db, report, as_of=as_of, run_id="fixed")


def test_independent_run_resources(tmp_path, corpus, as_of):
    inp = inputs(tmp_path, corpus)
    for worker in ("one", "two"):
        loc = tmp_path / worker
        loc.mkdir()
        assert (
            run(inp, loc / "db.sqlite", loc / "out.md", as_of=as_of, run_id=worker)["valid"] == 20
        )
    assert (tmp_path / "one/db.sqlite").resolve() != (tmp_path / "two/db.sqlite").resolve()
