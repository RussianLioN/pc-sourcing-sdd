import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pc_sourcing.evaluate import evaluate
from pc_sourcing.models import Offer

GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "fixtures/golden.json").read_text())


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda c: c["offer"]["id"])
def test_golden(case, as_of):
    offer = Offer.model_validate(case["offer"])
    result = evaluate(offer, as_of)
    for field, value in case["expected"].items():
        actual = getattr(result, field)
        assert list(actual) == value if isinstance(actual, tuple) else actual == value
    assert result.synthetic
    assert result.evidence_ids
    if result.eligibility == "manual":
        assert result.label == "требует ручной проверки"
        assert result.reasons
    if offer.stock == "preorder":
        assert not result.eligible


@given(
    st.sampled_from(["protected", "postpay"]),
    st.sampled_from(["unknown", "conflict", "confirmed_unavailable"]),
)
def test_or_symmetric_independent_route(route, other_status):
    from datetime import datetime

    confirmed_id = "protected-only" if route == "protected" else "postpay-only"
    data = next(c["offer"] for c in GOLDEN["cases"] if c["offer"]["id"] == confirmed_id)
    data = json.loads(json.dumps(data))
    other = "postpay" if route == "protected" else "protected"
    data[other] = {"status": other_status}
    result = evaluate(
        Offer.model_validate(data), datetime.fromisoformat(GOLDEN["as_of"].replace("Z", "+00:00"))
    )
    assert result.payment_gate_passed
    assert result.passed_routes == (route,)


def test_snippet_never_promoted(corpus, as_of):
    data = next(c["offer"] for c in corpus["cases"] if c["offer"]["id"] == "gpu-verified")
    offer = Offer.model_validate(dict(data, source="snippet"))
    assert evaluate(offer, as_of).eligibility == "candidate"


def test_missing_or_stale_evidence_blocks(corpus, as_of):
    data = json.loads(
        json.dumps(next(c["offer"] for c in corpus["cases"] if c["offer"]["id"] == "gpu-verified"))
    )
    data["evidence"] = [e for e in data["evidence"] if e["field"] != "price_rub"]
    assert not evaluate(Offer.model_validate(data), as_of).eligible
    for e in data["evidence"]:
        e["observed_at"] = "2025-10-11T10:00:00Z"
    assert not evaluate(Offer.model_validate(data), as_of).eligible


@given(st.booleans(), st.booleans())
def test_global_block_dominates(advance, conflict):
    from datetime import datetime

    data = json.loads(
        json.dumps(next(c["offer"] for c in GOLDEN["cases"] if c["offer"]["id"] == "both"))
    )
    data["global_advance_required"] = advance
    data["global_payment_conflict"] = conflict
    for e in data["evidence"]:
        if e["field"] == "global_advance_required":
            e["value"] = str(advance).lower()
    result = evaluate(
        Offer.model_validate(data), datetime.fromisoformat(GOLDEN["as_of"].replace("Z", "+00:00"))
    )
    assert result.payment_gate_passed == (not advance and not conflict)


def test_route_evidence_value_must_match(sample, as_of):
    data = sample.model_dump(mode="json")
    for e in data["evidence"]:
        if e["field"] == "postpay_route":
            e["value"] = "confirmed_unavailable"
    assert not evaluate(Offer.model_validate(data), as_of).payment_gate_passed
