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


def test_marketed_mhz_label_never_becomes_physical_or_transfer_unit():
    claims = extract([], "ram", {"memorySpeed": "6000 MHz"})
    assert claims[0].unit == "advertised-MHz" and claims[0].scope == "advertised"
    assert not validate(RAM, claims)  # agrees with requested nominal DDR grade only
    assert validate(RAM, extract([], "ram", {"memorySpeed": "3000 MHz"}))


@pytest.mark.parametrize(
    "field,raw,desired",
    [
        ("factory_liquid", "not factory liquid", GPU),
        ("factory_liquid", "factory liquid not installed", GPU),
        ("factory_liquid", "заводская СЖО не установлена", GPU),
        ("isComplete", "full mouse not supplied", MOUSE),
        ("isComplete", "not a full mouse", MOUSE),
        ("isComplete", "complete mouse is not included", MOUSE),
    ],
)
def test_structured_boolean_negation_never_becomes_positive(field, raw, desired):
    assert validate(desired, extract([], desired.category, {field: raw}))


@pytest.mark.parametrize(
    "field,raw,desired",
    [
        ("factory_liquid", "factory liquid", GPU),
        ("factory_liquid", "no seller conversion; factory liquid", GPU),
        ("factory_liquid", "factory liquid; not seller conversion", GPU),
        ("isComplete", "full mouse supplied", MOUSE),
        ("isComplete", "complete mouse included", MOUSE),
        ("isComplete", "full mouse; not receiver-only", MOUSE),
    ],
)
def test_positive_boolean_statements_and_negated_alternative_remain_supported(field, raw, desired):
    assert not validate(desired, extract([], desired.category, {field: raw}))


@pytest.mark.parametrize(
    "text",
    [
        "each module 48GB; total 96GB",
        "total 96GB; each module 48GB",
        "each module 48GB, total 96GB",
        "total 96GB, each module 48GB",
        "each module 48GB total 96GB",
        "total 96GB each module 48GB",
    ],
)
def test_capacity_subject_is_bound_to_declaration_not_prior_clause(text):
    assert not validate(RAM, extract([text], "ram"))


def test_conflicting_boolean_assertions_both_survive():
    claims = extract([], "mouse", {"isComplete": "full mouse supplied; full mouse not supplied"})
    assert {c.polarity for c in claims} == {"positive", "negative"}
    assert validate(MOUSE, claims) == ("full_item",)


def test_unknown_boolean_does_not_gain_truth_from_positive_word():
    claims = extract([], "gpu", {"factory_liquid": "factory liquid unconfirmed"})
    assert all(c.polarity == "unknown" and c.value is None for c in claims)
    assert validate(GPU, claims) == ("factory_liquid",)


@pytest.mark.parametrize(
    "field,value,desired,expected",
    [
        ("factory_liquid", "not factory liquid", GPU, "unresolved"),
        ("factory_liquid", "factory liquid not installed", GPU, "unresolved"),
        ("isComplete", "full mouse not supplied", MOUSE, "unresolved"),
        ("factory_liquid", "factory liquid installed", GPU, "exact"),
        ("isComplete", "full mouse supplied", MOUSE, "exact"),
        ("isComplete", "unknown; full mouse unconfirmed", MOUSE, "unresolved"),
    ],
)
def test_boolean_statements_through_actual_curated_reader(
    field, value, desired, expected, tmp_path
):
    from datetime import UTC, datetime
    from html import escape

    from pc_sourcing.curated_primary import CuratedReader
    from pc_sourcing.live_models import Candidate

    now = datetime.now(UTC)
    url = "https://28bit.ru/palit-card/"
    registry = {
        "origin": "https://28bit.ru",
        "status": "bounded_public_read",
        "reviewed_at": now.isoformat(),
        "listings": [{"url": url, "title": "SYNTHETIC CARD"}],
    }
    page = (
        "<h1>"
        + desired.name
        + '</h1><div itemscope itemtype="https://schema.org/Product"><meta itemprop="mpn" content="'
        + desired.mpn
        + '"><meta itemprop="'
        + field
        + '" content="'
        + escape(value, quote=True)
        + '"></div>'
    )
    calls = []

    def fetch(target):
        calls.append(target)
        if target.endswith("robots.txt"):
            return b"User-agent: *\nAllow: /", {"content-type": "text/plain"}
        return page.encode(), {"content-type": "text/html"}

    reader = CuratedReader(
        registry,
        tmp_path / "synthetic-source-state.json",
        transport=fetch,
        sleep=lambda delay: None,
    )
    candidate = Candidate(
        url=url, title="SYNTHETIC", queries=(), observed_at=now, response_sha256="a" * 64
    )
    observed = reader.observe(desired, candidate, now)
    assert observed.match == expected and observed.eligible is False
    assert len(calls) == 2


