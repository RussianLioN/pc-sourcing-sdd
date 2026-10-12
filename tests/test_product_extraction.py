"""EXTRACT-01–08 offline synthetic adversarial product scopes and price witnesses."""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from pc_sourcing.collection_capture import Capture, normalize_capture
from pc_sourcing.live_models import Candidate, Request
from pc_sourcing.product_extraction import extract_card, parse_rub_token

NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)
URL = "https://synthetic.example.test/target"
MPN = "F5-6000J3036F48GX2-TZ5NR"
REQUEST = Request(name="G.Skill DDR5 96GB 2x48GB 6000 MT/s CL30 EXPO", mpn=MPN, category="ram")
CANDIDATE = Candidate(
    url=URL, title=REQUEST.name, queries=(), observed_at=NOW, response_sha256="0" * 64
)


def product(**changes):
    return {
        "@type": "Product",
        "url": URL,
        "name": "SYNTHETIC G.Skill DDR5 96GB 2x48GB 6000 MT/s CL30 EXPO (" + MPN + ")",
        "offers": {
            "@type": "Offer",
            "price": "118 400,00",
            "priceCurrency": "RUB",
            "availability": "https://schema.org/InStock",
        },
        **changes,
    }


def card(value, surrounding=""):
    return surrounding + '<script type="application/ld+json">' + json.dumps(value) + "</script>"


def extract(value, surrounding=""):
    return extract_card(REQUEST, CANDIDATE, card(value, surrounding), NOW, synthetic=True)


@pytest.mark.parametrize(
    "token,amount",
    [
        (118400, "118400.00"),
        ("118400", "118400.00"),
        ("118 400,00", "118400.00"),
        ("118\u00a0400,50 ₽", "118400.50"),
        ("118\u202f400.25 RUB", "118400.25"),
        ("118.400,00", "118400.00"),
        ("12,34", "12.34"),
    ],
)
def test_local_rub_tokens_keep_exact_decimal(token, amount):
    assert str(parse_rub_token(token)) == amount


@pytest.mark.parametrize(
    "token",
    [
        True,
        118400.0,
        "0",
        "-1",
        "1e5",
        "NaN",
        "от 118400",
        "118400–120000",
        "11 84 00",
        "118,400",
        "118400/мес",
        "залог 118400",
        "118400 USD",
        "12.345",
        "1\n234",
        "1\t234",
    ],
)
def test_unsafe_or_ambiguous_tokens_never_become_amount(token):
    assert parse_rub_token(token) is None


def test_footer_recommendations_and_other_products_do_not_contaminate_selected_product():
    p = product()
    other = product(
        url="https://synthetic.example.test/other",
        name="ASUS DDR4 32GB",
        offers={"@type": "Offer", "price": "1", "priceCurrency": "RUB"},
    )
    baseline = extract(p)
    noisy = extract([other, p], "<footer>ASUS 32GB DDR4 2400MHz залог 12 руб. в месяц</footer>")
    assert noisy.observation.match == baseline.observation.match == "exact"
    assert noisy.observation.stock == "in_stock"
    assert noisy.displayed_amount_rub == baseline.displayed_amount_rub == "118400.00"
    assert noisy.observation.price_rub is None
    assert noisy.observation.payment_confirmed is None
    assert noisy.observation.eligible is False


@pytest.mark.parametrize("description", ["G.Skill DDR4 32GB", "6000MHz", "96GB; 32GB"])
def test_conflict_inside_selected_product_stays_unresolved(description):
    result = extract(product(description=description))
    assert result.observation.match == "unresolved"
    assert result.identity_conflicts


@pytest.mark.parametrize(
    "value", [[product(), product()], [product(url=URL + "/other"), product(url=URL + "/other2")]]
)
def test_ambiguous_or_unbound_products_fail_closed(value):
    result = extract(value)
    assert result.observation.status == "unresolved"
    assert result.displayed_amount_rub is None


def test_explicit_wrong_single_product_url_never_selected():
    assert extract(product(url=URL + "/wrong")).observation.status == "unresolved"


