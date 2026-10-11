"""DEF-006: invalid Unicode row isolation, original JSON and valid neighbors."""

import json
import sqlite3
from html import unescape

import pytest
from conftest import AS_OF, GOLDEN
from hypothesis import given, settings
from hypothesis import strategies as st

from pc_sourcing.models import Offer
from pc_sourcing.pipeline import run


def offer(sample, ident):
    data = sample.model_dump(mode="json")
    data["id"] = ident
    for item in data["evidence"]:
        item["offer_id"] = ident
    return data


@pytest.mark.parametrize(
    "path",
    [
        ("title",),
        ("id",),
        ("sku",),
        ("url",),
        ("region",),
        ("currency",),
        ("protected", "reason"),
        ("evidence", 0, "value"),
        ("evidence", 0, "id"),
        ("evidence", 0, "field"),
        ("evidence", 0, "url"),
        ("invalid_key",),
    ],
)
@pytest.mark.parametrize("bad", ["\ud800", "\udfff", "\udc00\ud800"])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_unpaired_unicode_rejected_with_raw_and_neighbors(
    tmp_path, sample, as_of, path, bad, encoding
):
    first, invalid, last = (offer(sample, ident) for ident in ("first", "invalid", "last"))
    if path == ("invalid_key",):
        invalid["unknown" + bad] = {"nested": ["bad" + bad]}
    else:
        node = invalid
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] += bad
        if path == ("id",):
            for item in invalid["evidence"]:
                item["offer_id"] = invalid["id"]
    encoded = json.dumps(invalid, ensure_ascii=True)
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    inp.write_bytes(
        ("[" + json.dumps(first) + "," + encoded + "," + json.dumps(last) + "]").encode(encoding)
    )
    result = run(inp, db, report, as_of=as_of, run_id="unicode")
    assert result["valid"] == 2
    assert result["rejected"] == 1
    with sqlite3.connect(db) as con:
        retained, reason = con.execute("SELECT data,reason FROM rejections").fetchone()
        assert retained == encoded
        assert "unicode" in reason.lower() or "surrogate" in reason.lower()
        reason.encode("utf-8")
        assert {row[0] for row in con.execute("SELECT id FROM offers")} == {"first", "last"}
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert encoded in unescape(report.read_text())
    original = report.read_bytes()
    report.unlink()
    assert run(inp, db, report, as_of=as_of, run_id="unicode") == result
    assert report.read_bytes() == original


@pytest.mark.parametrize("text", ["Москва 😍", "a\u0000b", "\uffff", "e\u0301", "\U00010000"])
def test_valid_unicode_not_changed(tmp_path, sample, as_of, text):
    data = offer(sample, "valid-unicode")
    data["title"] = text
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    inp.write_text(json.dumps([data], ensure_ascii=True))
    assert run(inp, db, report, as_of=as_of, run_id="valid")["valid"] == 1
    with sqlite3.connect(db) as con:
        assert json.loads(con.execute("SELECT data FROM offers").fetchone()[0])["title"] == text


@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=0xD800, max_value=0xDFFF))
def test_surrogate_class_rejects_before_serialization(tmp_path_factory, codepoint):
    folder = tmp_path_factory.mktemp("surrogate-property")
    sample = Offer.model_validate(GOLDEN["cases"][2]["offer"])
    as_of = AS_OF
    first, last = offer(sample, "before"), offer(sample, "after")
    invalid = offer(sample, "invalid-unicode")
    invalid["title"] = "prefix" + chr(codepoint) + "suffix"
    inp, db, report = (folder / p for p in ("input.json", "db.sqlite", "report.md"))
    clean = folder / "clean.json"
    clean.write_text(json.dumps([first, last]))
    baseline = folder / "baseline.sqlite"
    run(clean, baseline, folder / "baseline.md", as_of=as_of, run_id="baseline")
    inp.write_text(json.dumps([first, invalid, last]))
    result = run(inp, db, report, as_of=as_of, run_id="property")
    assert result["valid"] == 2
    assert result["rejected"] == 1
    with sqlite3.connect(baseline) as before, sqlite3.connect(db) as after:
        for table in ("offers", "evaluations", "evidence"):
            assert sorted(before.execute("SELECT data FROM " + table).fetchall()) == sorted(
                after.execute("SELECT data FROM " + table).fetchall()
            )