@pytest.mark.parametrize(
    "text",
    [
        "factory liquid possibly supplied",
        "factory liquid cannot be confirmed",
        "factory liquid?",
        "factory liquid not good",
        "factory liquid expected",
    ],
)
def test_unsupported_boolean_prose_is_unknown_instead_of_positive_substring(text):
    claims = extract([], "gpu", {"factory_liquid": text})
    assert all(c.polarity == "unknown" for c in claims)
    assert validate(GPU, claims) == ("factory_liquid",)


def test_completeness_module_count_is_a_scoped_assertion_not_just_matched_word():
    assert not validate(
        RAM,
        extract(
            [],
            "ram",
            {"additionalProperty": [{"name": "Kit completeness", "value": "2 matched modules"}]},
        ),
    )
    assert validate(
        RAM,
        extract(
            [],
            "ram",
            {"additionalProperty": [{"name": "Kit completeness", "value": "1 matched module"}]},
        ),
    ) == ("modules",)


@pytest.mark.parametrize(
    "positive,negative,attribute",
    [
        ("total 96GB", "total not 96GB", "capacity"),
        ("each module 48GB", "each module not 48GB", "capacity"),
        ("module capacity: 48GB", "module capacity: not 48GB", "capacity"),
        ("2 modules", "not 2 modules", "modules"),
        ("module count: 2", "module count: not 2", "modules"),
        ("effective transfer rate: 6000 MT/s", "effective transfer rate: not 6000 MT/s", "speed"),
        ("physical clock: 3000 MHz", "physical clock: not 3000 MHz", "clock"),
        ("CAS latency is 30 cycles", "CAS latency is not 30 cycles", "latency"),
        ("CL30", "CL not 30", "latency"),
        ("DDR5", "not DDR5", "memory_type"),
        ("DDR5-6000", "not DDR5-6000", "memory_grade"),
        ("2x48GB", "not 2x48GB", "topology"),
    ],
)
def test_every_numeric_extractor_preserves_positive_and_negative_polarity(
    positive, negative, attribute
):
    good = extract([positive], "ram")
    bad = extract([negative], "ram")
    assert any(c.attribute == attribute and c.polarity == "positive" for c in good)
    assert any(c.attribute == attribute and c.polarity == "negative" for c in bad)
    assert not validate(RAM, good)
    assert attribute in validate(RAM, bad)


@pytest.mark.parametrize(
    "name,positive,negative,attribute",
    [
        ("Total capacity", "96 GB", "not 96 GB", "capacity"),
        ("Capacity per module", "48GB", "not 48GB", "capacity"),
        ("Module count", "2", "not 2", "modules"),
        ("Transfer rate", "6000 MT/s", "not 6000 MT/s", "speed"),
        ("Physical clock", "3000 MHz", "not 3000 MHz", "clock"),
        ("CAS latency", "30 cycles", "not 30 cycles", "latency"),
        ("Memory generation", "DDR5", "not DDR5", "memory_type"),
    ],
)
def test_scalar_numeric_and_enum_schema_share_polarity(name, positive, negative, attribute):
    good = extract([], "ram", {"additionalProperty": [{"name": name, "value": positive}]})
    bad = extract([], "ram", {"additionalProperty": [{"name": name, "value": negative}]})
    assert not validate(RAM, good)
    assert attribute in validate(RAM, bad)


@pytest.mark.parametrize(
    "text",
    [
        "effective rate: maybe not 6000 MT/s",
        "physical clock: not necessarily 3000 MHz",
        "CAS latency maybe not 30 cycles",
        "total possibly 96GB",
        "not only 2 modules",
    ],
)
def test_uncertain_numeric_operator_never_supports_exact_match(text):
    claims = extract([text], "ram")
    assert any(c.polarity == "unknown" for c in claims)
    assert validate(RAM, claims)


def test_negated_topology_does_not_invent_negative_component_or_total_facts():
    claims = extract(["not 4x24GB"], "ram")
    assert [(c.attribute, c.polarity) for c in claims] == [("topology", "negative")]
    assert not validate(RAM, claims)  # excludes another topology; does not deny96GB


def test_negative_grade_does_not_negate_generation_independently():
    claims = extract(["not DDR5-5600"], "ram")
    assert not any(c.attribute == "memory_type" for c in claims)
    assert not validate(RAM, claims)


def test_adjacent_physical_and_effective_declarations_keep_their_own_subject():
    claims = extract(["physical clock 3000 MHz; effective rate 6000 MT/s"], "ram")
    assert {c.attribute for c in claims} >= {"clock", "speed"}
    assert not validate(RAM, claims)


@pytest.mark.parametrize(
    "text", ["effective transfer rate:not6000 MT/s", "CAS latency incorrectly30 cycles"]
)
def test_unparsed_numeric_declaration_is_a_gap_not_silently_ignored(text):
    assert "numeric_unknown" in validate(RAM, extract([text], "ram"))
