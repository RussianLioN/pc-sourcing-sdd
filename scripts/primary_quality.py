"""Fresh T010 quality receipts without overwriting prior evidence."""

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    out = ROOT / "artifacts/T010" / ("quality-" + uuid4().hex)
    raise SystemExit(
        subprocess.call(
            [sys.executable, str(ROOT / "scripts/quality.py"), "--out", str(out)], cwd=ROOT
        )
    )
