"""Small real collector loop; its finite experiment is not a project stop rule."""

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from quality import snapshot

from pc_sourcing.pipeline import run

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
args = ap.parse_args()
out = Path(os.environ["PC_LOOP_DIR"]).resolve()
if not out.is_relative_to(ROOT / "artifacts"):
    raise ValueError("loop resources must be private project artifacts")
out.mkdir(parents=True, exist_ok=True)
ledger = out / "ledger.json"
entries = json.loads(ledger.read_text()) if ledger.exists() else []
if args.check:
    assert all(e["snapshot"] == snapshot() for e in entries), "loop snapshot changed"
    assert len(entries) == 2, "loop must stop on its condition, before max_iterations=3"
    assert entries[0]["summary"] == entries[1]["summary"]
    assert entries[0]["report_hash"] == entries[1]["report_hash"]
    with sqlite3.connect(out / "pilot.sqlite") as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not con.execute("PRAGMA foreign_key_check").fetchall()
        assert con.execute("SELECT count(*) FROM offers").fetchone()[0] == 20
        assert con.execute("SELECT count(*) FROM rejections").fetchone()[0] == 2
    (out / "result.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "kind": "real_offline_collector_loop",
                "iterations": 2,
                "snapshot": snapshot(),
                "entries": entries,
            },
            indent=2,
        )
    )
    print("passed")
else:
    assert len(entries) < 2, "no accidental third collector execution"
    data = json.loads((ROOT / "fixtures/golden.json").read_text())
    inp = out / "input.json"
    if not inp.exists():
        invalid = json.loads((ROOT / "fixtures/invalid.json").read_text())
        inp.write_text(json.dumps([c["offer"] for c in data["cases"]] + invalid))
    report = out / "report.md"
    result = run(
        inp,
        out / "pilot.sqlite",
        report,
        as_of=datetime.fromisoformat(data["as_of"]),
        run_id="loop-pilot",
    )
    assert result == {"run_id": "loop-pilot", "valid": 20, "rejected": 2, "eligible": 3}
    entries.append(
        {
            "iteration": len(entries) + 1,
            "summary": result,
            "report_hash": hashlib.sha256(report.read_bytes()).hexdigest(),
            "synthetic": True,
            "snapshot": snapshot(),
        }
    )
    ledger.write_text(json.dumps(entries, indent=2))
    print("again" if len(entries) == 1 else "done", end="")
