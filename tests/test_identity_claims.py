"""Typed assertion contract: unit, subject, polarity and unknown before MPN."""

from decimal import Decimal

import pytest

from pc_sourcing.identity_claims import extract, validate
from pc_sourcing.live_models import Request

RAM = Request(
    name="G.Skill 96 GB 2x48GB DDR5-6000 CL30 EXPO", mpn="F5-6000J3036F48GX2-TZ5NR", category="ram"
)
GPU = Request(name="MSI RTX 5090 SUPRIM LIQUID OC", mpn="G5090-32SLC", category="gpu")
MOUSE = Request(name="Logitech G PRO X2 SUPERSTRIKE", mpn="SYNTHETIC-MOUSE", category="mouse")


def test_clock_rate_and_capacity_subjects_are_distinct():
    assertions = extract(
        ["total 96GB, each module 48GB; 2x48GB DDR5-6000; physical clock 3000 MHz"], "ram"
    )
    assert any(
        c.attribute == "clock"
        and c.value == Decimal(3000)
        and c.unit == "MHz"
        and c.scope == "physical"
        for c in assertions
    )
    assert any(
        c.attribute == "speed" and c.unit == "MT/s" and c.scope == "effective" for c in assertions
    )
    assert any(
        c.attribute == "capacity" and c.scope == "module" and c.value == Decimal(48)
        for c in assertions
    )
    assert not validate(RAM, assertions)


@pytest.mark.parametrize("text", ["CAS 30 cycles", "CL30", "CAS latency 30 cycles"])
def test_latency_cycles_are_not_nanoseconds(text):
    assert not validate(RAM, extract([text], "ram"))
    assert "latency" in validate(RAM, extract(["CAS latency 30 ns"], "ram"))


@pytest.mark.parametrize(
    "model,text",
    [
        (GPU, "not a separate waterblock"),
        (GPU, "no aftermarket modifications"),
        (MOUSE, "not receiver-only"),
        (MOUSE, "not SUPERLIGHT"),
        (RAM, "without registered ECC"),
    ],
)
def test_negated_other_kind_is_not_an_affirmative_conflict(model, text):
    assert not validate(model, extract([text], model.category))


@pytest.mark.parametrize(
    "name,value",
    [
        ("Memory capacity per module", "24 GB"),
        ("Kit total capacity", "48 GB"),
        ("Transfer rate", "5800 MT/s"),
        ("CAS latency", "32 cycles"),
        ("Manufacturer", "Corsair"),
        ("Complete product", "unknown"),
    ],
)
def test_structured_attribute_subject_and_unsupported_values_are_preserved(name, value):
    assertions = extract([], "ram", {"additionalProperty": [{"name": name, "value": value}]})
    assert assertions and assertions[0].source.startswith("Product.additionalProperty")
    assert validate(RAM, assertions)


def test_unsupported_property_does_not_disappear():
    claims = extract(
        [],
        "mouse",
        {"additionalProperty": [{"name": "Undocumented identity mode", "value": "something"}]},
    )
    assert claims[0].polarity == "unknown"
    assert validate(MOUSE, claims) == ("unsupported_property",)


def test_false_main_item_presence_and_true_receiver_presence_are_distinct():
    claims = extract(
        [], "mouse", {"additionalProperty": [{"name": "Mouse included", "value": False}]}
    )
    assert validate(MOUSE, claims) == ("full_item",)


def test_unknown_cooling_does_not_become_factory_true():
    claims = extract(
        [], "gpu", {"additionalProperty": [{"name": "Factory cooling", "value": "unknown"}]}
    )
    assert claims[0].value is None and claims[0].polarity == "unknown"
    assert validate(GPU, claims) == ("factory_liquid",)


def test_time_latency_conversion_requires_explicit_physical_clock():
    assert "latency" in validate(RAM, extract(["CAS latency 10 ns"], "ram"))
    assert not validate(RAM, extract(["physical clock 3000 MHz; CAS latency 10 ns"], "ram"))
    assert "latency" in validate(
        RAM, extract(["physical clock 3000 MHz; CAS latency 30 ns"], "ram")
    )


def test_secondary_presence_cannot_stand_for_main_presence():
    claims = extract(
        [],
        "mouse",
        {
            "additionalProperty": [
                {"name": "Receiver included", "value": True},
                {"name": "Mouse included", "value": False},
            ]
        },
    )
    assert {c.scope for c in claims} == {"accessory", "product"}
    assert validate(MOUSE, claims) == ("full_item",)


