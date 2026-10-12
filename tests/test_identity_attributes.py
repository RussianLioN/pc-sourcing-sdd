"""PRIMARY-06/07 normalized attributes: paraphrases, structural fields and controls."""

import json
from datetime import UTC, datetime

import pytest

from pc_sourcing.identity_attributes import attributes, conflicts
from pc_sourcing.live_models import Candidate, Request
from pc_sourcing.live_sourcing import parse_card

NOW = datetime(2026, 10, 12, tzinfo=UTC)
RAM = Request(
    name="G.Skill 96GB 2x48GB DDR5 6000 CL30 EXPO", mpn="F5-6000J3036F48GX2-TZ5NR", category="ram"
)
GPU = Request(name="MSI RTX 5090 SUPRIM LIQUID OC", mpn="G5090-32SLC", category="gpu")
MOUSE = Request(name="Logitech G PRO X2 SUPERSTRIKE", mpn="SYNTHETIC-MOUSE-MPN", category="mouse")


def observed(requested, title=None, visible="", **extra):
    product = {"@type": "Product", "name": title or requested.name, "mpn": requested.mpn, **extra}
    html = (
        '<script type="application/ld+json">'
        + json.dumps(product, ensure_ascii=False)
        + "</script>"
        + visible
    )
    candidate = Candidate(
        url="https://synthetic.example.test/card",
        title="SYNTHETIC",
        queries=(),
        observed_at=NOW,
        response_sha256="a" * 64,
    )
    return parse_card(requested, candidate, html, NOW)


@pytest.mark.parametrize(
    "declaration", ["memory speed 5600 MHz", "frequency: 5600 МГц", "DDR5-5600", "clock 5.6 GHz"]
)
def test_frequency_units_and_positions_conflict(declaration):
    assert observed(RAM, "G.Skill 96GB 2x48GB DDR5 CL30 EXPO; " + declaration).match == "unresolved"


@pytest.mark.parametrize("declaration", ["CL36", "CAS 36", "CAS latency 36", "CAS latency:36"])
def test_latency_aliases_conflict(declaration):
    assert observed(RAM, "G.Skill 96GB 2x48GB DDR5 6000 EXPO; " + declaration).match == "unresolved"


@pytest.mark.parametrize(
    "declaration",
    ["EXPO is not supported", "EXPO не поддерживается", "without EXPO", "EXPO unsupported"],
)
def test_profile_negation_conflicts(declaration):
    assert observed(RAM, "G.Skill 96GB 2x48GB DDR5 6000 CL30; " + declaration).match == "unresolved"


@pytest.mark.parametrize(
    "title",
    [
        "only receiver",
        "USB receiver for Logitech G PRO X2 SUPERSTRIKE; mouse not included",
        "Mousepad for Logitech G PRO X2 SUPERSTRIKE",
        "Spare housing for Logitech G PRO X2 SUPERSTRIKE; no mouse",
    ],
)
def test_partial_item_roles_not_model_mentions(title):
    assert observed(MOUSE, "Logitech G PRO X2 SUPERSTRIKE; " + title).match == "unresolved"


@pytest.mark.parametrize(
    "title",
    [
        "packaging only; GPU not included",
        "СЖО поставлена продавцом; не заводская жидкостная система",
        "32GB GDDR6",
    ],
)
def test_gpu_conflicts_are_not_hidden_by_code(title):
    assert observed(GPU, GPU.name + "; " + title).match == "unresolved"


@pytest.mark.parametrize(
    "requested,key,value",
    [
        (RAM, "memorySpeed", "5600 MHz"),
        (RAM, "casLatency", 36),
        (RAM, "memorySize", "48 GB"),
        (GPU, "factory_liquid", False),
        (MOUSE, "isComplete", False),
    ],
)
def test_structured_material_attribute_conflicts(requested, key, value):
    assert (
        observed(requested, additionalProperty=[{"name": key, "value": value}]).match
        == "unresolved"
    )


