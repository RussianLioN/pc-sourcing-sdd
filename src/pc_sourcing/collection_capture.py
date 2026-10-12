"""Bounded retained-primary import. Real dates/realm preserved; never fetch a URL."""

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, model_validator

from pc_sourcing.durable_jobs import absolute, encoded
from pc_sourcing.live_models import Observation, Request
from pc_sourcing.normalized_models import NormalizedOffer


def fact_matches_selected(fact, selected):
    """No asserted fact becomes evidence merely by sharing a fragment hash."""
    props = selected.get("properties", {})
    if not isinstance(props, dict):
        return False

    def values(key):
        v = props.get(key, [])
        return v if isinstance(v, list) else [v]

    field, value = fact.field, fact.value
    if field == "title":
        return type(value) is str and value in [
            selected.get("h1"),
            selected.get("title"),
            *values("name"),
        ]
    if field == "mpn":
        if type(value) is not str or not value.strip():
            return False
        if value in [selected.get("mpn"), *values("mpn")]:
            return True
        names = [selected.get("h1"), selected.get("title"), *values("name")]
        return any(
            isinstance(t, str) and re.search(r"(?<![\w-])" + re.escape(value) + r"(?![\w-])", t)
            for t in names
        )
    if field in {"price_rub", "displayed_price_rub"}:
        if type(value) not in (int, str) or not re.fullmatch(
            r"[0-9]+(?:\.[0-9]{1,2})?", str(value)
        ):
            return False
        # Explicit unconditional witness is different from generic displayed price.
        candidates = [selected.get(field)]
        if field == "displayed_price_rub" and values("priceCurrency") == ["RUB"]:
            candidates += values("price")
        return any(
            type(v) in (int, str)
            and re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", str(v))
            and Decimal(str(v)) == Decimal(str(value))
            for v in candidates
        )
    if field in {"stock", "declared_stock"}:
        mapping = {"InStock": "in_stock", "OutOfStock": "unavailable", "PreOrder": "preorder"}
        candidates = [selected.get(field)] + [
            mapping.get(str(v).rsplit("/", 1)[-1], v) for v in values("availability")
        ]
        return type(value) is str and value in candidates
    if field == "condition":
        if type(value) is not str:
            return False
        mapping = {"NewCondition": "new", "UsedCondition": "used"}
        return value in [
            selected.get("condition"),
            *[mapping.get(str(v).rsplit("/", 1)[-1], v) for v in values("itemCondition")],
        ]
    # Unsupported fields are never certified as primary facts by this adapter.
    return False


class Capture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: Request
    observation: Observation
    provenance: Literal["cached_primary_import", "live_primary", "synthetic_fixture"]
    synthetic: bool
    artifact_sha256: str

    @model_validator(mode="after")
    def valid_capture(self):
        if self.synthetic != (self.provenance == "synthetic_fixture"):
            raise ValueError("capture realm/provenance mismatch")
        if len(self.artifact_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in self.artifact_sha256
        ):
            raise ValueError("artifact hash invalid")
        o = self.observation
        primary = o.primary or {}
        fragment = primary.get("retained_content")
        if o.facts:
            if not isinstance(fragment, str) or not 0 < len(fragment) <= 65536:
                raise ValueError("bounded primary retained fragment required; no truncation")
            selected = json.loads(fragment)
            if not isinstance(selected, dict):
                raise ValueError("selected primary JSON object required")
            if "synthetic" in selected and selected["synthetic"] is not self.synthetic:
                raise ValueError("selected fragment/capture realm mismatch")
            for key in ("title", "mpn", "price_rub", "stock", "condition"):
                value = getattr(o, key)
                if value is not None and value != "unknown":
                    records = [f for f in o.facts if f.field == key]
                    if not records or any(
                        type(f.value) is not type(value) or f.value != value for f in records
                    ):
                        raise ValueError("observation/fact values not supported by selected bytes")
            if any(not fact_matches_selected(f, selected) for f in o.facts):
                raise ValueError("source fact value/kind not supported by selected bytes")
            h = hashlib.sha256(fragment.encode()).hexdigest()
            if h != primary.get("retained_sha256") or any(f.content_sha256 != h for f in o.facts):
                raise ValueError("retained fragment/source fact hash mismatch")
            if any(f.url != o.candidate.url or f.origin != "store_card" for f in o.facts):
                raise ValueError("primary fact URL/origin mismatch")
        return self


