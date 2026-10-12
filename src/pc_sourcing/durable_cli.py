"""Synthetic durable runtime CLI. No network adapters, scheduler or live permissions."""

import argparse
import json
import sqlite3
import sys

from pc_sourcing.durable_jobs import Busy, Store, clock, digest, encoded, validate_receipt
from pc_sourcing.live_models import canonical_url


class SourceStopped(RuntimeError):
    """A synthetic transport models a source denial; persist before continuing."""


def fixture_jobs(path):
    rows = json.loads(path.read_bytes())
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonempty synthetic fixture list required")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("synthetic") is not True:
            raise ValueError("fixture must explicitly declare synthetic=true")
        modes = sum(key in row for key in ("receipt", "primary_html", "blocked_reason"))
        if modes != 1:
            raise ValueError("exactly one synthetic receipt/card/denial mode required")
        if "primary_html" in row:
            from pc_sourcing.durable_product import prepare_product_fixture

            row = prepare_product_fixture(row)
        context = row.get("context")
        generation = row.get("generation", 0)
        source = row.get("source")
        if not isinstance(source, str) or not source.strip() or not isinstance(context, dict):
            raise ValueError("fixture source/context invalid")
        if type(generation) is not int or generation < 0:
            raise ValueError("fixture generation invalid")
        url = canonical_url(row["url"])
        listing = digest(encoded({"source": source, "url": url, "context": context}))
        job = digest(encoded({"listing": listing, "generation": generation}))
        if "receipt" in row:
            validate_receipt(row["receipt"], url)
        elif not isinstance(row.get("blocked_reason"), str) or not row["blocked_reason"].strip():
            raise ValueError("fixture receipt or denial required")
        if job in result and encoded(result[job]) != encoded(row):
            raise ValueError("conflicting fixture for same job key")
        result[job] = row
    return result


def work_once(store, fetch, *, now=None, lease_seconds=60):
    """fetch is an injected synthetic fixture callable, never selected by offer text."""
    claimed = store.claim(now=now, lease_seconds=lease_seconds)
    if claimed is None:
        return {"status": "idle"}
    job, token = claimed["id"], claimed["token"]
    if claimed["receipt"] is None:
        try:
            receipt = fetch(claimed)
        except SourceStopped as exc:
            store.stop_source(job, token, str(exc), now=now)
            return {"status": "source_blocked", "job": job, "reason": str(exc)}
        store.checkpoint(job, token, receipt, now=now)
    store.finish(job, token, now=now)
    return {"status": "done", "job": job, "synthetic": True}


def main():
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["submit", "work", "status", "recover", "backup", "restore", "report"]
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--max-jobs", type=int, default=1)
    args = parser.parse_args()
    try:
        if args.action in {"submit", "work"} and args.fixtures is None:
            raise ValueError("synthetic fixtures required")
        if args.action in {"report", "backup"} and args.output is None:
            raise ValueError("fresh output path required")
        if args.action == "restore" and args.backup is None:
            raise ValueError("backup path required")
        if args.action not in {"submit", "restore"} and not (args.root / "jobs.sqlite").is_file():
            raise ValueError("runtime not initialized; submit fixtures first")
        if args.action == "restore":
            Store.restore(args.backup, args.root)
            result = {"status": "restored", "synthetic": True}
        else:
            fixtures = fixture_jobs(args.fixtures) if args.action in {"submit", "work"} else None
            store = Store(args.root)
            if args.action == "submit":
                jobs = []
                for row in fixtures.values():
                    policy = row.get("policy", {"budget": 10, "interval": 5})
                    store.configure_source(
                        row["source"], limit=policy["budget"], interval=policy["interval"]
                    )
                    jobs.append(
                        store.enqueue(
                            row["source"],
                            row["url"],
                            row["context"],
                            generation=row.get("generation", 0),
                            input_hash=digest(encoded(row)),
                        )
                    )
                result = {"status": "submitted", "jobs": jobs, "synthetic": True}
            elif args.action == "work":
                if not 1 <= args.max_jobs <= 100:
                    raise ValueError("max jobs must be between 1 and 100")
                known = store.report()["jobs"]
                if any(
                    j["state"] == "ready" and j["receipt_hash"] is None and j["id"] not in fixtures
                    for j in known
                ):
                    raise ValueError("pending job lacks synthetic fixture; no claim made")

                for job in known:
                    if (
                        job["state"] == "ready"
                        and job["receipt_hash"] is None
                        and job["input_hash"] is not None
                    ):
                        if job["input_hash"] != digest(encoded(fixtures[job["id"]])):
                            raise ValueError("job generation input changed; no claim made")

                def fetch(job):
                    row = fixtures[job["id"]]
                    if "blocked_reason" in row:
                        raise SourceStopped(row["blocked_reason"])
                    return row["receipt"]

                results = []
                for _ in range(args.max_jobs):
                    step = work_once(store, fetch)
                    results.append(step)
                    if step["status"] == "idle":
                        break
                result = {"results": results, "synthetic": True}
            elif args.action == "status":
                result = store.report()
            elif args.action == "recover":
                result = {"expired_leases_recovered": store.recover(now=clock(None))}
            elif args.action == "backup":
                store.backup(args.output)
                result = {"status": "backed_up", "synthetic": True}
            else:
                store.export(args.output)
                result = {"status": "report_saved", "synthetic": True}
        print(encoded(result).decode(), end="")
        return 0
    except (Busy, ValueError, OSError, sqlite3.DatabaseError, KeyError, TypeError) as exc:
        print(encoded({"status": "failed", "reason": str(exc)}).decode(), file=sys.stderr, end="")
        return 1


if __name__ == "__main__":
    sys.exit(main())