@pytest.mark.parametrize(
    "schema", ["http://schema.org/Discontinued", "https://schema.org/Discontinued"]
)
def test_discontinued_has_original_schema_witness_and_unavailable(schema):
    p = product()
    p["offers"]["availability"] = schema
    result = extract(p)
    assert result.observation.stock == "unavailable"
    selected = json.loads(result.observation.primary["retained_content"])
    assert selected["properties"]["availability"] == [schema]
    cap = Capture(
        request=REQUEST,
        observation=result.observation,
        provenance="synthetic_fixture",
        synthetic=True,
        artifact_sha256="0" * 64,
    )
    assert normalize_capture(cap).stock == "unavailable"


def test_unknown_stock_is_not_false_or_in_stock():
    p = product()
    p["offers"]["availability"] = "mystery"
    assert extract(p).observation.stock == "unknown"


def test_title_derived_mpn_selector_and_hash_do_not_claim_structured_mpn():
    result = extract(product())
    f = next(f for f in result.observation.facts if f.field == "mpn")
    assert result.observation.mpn == MPN
    assert "title-derived" in f.selector
    assert f.origin == "store_card" and f.observed_at == NOW and f.url == URL
    assert (
        result.observation.primary["retained_sha256"]
        == hashlib.sha256(result.observation.primary["retained_content"].encode()).hexdigest()
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"mpn": "F5-6000J3036F48GX2-FX5"},
        {"name": "G.Skill DDR5 96GB NOT " + MPN},
        {"name": "G.Skill DDR5 96GB " + MPN + " F5-6000J3036F48GX2-FX5"},
    ],
)
def test_structured_title_mpn_conflict_or_negation_not_confirmed(changes):
    result = extract(product(**changes))
    assert result.observation.match != "exact"


def test_structured_target_mpn_cannot_hide_different_title_code():
    result = extract(product(mpn=MPN, name="G.Skill DDR5 96GB F5-6000J3036F48GX2-FX5"))
    assert result.observation.match == "unresolved"


@pytest.mark.parametrize(
    "context",
    ["первый платёж", "рассрочка 12 месяцев", "залог", "при оплате наличными", "скидка по карте"],
)
def test_product_conditional_price_never_regular(context):
    result = extract(product(description=context))
    assert result.displayed_amount_rub is None
    assert result.price_tokens[0].raw == "118 400,00"
    assert result.price_tokens[0].kind == "conditional_or_unknown"
    assert result.observation.price_rub is None


def test_price_specification_and_multiple_offers_do_not_choose_cheapest():
    p = product()
    p["offers"]["priceSpecification"] = {"@type": "UnitPriceSpecification", "name": "monthly"}
    assert extract(p).displayed_amount_rub is None
    p = product()
    p["offers"] = [p["offers"], {"@type": "Offer", "price": "1", "priceCurrency": "RUB"}]
    result = extract(p)
    assert result.displayed_amount_rub is None and len(result.price_tokens) == 2


def test_price_token_original_selector_survives_unsupported_format():
    p = product()
    p["offers"]["price"] = "118,400"
    result = extract(p)
    token = result.price_tokens[0]
    assert token.raw == "118,400" and token.parsed_amount_rub is None
    assert (
        token.selector.endswith(".offers.price") and token.url == URL and token.observed_at == NOW
    )


def test_displayed_price_enters_only_unknown_conditional_alternative():
    result = extract(product())
    cap = Capture(
        request=REQUEST,
        observation=result.observation,
        provenance="synthetic_fixture",
        synthetic=True,
        artifact_sha256="0" * 64,
    )
    offer = normalize_capture(cap)
    assert offer.price is None and offer.conditional_prices[0].kind == "unknown"
    assert offer.conditional_prices[0].money.amount == 118400
    assert offer.delivery_cost is None and offer.available_quantity is None


def test_store_unknown_payment_not_avito_gate_and_avito_preorder_is_manual():
    # Frozen synthetic proof builder; no live rows or golden expectations changed.
    from test_normalized_offers import proven, row

    from pc_sourcing.normalized_models import NormalizedOffer
    from pc_sourcing.normalized_offers import evaluate_offer

    store = evaluate_offer(NormalizedOffer.model_validate(proven(row())), NOW.replace(hour=3))
    assert store["gates"]["payment"] is True and store["payment"]["passed"] is False
    assert store["meets_data_gates"] is True
    avito = evaluate_offer(
        NormalizedOffer.model_validate(proven(row(source="avito", stock="preorder"))),
        NOW.replace(hour=3),
    )
    assert avito["gates"]["payment"] is False
    assert avito["label"] == "требует ручной проверки" and not avito["meets_data_gates"]


