"""Run full quality in a fresh evidence directory; never overwrite a previous receipt."""

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    output = ROOT / "artifacts/T009" / ("workflow-quality-" + uuid4().hex)
    raise SystemExit(
        subprocess.call(
            [sys.executable, str(ROOT / "scripts/quality.py"), "--out", str(output)], cwd=ROOT
        )
    )
