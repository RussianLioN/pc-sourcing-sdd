"""Run inside verifier sandbox: scratch writable, project write denied."""

import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
probe = ROOT / "artifacts" / ("verifier-permission-probe-" + str(os.getpid()))
denied = False
try:
    with probe.open("x") as f:
        f.write("temporary permission probe")
except PermissionError:
    denied = True
else:
    probe.unlink()
scratch = Path(os.environ["TMPDIR"])
with tempfile.TemporaryFile(dir=scratch) as f:
    f.write(b"scratch test")
print(json.dumps({"project_write_denied": denied, "scratch_writable": True}))
raise SystemExit(0 if denied else 1)