def test_malformed_property_name_is_an_explicit_unknown():
    assert validate(
        MOUSE, extract([], "mouse", {"additionalProperty": [{"name": None, "value": False}]})
    ) == ("schema",)


def test_text_budget_blocks_confirmation():
    assert "text_budget" in validate(MOUSE, extract(["x" * 17000], "mouse"))


@pytest.mark.parametrize(
    "desired,title,expected",
    [
        (
            RAM,
            "Оперативная память G.Skill 96GB 2x48GB DDR5-6000 CL30 EXPO; physical clock 3000 MHz; each module 48GB",
            "exact",
        ),
        (GPU, "MSI RTX 5090 SUPRIM LIQUID OC; не отдельный водоблок", "exact"),
        (GPU, "MSI RTX 5090 SUPRIM LIQUID OC; no aftermarket modifications", "exact"),
        (MOUSE, "Logitech G PRO X2 SUPERSTRIKE; not receiver-only", "exact"),
        (MOUSE, "Logitech G PRO X2 SUPERSTRIKE; not SUPERLIGHT", "exact"),
        (GPU, "MSI RTX 5090 SUPRIM LIQUID OC; radiator only", "unresolved"),
        (MOUSE, "Logitech G PRO X2 SUPERSTRIKE; standalone dongle", "unresolved"),
        (MOUSE, "Logitech G PRO X2 SUPERSTRIKE; самой мыши нет", "unresolved"),
    ],
)
def test_curated_route_scoped_assertions_reported_separately(desired, title, expected):
    import json
    from datetime import UTC, datetime

    from pc_sourcing.curated_primary import observe
    from pc_sourcing.live_models import Candidate

    now = datetime.now(UTC)
    page = (
        "<h1>"
        + title
        + '</h1><div itemscope itemtype="https://schema.org/Product"><meta itemprop="mpn" content="'
        + desired.mpn
        + '"></div>'
    )
    c = Candidate(
        url="https://synthetic.example.test/card",
        title="SYNTHETIC",
        queries=(),
        observed_at=now,
        response_sha256="a" * 64,
    )
    o = observe(desired, c, page, {}, now)
    assert o.match == expected
    assert isinstance(json.loads(o.primary["retained_content"])["identity_assertions"], list)


def test_curated_unknown_propertyvalue_schema_does_not_silently_confirm():
    from datetime import UTC, datetime

    from pc_sourcing.curated_primary import observe
    from pc_sourcing.live_models import Candidate

    now = datetime.now(UTC)
    page = (
        "<h1>"
        + MOUSE.name
        + '</h1><div itemscope itemtype="https://schema.org/Product"><meta itemprop="mpn" content="'
        + MOUSE.mpn
        + '"><div itemprop="additionalProperty" itemscope itemtype="https://schema.org/PropertyValue"><meta itemprop="name" content="Mouse included"><meta itemprop="value" content="false"></div></div>'
    )
    c = Candidate(
        url="https://synthetic.example.test/card",
        title="SYNTHETIC",
        queries=(),
        observed_at=now,
        response_sha256="a" * 64,
    )
    assert observe(MOUSE, c, page, {}, now).match == "unresolved"


def test_curated_brand_relation_conflict_is_not_lost_as_nested_name():
    from datetime import UTC, datetime

    from pc_sourcing.curated_primary import observe
    from pc_sourcing.live_models import Candidate

    now = datetime.now(UTC)
    page = (
        "<h1>"
        + MOUSE.name
        + '</h1><div itemscope itemtype="https://schema.org/Product"><meta itemprop="mpn" content="'
        + MOUSE.mpn
        + '"><div itemprop="brand" itemscope itemtype="https://schema.org/Brand"><meta itemprop="name" content="Razer"></div></div>'
    )
    c = Candidate(
        url="https://synthetic.example.test/card",
        title="SYNTHETIC",
        queries=(),
        observed_at=now,
        response_sha256="a" * 64,
    )
    assert observe(MOUSE, c, page, {}, now).match == "unresolved"


@pytest.mark.parametrize("title", ["Unspecified item", "G.Skill"])
def test_copied_code_alone_cannot_confirm_ram_model(title):
    from pc_sourcing.live_sourcing import identity

    assert identity(RAM, title, RAM.mpn)[0] == "unresolved"
