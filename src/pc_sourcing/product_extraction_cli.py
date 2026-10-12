"""Offline local bytes → selected Product → frozen Capture/Journal/report. No HTTP."""

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

from pc_sourcing.collection_capture import Capture
from pc_sourcing.collection_runtime import Journal
from pc_sourcing.durable_jobs import Busy, absolute, encoded, publish_directory, write_file
from pc_sourcing.live_models import Candidate, Request
from pc_sourcing.product_extraction import (
    extract_card,
    extraction_capture,
    retained_diagnostics,
    unique_members,
)


def bounded(path, maximum):
    path = absolute(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("bounded regular local input file required")
    return path.read_bytes()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["parse", "retained"])
    p.add_argument("--metadata", type=Path)
    p.add_argument("--html", type=Path)
    p.add_argument("--capture", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        output = absolute(args.output)
        if output.exists() or output.is_symlink():
            raise ValueError("fresh output directory required")
        if args.action == "parse":
            if args.metadata is None or args.html is None or args.capture is not None:
                raise ValueError("parse requires metadata and HTML only")
            metadata = json.loads(bounded(args.metadata, 8192), object_pairs_hook=unique_members)
            if set(metadata) != {
                "request",
                "candidate",
                "source_observed_at",
                "synthetic",
                "html_sha256",
            }:
                raise ValueError(
                    "exact request/candidate/original date/realm/body hash metadata required"
                )
            request = Request.model_validate(metadata["request"])
            candidate = Candidate.model_validate(metadata["candidate"])
            if type(metadata["synthetic"]) is not bool:
                raise ValueError("explicit boolean realm required")
            body = bounded(args.html, 1_000_000)
            if hashlib.sha256(body).hexdigest() != metadata["html_sha256"]:
                raise ValueError("original input HTML hash mismatch")
            stamp = datetime.fromisoformat(metadata["source_observed_at"])
            extraction = extract_card(
                request, candidate, body.decode("utf-8"), stamp, synthetic=metadata["synthetic"]
            )
            capture = extraction_capture(request, extraction)
            extra = extraction.model_dump(mode="json")
        else:
            if args.capture is None or args.metadata is not None or args.html is not None:
                raise ValueError("retained requires immutable Capture only")
            capture = Capture.model_validate(
                json.loads(bounded(args.capture, 150_000), object_pairs_hook=unique_members)
            )
            extra = retained_diagnostics(capture)
        stamps = [f.observed_at for f in capture.observation.facts]
        source_date = (capture.observation.primary or {}).get("retrieved_at")
        asof = (
            max(stamps)
            if stamps
            else datetime.fromisoformat(source_date)
            if source_date
            else capture.observation.candidate.observed_at
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        stage = output.parent / ("." + uuid.uuid4().hex + ".extraction")
        stage.mkdir()
        journal = Journal(stage / "journal")
        journal.submit([capture])
        journal.work()
        journal.report(stage / "report", asof)
        write_file(stage / "capture.json", encoded(capture.model_dump(mode="json")))
        write_file(stage / "extraction.json", encoded(extra))
        write_file(
            stage / "manifest.json",
            encoded(
                {
                    "mode": "offline_retained_bytes",
                    "provenance": capture.provenance,
                    "synthetic": capture.synthetic,
                    "source_observed_at": asof.isoformat(),
                    "new_HTTP": 0,
                    "original_source_date_not_refreshed": True,
                    "full_product_DoD": "pending",
                    "limitations": "No current primary verification or unconditional purchase price; input metadata/hash is not source authentication",
                }
            ),
        )
        publish_directory(stage, output)
        print(
            encoded(
                {"status": "completed_with_gaps", "output": str(output), "new_HTTP": 0}
            ).decode(),
            end="",
        )
        return 0
    except (Busy, ValueError, OSError, TypeError, KeyError, sqlite3.DatabaseError) as exc:
        print(encoded({"status": "failed", "reason": str(exc)}).decode(), file=sys.stderr, end="")
        return 1


if __name__ == "__main__":
    sys.exit(main())
