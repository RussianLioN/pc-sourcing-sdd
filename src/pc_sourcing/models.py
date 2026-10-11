from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["confirmed_applicable", "confirmed_unavailable", "unknown", "conflict"]
TARGETS = {
    "gpu": "G5090-32SLC",
    "ram": "F5-6000J3036F48GX2-TZ5NR",
    "mouse": "Logitech G PRO X2 SUPERSTRIKE",
}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0.0"] = "1.0.0"


class Evidence(Contract):
    id: str = Field(min_length=1)
    offer_id: str = Field(min_length=1)
    url: str = Field(pattern=r"^https?://[^\s]+$")
    observed_at: datetime
    field: str = Field(min_length=1)
    value: str
    origin: Literal["store_card", "seller_statement", "platform_transaction", "search_snippet"]
    synthetic: bool

    @model_validator(mode="after")
    def aware(self):
        if self.observed_at.tzinfo is None:
            raise ValueError("evidence timestamp must include timezone")
        return self


class Route(Contract):
    status: Status = "unknown"
    covers_item: bool = False
    covers_amount: bool = False
    covers_region: bool = False
    covers_order: bool = False
    external_advance_required: bool | None = None
    evidence_ids: tuple[str, ...] = ()
    reason: str = "not confirmed"


class Offer(Contract):
    id: str = Field(min_length=1)
    product: Literal["gpu", "ram", "mouse"]
    sku: str = Field(min_length=1)
    title: str
    source: Literal["store", "avito", "snippet"]
    url: str = Field(pattern=r"^https?://[^\s]+$")
    observed_at: datetime
    synthetic: bool
    price_rub: Annotated[int, Field(gt=0, strict=True)] | None
    currency: str = "RUB"
    stock: Literal["in_stock", "preorder", "unknown", "unavailable"]
    region: str
    condition: Literal["new", "used", "unknown"]
    seller_checked: bool
    factory_liquid: bool | None = None
    global_advance_required: bool | None = None
    global_payment_conflict: bool = False
    optional_risky_alternative: bool = False
    protected: Route = Route()
    postpay: Route = Route()
    evidence: tuple[Evidence, ...]

    @model_validator(mode="after")
    def provenance(self):
        if self.observed_at.tzinfo is None:
            raise ValueError("offer timestamp must include timezone")
        ids = [e.id for e in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate evidence id")
        if any(e.offer_id != self.id or e.synthetic != self.synthetic for e in self.evidence):
            raise ValueError("evidence owner or synthetic status mismatch")
        if any(i not in ids for r in (self.protected, self.postpay) for i in r.evidence_ids):
            raise ValueError("dangling route evidence reference")
        return self


class Evaluation(Contract):
    offer_id: str
    evaluated_at: datetime
    exact_sku: bool
    payment_gate_passed: bool
    passed_routes: tuple[Literal["protected", "postpay"], ...]
    eligibility: Literal["verified", "conditional", "manual", "excluded", "candidate"]
    eligible: bool
    label: str
    reasons: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    synthetic: bool
