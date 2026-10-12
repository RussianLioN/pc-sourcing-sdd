"""Source-field confirmations, unchanged PAY adapter and comparable normalized rows."""

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from pc_sourcing.evaluate import evaluate, utc_time
from pc_sourcing.identity_claims import Claim, assertions_data, extract, validate
from pc_sourcing.live_sourcing import identity
from pc_sourcing.models import Evidence as LegacyEvidence
from pc_sourcing.models import Offer as LegacyOffer
from pc_sourcing.models import Route as LegacyRoute
from pc_sourcing.normalized_models import Fulfillment, Money, NormalizedOffer, Price, Warranty

PRIMARY = {
    "store_card",
    "seller_statement",
    "platform_transaction",
    "manufacturer_spec",
    "operator_review",
}
FAST = {
    "price",
    "stock",
    "available_quantity",
    "complete_item",
    "fulfillment",
    "delivery_cost",
    "other_cost",
}
MODEL_FIELDS = {
    "price": Price,
    "warranty": Warranty,
    "fulfillment": Fulfillment,
    "delivery_cost": Money,
    "other_cost": Money,
}


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    )


def shape(field, value):
    if value is not None and field in MODEL_FIELDS:
        return MODEL_FIELDS[field].model_validate(value).model_dump(mode="json")
    return value


def scope_matches(offer, field, scope):
    """Optional metadata may be absent; explicit conflicting context is never ignored."""
    expected = {
        "mpn": offer.mpn,
        "quantity": offer.request.quantity,
        "region": offer.request.region,
        "offer_id": offer.id,
        "listing_id": offer.listing_id,
    }
    if field in {"price", "delivery_cost", "other_cost"}:
        money = (
            offer.price.money if field == "price" and offer.price else getattr(offer, field, None)
        )
        expected.update(
            price_id=offer.price.id if offer.price else None,
            currency=money.currency if money else None,
            amount=money.amount if money else None,
        )
        if field == "price":
            expected.update(
                basis=offer.price.basis if offer.price else None,
                kind=offer.price.kind if offer.price else None,
            )
    for key in expected.keys() & scope.keys():
        actual, wanted = scope[key], expected[key]
        if wanted is None or actual is None:
            return False
        if key == "amount":
            try:
                actual = Money(amount=actual, currency="RUB").amount
            except (ValueError, TypeError):
                return False
            if actual != wanted:
                return False
        elif canonical(actual) != canonical(wanted):
            return False
    return True


def field_state(offer, field, as_of):
    expected = shape(field, offer.model_dump(mode="json").get(field))
    records = [e for e in offer.evidence if e.field == field]
    current = []
    states = []
    for e in records:
        age = as_of - e.observed_at
        ttl = 3600 if field in FAST else 86400
        status = (
            "future"
            if age.total_seconds() < 0
            else "stale"
            if age.total_seconds() > ttl
            else "snippet"
            if e.origin == "search_snippet" or offer.source == "snippet"
            else "current"
        )
        states.append(
            {
                "id": e.id,
                "status": status,
                "url": e.url,
                "observed_at": e.observed_at.isoformat(),
                "origin": e.origin,
                "content_sha256": e.content_sha256,
            }
        )
        allowed = {"store_card", "seller_statement", "platform_transaction"}
        if field in {"title", "mpn", "factory_liquid", "warranty"}:
            allowed.add("manufacturer_spec")
        if field in {
            "seller_checked",
            "seller_entity_key",
            "analogue_compatible",
            "analogue_differences",
        }:
            allowed.add("operator_review")
        if status == "current" and e.origin in allowed:
            if not scope_matches(offer, field, e.scope):
                return {"status": "conflict", "evidence": states}
            current.append(e)
    try:
        values = [canonical(shape(field, e.value)) for e in current]
    except (ValueError, TypeError):
        return {"status": "conflict", "evidence": states}
    if expected is None:
        return {"status": "unknown", "evidence": states}
    if not values:
        return {"status": "unconfirmed", "evidence": states}
    if any(v != canonical(expected) for v in values):
        return {"status": "conflict", "evidence": states}
    return {"status": "confirmed", "evidence": states}


