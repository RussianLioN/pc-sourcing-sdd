"""Offline normalized imports and an explicit synthetic durable bridge."""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree.ElementTree import ParseError

from pc_sourcing.durable_cli import work_once
from pc_sourcing.durable_jobs import Busy, Store, absolute, digest, encoded
from pc_sourcing.normalized_exports import export_bundle, preflight_export, verify_bundle
from pc_sourcing.normalized_models import NormalizedOffer
from pc_sourcing.normalized_offers import compare, evaluate_offer


def persist_synthetic(offers, root, as_of, generation=0):
    # Validate the whole batch before initializing or mutating the runtime.
    offers = list(offers)
    if any(not offer.synthetic for offer in offers):
        raise ValueError("real records cannot enter the synthetic durable runtime")
    if type(generation) is not int or generation < 0:
        raise ValueError("nonnegative integer generation required")
    offers = list(offers)
    compare(offers, as_of)  # validate IDs and realm before creating the root
    prepared = {}
    # Runtime is a raw canonical-URL observation layer; logical listing aliases
    # remain separate here and are coalesced only in comparison/export.
    for offer in sorted(offers, key=lambda o: (o.observed_at, o.id), reverse=True):
        if offer.observed_at > as_of:
            raise ValueError("future receipt cannot enter durable runtime")
        source = "normalized:" + urlsplit(offer.url).netloc
        context = {
            "contract": "normalized-offer-1",
            "request": offer.request.model_dump(mode="json"),
            "mpn": offer.mpn,
            "condition": offer.condition,
        }
        listing = digest(encoded({"source": source, "url": offer.url, "context": context}))
        job = digest(encoded({"listing": listing, "generation": generation}))
        if job in prepared:
            prepared[job]["observations"].append(offer.model_dump(mode="json"))
            continue
        prepared[job] = {
            "offer": offer,
            "context": context,
            "source": source,
            "listing": listing,
            "observations": [offer.model_dump(mode="json")],
        }
    receipts, inputs = {}, {}
    for job, entry in prepared.items():
        offer = entry["offer"]
        receipts[job] = {
            "synthetic": True,
            "origin": "synthetic_fixture",
            "url": offer.url,
            "observed_at": offer.observed_at.isoformat(),
            "facts": {
                "normalized_offer": offer.model_dump(mode="json"),
                "decision": evaluate_offer(offer, as_of),
                "raw_observations": entry["observations"],
            },
        }
        # Input identity excludes evaluation clock; existing receipts retain their
        # original decision/as-of until an explicit refresh generation is supplied.
        inputs[job] = digest(encoded(entry["observations"]))
    store = Store(root)
    # One cooperating lock + SQLite transaction preflights the complete batch and
    # pending queue, then commits all source configuration and enqueues atomically.
    with store.transaction() as db:
        for pending in db.execute("SELECT * FROM jobs WHERE state='ready'"):
            if pending["id"] not in prepared or pending["input_hash"] != inputs[pending["id"]]:
                raise ValueError("runtime contains an unrelated or changed pending input")
        for job, entry in prepared.items():
            source = entry["source"]
            origin = "https://" + urlsplit(entry["offer"].url).netloc
            prior = db.execute("SELECT input_hash FROM jobs WHERE id=?", (job,)).fetchone()
            if prior and prior["input_hash"] != inputs[job]:
                raise ValueError(
                    "job generation input changed; explicit refresh generation required"
                )
            config = db.execute("SELECT * FROM sources WHERE id=?", (source,)).fetchone()
            if config and (
                config["budget"] != 100
                or config["interval"] != 0
                or config["origin"] not in (None, origin)
            ):
                raise ValueError("source configuration immutable; no budget/stop reset")
            if db.execute(
                "SELECT id FROM sources WHERE origin=? AND id!=?", (origin, source)
            ).fetchone():
                raise ValueError("canonical origin already bound; no source alias bypass")
        for job, entry in prepared.items():
            offer, source = entry["offer"], entry["source"]
            db.execute(
                "INSERT OR IGNORE INTO sources(id,origin,budget,interval) VALUES (?,?,100,0)",
                (source, "https://" + urlsplit(offer.url).netloc),
            )
            db.execute(
                "UPDATE sources SET origin=? WHERE id=? AND origin IS NULL",
                ("https://" + urlsplit(offer.url).netloc, source),
            )
            db.execute(
                "INSERT OR IGNORE INTO jobs(id,source,url,context,listing_key,generation,input_hash) VALUES (?,?,?,?,?,?,?)",
                (
                    job,
                    source,
                    offer.url,
                    encoded(entry["context"]).decode(),
                    entry["listing"],
                    generation,
                    inputs[job],
                ),
            )
    results = []
    for _ in prepared:
        result = work_once(store, lambda job: receipts[job["id"]], now=as_of.timestamp())
        results.append(result)
        if result["status"] == "idle":
            break
    return {"synthetic": True, "results": results, "runtime": store.report()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", "verify"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--generation", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.action == "verify":
            result = verify_bundle(args.output)
        else:
            if args.input is None or args.as_of is None:
                raise ValueError("input and explicit timezone-aware as-of required")
            as_of = datetime.fromisoformat(args.as_of)
            if as_of.tzinfo is None or args.generation < 0:
                raise ValueError("aware as-of and nonnegative generation required")
            raw = json.loads(args.input.read_bytes())
            if not isinstance(raw, list) or not raw:
                raise ValueError("nonempty normalized offer list required")
            offers = [NormalizedOffer.model_validate(row) for row in raw]
            if len({o.id for o in offers}) != len(offers):
                raise ValueError("offer IDs must be unique")
            if len({o.synthetic for o in offers}) != 1:
                raise ValueError("real and synthetic datasets must be separate")
            args.output = absolute(args.output)
            preflight_export(offers, as_of)
            if args.output.exists():
                raise ValueError("export output already exists")
            runtime = None
            if args.runtime_root is not None:
                runtime = persist_synthetic(offers, args.runtime_root, as_of, args.generation)
            data = export_bundle(offers, args.output, as_of)
            result = {"status": "exported", "rows": len(data["rows"]), "runtime": runtime}
        print(encoded(result).decode(), end="")
        return 0
    except (
        Busy,
        sqlite3.DatabaseError,
        ParseError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
    ) as exc:
        print(encoded({"status": "failed", "reason": str(exc)}).decode(), file=sys.stderr, end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
