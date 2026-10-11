"""Counterexamples discovered by the independent Codex verifier."""

import json
import sqlite3
from decimal import Decimal

from pc_sourcing.evaluate import evaluate
from pc_sourcing.models import Offer
from pc_sourcing.pipeline import run


def test_current_global_conflict_evidence_blocks_route(sample, as_of):
    data = sample.model_dump(mode="json")
    witness = dict(
        data["evidence"][0],
        id="global-conflict-witness",
        field="global_payment_conflict",
        value="true",
    )
    data["evidence"].append(witness)
    assert data["global_payment_conflict"] is False
    result = evaluate(Offer.model_validate(data), as_of)
    assert not result.payment_gate_passed
    assert result.eligibility == "manual"
    assert result.label == "требует ручной проверки"
    assert witness["id"] in result.evidence_ids
    assert result.reasons


def test_large_json_number_retained_without_losing_valid_rows(tmp_path, sample, as_of):
    inp, db, report = (tmp_path / p for p in ("input.json", "db.sqlite", "report.md"))
    inp.write_text("[" + sample.model_dump_json() + ', {"id":"overflow","price_rub":1e400}]')
    summary = run(inp, db, report, as_of=as_of, run_id="overflow")
    assert summary["valid"] == 1
    assert summary["rejected"] == 1
    with sqlite3.connect(db) as con:
        row = con.execute("SELECT data,reason FROM rejections").fetchone()
        retained = json.loads(row[0], parse_float=Decimal)
        assert retained == {"id": "overflow", "price_rub": Decimal("1e400")}
        assert row[1]
        assert con.execute("SELECT count(*) FROM offers").fetchone()[0] == 1
    assert "overflow" in report.read_text()
    assert run(inp, db, report, as_of=as_of, run_id="overflow") == summary