def item_amount(offer):
    p = offer.price
    if (
        not p
        or p.kind != "unconditional"
        or p.basis == "unknown"
        or p.quantity is None
        or p.money.currency != "RUB"
    ):
        return None
    if p.basis == "purchase":
        return p.money.amount if p.quantity == offer.request.quantity else None
    if p.quantity != 1:
        return None
    return p.money.amount * offer.request.quantity


def payment_projection(offer, as_of):
    """Only payment results are consumed. Nonpayment placeholders never enter public data."""
    amount = item_amount(offer)
    routes = {}
    evidence = []
    for e in offer.evidence:
        if e.origin not in {
            "store_card",
            "seller_statement",
            "platform_transaction",
            "search_snippet",
        }:
            continue
        field = "sku" if e.field == "mpn" else e.field
        value = str(e.value).lower() if type(e.value) is bool else str(e.value)
        evidence.append(
            LegacyEvidence(
                id=e.id,
                offer_id=offer.id,
                url=e.url,
                observed_at=e.observed_at,
                field=field,
                value=value,
                origin=e.origin,
                synthetic=offer.synthetic,
            )
        )
    for name in ("protected", "postpay"):
        r = getattr(offer, name)
        context = (
            isinstance(offer.mpn, str)
            and bool(offer.mpn.strip())
            and r.applies_mpn == offer.mpn
            and r.applies_quantity == offer.request.quantity
            and r.applies_amount is not None
            and amount is not None
            and r.applies_amount.currency == "RUB"
            and r.applies_amount.amount == amount
            and offer.price is not None
            and r.price_id == offer.price.id
        )
        expected_scope = {
            "mpn": offer.mpn,
            "quantity": offer.request.quantity,
            "amount": str(amount),
            "currency": "RUB",
            "region": "Москва",
            "price_id": offer.price.id if offer.price else None,
        }
        valid_ids = []
        for e in offer.evidence:
            if e.id not in r.evidence_ids:
                continue
            scope = dict(e.scope)
            try:
                same_amount = Money(amount=scope.get("amount"), currency="RUB").amount == amount
            except (ValueError, TypeError, ArithmeticError):
                same_amount = False
            if same_amount and all(
                canonical(scope.get(k)) == canonical(v)
                for k, v in expected_scope.items()
                if k != "amount"
            ):
                valid_ids.append(e.id)
        # False here means confirmation predicate not satisfied, not a rewritten source fact.
        routes[name] = LegacyRoute(
            status=r.status,
            covers_item=r.covers_item is True and context,
            covers_amount=r.covers_amount is True and context,
            covers_region=r.covers_region is True,
            covers_order=r.covers_order is True,
            external_advance_required=r.external_advance_required,
            evidence_ids=tuple(valid_ids),
            reason=r.reason,
        )
    projected = LegacyOffer(
        id=offer.id,
        product=offer.request.category
        if offer.request.category in {"gpu", "ram", "mouse"}
        else "mouse",
        sku=offer.mpn or "unknown",
        title=offer.title,
        source=offer.source,
        url=offer.url,
        observed_at=offer.observed_at,
        synthetic=offer.synthetic,
        price_rub=None,
        stock="unknown",
        region="unknown",
        condition="unknown",
        seller_checked=False,
        factory_liquid=None,
        global_advance_required=offer.global_advance_required,
        global_payment_conflict=offer.global_payment_conflict is True,
        optional_risky_alternative=offer.optional_risky_alternative is True,
        protected=routes["protected"],
        postpay=routes["postpay"],
        evidence=tuple(evidence),
    )
    result = evaluate(projected, as_of)
    return {
        "passed": result.payment_gate_passed,
        "passed_routes": list(result.passed_routes),
        "reasons": [
            r
            for r in result.reasons
            if r.startswith(("protected:", "postpay:", "Глобальный", "Отсутствие", "Предложен"))
        ],
    }