def test_nested_related_products_and_jsonld_id_are_nonmaterial_context():
    other = product(url=URL + "/other", name="ASUS DDR4 32GB рассрочка")
    selected = product(**{"@id": URL + "#product", "isRelatedTo": other, "isSimilarTo": [other]})
    result = extract(selected)
    assert result.observation.match == "exact" and result.displayed_amount_rub == "118400.00"


def test_raw_json_number_lexeme_survives_without_float_rounding():
    text = card(product()).replace('"118 400,00"', "118400.50")
    result = extract_card(REQUEST, CANDIDATE, text, NOW, synthetic=True)
    assert result.price_tokens[0].raw == "118400.50"
    assert result.price_tokens[0].raw_type == "json_number_lexeme"
    assert result.displayed_amount_rub == "118400.50"
    text = text.replace("118400.50", "1e5")
    result = extract_card(REQUEST, CANDIDATE, text, NOW, synthetic=True)
    assert result.price_tokens[0].raw == "1e5" and result.displayed_amount_rub is None


def test_sensitive_price_scalar_is_not_retained_or_normalized():
    secret = "sk-" + "proj-" + "a" * 25
    p = product()
    p["offers"]["price"] = secret
    result = extract(p)
    assert result.displayed_amount_rub is None
    assert secret not in result.model_dump_json()


def microdata(name=None, description="", extra=""):
    return f'<div itemscope itemtype="https://schema.org/Product" itemid="{URL}"><h1>{name or product()["name"]}</h1><span itemprop="description">{description}</span><div itemprop="offers" itemscope itemtype="https://schema.org/Offer"><meta itemprop="price" content="118 400,00"><meta itemprop="priceCurrency" content="RUB"><link itemprop="availability" href="http://schema.org/Discontinued"></div>{extra}</div>'


def test_microdata_footer_nested_recommendation_and_other_offer_not_target_claims():
    other = '<aside itemscope itemtype="https://schema.org/Product" itemid="https://synthetic.example.test/other"><h1>ASUS DDR4 32GB залог</h1><div itemprop="offers" itemscope itemtype="https://schema.org/Offer"><meta itemprop="price" content="1"></div></aside>'
    result = extract_card(
        REQUEST,
        CANDIDATE,
        "<footer>ASUS 32GB рассрочка</footer>" + microdata(extra=other),
        NOW,
        synthetic=True,
    )
    assert result.observation.match == "exact" and result.observation.stock == "unavailable"
    assert result.displayed_amount_rub == "118400.00"
    assert result.price_tokens[0].selector.startswith("microdata.Product[0]")


@pytest.mark.parametrize("description", ["DDR4 32GB", "6000 MHz"])
def test_microdata_material_conflict_inside_product_preserved(description):
    result = extract_card(
        REQUEST, CANDIDATE, microdata(description=description), NOW, synthetic=True
    )
    assert result.observation.match == "unresolved"


def test_microdata_conditional_offer_and_duplicate_price_never_regular():
    result = extract_card(
        REQUEST, CANDIDATE, microdata(description="рассрочка"), NOW, synthetic=True
    )
    assert result.displayed_amount_rub is None and result.price_tokens[0].raw == "118 400,00"
    text = microdata().replace(
        '<meta itemprop="priceCurrency"',
        '<meta itemprop="price" content="1"><meta itemprop="priceCurrency"',
    )
    result = extract_card(REQUEST, CANDIDATE, text, NOW, synthetic=True)
    assert result.displayed_amount_rub is None


def test_bridge_journal_restore_preserves_original_price_witness_and_unknowns(tmp_path):
    from pc_sourcing.collection_runtime import Journal
    from pc_sourcing.product_extraction import extraction_capture

    result = extract(product())
    capture = extraction_capture(REQUEST, result)
    j = Journal(tmp_path / "runtime")
    j.submit([capture])
    j.work()
    j.report(tmp_path / "report", NOW)
    j.backup(tmp_path / "backup")
    restored = Journal.restore(tmp_path / "backup", tmp_path / "restored")
    assert restored.status()["jobs"] == j.status()["jobs"]
    comparison = json.loads((tmp_path / "report/offers/comparison.json").read_text())
    assert len(comparison["rows"]) == 1
    row = comparison["rows"][0]
    assert row["offer"]["price"] is None and row["decision"]["purchase_ready"] is False
    assert row["offer"]["observed_at"] == NOW.isoformat().replace("+00:00", "Z")
    assert row["offer"]["conditional_prices"][0]["kind"] == "unknown"
    selected = json.loads(
        j.status()["jobs"][0]["capture"]["observation"]["primary"]["retained_content"]
    )
    assert selected["price_tokens"][0]["raw"] == "118 400,00"


