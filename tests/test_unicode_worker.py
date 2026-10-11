"""Изоляция Unicode до диагностики модели и учёта повторных идентификаторов."""

import json
import sqlite3
from html import unescape

import pytest

from pc_sourcing.pipeline import run


@pytest.mark.parametrize("bad", ["\ud800", "\udfff", "\udc00\ud800"])
@pytest.mark.parametrize("shape", ["scalar", "array", "key", "nested", "same_id"])
def test_unicode_rejection_preserves_neighbors(tmp_path, sample, as_of, bad, shape):
    first = sample.model_dump(mode="json")
    last = sample.model_dump(mode="json")
    last["id"] = "последний 😍"
    last["title"] = "Москва 😍 \uffff e\u0301"
    for item in last["evidence"]:
        item["offer_id"] = last["id"]
    invalid = {
        "scalar": bad,
        "array": [{"nested": [bad]}],
        "key": {"nested": [{bad: "обычная строка"}]},
        "nested": {"unknown": [{"more": [bad]}]},
        "same_id": dict(last, title=bad),
    }[shape]
    # Пробелы и написание escape-последовательностей должны сохраняться точно.
    raw = json.dumps(invalid, ensure_ascii=True, indent=2)
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    baseline = tmp_path / "baseline.sqlite"
    inp.write_text(json.dumps([first, last], ensure_ascii=False), encoding="utf-8")
    run(inp, baseline, tmp_path / "baseline.md", as_of=as_of, run_id="clean")
    inp.write_text(
        "[" + json.dumps(first) + ",\n" + raw + ",\n" + json.dumps(last) + "]",
        encoding="utf-8",
    )
    result = run(inp, db, report, as_of=as_of, run_id="mixed")
    assert result["valid"] == 2
    assert result["rejected"] == 1
    with sqlite3.connect(baseline) as before, sqlite3.connect(db) as after:
        for table in ("offers", "evaluations", "evidence"):
            assert sorted(before.execute("SELECT data FROM " + table).fetchall()) == sorted(
                after.execute("SELECT data FROM " + table).fetchall()
            )
        index, retained, reason = after.execute(
            "SELECT input_index,data,reason FROM rejections"
        ).fetchone()
        assert (index, retained) == (1, raw)
        assert "Unicode" in reason
        reason.encode("utf-8")
    assert raw in unescape(report.read_text(encoding="utf-8"))
    saved = report.read_bytes()
    report.unlink()
    assert run(inp, db, report, as_of=as_of, run_id="mixed") == result
    assert report.read_bytes() == saved


@pytest.mark.parametrize(
    "broken",
    [
        b'["\xed\xa0\x80"]',
        b'["\xff"]',
        b'\xff\xfe[\x00"\x00\x00\xd8"\x00]\x00',
        b'["\\ud800",]',
        b'["\\ud800"] trailing',
        b'["\\uZZZZ"]',
    ],
)
def test_document_errors_leave_existing_outputs_unchanged(tmp_path, sample, as_of, broken):
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    inp.write_text("[" + sample.model_dump_json() + "]", encoding="utf-8")
    run(inp, db, report, as_of=as_of, run_id="existing")
    saved_db, saved_report = db.read_bytes(), report.read_bytes()
    inp.write_bytes(broken)
    with pytest.raises((UnicodeDecodeError, json.JSONDecodeError)):
        run(inp, db, report, as_of=as_of, run_id="broken")
    assert db.read_bytes() == saved_db
    assert report.read_bytes() == saved_report
