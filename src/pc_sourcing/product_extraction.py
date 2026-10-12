"""Offline selected-Product adapter. No HTTP; displayed amounts never imply purchase price."""

import hashlib
import json
import re
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from html.parser import HTMLParser
from typing import Literal

from pydantic import BaseModel, ConfigDict

from pc_sourcing.collection_capture import Capture
from pc_sourcing.identity_claims import assertions_data, extract, positive_text, validate
from pc_sourcing.live_models import Candidate, Fact, Observation, Request, canonical_url
from pc_sourcing.live_sourcing import CardHTML, identity, products
from pc_sourcing.normalized_offers import assertion_collisions

SPACE = " \u00a0\u202f"
CONDITIONAL = re.compile(
    r"залог|задаток|аванс|предоплат|рассроч|кредит|перв\w*\s+плат[её]ж|"
    r"в\s+месяц|/\s*мес|при\s+оплате|наличными|скидк|промокод|по\s+карте|"
    r"бонус|к[еэ]шб[еэ]к|подписк|installment|deposit|monthly|cash\s+only|discount",
    re.IGNORECASE,
)
CODE = re.compile(r"(?<![\w-])(?:F5-[A-Z0-9]+-[A-Z0-9]+|G5090-[A-Z0-9]+|910-\d{6})(?![\w-])")
SENSITIVE = re.compile(
    r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9_]{16,}|Bearer\s+\S+|[\w.+-]+@[\w.-]+", re.I
)

VOID = {
    "meta",
    "link",
    "img",
    "input",
    "br",
    "hr",
    "source",
    "area",
    "wbr",
    "embed",
    "base",
    "col",
    "param",
    "track",
}


class ScopedMicrodata(HTMLParser):
    """28BIT-style scalar microdata, owned by the nearest Product/Offer scope."""

    def __init__(self):
        super().__init__()
        self.stack, self.products = [], []

    @staticmethod
    def put(owner, key, value):
        if value is None:
            return
        old = owner.get(key)
        if old is None:
            owner[key] = value
        elif old != value:
            owner[key] = [*old, value] if isinstance(old, list) else [old, value]

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        previous = self.stack[-1] if self.stack else {}
        owner, kind = previous.get("owner"), previous.get("kind")
        prop = attrs.get("itemprop", "").split()
        if "itemscope" in attrs:
            raw_type = attrs.get("itemtype", "")
            valid = re.fullmatch(
                r"https?://schema.org/(Product|Offer|Brand|PropertyValue)", raw_type
            )
            next_kind = valid[1] if valid else "unknown"
            next_owner = {"@type": next_kind}
            if next_kind == "Product":
                if "itemid" in attrs:
                    next_owner["url"] = attrs["itemid"]
                self.products.append(next_owner)
            elif owner is not None and prop:
                for name in prop:
                    self.put(owner, name, next_owner)
            owner, kind = next_owner, next_kind
            prop = []
        frame = {
            "tag": tag,
            "owner": owner,
            "kind": kind,
            "prop": prop,
            "chunks": [],
            "hidden": previous.get("hidden", False) or tag in {"script", "style"},
        }
        value = attrs.get("content", attrs.get("href"))
        if value is not None and owner is not None:
            for name in prop:
                self.put(owner, name, value)
            frame["prop"] = []
        if tag == "h1" and kind == "Product":
            frame["heading"] = True
        if tag not in VOID:
            self.stack.append(frame)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.stack or self.stack[-1]["hidden"]:
            return
        owner = self.stack[-1]["owner"]
        for frame in self.stack:
            if frame["owner"] is owner and (frame["prop"] or frame.get("heading")):
                frame["chunks"].append(data)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        matches = [i for i, frame in enumerate(self.stack) if frame["tag"] == tag]
        if not matches:
            return
        index = matches[-1]
        for frame in self.stack[index:]:
            owner = frame["owner"]
            if owner is None:
                continue
            text = "".join(frame["chunks"]).strip()
            for prop in frame["prop"]:
                self.put(owner, prop, text)
            if frame.get("heading") and text:
                if "name" not in owner:
                    owner["name"] = text
                else:
                    owner["@heading"] = text
        del self.stack[index:]


class Witness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    raw: str | int | bool | float | None
    raw_type: str
    selector: str
    url: str
    observed_at: datetime
    origin: str = "store_card"
    kind: Literal["displayed", "conditional_or_unknown"]
    parsed_amount_rub: str | None = None
    raw_sha256: str
    condition_markers: tuple[str, ...] = ()


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation: Observation
    price_tokens: tuple[Witness, ...] = ()
    displayed_amount_rub: str | None = None
    identity_conflicts: tuple[str, ...] = ()
    synthetic: bool
    adapter_version: str = "T015/1.0.0/offline"