def identity_assertions(offer):
    """Independent claim streams have no dictionary override precedence."""
    claims = [
        replace(c, source="offer.title/" + c.source)
        for c in extract([offer.title], offer.request.category)
    ]
    claims.extend(
        replace(c, source="attributes/" + c.source)
        for c in extract([], offer.request.category, offer.attributes)
    )
    top = {}
    if offer.factory_liquid is not None:
        top["factory_liquid"] = offer.factory_liquid
    if offer.complete_item is not None:
        top["isComplete"] = offer.complete_item
    claims.extend(
        replace(c, source="top_level/" + c.source) for c in extract([], offer.request.category, top)
    )
    # The frozen schema parser intentionally skips Product.mpn/sku/name/description.
    # Here they are independent normalized identity declarations, not card metadata.
    for key in ("mpn", "sku"):
        if key in offer.attributes:
            raw = offer.attributes[key]
            known = isinstance(raw, str) and bool(raw.strip())
            claims.append(
                Claim(
                    "mpn",
                    raw if known else None,
                    "",
                    "product",
                    "positive" if known else "unknown",
                    "attributes/" + key,
                    str(raw),
                )
            )
    if offer.mpn:
        claims.append(
            Claim("mpn", offer.mpn, "", "product", "positive", "top_level/mpn", offer.mpn)
        )
    for key in ("name", "description"):
        if key in offer.attributes:
            raw = offer.attributes[key]
            if isinstance(raw, str):
                claims.extend(
                    replace(c, source="attributes/" + key + "/" + c.source)
                    for c in extract([raw], offer.request.category)
                )
            else:
                claims.append(
                    Claim("schema", None, "", "product", "unknown", "attributes/" + key, str(raw))
                )
    return tuple(claims)


def assertion_collisions(claims):
    """Compare normalized dimensions and polarity, retaining every original claim."""
    slots = {}
    unknown = {c.attribute for c in claims if c.polarity == "unknown" or c.value is None}
    for c in claims:
        if c.polarity == "unknown" or c.value is None:
            continue  # frozen validator already reports unknown material claims
        value, polarity = c.value, c.polarity
        if type(value) is bool and polarity == "negative":
            value, polarity = not value, "positive"
        positive, negative = slots.setdefault((c.attribute, c.scope, c.unit), (set(), set()))
        (positive if polarity == "positive" else negative).add((type(value), value))
    return tuple(
        sorted(
            unknown
            | {
                attribute
                for (attribute, _scope, _unit), (positive, negative) in slots.items()
                if len(positive) > 1 or positive & negative
            }
        )
    )


def evaluate_offer(offer: NormalizedOffer, as_of):
    as_of = utc_time(as_of)
    states = {}
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
    for f in fields:
        states[f] = field_state(offer, f, as_of)

    def confirmed(f):
        return states[f]["status"] == "confirmed"

    match, differences = identity(offer.request, offer.title, offer.mpn)
    claims = identity_assertions(offer)
    problems = tuple(
        sorted(
            set(
                validate(
                    offer.request,
                    tuple(c for c in claims if c.attribute != "mpn"),
                    allow_variant_difference=bool(
                        offer.mpn and offer.request.mpn and offer.mpn != offer.request.mpn
                    ),
                )
            )
            | set(assertion_collisions(claims))
        )
    )
    if not (isinstance(offer.mpn, str) and offer.mpn.strip()) and any(
        c.attribute == "mpn" and c.source.startswith("attributes/") for c in claims
    ):
        problems = tuple(sorted(set(problems) | {"mpn"}))
    if problems and match != "excluded":
        match = "unresolved"
        differences = ("Conflicting normalized identity: " + ", ".join(problems),)
    if not confirmed("title") or (offer.request.mpn is not None and not confirmed("mpn")):
        match = "unresolved"
    subtotal = item_amount(offer) if confirmed("price") else None
    known = subtotal
    full = None
    costs = []
    for name in ("delivery_cost", "other_cost"):
        m = getattr(offer, name)
        if m is not None and m.currency == "RUB" and confirmed(name):
            costs.append(m.amount)
        else:
            costs.append(None)
    if subtotal is not None:
        known = subtotal + sum((c for c in costs if c is not None), Decimal(0))
        if all(c is not None for c in costs):
            full = known
    pay = payment_projection(offer, as_of)
    gates = {
        "supported_identity": match == "exact"
        or (
            match == "analogue"
            and offer.analogue_compatible is True
            and bool(offer.analogue_differences)
            and confirmed("analogue_compatible")
            and confirmed("analogue_differences")
        ),
        "quantity": offer.available_quantity is not None
        and offer.available_quantity >= offer.request.quantity
        and confirmed("available_quantity"),
        "complete_item": offer.complete_item is True and confirmed("complete_item"),
        "condition": offer.condition in {"new", "sealed"} and confirmed("condition"),
        "warranty": bool(
            offer.warranty.issuer and offer.warranty.months and offer.warranty.territory
        )
        and offer.warranty.applicable_moscow is True
        and confirmed("warranty"),
        "moscow": offer.fulfillment.city == "Москва"
        and offer.fulfillment.confirmed is True
        and offer.fulfillment.method != "unknown"
        and confirmed("fulfillment"),
        "stock": offer.stock == "in_stock" and confirmed("stock"),
        "seller_check": offer.seller_checked is True
        and confirmed("seller_checked")
        and bool(offer.seller_entity_key)
        and confirmed("seller_entity_key"),
        "factory_liquid": offer.request.category != "gpu"
        or offer.factory_liquid is True
        and confirmed("factory_liquid"),
        "full_unconditional_price": full is not None,
        "offer_time": timedelta(0) <= as_of - offer.observed_at <= timedelta(hours=24),
        "primary_source": offer.source != "snippet",
        "payment": offer.source != "avito" or pay["passed"],
    }
    data_ready = all(gates.values())
    manual = offer.source == "avito" and not pay["passed"]

    def amount_text(a):
        return format(a, ".2f") if a is not None else None

    seller_key = offer.seller_entity_key if confirmed("seller_entity_key") else None
    return {
        "offer_id": offer.id,
        "synthetic": offer.synthetic,
        "match": match,
        "differences": list(differences),
        "identity_assertions": assertions_data(claims),
        "meets_data_gates": data_ready,
        "purchase_ready": data_ready and not offer.synthetic,
        "label": "требует ручной проверки"
        if manual
        else "synthetic — data gates passed"
        if data_ready and offer.synthetic
        else "подтверждено по данным"
        if data_ready
        else "недостаточно подтверждений",
        "gates": gates,
        "gaps": [name for name, ok in gates.items() if not ok],
        "field_states": states,
        "item_subtotal_rub": amount_text(subtotal),
        "known_cost_rub": amount_text(known),
        "full_total_rub": amount_text(full),
        "payment": pay,
        "confirmed_seller_key": seller_key,
        "evaluated_at": as_of.isoformat(),
    }


