"""Synthetic orchestration action, not an AI worker."""

import argparse
import json
import os
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("action", choices=["once", "fault", "hold"])
ap.add_argument("--state", choices=["fail", "pass"], default="pass")
args = ap.parse_args()
root = Path(os.environ["PC_PROBE_DIR"])
root.mkdir(parents=True, exist_ok=True)
if args.action == "once":
    with (root / "ledger.jsonl").open("a") as f:
        f.write(json.dumps({"step": "once"}) + "\n")
if args.action == "fault" and args.state == "fail":
    raise SystemExit(7)
if args.action == "hold":
    (root / "child.json").write_text(json.dumps({"pid": os.getpid()}))
    time.sleep(5)
print(json.dumps({"synthetic_probe": True, "action": args.action, "status": "passed"}))
