import json
import subprocess
from pathlib import Path

from quality import ROOT, snapshot

path = ROOT / "artifacts/acceptance/manifest.json"
if not path.exists():
    raise SystemExit("NOT RUN no acceptance record")
data = json.loads(path.read_text())
dirty = subprocess.check_output(
    ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True
)
if dirty or data["snapshot"] != snapshot():
    raise SystemExit("STALE snapshot changed; acceptance invalidated")
review = data.get("independent_review", {})
if (
    data["status"] != "passed"
    or review.get("verdict") != "passed"
    or review.get("commit") != data["snapshot"]["commit"]
):
    raise SystemExit("BLOCKED required checks or independent verdict missing")
for file, expected in data.get("artifact_hashes", {}).items():
    import hashlib

    if hashlib.sha256(Path(file).read_bytes()).hexdigest() != expected:
        raise SystemExit("STALE acceptance artifact changed: " + file)
print(
    json.dumps(
        {
            "status": "passed",
            "scope": "offline",
            "commit": data["snapshot"]["commit"],
            "live": "blocked",
        }
    )
)
