"""Additive live contracts: an unknown observation never becomes a boolean fact."""

from datetime import datetime
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LiveContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Request(LiveContract):
    name: str = Field(min_length=3, max_length=200)
    mpn: str | None = Field(default=None, min_length=3, max_length=100)
    category: Literal["gpu", "ram", "mouse", "other"] = "other"
    quantity: int = Field(default=1, gt=0, le=100, strict=True)
    region: Literal["Москва"] = "Москва"

    @field_validator("name", "mpn")
    @classmethod
    def printable(cls, value):
        if value is not None and (not value.strip() or any(ord(c) < 32 for c in value)):
            raise ValueError("request must contain printable text")
        return value

    def queries(self):
        return list(
            dict.fromkeys(
                [f'"{self.mpn or self.name}" Москва купить', f'"{self.name}" Москва купить']
            )
        )


def canonical_url(value):
    p = urlsplit(value)
    if (
        p.scheme != "https"
        or not p.hostname
        or p.username
        or p.password
        or p.port not in (None, 443)
        or any(ord(c) <= 32 for c in value)
    ):
        raise ValueError("only public HTTPS URLs without credentials are allowed")
    host = p.hostname.lower().encode("idna").decode()
    query = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "yclid"}
    ]
    return urlunsplit(("https", host, p.path or "/", urlencode(query), ""))


def aware(value):
    if value.tzinfo is None:
        raise ValueError("UTC offset is required")
    return value


class Fact(LiveContract):
    field: str
    value: str | int | bool
    url: str
    observed_at: datetime
    origin: Literal["store_card", "search_snippet"]
    selector: str
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    _aware = field_validator("observed_at")(aware)


class Candidate(LiveContract):
    url: str
    title: str
    queries: tuple[str, ...]
    observed_at: datetime
    response_sha256: str
    _url = field_validator("url")(canonical_url)
    _aware = field_validator("observed_at")(aware)


class Observation(LiveContract):
    candidate: Candidate
    status: Literal["observed", "blocked", "unresolved"]
    reason: str
    title: str | None = None
    mpn: str | None = None
    price_rub: int | None = Field(default=None, gt=0, strict=True)
    stock: Literal["in_stock", "preorder", "unavailable", "unknown"] = "unknown"
    condition: Literal["new", "used", "unknown"] = "unknown"
    region: str | None = None
    seller_identity: str | None = None
    seller_checked: bool | None = None
    delivery_rub: int | None = None
    payment_confirmed: bool | None = None
    match: Literal["exact", "analogue", "excluded", "unresolved"] = "unresolved"
    differences: tuple[str, ...] = ()
    eligible: Literal[False] = False
    label: str = "недостаточно подтверждений"
    facts: tuple[Fact, ...] = ()


class SourcePolicy(LiveContract):
    domain: str
    seller: str
    status: Literal["pending", "allowed", "denied"]
    terms_url: str | None = None
    reviewed_at: datetime | None = None
    basis: str
    retain_facts: bool = False
    min_interval_seconds: int = Field(default=5, ge=1, le=60)

    @field_validator("reviewed_at")
    @classmethod
    def review_aware(cls, value):
        return aware(value) if value is not None else value
