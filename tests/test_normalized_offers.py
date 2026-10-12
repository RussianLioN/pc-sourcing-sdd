"""OFFER-01–08: explicit nulls, field proof, current source data and unchanged PAY OR."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from pc_sourcing.normalized_models import Money, NormalizedOffer
from pc_sourcing.normalized_offers import compare, evaluate_offer

NOW = datetime(2026, 10, 12, 3, tzinfo=UTC)


def row(**changes):
    return {
        "id": "offer-one",
        "request": {
            "name": "MSI RTX 5090 SUPRIM LIQUID OC",
            "mpn": "G5090-32SLC",
            "category": "gpu",
            "quantity": 1,
            "region": "Москва",
        },
        "title": "MSI RTX 5090 SUPRIM LIQUID OC",
        "mpn": "G5090-32SLC",
        "source": "store",
        "url": "https://synthetic.example.test/card",
        "observed_at": NOW.isoformat(),
        "synthetic": True,
        "available_quantity": 1,
        "complete_item": True,
        "condition": "sealed",
        "warranty": {
            "issuer": "synthetic store",
            "months": 12,
            "territory": "Россия",
            "applicable_moscow": True,
        },
        "fulfillment": {
            "city": "Москва",
            "method": "delivery",
            "confirmed": True,
            "terms": "SYNTHETIC",
        },
        "stock": "in_stock",
        "seller_name": "SYNTHETIC",
        "seller_entity_key": "SYNTHETIC-ENTITY",
        "seller_checked": True,
        "factory_liquid": True,
        "price": {
            "id": "regular",
            "money": {"amount": "450000.00", "currency": "RUB"},
            "kind": "unconditional",
            "basis": "unit",
            "quantity": 1,
        },
        "delivery_cost": {"amount": "0", "currency": "RUB"},
        "other_cost": {"amount": "0", "currency": "RUB"},
        "global_advance_required": False,
        "global_payment_conflict": False,
        "evidence": [],
        **changes,
    }


def proven(data):
    data = dict(data)
    data["evidence"] = []
    fields = [
        "title",
        "mpn",
        "available_quantity",
        "complete_item",
        "condition",
        "warranty",
        "fulfillment",
        "stock",
        "seller_entity_key",
        "seller_checked",
        "factory_liquid",
        "price",
        "delivery_cost",
        "other_cost",
        "global_advance_required",
        "global_payment_conflict",
        "analogue_compatible",
        "analogue_differences",
    ]
    for field in fields:
        value = data.get(field)
        fragment = "SYNTHETIC " + field + " declaration"
        data["evidence"].append(
            {
                "id": field,
                "offer_id": data["id"],
                "field": field,
                "value": value,
                "url": data["url"],
                "observed_at": NOW.isoformat(),
                "origin": "store_card",
                "selector": "SYNTHETIC field " + field,
                "retained_fragment": fragment,
                "content_sha256": hashlib.sha256(fragment.encode()).hexdigest(),
                "synthetic": True,
            }
        )
    return data


def test_complete_synthetic_offer_can_meet_data_gates_but_is_not_live_purchase():
    result = evaluate_offer(NormalizedOffer.model_validate(proven(row())), NOW)
    assert result["meets_data_gates"] and not result["purchase_ready"]
    assert result["full_total_rub"] == "450000.00" and result["synthetic"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("delivery_cost", None),
        ("other_cost", None),
        ("available_quantity", None),
        ("complete_item", None),
        ("seller_checked", None),
    ],
)
def test_unknown_fields_not_replaced_with_zero_or_confirmation(field, value):
    offer = NormalizedOffer.model_validate(proven(row(**{field: value})))
    result = evaluate_offer(offer, NOW)
    assert getattr(offer, field) is None and not result["meets_data_gates"]
    if field.endswith("cost"):
        assert result["full_total_rub"] is None


@pytest.mark.parametrize("value", [0.1, True, -1, "NaN"])
def test_money_rejects_float_bool_negative_nonfinite(value):
    with pytest.raises(ValidationError):
        Money(amount=value, currency="RUB")


def test_stale_and_conflicting_price_never_choose_cheaper_price():
    data = proven(row())
    data["evidence"].append(
        {
            **data["evidence"][11],
            "id": "conflicting-price",
            "field": "price",
            "value": {**data["price"], "money": {"amount": "400000.00", "currency": "RUB"}},
        }
    )
    assert not evaluate_offer(NormalizedOffer.model_validate(data), NOW)["meets_data_gates"]
    data = proven(row())
    next(e for e in data["evidence"] if e["field"] == "price")["observed_at"] = (
        NOW - timedelta(hours=2)
    ).isoformat()
    assert not evaluate_offer(NormalizedOffer.model_validate(data), NOW)["meets_data_gates"]


def test_same_evidenced_seller_across_domains_counts_once_unknown_does_not_count():
    a = NormalizedOffer.model_validate(proven(row()))
    b = NormalizedOffer.model_validate(
        proven(row(id="offer-two", url="https://other-synthetic.example.test/card"))
    )
    c = NormalizedOffer.model_validate(
        proven(
            row(
                id="offer-three",
                url="https://unknown-synthetic.example.test/card",
                seller_entity_key=None,
            )
        )
    )
    result = compare([a, b, c], NOW)
    assert result["independent_sellers_confirmed"] == 1


def test_deposit_and_conditional_prices_do_not_become_unconditional_full_price():
    for kind in ["deposit", "conditional", "installment", "unknown"]:
        data = row()
        data["price"]["kind"] = kind
        result = evaluate_offer(NormalizedOffer.model_validate(proven(data)), NOW)
        assert not result["meets_data_gates"] and result["full_total_rub"] is None


def test_pay_projection_matches_all_unchanged_original_golden_payment_results():
    import json
    from pathlib import Path

    from pc_sourcing.evaluate import evaluate
    from pc_sourcing.models import Offer
    from pc_sourcing.normalized_offers import payment_projection

    raw = json.loads((Path(__file__).resolve().parents[1] / "fixtures/golden.json").read_text())
    rows = raw["offers"] if isinstance(raw, dict) and "offers" in raw else raw
    if isinstance(rows, dict):
        rows = rows["cases"]
    count = 0
    for original in rows:
        original = original.get("offer", original)
        legacy = Offer.model_validate(original)
        if legacy.price_rub is None:
            continue
        as_of = legacy.observed_at
        data = row(
            id=legacy.id,
            title=legacy.title,
            mpn=legacy.sku,
            source=legacy.source,
            url=legacy.url,
            observed_at=legacy.observed_at.isoformat(),
            synthetic=legacy.synthetic,
            global_advance_required=legacy.global_advance_required,
            global_payment_conflict=legacy.global_payment_conflict,
            optional_risky_alternative=legacy.optional_risky_alternative,
        )
        data["price"]["money"]["amount"] = str(legacy.price_rub)
        scope = {
            "mpn": legacy.sku,
            "quantity": 1,
            "amount": str(legacy.price_rub),
            "currency": "RUB",
            "region": "Москва",
            "price_id": "regular",
        }
        for name in ("protected", "postpay"):
            route = getattr(legacy, name).model_dump(mode="json")
            route.update(
                applies_mpn=legacy.sku,
                applies_quantity=1,
                applies_amount={"amount": str(legacy.price_rub), "currency": "RUB"},
                price_id="regular",
            )
            data[name] = route
        data["evidence"] = []
        for e in legacy.evidence:
            d = e.model_dump(mode="json")
            d["field"] = "mpn" if e.field == "sku" else e.field
            if e.value in {"true", "false"}:
                d["value"] = e.value == "true"
            frag = "SYNTHETIC original golden field"
            d.update(
                selector="golden replay",
                retained_fragment=frag,
                content_sha256=hashlib.sha256(frag.encode()).hexdigest(),
                scope=scope,
            )
            data["evidence"].append(d)
        payment = payment_projection(NormalizedOffer.model_validate(data), as_of)
        expected = evaluate(legacy, as_of)
        assert payment["passed"] == expected.payment_gate_passed, legacy.id
        assert payment["passed_routes"] == list(expected.passed_routes), legacy.id
        count += 1
    assert count == 19  # all nineteen priced golden rows; unknown amount is a separate context gap


def test_snippet_and_operator_price_claim_do_not_confirm_primary_price():
    for origin in ["search_snippet", "operator_review"]:
        data = proven(row())
        next(e for e in data["evidence"] if e["field"] == "price")["origin"] = origin
        result = evaluate_offer(NormalizedOffer.model_validate(data), NOW)
        assert not result["meets_data_gates"] and result["full_total_rub"] is None


def test_warranty_unknown_moscow_applicability_is_not_inferred_from_name():
    data = row()
    data["warranty"]["applicable_moscow"] = None
    assert not evaluate_offer(NormalizedOffer.model_validate(proven(data)), NOW)["gates"][
        "warranty"
    ]


def test_quantity_purchase_basis_and_nonrub_do_not_convert_or_guess():
    data = row()
    data["request"]["quantity"] = 2
    data["available_quantity"] = 2
    result = evaluate_offer(NormalizedOffer.model_validate(proven(data)), NOW)
    assert result["full_total_rub"] == "900000.00"
    data["price"]["basis"] = "purchase"
    assert (
        evaluate_offer(NormalizedOffer.model_validate(proven(data)), NOW)["full_total_rub"] is None
    )
    data["price"]["quantity"] = 2
    assert (
        evaluate_offer(NormalizedOffer.model_validate(proven(data)), NOW)["full_total_rub"]
        == "450000.00"
    )
    data["price"]["money"]["currency"] = "USD"
    assert (
        evaluate_offer(NormalizedOffer.model_validate(proven(data)), NOW)["full_total_rub"] is None
    )


@pytest.mark.parametrize("stock", ["supplier", "under_order", "preorder", "unavailable", "unknown"])
def test_stock_states_never_promoted_to_in_stock(stock):
    result = evaluate_offer(NormalizedOffer.model_validate(proven(row(stock=stock))), NOW)
    assert not result["gates"]["stock"]


def test_field_evidence_future_hash_and_owner_fail_closed():
    data = proven(row())
    data["evidence"][0]["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    assert not evaluate_offer(NormalizedOffer.model_validate(data), NOW)["meets_data_gates"]
    data = proven(row())
    data["evidence"][0]["content_sha256"] = "a" * 64
    with pytest.raises(ValidationError):
        NormalizedOffer.model_validate(data)
    data = proven(row())
    data["evidence"][0]["offer_id"] = "other"
    with pytest.raises(ValidationError):
        NormalizedOffer.model_validate(data)


def test_unknown_item_amount_cannot_confirm_payment_context():
    data = proven(row(source="avito", price=None))
    offer = NormalizedOffer.model_validate(data)
    decision = evaluate_offer(offer, NOW)
    assert decision["item_subtotal_rub"] is None
    assert decision["payment"]["passed"] is False
    assert decision["label"] == "требует ручной проверки"


def test_mixed_real_synthetic_comparison_is_rejected():
    a = NormalizedOffer.model_validate(proven(row()))
    raw = proven(row(id="real", url="https://example.org/real"))
    raw["synthetic"] = False
    for evidence in raw["evidence"]:
        evidence["synthetic"] = False
    b = NormalizedOffer.model_validate(raw)
    with pytest.raises(ValueError, match="separate"):
        compare([a, b], NOW)


def test_rankings_have_explicit_same_request_context():
    data = compare([NormalizedOffer.model_validate(proven(row()))], NOW)
    assert len(data["rankings"]) == 1
    key, ranking = next(iter(data["rankings"].items()))
    assert json.loads(key)["quantity"] == 1
    assert set(ranking) == {"exact", "analogue"}


@pytest.mark.parametrize(
    "field,gate",
    [
        ("title", "supported_identity"),
        ("mpn", "supported_identity"),
        ("available_quantity", "quantity"),
        ("complete_item", "complete_item"),
        ("condition", "condition"),
        ("warranty", "warranty"),
        ("fulfillment", "moscow"),
        ("stock", "stock"),
        ("seller_entity_key", "seller_check"),
        ("seller_checked", "seller_check"),
        ("factory_liquid", "factory_liquid"),
        ("price", "full_unconditional_price"),
        ("delivery_cost", "full_unconditional_price"),
        ("other_cost", "full_unconditional_price"),
    ],
)
@pytest.mark.parametrize("mode", ["missing", "stale", "contradictory", "snippet", "future"])
def test_each_positive_gate_requires_current_matching_primary_evidence(field, gate, mode):
    data = proven(row())
    evidence = next(e for e in data["evidence"] if e["field"] == field)
    if mode == "missing":
        data["evidence"].remove(evidence)
    elif mode == "stale":
        evidence["observed_at"] = (NOW - timedelta(hours=25)).isoformat()
    elif mode == "future":
        evidence["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif mode == "snippet":
        evidence["origin"] = "search_snippet"
    else:
        data["evidence"].append({**evidence, "id": "contradictory", "value": None})
    decision = evaluate_offer(NormalizedOffer.model_validate(data), NOW)
    assert not decision["gates"][gate]
    assert not decision["meets_data_gates"]
    assert not decision["purchase_ready"]


@pytest.mark.parametrize("field", ["delivery_cost", "other_cost"])
@pytest.mark.parametrize("currency", ["USD", "EUR", "CNY"])
def test_nonrub_fees_do_not_become_free_or_auto_converted(field, currency):
    data = proven(row(**{field: {"amount": "0.01", "currency": currency}}))
    result = evaluate_offer(NormalizedOffer.model_validate(data), NOW)
    assert result["full_total_rub"] is None
    assert result["known_cost_rub"] == "450000.00"
    assert not result["meets_data_gates"]


def test_unknown_quantity_differs_from_confirmed_zero_and_sufficient_quantity():
    for quantity, state in [(None, "unknown"), (0, "confirmed"), (1, "confirmed")]:
        data = proven(row(available_quantity=quantity))
        offer = NormalizedOffer.model_validate(data)
        decision = evaluate_offer(offer, NOW)
        assert offer.available_quantity is quantity
        assert decision["field_states"]["available_quantity"]["status"] == state
        assert decision["gates"]["quantity"] is (quantity == 1)


def test_low_conditional_price_is_preserved_but_cannot_replace_regular_price():
    cheap = {
        "id": "conditional",
        "money": {"amount": "1.00", "currency": "RUB"},
        "kind": "conditional",
        "basis": "unit",
        "quantity": 1,
        "conditions": ["requires unsupported subscription"],
    }
    offer = NormalizedOffer.model_validate(proven(row(conditional_prices=[cheap])))
    dataset = compare([offer], NOW)
    assert dataset["rows"][0]["decision"]["full_total_rub"] == "450000.00"
    assert dataset["rows"][0]["offer"]["conditional_prices"][0]["money"]["amount"] == "1.00"


def test_newest_canonical_listing_wins_and_retains_old_evidence_in_rejection():
    a = proven(row(id="old", url="https://synthetic.example.test/card?utm_source=old"))
    a["observed_at"] = (NOW - timedelta(minutes=1)).isoformat()
    b = proven(row(id="new", url="https://synthetic.example.test/card?utm_source=new"))
    data = compare([NormalizedOffer.model_validate(a), NormalizedOffer.model_validate(b)], NOW)
    assert [r["offer"]["id"] for r in data["rows"]] == ["new"]
    assert data["rejections"][0]["offer"]["id"] == "old"
    assert data["rejections"][0]["offer"]["evidence"]
    assert data["independent_sellers_confirmed"] == 1


@pytest.mark.parametrize("mode", ["missing", "stale", "contradictory", "snippet"])
def test_seller_name_and_domain_cannot_replace_confirmed_entity_key(mode):
    data = proven(row())
    evidence = next(e for e in data["evidence"] if e["field"] == "seller_entity_key")
    if mode == "missing":
        data["evidence"].remove(evidence)
    elif mode == "stale":
        evidence["observed_at"] = (NOW - timedelta(hours=25)).isoformat()
    elif mode == "contradictory":
        data["evidence"].append({**evidence, "id": "other-entity", "value": "different"})
    else:
        evidence["origin"] = "search_snippet"
    dataset = compare([NormalizedOffer.model_validate(data)], NOW)
    assert dataset["independent_sellers_confirmed"] == 0
    assert dataset["unknown_seller_relations"] == 1
    assert not dataset["rows"][0]["decision"]["gates"]["seller_check"]


@pytest.mark.parametrize("field", ["factory_liquid", "price", "warranty", "available_quantity"])
@pytest.mark.parametrize(
    "scope",
    [
        {"mpn": "OTHER-MODEL"},
        {"mpn": None},
        {"quantity": 7},
        {"quantity": True},
        {"region": "other-region"},
    ],
)
def test_explicit_conflicting_scope_cannot_confirm_matching_field_value(field, scope):
    data = proven(row())
    next(e for e in data["evidence"] if e["field"] == field)["scope"] = scope
    decision = evaluate_offer(NormalizedOffer.model_validate(data), NOW)
    assert decision["field_states"][field]["status"] == "conflict"
    assert not decision["meets_data_gates"]


@pytest.mark.parametrize(
    "scope",
    [
        {"price_id": "other-price"},
        {"currency": "USD"},
        {"amount": "1.00"},
        {"amount": True},
        {"amount": 450000.0},
        {"basis": "unknown"},
        {"kind": "deposit"},
    ],
)
def test_price_context_conflict_preserves_original_and_blocks_total(scope):
    data = proven(row())
    next(e for e in data["evidence"] if e["field"] == "price")["scope"] = scope
    offer = NormalizedOffer.model_validate(data)
    decision = evaluate_offer(offer, NOW)
    assert offer.evidence[11].scope == scope
    assert decision["full_total_rub"] is None
    assert not decision["meets_data_gates"]


@pytest.mark.parametrize("spelling", ["450000.0", "450000", 450000])
def test_equivalent_decimal_evidence_is_not_a_price_conflict(spelling):
    import copy

    data = proven(row())
    evidence = next(e for e in data["evidence"] if e["field"] == "price")
    evidence["value"] = copy.deepcopy(evidence["value"])
    evidence["value"]["money"]["amount"] = spelling
    evidence["scope"] = {
        "amount": spelling,
        "currency": "RUB",
        "price_id": "regular",
        "mpn": data["mpn"],
        "quantity": 1,
    }
    offer = NormalizedOffer.model_validate(data)
    result = evaluate_offer(offer, NOW)
    assert result["meets_data_gates"]
    assert result["full_total_rub"] == "450000.00"
    assert offer.evidence[11].value["money"]["amount"] == spelling


def postpay_context(data):
    scope = {
        "mpn": data["mpn"],
        "quantity": 1,
        "amount": "450000.00",
        "currency": "RUB",
        "region": "Москва",
        "price_id": "regular",
    }
    data["postpay"] = {
        "status": "confirmed_applicable",
        "covers_item": True,
        "covers_amount": True,
        "covers_region": True,
        "covers_order": True,
        "external_advance_required": False,
        "applies_mpn": data["mpn"],
        "applies_quantity": 1,
        "applies_amount": {"amount": "450000.00", "currency": "RUB"},
        "price_id": "regular",
        "evidence_ids": ["postpay-route"],
    }
    fragment = "SYNTHETIC whole purchase postpay"
    data["evidence"].append(
        {
            "id": "postpay-route",
            "offer_id": data["id"],
            "field": "postpay_route",
            "value": "confirmed_applicable",
            "url": data["url"],
            "observed_at": NOW.isoformat(),
            "origin": "seller_statement",
            "selector": "synthetic route",
            "retained_fragment": fragment,
            "content_sha256": hashlib.sha256(fragment.encode()).hexdigest(),
            "synthetic": True,
            "scope": scope,
        }
    )
    return data


def test_payment_unknown_mpn_cannot_be_agreement_but_known_control_passes():
    from pc_sourcing.normalized_offers import payment_projection

    good = postpay_context(proven(row(source="avito")))
    assert payment_projection(NormalizedOffer.model_validate(good), NOW)["passed"]
    unknown = postpay_context(proven(row(source="avito", mpn=None)))
    result = evaluate_offer(NormalizedOffer.model_validate(unknown), NOW)
    assert not result["payment"]["passed"]
    assert result["label"] == "требует ручной проверки"


@pytest.mark.parametrize("amount", [450000.0, True, "NaN", "450000.001"])
def test_payment_scope_money_keeps_decimal_contract(amount):
    data = postpay_context(proven(row(source="avito")))
    data["evidence"][-1]["scope"]["amount"] = amount
    result = evaluate_offer(NormalizedOffer.model_validate(data), NOW)
    assert not result["payment"]["passed"]
    assert result["label"] == "требует ручной проверки"


@pytest.mark.parametrize(
    "key,attribute",
    [
        ("factory_liquid", "factory_liquid"),
        ("factoryLiquid", "factory_liquid"),
        ("Factory Liquid", "factory_liquid"),
        ("isComplete", "full_item"),
        ("completeItem", "full_item"),
        ("complete_item", "full_item"),
    ],
)
@pytest.mark.parametrize("value", [False, None, "unknown", [True, False]])
def test_top_level_identity_never_overwrites_contrary_or_unknown_alias_claim(key, attribute, value):
    raw = {key: value}
    offer = NormalizedOffer.model_validate(proven(row(attributes=raw)))
    decision = evaluate_offer(offer, NOW)
    assert decision["match"] == "unresolved"
    assert not decision["meets_data_gates"]
    assert not decision["gates"]["supported_identity"]
    assert offer.attributes == raw
    claims = [c for c in decision["identity_assertions"] if c["attribute"] == attribute]
    assert any(c["source"].startswith("attributes/") for c in claims)
    assert any(c["source"].startswith("top_level/") for c in claims)


@pytest.mark.parametrize(
    "key",
    [
        "factory_liquid",
        "factoryLiquid",
        "Factory Liquid",
        "isComplete",
        "completeItem",
        "complete_item",
    ],
)
@pytest.mark.parametrize("value", [True, "true", [True, True]])
def test_agreeing_identity_aliases_remain_ready_and_retain_both_sources(key, value):
    offer = NormalizedOffer.model_validate(proven(row(attributes={key: value})))
    decision = evaluate_offer(offer, NOW)
    assert decision["match"] == "exact"
    assert decision["meets_data_gates"]
    assert not decision["purchase_ready"]
    assert offer.attributes[key] == value
    assert any(c["source"].startswith("attributes/") for c in decision["identity_assertions"])
    assert any(c["source"].startswith("top_level/") for c in decision["identity_assertions"])


@pytest.mark.parametrize(
    "attributes",
    [
        {"manufacturer": "MSI", "brand": "ASUS"},
        {"memoryCapacity": "32 GB", "vram": "24 GB"},
        {"mpn": "OTHER-MPN"},
        {"sku": None},
        {"profileEXPO": True, "profile_EXPO": False},
        {
            "additionalProperty": [
                {"name": "factoryLiquid", "value": False},
                {"name": "isComplete", "value": True},
            ]
        },
    ],
)
def test_all_duplicate_identity_dimensions_are_reconciled_without_key_precedence(attributes):
    decision = evaluate_offer(
        NormalizedOffer.model_validate(proven(row(attributes=attributes))), NOW
    )
    assert decision["match"] == "unresolved"
    assert not decision["meets_data_gates"]
    assert decision["identity_assertions"]


def test_agreeing_mpn_aliases_do_not_destroy_supported_analogue():
    data = row(
        title="MSI RTX 5090 SUPRIM LIQUID SOC",
        mpn="G5090-32SLSC",
        attributes={
            "mpn": "G5090-32SLSC",
            "sku": "G5090-32SLSC",
            "factoryLiquid": True,
            "completeItem": True,
        },
        analogue_compatible=True,
        analogue_differences=["SOC instead of OC"],
    )
    decision = evaluate_offer(NormalizedOffer.model_validate(proven(data)), NOW)
    assert decision["match"] == "analogue"
    assert decision["meets_data_gates"]
    assert any(c["attribute"] == "mpn" for c in decision["identity_assertions"])


def test_attribute_mpn_without_top_level_binding_remains_unresolved():
    data = row(mpn=None, attributes={"sku": "G5090-32SLC"})
    data["request"]["mpn"] = None
    result = evaluate_offer(NormalizedOffer.model_validate(proven(data)), NOW)
    assert result["match"] == "unresolved"
    assert not result["meets_data_gates"]
    assert any(c["source"] == "attributes/sku" for c in result["identity_assertions"])
