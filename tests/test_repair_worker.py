"""Проверки исправлений T003 без изменения независимых регрессий."""

import json
import sqlite3
from datetime import timedelta
from html import unescape

import pytest

from pc_sourcing.evaluate import evaluate
from pc_sourcing.models import Offer
from pc_sourcing.pipeline import run


@pytest.mark.parametrize("case_id", ["protected-only", "postpay-only", "both"])
@pytest.mark.parametrize("opposing", [False, True])
def test_global_conflict_blocks_each_route(corpus, as_of, case_id, opposing):
    data = json.loads(
        json.dumps(next(c["offer"] for c in corpus["cases"] if c["offer"]["id"] == case_id))
    )
    witness = dict(
        data["evidence"][0], id="conflict", field="global_payment_conflict", value="true"
    )
    data["evidence"].append(witness)
    if opposing:
        data["evidence"].append(dict(witness, id="no-conflict", value="false"))
    result = evaluate(Offer.model_validate(data), as_of)
    assert not result.payment_gate_passed
    assert result.passed_routes == ()
    assert result.label == "требует ручной проверки"
    assert "conflict" in result.evidence_ids
    assert "Глобальный конфликт условий оплаты" in result.reasons


@pytest.mark.parametrize(
    ("origin", "age", "blocked"),
    [
        ("seller_statement", timedelta(hours=24), True),
        ("platform_transaction", timedelta(), True),
        ("store_card", timedelta(), True),
        ("search_snippet", timedelta(), False),
        ("seller_statement", timedelta(hours=24, microseconds=1), False),
        ("seller_statement", timedelta(microseconds=-1), False),
    ],
)
def test_conflict_uses_current_supported_evidence(sample, as_of, origin, age, blocked):
    data = sample.model_dump(mode="json")
    data["evidence"].append(
        dict(
            data["evidence"][0],
            id="conflict",
            field="global_payment_conflict",
            value="true",
            origin=origin,
            observed_at=(as_of - age).isoformat(),
        )
    )
    result = evaluate(Offer.model_validate(data), as_of)
    assert result.payment_gate_passed is not blocked
    assert "conflict" in result.evidence_ids


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-32"])
def test_raw_numbers_survive_rejection_and_report_recovery(tmp_path, sample, as_of, encoding):
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    rejected = [
        '{ "id": "overflow", "price_rub": 1e400 }',
        '{"id":"nested","extra":[-1E+400,1.2300e-400,9007199254740993]}',
        "-1e400",
        '"строка с разделителями ], { и числом 1e400"',
        '{"id":"overflow","price_rub":2.000e+400}',
    ]
    inp.write_bytes(
        (" \n[\n" + ",\n".join([*rejected, sample.model_dump_json()]) + "\n]\t").encode(encoding)
    )
    summary = run(inp, db, report, as_of=as_of, run_id="raw")
    assert summary["valid"] == 1
    assert summary["rejected"] == len(rejected)
    with sqlite3.connect(db) as con:
        rows = con.execute("SELECT data,reason FROM rejections ORDER BY input_index").fetchall()
        assert [raw for raw, _ in rows] == rejected
        assert all(reason for _, reason in rows)
        assert con.execute("SELECT count(*) FROM offers").fetchone()[0] == 1
    before = report.read_bytes()
    assert all(raw in unescape(report.read_text()) for raw in rejected)
    report.unlink()
    assert run(inp, db, report, as_of=as_of, run_id="raw") == summary
    assert report.read_bytes() == before


@pytest.mark.parametrize(
    "suffix", [",]", "] trailing", ",", ",NaN]", ",Infinity]", ",-Infinity]", ",01]"]
)
def test_invalid_document_never_creates_partial_run(tmp_path, sample, as_of, suffix):
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    inp.write_text("[" + sample.model_dump_json() + suffix)
    with pytest.raises(ValueError):
        run(inp, db, report, as_of=as_of, run_id="invalid")
    assert not db.exists()
    assert not report.exists()
