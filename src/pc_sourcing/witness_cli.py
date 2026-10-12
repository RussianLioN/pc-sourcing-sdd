"""Fixed bounded witness controller CLI. Production writes/HTTP require exact-SHA review."""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from pc_sourcing.collection_runtime import Journal
from pc_sourcing.durable_jobs import Busy, encoded
from pc_sourcing.live_models import Request
from pc_sourcing.live_transport import AccessBlocked
from pc_sourcing.product_extraction import unique_members
from pc_sourcing.witness_controller import Controller
from pc_sourcing.witness_profiles import PROFILES, ROOT
from pc_sourcing.witness_transfer import backup, restore


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=["bootstrap", "acquire", "ram-replay", "status", "source-backup", "source-restore"],
    )
    p.add_argument("--source", choices=sorted(PROFILES))
    p.add_argument("--root", type=Path)
    p.add_argument("--request", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--snapshot", type=Path)
    p.add_argument("--review-receipt", type=Path)
    p.add_argument("--review-sha256")
    args = p.parse_args()
    c = None
    try:
        if args.action == "source-backup":
            if args.output is None:
                raise ValueError("snapshot output required")
            backup(ROOT / "artifacts/source-state", args.output)
            result = {"status": "source_snapshot_created", "new_HTTP": 0}
        elif args.action == "source-restore":
            if args.snapshot is None:
                raise ValueError("snapshot required")
            restore(args.snapshot, ROOT / "artifacts/source-state")
            result = {"status": "source_snapshot_restored", "new_HTTP": 0}
        else:
            if args.source is None:
                raise ValueError("fixed reviewed source required")
            c = Controller(
                args.source, review_receipt=args.review_receipt, review_hash=args.review_sha256
            )
            if args.action == "status":
                result = c.status()
            elif args.action == "bootstrap":
                result = c.bootstrap()
            else:
                if args.root is None or args.request is None:
                    raise ValueError("original request and fresh CPU root required")
                request = Request.model_validate(
                    json.loads(args.request.read_bytes(), object_pairs_hook=unique_members)
                )
                journal = Journal(args.root)
                result = (
                    c.replay_ram(request, journal)
                    if args.action == "ram-replay"
                    else c.acquire(request, journal)
                )
                while journal.work()["status"] == "done":
                    pass
                if args.output is not None:
                    state = journal.status()
                    dates = [
                        f["observed_at"]
                        for j in state["jobs"]
                        for f in j["capture"]["observation"]["facts"]
                    ]
                    stamp = (
                        max(map(datetime.fromisoformat, dates))
                        if dates
                        else datetime.fromisoformat(
                            state["jobs"][0]["capture"]["observation"]["primary"]["retrieved_at"]
                        )
                    )
                    journal.report(args.output, stamp)
        print(encoded(result).decode(), end="")
        return 0
    except (
        AccessBlocked,
        Busy,
        ValueError,
        OSError,
        TypeError,
        KeyError,
        sqlite3.DatabaseError,
    ) as exc:
        attempts = getattr(c, "operation_attempts", 0)
        print(
            encoded(
                {
                    "status": "blocked_or_failed",
                    "reason": str(exc),
                    "source_requests_attempted": attempts,
                    "new_merchant_HTTP": 0 if not attempts or c.synthetic else None,
                }
            ).decode(),
            file=sys.stderr,
            end="",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