def compare(offers, as_of):
    offers = list(offers)
    if len({o.synthetic for o in offers}) > 1:
        raise ValueError("real and synthetic datasets must be separate")
    if len({o.id for o in offers}) != len(offers):
        raise ValueError("offer IDs must be unique")
    rows = []
    seen = {}
    rejections = []
    for offer in sorted(offers, key=lambda o: (o.observed_at, o.id), reverse=True):
        listing = (urlsplit(offer.url).netloc, offer.listing_id) if offer.listing_id else offer.url
        key = (
            listing,
            canonical(offer.request.model_dump(mode="json")),
            offer.mpn,
            offer.condition,
        )
        if key in seen:
            rejections.append(
                {
                    "offer_id": offer.id,
                    "reason": "duplicate canonical listing/request",
                    "retained_offer_id": seen[key],
                    "offer": offer.model_dump(mode="json"),
                }
            )
            continue
        seen[key] = offer.id
        result = evaluate_offer(offer, as_of)
        rows.append({"offer": offer.model_dump(mode="json"), "decision": result})
    confirmed = {
        r["decision"]["confirmed_seller_key"] for r in rows if r["decision"]["confirmed_seller_key"]
    }
    ranks = {}
    requests = {canonical(r["offer"]["request"]) for r in rows}
    for request_key in sorted(requests):
        ranks[request_key] = {}
        for group in ("exact", "analogue"):
            candidates = [
                r
                for r in rows
                if canonical(r["offer"]["request"]) == request_key
                and r["decision"]["match"] == group
                and r["decision"]["full_total_rub"] is not None
                and r["decision"]["meets_data_gates"]
            ]
            ranks[request_key][group] = [
                r["offer"]["id"]
                for r in sorted(candidates, key=lambda r: Decimal(r["decision"]["full_total_rub"]))
            ]
    return {
        "schema_version": "1.0.0",
        "as_of": utc_time(as_of).isoformat(),
        "rows": rows,
        "rejections": rejections,
        "independent_sellers_confirmed": len(confirmed),
        "unknown_seller_relations": sum(
            r["decision"]["confirmed_seller_key"] is None for r in rows
        ),
        "rankings": ranks,
        "all_synthetic": bool(rows) and all(r["offer"]["synthetic"] for r in rows),
        "full_product_dod": "not complete",
    }
