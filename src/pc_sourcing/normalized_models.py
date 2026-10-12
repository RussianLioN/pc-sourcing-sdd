"""Versioned normalized source declarations. Unknown is null; money never uses float."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_serializer,
    field_validator,
    model_validator,
)

from pc_sourcing.live_models import Request, canonical_url


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0.0"] = "1.0.0"


class Money(Contract):
    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @field_serializer("amount", when_used="json")
    def canonical_amount(self, value):
        return format(value, ".2f")

    @field_validator("amount", mode="before")
    @classmethod
    def decimal_only(cls, value):
        if type(value) in (float, bool):
            raise ValueError("monetary float/bool forbidden")
        return value


class Price(Contract):
    id: str = Field(min_length=1)
    money: Money
    kind: Literal["unconditional", "conditional", "deposit", "installment", "unknown"]
    basis: Literal["unit", "purchase", "unknown"]
    quantity: int | None = Field(default=None, gt=0, strict=True)
    conditions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def coherent(self):
        if self.money.amount <= 0:
            raise ValueError("price must be positive; free fee differs from item price")
        if self.kind == "unconditional" and self.conditions:
            raise ValueError("unconditional price cannot contain conditions")
        return self


class Warranty(Contract):
    issuer: str | None = None
    months: int | None = Field(default=None, gt=0, strict=True)
    territory: str | None = None
    applicable_moscow: bool | None = None


class Fulfillment(Contract):
    city: str | None = None
    method: Literal["pickup", "delivery", "unknown"] = "unknown"
    confirmed: bool | None = None
    terms: str | None = None


class Route(Contract):
    status: Literal["confirmed_applicable", "confirmed_unavailable", "unknown", "conflict"] = (
        "unknown"
    )
    covers_item: bool | None = None
    covers_amount: bool | None = None
    covers_region: bool | None = None
    covers_order: bool | None = None
    external_advance_required: bool | None = None
    applies_mpn: str | None = None
    applies_quantity: int | None = Field(default=None, gt=0, strict=True)
    applies_amount: Money | None = None
    price_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    reason: str = "not confirmed"


class Evidence(Contract):
    id: str = Field(min_length=1)
    offer_id: str = Field(min_length=1)
    field: str = Field(min_length=1)
    value: JsonValue
    url: str
    observed_at: datetime
    origin: Literal[
        "store_card",
        "seller_statement",
        "platform_transaction",
        "search_snippet",
        "manufacturer_spec",
        "operator_review",
    ]
    selector: str = Field(min_length=1)
    retained_fragment: str = Field(min_length=1, max_length=4000)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    synthetic: bool
    scope: dict = Field(default_factory=dict)

    _url = field_validator("url")(canonical_url)

    @field_validator("observed_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("UTC offset required")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def fragment_hash(self):
        if hashlib.sha256(self.retained_fragment.encode()).hexdigest() != self.content_sha256:
            raise ValueError("retained evidence hash mismatch")
        return self


class NormalizedOffer(Contract):
    id: str = Field(min_length=1)
    request: Request
    title: str = Field(min_length=1)
    listing_id: str | None = None
    mpn: str | None = None
    source: Literal["store", "avito", "snippet"]
    url: str
    observed_at: datetime
    synthetic: bool
    attributes: dict = Field(default_factory=dict)
    analogue_compatible: bool | None = None
    analogue_differences: tuple[str, ...] = ()
    available_quantity: int | None = Field(default=None, ge=0, strict=True)
    complete_item: bool | None = None
    condition: Literal["new", "sealed", "open_box", "used", "refurbished", "unknown"] = "unknown"
    warranty: Warranty = Warranty()
    fulfillment: Fulfillment = Fulfillment()
    stock: Literal["in_stock", "supplier", "under_order", "preorder", "unavailable", "unknown"] = (
        "unknown"
    )
    seller_name: str | None = None
    seller_entity_key: str | None = None
    seller_checked: bool | None = None
    factory_liquid: bool | None = None
    price: Price | None = None
    conditional_prices: tuple[Price, ...] = ()
    delivery_cost: Money | None = None
    other_cost: Money | None = None
    global_advance_required: bool | None = None
    global_payment_conflict: bool | None = None
    optional_risky_alternative: bool | None = None
    protected: Route = Route()
    postpay: Route = Route()
    evidence: tuple[Evidence, ...]

    _url = field_validator("url")(canonical_url)
    _aware = field_validator("observed_at")(Evidence.aware.__func__)

    @model_validator(mode="after")
    def evidence_owner(self):
        ids = [e.id for e in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate evidence id")
        if any(e.offer_id != self.id or e.synthetic != self.synthetic for e in self.evidence):
            raise ValueError("evidence owner/realm mismatch")
        if any(i not in ids for r in (self.protected, self.postpay) for i in r.evidence_ids):
            raise ValueError("dangling payment evidence")
        prices = ([self.price] if self.price else []) + list(self.conditional_prices)
        if len({p.id for p in prices}) != len(prices):
            raise ValueError("duplicate price context")
        return self