def test_cli_real_retained_capture_keeps_old_status_and_original_dates(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "artifacts/source-state/28bit-acquisition-captures/38ea855aa73b3b55ad197102739cf9d68080b948ad909f759127863b7a163a31.json"
    )
    if not source.exists():
        pytest.skip(
            "actual retained capture is an external operational receipt; unit-only bundle lacks it"
        )
    before = source.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pc_sourcing.product_extraction_cli",
            "retained",
            "--capture",
            str(source),
            "--output",
            str(tmp_path / "output"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    original = json.loads(before)
    capture = json.loads((tmp_path / "output/capture.json").read_text())
    assert capture == original and source.read_bytes() == before
    assert capture["observation"]["match"] == "unresolved"
    assert capture["observation"]["primary"]["retrieved_at"].startswith("2026-10-12T09:21:11")
    assert json.loads((tmp_path / "output/report/offers/comparison.json").read_text())["rows"] == []


def test_conditional_markers_and_price_token_are_retained_in_selected_witness():
    result = extract(product(description="При оплате наличными: скидка"))
    assert result.price_tokens[0].condition_markers
    selected = json.loads(result.observation.primary["retained_content"])
    assert selected["price_tokens"][0]["condition_markers"] == list(
        result.price_tokens[0].condition_markers
    )
    assert (
        result.price_tokens[0].raw_sha256
        == hashlib.sha256(json.dumps("118 400,00", ensure_ascii=False).encode()).hexdigest()
    )


def test_secret_in_unknown_material_property_is_redacted_but_not_ignored():
    secret = "sk-" + "proj-" + "b" * 25
    p = product(additionalProperty=[{"name": "unsupported property", "value": secret}])
    result = extract(p)
    assert (
        result.observation.match == "unresolved"
        and "unsafe_identity_metadata" in result.identity_conflicts
    )
    assert secret not in result.model_dump_json()


def test_microdata_heading_and_structured_name_conflict_inside_target_preserved():
    text = microdata().replace("<h1>", '<meta itemprop="name" content="G.Skill DDR4 32GB"><h1>')
    result = extract_card(REQUEST, CANDIDATE, text, NOW, synthetic=True)
    assert result.observation.match != "exact"


def cli_inputs(tmp_path, value=None):
    body = card(value or product()).encode()
    html_path = tmp_path / "input.html"
    html_path.write_bytes(body)
    metadata = dict(
        request=REQUEST.model_dump(mode="json"),
        candidate=CANDIDATE.model_dump(mode="json"),
        source_observed_at=NOW.isoformat(),
        synthetic=True,
        html_sha256=hashlib.sha256(body).hexdigest(),
    )
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata))
    return metadata_path, html_path, metadata


@pytest.mark.parametrize("mutation", ["hash", "realm", "naive_date", "extra_key"])
def test_cli_metadata_rejection_never_publishes_output(tmp_path, mutation):
    import subprocess
    import sys

    meta, body, data = cli_inputs(tmp_path)
    if mutation == "hash":
        data["html_sha256"] = "0" * 64
    elif mutation == "realm":
        data["synthetic"] = "true"
    elif mutation == "naive_date":
        data["source_observed_at"] = "2026-10-12T12:00:00"
    else:
        data["unexpected"] = True
    meta.write_text(json.dumps(data))
    out = tmp_path / "output"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pc_sourcing.product_extraction_cli",
            "parse",
            "--metadata",
            str(meta),
            "--html",
            str(body),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1 and not out.exists()


