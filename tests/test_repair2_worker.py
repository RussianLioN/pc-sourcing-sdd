"""Проверки сохранения больших целых без изменения правил JSON и типов."""

import json
import sqlite3
import sys
from html import unescape

import pytest

from pc_sourcing.pipeline import _input_rows, run


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
@pytest.mark.parametrize("sign", ["", "-"])
def test_large_integers_at_multiple_depths(tmp_path, sample, as_of, encoding, sign):
    limit = sys.get_int_max_str_digits()
    token = sign + "9" * 5000
    rejected = [
        token,
        '{ "id" : ' + token + " }",
        '{"id":"nested", "evidence":[{"value":' + token + "}]}",
        "[" + token + "]",
    ]
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    inp.write_bytes(
        ("[\n" + ",\n".join([*rejected, sample.model_dump_json()]) + "\n]").encode(encoding)
    )
    summary = run(inp, db, report, as_of=as_of, run_id="large")
    assert summary["valid"] == 1
    assert summary["rejected"] == len(rejected)
    with sqlite3.connect(db) as con:
        rows = con.execute("SELECT data,reason FROM rejections ORDER BY input_index").fetchall()
        assert [raw for raw, _ in rows] == rejected
        assert all("Целое JSON превышает" in reason for _, reason in rows)
        assert con.execute("SELECT id FROM offers").fetchall() == [(sample.id,)]
        assert con.execute("SELECT count(*) FROM evidence").fetchone()[0] == len(sample.evidence)
    assert all(raw in unescape(report.read_text()) for raw in rejected)
    original_report = report.read_bytes()
    report.unlink()
    assert run(inp, db, report, as_of=as_of, run_id="large") == summary
    assert report.read_bytes() == original_report
    assert sys.get_int_max_str_digits() == limit


@pytest.mark.parametrize("sign", ["", "-"])
def test_bounded_integer_conversion_preserves_types(sign):
    limit = min(
        sys.get_int_max_str_digits() or sys.int_info.default_max_str_digits,
        sys.int_info.default_max_str_digits,
    )
    token = sign + "9" * limit
    (number, raw), (text, _) = list(_input_rows(f'[{token},"{token}"]'.encode()))
    assert type(number) is int
    assert str(number) == raw == token
    assert type(text) is str
    assert text == token


def test_long_quoted_id_remains_valid(tmp_path, sample, as_of):
    data = sample.model_dump(mode="json")
    data["id"] = "9" * 5000
    for witness in data["evidence"]:
        witness["offer_id"] = data["id"]
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    inp.write_text(json.dumps([data]))
    summary = run(inp, db, report, as_of=as_of, run_id="quoted")
    assert summary["valid"] == 1
    assert summary["rejected"] == 0
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT id FROM offers").fetchone()[0] == data["id"]


@pytest.mark.parametrize("suffix", [",]", "] trailing", "0]", ".]", "e+]", ",01]"])
def test_large_integer_does_not_hide_json_syntax_errors(tmp_path, sample, as_of, suffix):
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    # Пробел перед суффиксом не позволяет присоединить цифру к целому токену.
    inp.write_text("[" + sample.model_dump_json() + "," + "9" * 5000 + " " + suffix)
    with pytest.raises(json.JSONDecodeError):
        run(inp, db, report, as_of=as_of, run_id="syntax")
    assert not db.exists()
    assert not report.exists()