def import_artifact(directory: Path, request: Request):
    directory = absolute(directory)
    manifest_path = directory / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("symlink manifest")
    manifest = json.loads(manifest_path.read_bytes())
    if not isinstance(manifest.get("files"), dict) or "result.json" not in manifest["files"]:
        raise ValueError("retained artifact inventory required")
    if len(manifest["files"]) > 20:
        raise ValueError("artifact inventory exceeds bound")
    for name, h in manifest["files"].items():
        if not isinstance(name, str) or Path(name).name != name or name in {".", ".."}:
            raise ValueError("unsafe artifact inventory path")
        path = directory / name
        if (
            path.is_symlink()
            or path.stat().st_size > 8_000_000
            or hashlib.sha256(path.read_bytes()).hexdigest() != h
        ):
            raise ValueError("artifact file hash mismatch")
    data = json.loads((directory / "result.json").read_bytes())
    if Request.model_validate(data["request"]) != request:
        raise ValueError("captured request differs from user request")
    if data.get("synthetic") is not False:
        # Older live artifacts have no synthetic field. Their import remains explicitly
        # unverified cached primary, never a claim of authenticated live acquisition.
        if data.get("synthetic") is not None:
            raise ValueError("synthetic artifact needs an explicit synthetic input path")
    return [
        Capture(
            request=request,
            observation=Observation.model_validate(o),
            provenance="cached_primary_import",
            synthetic=False,
            artifact_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        )
        for o in data["observations"]
    ], data.get("events", [])


def field_fragment(fact, primary):
    fragment = primary["retained_content"]
    if len(fragment) <= 4000:
        return fragment
    # Derived bounded fact witness links to the complete retained capture hash.
    # Full selected metadata remains in the journal, never silently truncated.
    fragment = json.dumps(
        {
            "kind": "derived_fact_witness",
            "field": fact.field,
            "value": fact.value,
            "selector": fact.selector,
            "source_retained_sha256": primary["retained_sha256"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    if len(fragment) > 4000:
        raise ValueError("fact witness exceeds normalized evidence bound")
    return fragment


def normalize_capture(capture: Capture):
    o = capture.observation
    if o.status != "observed" or o.match not in {"exact", "analogue"}:
        return None  # preserved as a coverage observation, never promoted
    if not o.title:
        return None
    dates = [f.observed_at for f in o.facts]
    stamp = max(dates) if dates else o.candidate.observed_at
    identity = hashlib.sha256(encoded(capture.model_dump(mode="json"))).hexdigest()
    data = {
        "id": identity,
        "request": capture.request.model_dump(mode="json"),
        "title": o.title,
        "mpn": o.mpn,
        "source": "avito"
        if urlsplit(o.candidate.url).hostname == "avito.ru"
        or urlsplit(o.candidate.url).hostname.endswith(".avito.ru")
        else "store",
        "url": o.candidate.url,
        "observed_at": stamp,
        "synthetic": capture.synthetic,
        "stock": o.stock,
        "condition": o.condition,
        "evidence": [],
    }
    mapped = {"title": "title", "mpn": "mpn", "stock": "stock", "condition": "condition"}
    for i, f in enumerate(o.facts):
        field, value = mapped.get(f.field, "source_" + f.field), f.value
        if f.field == "price_rub" and o.price_rub is not None:
            field = "price"
            value = {
                "id": "primary",
                "money": {"amount": str(f.value), "currency": "RUB"},
                "kind": "unconditional",
                "basis": "unit",
                "quantity": 1,
            }
            data["price"] = {**value, "money": {"amount": str(o.price_rub), "currency": "RUB"}}
        if f.field == "displayed_price_rub":
            data.setdefault("conditional_prices", []).append(
                {
                    "id": "displayed-" + str(i),
                    "money": {"amount": str(f.value), "currency": "RUB"},
                    "kind": "unknown",
                    "basis": "unknown",
                    "quantity": None,
                }
            )
        data["evidence"].append(
            {
                "id": "fact-" + str(i),
                "offer_id": identity,
                "field": field,
                "value": value,
                "url": f.url,
                "observed_at": f.observed_at,
                "origin": f.origin,
                "selector": f.selector,
                "retained_fragment": field_fragment(f, o.primary),
                "content_sha256": hashlib.sha256(field_fragment(f, o.primary).encode()).hexdigest(),
                "synthetic": capture.synthetic,
            }
        )
    return NormalizedOffer.model_validate(data)