def test_cli_parse_e2e_and_ambiguous_product_preserves_coverage_not_eligibility(tmp_path):
    import subprocess
    import sys

    for label, value in [("exact", product()), ("ambiguous", [product(), product()])]:
        folder = tmp_path / label
        folder.mkdir()
        meta, body, data = cli_inputs(folder, value)
        out = folder / "output"
        command = [
            sys.executable,
            "-m",
            "pc_sourcing.product_extraction_cli",
            "parse",
            "--metadata",
            str(meta),
            "--html",
            str(body),
            "--output",
            str(out),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        coverage = json.loads((out / "report/coverage.json").read_text())
        assert len(coverage["jobs"]) == 1 and coverage["source_calls"] == 0
        assert (
            json.loads((out / "manifest.json").read_text())["source_observed_at"] == NOW.isoformat()
        )
        comparison = json.loads((out / "report/offers/comparison.json").read_text())
        assert not any(r["decision"]["purchase_ready"] for r in comparison["rows"])
        if label == "ambiguous":
            assert comparison["rows"] == []
        before = (out / "capture.json").read_bytes()
        rerun = subprocess.run(command, capture_output=True, text=True)
        assert rerun.returncode == 1 and (out / "capture.json").read_bytes() == before


@pytest.mark.parametrize(
    "title,mpn,expected",
    [
        ("MSI RTX 5090 SUPRIM LIQUID OC (G5090-32SLC)", "G5090-32SLC", "exact"),
        ("MSI RTX 5090 SUPRIM LIQUID SOC (G5090-32SLSOC)", "G5090-32SLSOC", "analogue"),
        ("PALIT RTX 5090 GAMEROCK", None, "excluded"),
        ("MSI RTX 5090 SUPRIM LIQUID SOC (G5090-32SLC)", "G5090-32SLC", "unresolved"),
    ],
)
def test_gpu_factory_family_variant_and_code_constraints_remain_frozen(title, mpn, expected):
    request = Request(name="MSI RTX 5090 SUPRIM LIQUID OC", mpn="G5090-32SLC", category="gpu")
    p = product(name=title)
    if mpn is not None:
        p["mpn"] = mpn
    result = extract_card(request, CANDIDATE, card(p), NOW, synthetic=True)
    assert result.observation.match == expected
    assert result.observation.eligible is False
    if expected == "analogue":
        assert "OC/SOC" in " ".join(result.observation.differences)


def test_mouse_title_derived_regional_mpn_and_superlight_not_substituted():
    request = Request(name="Logitech G PRO X2 SUPERSTRIKE", mpn="910-007776", category="mouse")
    p = product(name="Logitech G PRO X2 SUPERSTRIKE 910-007776")
    result = extract_card(request, CANDIDATE, card(p), NOW, synthetic=True)
    assert result.observation.mpn == "910-007776" and result.observation.match == "exact"
    assert any("title-derived" in f.selector for f in result.observation.facts if f.field == "mpn")
    p = product(name="Logitech G PRO X SUPERLIGHT 910-007777")
    assert (
        extract_card(request, CANDIDATE, card(p), NOW, synthetic=True).observation.match
        == "excluded"
    )


@pytest.mark.parametrize(
    "member,first,second",
    [
        ("memoryCapacity", "32 GB", "96 GB"),
        ("url", URL + "/other", URL),
        ("name", "G.Skill DDR4 32GB", product()["name"]),
        ("mpn", "F5-6000J3036F48GX2-FX5", MPN),
        ("@type", "Offer", "Product"),
        ("unknownMember", None, "retained unknown"),
        ("memoryCapacity", "96 GB", "96 GB"),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_top_product_json_members_never_discard_assertions(
    member, first, second, reverse
):
    first, second = (second, first) if reverse else (first, second)
    p = product()
    p.pop(member, None)
    text = (
        json.dumps(p)[:-1]
        + ","
        + json.dumps(member)
        + ":"
        + json.dumps(first)
        + ","
        + json.dumps(member)
        + ":"
        + json.dumps(second)
        + "}"
    )
    result = extract_card(
        REQUEST,
        CANDIDATE,
        '<script type="application/ld+json">' + text + "</script>",
        NOW,
        synthetic=True,
    )
    assert result.observation.status == "unresolved" and result.observation.match == "unresolved"
    assert result.displayed_amount_rub is None and not result.observation.facts
    assert "Duplicate JSON member" in result.observation.reason


@pytest.mark.parametrize(
    "member,first,second",
    [
        ("price", "1", "118 400,00"),
        ("priceCurrency", "USD", "RUB"),
        ("availability", "https://schema.org/OutOfStock", "https://schema.org/InStock"),
        ("@type", "AggregateOffer", "Offer"),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_nested_offer_duplicate_members_are_ambiguous_in_both_orders(
    member, first, second, reverse
):
    first, second = (second, first) if reverse else (first, second)
    p = product()
    offer = p["offers"]
    offer.pop(member, None)
    duplicate = (
        json.dumps(offer)[:-1]
        + ","
        + json.dumps(member)
        + ":"
        + json.dumps(first)
        + ","
        + json.dumps(member)
        + ":"
        + json.dumps(second)
        + "}"
    )
    text = json.dumps(p).replace(json.dumps(offer), duplicate)
    result = extract_card(
        REQUEST,
        CANDIDATE,
        '<script type="application/ld+json">' + text + "</script>",
        NOW,
        synthetic=True,
    )
    assert result.observation.status == "unresolved" and result.observation.match == "unresolved"
    assert "Duplicate JSON member" in result.observation.reason


@pytest.mark.parametrize("reverse", [False, True])
def test_nested_array_property_value_and_graph_duplicate_keys_refuse(reverse):
    values = ["32 GB", "96 GB"]
    values = values[::-1] if reverse else values
    prop = (
        '{"@type":"PropertyValue","name":"memoryCapacity","value":'
        + json.dumps(values[0])
        + ',"value":'
        + json.dumps(values[1])
        + "}"
    )
    p = product(additionalProperty=["PLACEHOLDER"])
    text = json.dumps({"@graph": [p]}).replace('"PLACEHOLDER"', prop)
    result = extract_card(
        REQUEST,
        CANDIDATE,
        '<script type="application/ld+json">' + text + "</script>",
        NOW,
        synthetic=True,
    )
    assert (
        result.observation.status == "unresolved"
        and "Duplicate JSON member" in result.observation.reason
    )


def test_same_named_members_in_separate_objects_are_not_duplicates():
    p = product(additionalProperty=[{"name": "memoryCapacity", "value": "96 GB"}])
    result = extract(p)
    assert result.observation.match == "exact"


@pytest.mark.parametrize("encoded_key", ["\\u0075rl", "u\\u0072l"])
def test_escaped_equivalent_json_keys_are_duplicates(encoded_key):
    p = product()
    p.pop("url")
    raw = (
        json.dumps(p)[:-1]
        + ',"url":'
        + json.dumps(URL + "/other")
        + ',"'
        + encoded_key
        + '":'
        + json.dumps(URL)
        + "}"
    )
    result = extract_card(
        REQUEST,
        CANDIDATE,
        '<script type="application/ld+json">' + raw + "</script>",
        NOW,
        synthetic=True,
    )
    assert (
        result.observation.status == "unresolved"
        and "Duplicate JSON member" in result.observation.reason
    )


@pytest.mark.parametrize("position", ["metadata", "source_product"])
def test_cli_duplicate_json_members_are_not_last_wins(tmp_path, position):
    import subprocess
    import sys

    meta, body, data = cli_inputs(tmp_path)
    if position == "metadata":
        raw = meta.read_text()[:-1] + ',"synthetic":false}'
        meta.write_text(raw)
    else:
        text = body.read_text().replace(
            '"url": ' + json.dumps(URL),
            '"url": ' + json.dumps(URL + "/other") + ', "url": ' + json.dumps(URL),
        )
        body.write_text(text)
        data["html_sha256"] = hashlib.sha256(body.read_bytes()).hexdigest()
        meta.write_text(json.dumps(data))
    output = tmp_path / "output"
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "pc_sourcing.product_extraction_cli",
            "parse",
            "--metadata",
            str(meta),
            "--html",
            str(body),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    if position == "metadata":
        assert p.returncode == 1 and not output.exists()
    else:
        assert p.returncode == 0, p.stderr
        cap = json.loads((output / "capture.json").read_text())
        assert cap["observation"]["status"] == "unresolved" and cap["observation"]["facts"] == []
        assert cap["observation"]["primary"]["retrieved_at"] == NOW.isoformat()
        assert json.loads((output / "report/offers/comparison.json").read_text())["rows"] == []
