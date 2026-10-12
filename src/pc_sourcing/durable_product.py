"""Synthetic product request/primary-card bridge into durable receipt storage.

Calls the real deterministic product parser. Never discovers or fetches a source.
Every result remains synthetic; product purchase eligibility is unchanged.
"""

from datetime import datetime
from pathlib import Path

from pc_sourcing.durable_jobs import digest, encoded, validate_receipt
from pc_sourcing.live_models import Candidate, Request, canonical_url
from pc_sourcing.live_sourcing import parse_card


def prepare_product_fixture(row):
    if row.get("synthetic") is not True:
        raise ValueError("product fixture must explicitly be synthetic")
    html = row.get("primary_html")
    if not isinstance(html, str) or not html.strip() or len(html.encode()) > 1_000_000:
        raise ValueError("bounded synthetic primary_html required")
    requested = Request.model_validate(row["request"])
    url = canonical_url(row["url"])
    stamp = datetime.fromisoformat(row["observed_at"])
    if stamp.tzinfo is None:
        raise ValueError("product fixture timestamp requires timezone")
    package = Path(__file__).resolve().parent
    code = encoded(
        {
            name: digest((package / name).read_bytes())
            for name in (
                "live_models.py",
                "live_sourcing.py",
                "identity_attributes.py",
                "identity_claims.py",
                "durable_product.py",
            )
        }
    )
    context = {
        "user_context": row["context"],
        "product_request": requested.model_dump(mode="json"),
        "evaluation_fingerprint": digest(code),
        "bridge_contract": "synthetic-product-1",
    }
    seed = {"synthetic": True, "url": url, "primary_html_sha256": digest(html.encode())}
    candidate = Candidate(
        url=url,
        title="SYNTHETIC primary fixture",
        queries=(),
        observed_at=stamp,
        response_sha256=digest(encoded(seed)),
        origin="curated_registry",
    )
    observed = parse_card(requested, candidate, html, stamp)
    receipt = {
        "url": url,
        "observed_at": stamp.isoformat(),
        "origin": "synthetic_fixture",
        "synthetic": True,
        "facts": {
            "input_provenance": "synthetic_primary_html_and_fixture_seed_not_live_search",
            "primary_html_sha256": seed["primary_html_sha256"],
            "observation": observed.model_dump(mode="json"),
        },
    }
    validate_receipt(receipt, url)
    return {**row, "context": context, "receipt": receipt}