@pytest.mark.parametrize(
    "requested,visible",
    [
        (RAM, "<p>memory speed 5600 MHz</p>"),
        (GPU, "<p>GPU not included; packaging only</p>"),
        (MOUSE, "<p>only receiver</p>"),
    ],
)
def test_visible_conflict_has_precedence_over_full_jsonld_identity(requested, visible):
    assert observed(requested, visible=visible).match == "unresolved"


@pytest.mark.parametrize(
    "requested,title",
    [
        (GPU, "MSI GeForce RTX 5090 32GB SUPRIM LIQUID OC"),
        (RAM, "G.Skill 96 GB 2 × 48 GB DDR5-6000 CL30 EXPO"),
        (MOUSE, "Logitech G PRO X2 SUPERSTRIKE mouse; receiver included"),
    ],
)
def test_positive_controls_preserved(requested, title):
    assert observed(requested, title).match == "exact"


def test_conflicting_attribute_values_are_retained_not_last_value_wins():
    result = attributes("DDR5-6000; speed 5600 MHz", category="ram")
    assert result["speed"] == {"6000", "5600"}
    assert "speed" in conflicts(RAM, ["DDR5-6000; speed 5600 MHz"])


def test_unknown_structured_completeness_does_not_default_to_true():
    assert observed(MOUSE, isComplete="unknown").match == "unresolved"


def test_structured_profile_false_has_precedence_over_title():
    assert (
        observed(RAM, additionalProperty=[{"name": "EXPO", "value": False}]).match == "unresolved"
    )


def test_same_attributes_structured_and_visible_keep_positive_identity():
    assert (
        observed(
            RAM, memorySpeed="6000 MHz", casLatency=30, memorySize="96 GB", memoryType="DDR5"
        ).match
        == "exact"
    )


def test_curated_product_attribute_conflict_is_also_unresolved():
    from pc_sourcing.curated_primary import observe

    page = (
        "<h1>"
        + RAM.name
        + '</h1><div itemscope itemtype="https://schema.org/Product"><meta itemprop="mpn" content="'
        + RAM.mpn
        + '"><meta itemprop="memorySpeed" content="5600 MHz"></div>'
    )
    candidate = Candidate(
        url="https://synthetic.example.test/card",
        title="SYNTHETIC",
        queries=(),
        observed_at=NOW,
        response_sha256="a" * 64,
    )
    result = observe(RAM, candidate, page, {}, NOW)
    assert result.match == "unresolved"
    assert "speed" in result.primary["retained_content"]


def test_curated_visible_partial_item_is_also_unresolved():
    from pc_sourcing.curated_primary import observe

    page = (
        "<h1>"
        + MOUSE.name
        + '</h1><div itemscope itemtype="https://schema.org/Product"><meta itemprop="mpn" content="'
        + MOUSE.mpn
        + '">only receiver</div>'
    )
    candidate = Candidate(
        url="https://synthetic.example.test/card",
        title="SYNTHETIC",
        queries=(),
        observed_at=NOW,
        response_sha256="a" * 64,
    )
    assert observe(MOUSE, candidate, page, {}, NOW).match == "unresolved"


def test_structured_exclusive_profile_is_not_discarded():
    assert (
        observed(RAM, additionalProperty=[{"name": "profile", "value": "XMP only"}]).match
        == "unresolved"
    )


def test_curated_text_budget_is_a_gap_not_false_product_count():
    from pc_sourcing.curated_primary import observe

    page = (
        "<h1>"
        + MOUSE.name
        + '</h1><div itemscope itemtype="https://schema.org/Product"><meta itemprop="mpn" content="'
        + MOUSE.mpn
        + '">'
        + ("x" * 4100)
        + "</div>"
    )
    candidate = Candidate(
        url="https://synthetic.example.test/card",
        title="SYNTHETIC",
        queries=(),
        observed_at=NOW,
        response_sha256="a" * 64,
    )
    result = observe(MOUSE, candidate, page, {}, NOW)
    assert result.match == "unresolved"
    retained = json.loads(result.primary["retained_content"])
    assert retained["product_count"] == 1 and retained["visible_text_truncated"] is True
