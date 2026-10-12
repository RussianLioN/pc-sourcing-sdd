"""CHAIN-01–04: synthetic unit captures are never historical real offers."""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from pc_sourcing.collection_capture import Capture, normalize_capture

NOW = datetime(2026, 10, 12, 3, tzinfo=UTC)


def fixture_capture():
    title = "SYNTHETIC G.Skill Trident Z5 Neo DDR5 96GB 6000 CL30"
    mpn = "F5-6000J3036F48GX2-TZ5NR"
    url = "https://synthetic.example.test/ram"
    raw = json.dumps({"synthetic": True, "h1": title, "mpn": mpn, "displayed_price_rub": 12345})
    h = hashlib.sha256(raw.encode()).hexdigest()
    facts = [
        {
            "field": field,
            "value": value,
            "url": url,
            "observed_at": NOW,
            "origin": "store_card",
            "selector": "SYNTHETIC " + field,
            "content_sha256": h,
        }
        for field, value in [("title", title), ("mpn", mpn), ("displayed_price_rub", 12345)]
    ]
    return Capture.model_validate(
        {
            "request": {"name": title, "mpn": mpn, "category": "ram"},
            "observation": {
                "candidate": {
                    "url": url,
                    "title": title,
                    "queries": [],
                    "observed_at": NOW,
                    "response_sha256": h,
                },
                "status": "observed",
                "reason": "SYNTHETIC test only",
                "title": title,
                "mpn": mpn,
                "match": "exact",
                "facts": facts,
                "primary": {
                    "retained_content": raw,
                    "retained_sha256": h,
                    "content_kind": "selected_primary_metadata",
                },
            },
            "provenance": "synthetic_fixture",
            "synthetic": True,
            "artifact_sha256": h,
        }
    )


def test_mapping_preserves_origin_date_unknowns_and_displayed_alternative():
    capture = fixture_capture()
    offer = normalize_capture(capture)
    assert offer.synthetic is True
    assert offer.observed_at == NOW
    assert offer.price is None
    assert offer.conditional_prices[0].kind == "unknown"
    assert offer.conditional_prices[0].money.amount == 12345
    assert offer.available_quantity is None and offer.delivery_cost is None
    assert offer.complete_item is None and offer.seller_checked is None


def test_primary_hash_origin_and_realm_conflicts_fail_closed():
    data = fixture_capture().model_dump(mode="json")
    data["observation"]["facts"][0]["content_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        Capture.model_validate(data)
    data = fixture_capture().model_dump(mode="json")
    data["provenance"] = "cached_primary_import"
    with pytest.raises(ValueError, match="realm"):
        Capture.model_validate(data)


@pytest.mark.parametrize("match", ["unresolved", "excluded"])
def test_unresolved_and_excluded_observations_are_not_promoted(match):
    data = fixture_capture().model_dump(mode="json")
    data["observation"]["match"] = match
    assert normalize_capture(Capture.model_validate(data)) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "other title"),
        ("mpn", "OTHER-MPN"),
        ("displayed_price_rub", 99999),
        ("price_rub", 12345),
        ("stock", "in_stock"),
    ],
)
def test_fact_value_and_kind_must_match_unchanged_selected_bytes(field, value):
    data = fixture_capture().model_dump(mode="json")
    data["observation"]["facts"][2].update(field=field, value=value)
    with pytest.raises(ValueError, match="selected bytes"):
        Capture.model_validate(data)
