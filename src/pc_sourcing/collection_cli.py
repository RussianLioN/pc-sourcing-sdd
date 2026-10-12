"""Cloud CLI retained-primary replay. No discovery, HTTP, hosting or source resets."""

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from pc_sourcing.collection_capture import import_artifact
from pc_sourcing.collection_runtime import Journal
from pc_sourcing.durable_jobs import Busy, encoded
from pc_sourcing.live_models import Request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=[
            "acquire",
            "import",
            "work",
            "recover",
            "status",
            "report",
            "backup",
            "restore",
            "source-backup",
            "source-restore",
        ],
    )
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--artifact", type=Path)
    p.add_argument("--request", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--as-of")
    p.add_argument("--source", choices=["28bit", "regard"], default="28bit")
    p.add_argument("--max-jobs", type=int, default=10)
    args = p.parse_args()
    try:
        if args.action in {"source-backup", "source-restore"}:
            from pc_sourcing.collection_acquisition import PACKAGE_ROOT
            from pc_sourcing.collection_state import backup_state, restore_state

            state = PACKAGE_ROOT / "artifacts/source-state"
            if args.action == "source-backup":
                if args.output is None:
                    raise ValueError("source snapshot output required")
                backup_state(state, args.output)
            else:
                if args.artifact is None:
                    raise ValueError("source snapshot required")
                restore_state(args.artifact, state)
            result = {"status": "source_state_transferred", "source_calls": 0}
        elif args.action == "acquire":
            if args.request is None:
                raise ValueError("reviewed exact RAM request required")
            from pc_sourcing.collection_acquisition import Acquisition

            request = Request.model_validate(json.loads(args.request.read_bytes()))
            if args.source == "regard":
                from pc_sourcing.collection_profiles import RegardAcquisition

                acquisition = RegardAcquisition()
            else:
                acquisition = Acquisition()
            result = acquisition.acquire(request, Journal(args.root))
        elif args.action == "import":
            if args.artifact is None or args.request is None:
                raise ValueError("retained artifact and original request required")
            captures, events = import_artifact(
                args.artifact, Request.model_validate(json.loads(args.request.read_bytes()))
            )
            result = {
                "status": "imported",
                "jobs": Journal(args.root).submit(captures, events),
                "provenance": "cached_primary_import",
                "source_calls": 0,
            }
        elif args.action == "restore":
            if args.artifact is None:
                raise ValueError("backup artifact required")
            Journal.restore(args.artifact, args.root)
            result = {"status": "restored", "source_calls": 0}
        else:
            if not (args.root / "collection.sqlite").is_file():
                raise ValueError("collection root not initialized")
            journal = Journal(args.root)
            if args.action == "status":
                result = journal.status()
            elif args.action == "recover":
                result = {"recovered": journal.recover(), "source_calls": 0}
            elif args.action == "work":
                if not 1 <= args.max_jobs <= 100:
                    raise ValueError("max jobs must be 1..100")
                steps = []
                for _ in range(args.max_jobs):
                    step = journal.work()
                    steps.append(step)
                    if step["status"] == "idle":
                        break
                result = {"steps": steps, "source_calls": 0}
            else:
                if args.output is None:
                    raise ValueError("fresh absolute output required")
                if args.action == "backup":
                    journal.backup(args.output)
                    result = {"status": "backed_up", "source_calls": 0}
                else:
                    asof = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(UTC)
                    result = journal.report(args.output, asof)
        print(encoded(result).decode(), end="")
        return 0
    except (Busy, ValueError, OSError, sqlite3.DatabaseError, KeyError, TypeError) as exc:
        print(encoded({"status": "failed", "reason": str(exc)}).decode(), file=sys.stderr, end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
