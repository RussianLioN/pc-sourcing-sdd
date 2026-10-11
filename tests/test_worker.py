"""Пограничные проверки исполнителя без изменений эталонного набора."""

import json
import sqlite3
from datetime import timedelta
from html import unescape
from pathlib import Path

import pytest

from pc_sourcing.evaluate import evaluate
from pc_sourcing.models import Offer
from pc_sourcing.pipeline import run


@pytest.mark.parametrize("field", ["covers_item", "covers_amount", "covers_region", "covers_order"])
def test_partial_route_fails(sample, as_of, field):
    data = sample.model_dump(mode="json")
    data["postpay"][field] = False
    result = evaluate(Offer.model_validate(data), as_of)
    assert not result.payment_gate_passed
    assert field in " ".join(result.reasons)


@pytest.mark.parametrize("value", [None, True])
def test_unknown_or_required_route_advance(sample, as_of, value):
    data = sample.model_dump(mode="json")
    data["postpay"]["external_advance_required"] = value
    assert not evaluate(Offer.model_validate(data), as_of).payment_gate_passed


@pytest.mark.parametrize(
    ("age", "passed"),
    [
        (timedelta(hours=24), True),
        (timedelta(hours=24, microseconds=1), False),
        (timedelta(microseconds=-1), False),
    ],
)
def test_exact_freshness_boundary(sample, as_of, age, passed):
    data = sample.model_dump(mode="json")
    for evidence in data["evidence"]:
        evidence["observed_at"] = (as_of - age).isoformat()
    assert evaluate(Offer.model_validate(data), as_of).payment_gate_passed == passed


@pytest.mark.parametrize(
    "field",
    ["sku", "price_rub", "stock", "region", "condition", "seller_checked", "factory_liquid"],
)
@pytest.mark.parametrize("mutation", ["missing", "mismatch", "snippet", "conflict"])
def test_every_required_field_needs_matching_evidence(corpus, as_of, field, mutation):
    data = next(c["offer"] for c in corpus["cases"] if c["offer"]["id"] == "gpu-verified")
    data = json.loads(json.dumps(data))
    evidence = next(e for e in data["evidence"] if e["field"] == field)
    if mutation == "missing":
        data["evidence"].remove(evidence)
    elif mutation == "mismatch":
        evidence["value"] = "другое значение"
    elif mutation == "snippet":
        evidence["origin"] = "search_snippet"
    else:
        data["evidence"].append(dict(evidence, id="conflicting-record", value="другое значение"))
    assert not evaluate(Offer.model_validate(data), as_of).eligible


def test_protected_cannot_use_seller_claim(corpus, as_of):
    data = next(c["offer"] for c in corpus["cases"] if c["offer"]["id"] == "protected-only")
    data = json.loads(json.dumps(data))
    for evidence in data["evidence"]:
        evidence["origin"] = "seller_statement"
    assert not evaluate(Offer.model_validate(data), as_of).payment_gate_passed


def test_conflict_reason_survives_independent_route(corpus, as_of):
    data = next(c["offer"] for c in corpus["cases"] if c["offer"]["id"] == "protected-conflict")
    result = evaluate(Offer.model_validate(data), as_of)
    assert result.payment_gate_passed
    assert any("protected" in r and "conflict" in r for r in result.reasons)
    assert any(data["protected"]["reason"] in r for r in result.reasons)


def test_naive_as_of_rejected(sample, as_of):
    with pytest.raises(ValueError, match="часовой пояс"):
        evaluate(sample, as_of.replace(tzinfo=None))


def prepare(tmp_path, sample):
    inp, db, report = (tmp_path / name for name in ("input.json", "db.sqlite", "report.md"))
    inp.write_text(json.dumps([sample.model_dump(mode="json")]), encoding="utf-8")
    return inp, db, report


def test_all_malformed_rows_and_duplicates_retained(tmp_path, sample, as_of):
    inp, db, report = prepare(tmp_path, sample)
    rows = [None, 3, "bad", [], {"id": "broken"}, {"id": "broken"}]
    inp.write_text(json.dumps(rows), encoding="utf-8")
    assert run(inp, db, report, as_of=as_of, run_id="rejects")["rejected"] == len(rows)
    with sqlite3.connect(db) as con:
        stored = con.execute(
            "SELECT input_index, data, reason FROM rejections ORDER BY input_index"
        )
        for index, raw, reason in stored:
            assert json.loads(raw) == rows[index]
            assert reason
            assert reason in unescape(report.read_text())


@pytest.mark.parametrize("part", ["as_of", "spec.md", "evaluate.py", "models.py"])
def test_fingerprint_binds_time_spec_and_code(tmp_path, sample, as_of, monkeypatch, part):
    inp, db, report = prepare(tmp_path, sample)
    run(inp, db, report, as_of=as_of, run_id="bound")
    before = report.read_bytes()
    original = Path.read_bytes
    if part == "as_of":
        as_of += timedelta(seconds=1)
    else:

        def changed(path):
            data = original(path)
            return data + b"\n" if path.name == part else data

        monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(ValueError, match="fingerprint"):
        run(inp, db, report, as_of=as_of, run_id="bound")
    assert report.read_bytes() == before


def test_report_preparation_failure_rolls_back(tmp_path, sample, as_of, monkeypatch):
    inp, db, report = prepare(tmp_path, sample)
    run(inp, db, report, as_of=as_of, run_id="old")
    before = report.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("тестовый сбой записи")

    monkeypatch.setattr("pc_sourcing.pipeline.tempfile.NamedTemporaryFile", fail)
    with pytest.raises(OSError, match="тестовый сбой"):
        run(inp, db, report, as_of=as_of, run_id="new")
    with sqlite3.connect(db) as con:
        for table in ("runs", "offers", "evaluations", "evidence", "rejections"):
            assert (
                con.execute(f"SELECT count(*) FROM {table} WHERE run_id='new'").fetchone()[0] == 0
            )
    assert report.read_bytes() == before


def test_committed_run_restores_report_after_replace_failure(tmp_path, sample, as_of, monkeypatch):
    inp, db, report = prepare(tmp_path, sample)

    def fail(*args, **kwargs):
        raise OSError("тестовый сбой замены")

    with monkeypatch.context() as patch:
        patch.setattr("pc_sourcing.pipeline.os.replace", fail)
        with pytest.raises(OSError, match="тестовый сбой"):
            run(inp, db, report, as_of=as_of, run_id="recover")
    result = run(inp, db, report, as_of=as_of, run_id="recover")
    assert result["valid"] == 1
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT count(*) FROM offers").fetchone()[0] == 1
        evaluation = con.execute("SELECT data FROM evaluations").fetchone()[0]
        assert evaluation in unescape(report.read_text())
    assert not list(tmp_path.glob(".pc-report-*"))


def test_evidence_insert_failure_rolls_back_whole_run(tmp_path, sample, as_of):
    inp, db, report = prepare(tmp_path, sample)
    run(inp, db, report, as_of=as_of, run_id="old")
    before = report.read_bytes()
    with sqlite3.connect(db) as con:
        con.execute(
            "CREATE TRIGGER fail_insert BEFORE INSERT ON evidence "
            "BEGIN SELECT RAISE(ABORT, 'test failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        run(inp, db, report, as_of=as_of, run_id="new")
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT count(*) FROM runs").fetchone()[0] == 1
        assert con.execute("SELECT count(*) FROM offers").fetchone()[0] == 1
    assert report.read_bytes() == before