class JsonNumber(str):
    """Original JSON numeric lexeme, never rounded through a binary float."""


class DuplicateMember(ValueError):
    pass


def unique_members(pairs):
    """Reject repeated decoded keys at every object depth before dict construction."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateMember("Duplicate JSON member")
        result[key] = value
    return result


def reject_constant(_value):
    raise ValueError("Nonstandard nonfinite JSON number")


def parse_rub_token(token):
    """Strict positive Russian locale scalar grammar; no floats, guessing or rounding."""
    if type(token) is int:
        return Decimal(token).quantize(Decimal(".01")) if 0 < token < 10**10 else None
    if type(token) is not str or len(token) > 80 or any(ord(c) < 32 for c in token):
        return None
    value = token.strip(SPACE)
    value = re.sub(r"[ \u00a0\u202f]*(?:₽|RUB|руб\.?)[ \u00a0\u202f]*$", "", value, flags=re.I)
    if re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,2})?", value):
        value = value.replace(",", ".")
    elif re.fullmatch(r"[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+(?:[.,][0-9]{1,2})?", value):
        value = re.sub(r"[ \u00a0\u202f]", "", value).replace(",", ".")
    elif re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3})+,[0-9]{1,2}", value):
        value = value.replace(".", "").replace(",", ".")
    else:
        return None
    amount = Decimal(value)
    return amount.quantize(Decimal(".01")) if 0 < amount < 10**10 else None


def scalar(value, maximum):
    if (
        type(value) is str
        and len(value) <= maximum
        and not any(ord(c) < 32 for c in value)
        and not SENSITIVE.search(value)
    ):
        return value
    return None


def bound_url(product, url):
    declared = [product[k] for k in ("url", "@id") if k in product]
    if not declared:
        return None
    try:
        return all(isinstance(v, str) and canonical_url(v) == url for v in declared)
    except ValueError:
        return False


def extract_card(
    request: Request, candidate: Candidate, html: str, now: datetime, *, synthetic: bool
):
    if now.tzinfo is None or type(synthetic) is not bool:
        raise ValueError("aware original source timestamp and explicit realm required")
    if not isinstance(html, str) or len(html.encode()) > 1_000_000:
        raise ValueError("bounded local HTML required")
    document = CardHTML()
    document.feed(html)

    def failed(reason):
        return Extraction(
            observation=Observation(
                candidate=candidate,
                status="unresolved",
                reason=reason,
                primary={
                    "retrieved_at": now.isoformat(),
                    "response_body_sha256": hashlib.sha256(html.encode()).hexdigest(),
                    "adapter": "T015/offline",
                },
            ),
            synthetic=synthetic,
        )

    try:
        found = [
            p
            for block in document.blocks
            for p in products(
                json.loads(
                    block,
                    parse_int=JsonNumber,
                    parse_float=JsonNumber,
                    parse_constant=reject_constant,
                    object_pairs_hook=unique_members,
                )
            )
        ]
    except DuplicateMember:
        return failed("Duplicate JSON member; primary JSON-LD is ambiguous")
    except (ValueError, RecursionError):
        return failed("Malformed or overnested JSON-LD")
    layout = "JSON-LD"
    if not found:
        microdata = ScopedMicrodata()
        microdata.feed(html)
        found, layout = microdata.products, "microdata"
    matching = [(i, p) for i, p in enumerate(found) if bound_url(p, candidate.url) is True]
    if len(matching) == 1:
        index, product = matching[0]
    elif len(found) == 1 and bound_url(found[0], candidate.url) is None:
        index, product = 0, found[0]
    else:
        return failed("Selected Product URL unbound, contradictory or ambiguous")
    selector = f"{layout}.Product[{index}]"
    title = scalar(product.get("name"), 500)
    description = scalar(product.get("description"), 4000)
    if not title:
        return failed("Selected Product title missing or outside bounded scalar grammar")
    issues = []
    if product.get("description") is not None and description is None:
        issues.append("description")
    declared = product.get("mpn")
    mpn = scalar(declared, 100)
    if declared is not None and (not mpn or not mpn.strip()):
        issues.append("mpn")
    codes = set(CODE.findall(title.upper()))
    if request.mpn and re.search(
        r"(?<![\w-])" + re.escape(request.mpn.upper()) + r"(?![\w-])", title.upper()
    ):
        codes.add(request.mpn.upper())
    asserted_codes = {
        c
        for c in codes
        if re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", positive_text(title))
    }
    if codes != asserted_codes or len(codes) > 1 or (mpn and codes and {mpn.upper()} != codes):
        issues.append("mpn")
    derived = mpn is None and len(asserted_codes) == 1 and "mpn" not in issues
    if derived:
        mpn = next(iter(asserted_codes))
    match, differences = identity(request, title, mpn)
    # These schema identity/link edges describe other products, not attributes of
    # this selected Product. Unknown material properties are still validated.
    structured = {
        k: v
        for k, v in product.items()
        if k not in {"@id", "isRelatedTo", "isSimilarTo", "@heading"}
    }
    heading = product.get("@heading")
    if heading is not None and scalar(heading, 500) is None:
        issues.append("heading")
    claims = extract([title, description, heading], request.category, structured)
    claims = tuple(replace(c, source=selector + "/" + c.source) for c in claims)
    safe_claims = []
    for claim in claims:
        if (
            SENSITIVE.search(str(claim.value))
            or SENSITIVE.search(claim.source)
            or len(str(claim.value)) > 500
        ):
            issues.append("unsafe_identity_metadata")
            claim = replace(
                claim,
                value=None,
                polarity="unknown",
                source=selector + "/redacted_property",
                raw="",
            )
        safe_claims.append(claim)
    claims = tuple(safe_claims)
    issues.extend(
        validate(
            request,
            claims,
            allow_variant_difference=bool(mpn and request.mpn and mpn != request.mpn),
        )
    )
    issues.extend(assertion_collisions(claims))
    problems = tuple(sorted(set(issues)))
    if problems and match != "excluded":
        match, differences = (
            "unresolved",
            ("Conflicting selected Product attributes: " + ", ".join(problems),),
        )
    offers = product.get("offers", [])
    offers = offers if isinstance(offers, list) else [offers]
    if len(offers) > 20:
        return failed("Offer count exceeds bounded selected Product grammar")
    tokens = []
    reasons = []
    amount, stock, condition = None, "unknown", "unknown"
    offer = offers[0] if len(offers) == 1 and isinstance(offers[0], dict) else None
    if offer is None or offer.get("@type") != "Offer":
        reasons.append("Exactly one selected Product Offer not confirmed")
        offer = None
    context_markers = tuple(m[0] for m in CONDITIONAL.finditer((description or "") + " " + title))
    conditional = bool(context_markers)
    for i, item in enumerate(offers):
        if not isinstance(item, dict):
            continue
        raw = item.get("price")
        raw_type = "json_number_lexeme" if isinstance(raw, JsonNumber) else type(raw).__name__
        if isinstance(raw, JsonNumber):
            raw = str(raw)
        if type(raw) is str and (
            len(raw) > 80 or any(ord(c) < 32 for c in raw) or SENSITIVE.search(raw)
        ):
            reasons.append("Price token outside safe scalar retention grammar")
            continue
        if (
            type(raw) not in (str, int, bool, float, type(None))
            or type(raw) is float
            and not Decimal(str(raw)).is_finite()
        ):
            reasons.append("Price token unsupported non-scalar/nonfinite value")
            continue
        item_context = " ".join(
            str(item[k])
            for k in ("name", "description")
            if type(item.get(k)) is str and len(item[k]) <= 4000
        )
        item_markers = tuple(m[0] for m in CONDITIONAL.finditer(item_context))
        ambiguous = (
            conditional
            or bool(item_markers)
            or "priceSpecification" in item
            or any(k in item and scalar(item[k], 4000) is None for k in ("name", "description"))
            or offer is None
        )
        parsed = (
            parse_rub_token(raw) if item.get("priceCurrency") == "RUB" and not ambiguous else None
        )
        path = selector + (
            ".offers.price"
            if not isinstance(product.get("offers"), list)
            else f".offers[{i}].price"
        )
        tokens.append(
            Witness(
                raw=raw,
                raw_type=raw_type,
                selector=path,
                url=candidate.url,
                observed_at=now,
                kind="displayed" if parsed is not None else "conditional_or_unknown",
                parsed_amount_rub=str(parsed) if parsed is not None else None,
                raw_sha256=hashlib.sha256(
                    json.dumps(raw, ensure_ascii=False, allow_nan=False).encode()
                ).hexdigest(),
                condition_markers=context_markers
                + item_markers
                + (("priceSpecification",) if "priceSpecification" in item else ()),
            )
        )
        if parsed is not None and item is offer:
            amount = str(parsed)
        else:
            reasons.append("Displayed amount unsupported or conditional; no regular purchase price")
    props = {"name": [title]}
    if mpn and not derived:
        props["mpn"] = [mpn]
    if offer is not None:
        raw_stock = offer.get("availability")
        if type(raw_stock) is str and len(raw_stock) <= 100:
            props["availability"] = [raw_stock]
            stock = {
                scheme + "://schema.org/" + state: result
                for scheme in ("http", "https")
                for state, result in [
                    ("InStock", "in_stock"),
                    ("PreOrder", "preorder"),
                    ("OutOfStock", "unavailable"),
                    ("Discontinued", "unavailable"),
                ]
            }.get(raw_stock, "unknown")
        raw_condition = offer.get("itemCondition")
        if type(raw_condition) is str and len(raw_condition) <= 100:
            props["itemCondition"] = [raw_condition]
            condition = {
                scheme + "://schema.org/" + state: result
                for scheme in ("http", "https")
                for state, result in [("NewCondition", "new"), ("UsedCondition", "used")]
            }.get(raw_condition, "unknown")
    selected = {
        "synthetic": synthetic,
        "h1": title,
        "properties": props,
        "identity_assertions": [
            {k: v for k, v in c.items() if k != "raw"} for c in assertions_data(claims)
        ],
        "identity_conflicts": list(problems),
        "price_tokens": [w.model_dump(mode="json") for w in tokens],
        "retention": "selected Product scalar witnesses; no full HTML or description retained",
    }
    if amount is not None:
        selected["displayed_price_rub"] = amount
    raw = json.dumps(selected, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if len(raw) > 65536:
        return failed("Selected evidence exceeds capture bound; no silent truncation")
    sha = hashlib.sha256(raw.encode()).hexdigest()
    facts = []
    for field, value, path in [
        ("title", title, selector + ".name"),
        ("mpn", mpn, selector + (".name/title-derived MPN" if derived else ".mpn")),
        ("displayed_price_rub", amount, tokens[0].selector if tokens else selector),
        ("stock", stock if stock != "unknown" else None, selector + ".offers.availability"),
        (
            "condition",
            condition if condition != "unknown" else None,
            selector + ".offers.itemCondition",
        ),
    ]:
        if value is not None:
            facts.append(
                Fact(
                    field=field,
                    value=value,
                    url=candidate.url,
                    observed_at=now,
                    origin="store_card",
                    selector=path,
                    content_sha256=sha,
                )
            )
    # Frozen Capture cannot map Discontinued yet; explicit canonical field witnesses
    # supplement, never replace, the original schema availability in retained bytes.
    if stock != "unknown":
        selected["stock"] = stock
        raw = json.dumps(selected, ensure_ascii=False, sort_keys=True, allow_nan=False)
        sha = hashlib.sha256(raw.encode()).hexdigest()
        facts = [f.model_copy(update={"content_sha256": sha}) for f in facts]
    primary = {
        "retained_content": raw,
        "retained_sha256": sha,
        "content_kind": "selected_primary_metadata",
        "response_body_sha256": hashlib.sha256(html.encode()).hexdigest(),
        "retrieved_at": now.isoformat(),
        "adapter": "T015/offline",
        "mpn_derivation": "title-derived" if derived else "structured" if mpn else "unknown",
    }
    observation = Observation(
        candidate=candidate,
        status="unresolved" if reasons else "observed",
        reason="; ".join(
            reasons
            + [
                "Displayed amount only; quantity, full costs, Moscow, warranty, seller and payment unconfirmed"
            ]
        ),
        title=title,
        mpn=mpn,
        stock=stock,
        condition=condition,
        match=match,
        differences=differences,
        facts=tuple(facts),
        primary=primary,
    )
    return Extraction(
        observation=observation,
        price_tokens=tuple(tokens),
        displayed_amount_rub=amount,
        identity_conflicts=problems,
        synthetic=synthetic,
    )


def extraction_capture(request, extraction):
    """Validated bridge to frozen journal contracts, never a fresh live claim."""
    payload = extraction.model_dump(mode="json")
    sha = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()
    return Capture(
        request=request,
        observation=extraction.observation,
        provenance="synthetic_fixture" if extraction.synthetic else "cached_primary_import",
        synthetic=extraction.synthetic,
        artifact_sha256=sha,
    )


def retained_diagnostics(capture):
    """Read immutable historical captures without reclassifying partial metadata."""
    capture = Capture.model_validate(capture.model_dump(mode="json"))
    o = capture.observation
    return {
        "capture": capture.model_dump(mode="json"),
        "status": "retained_original",
        "source_timestamp": (o.primary or {}).get("retrieved_at"),
        "not_reclassified": True,
        "new_HTTP": 0,
        "limitation": "Full original HTML/JSON-LD not retained; unsupported original price spelling cannot be reconstructed. No new source facts or readiness.",
    }
