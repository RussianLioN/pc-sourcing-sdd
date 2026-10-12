"""Fixed reviewed source capabilities. No query/discovery/configurable endpoint."""

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from pc_sourcing.durable_jobs import digest, encoded
from pc_sourcing.live_transport import AccessBlocked
from pc_sourcing.product_extraction import unique_members

ROOT = Path(__file__).resolve().parents[2]
GPU_POLICY = "7155cdbd94edcd86fb6f5dfe175be75749b2fc1478aacf3027a1318e2b9e9623"
RAM_MPN = "F5-6000J3036F48GX2-TZ5NR"
GPU_MPN = "G5090-32SLC"


@dataclass(frozen=True)
class Profile:
    key: str
    url: str
    category: str
    reviewed_at: str
    policy_hash: str
    card_limit: int = 1
    http_limit: int = 2
    byte_limit: int = 1_000_000
    timeout: int = 15
    interval: int = 10

    @property
    def origin(self):
        p = urlsplit(self.url)
        return p.scheme + "://" + p.netloc

    @property
    def robots_url(self):
        return self.origin + "/robots.txt"

    @property
    def fingerprint(self):
        return digest(encoded(asdict(self)))

    def fresh(self, now):
        start = datetime.fromisoformat(self.reviewed_at)
        if not start <= now < start + timedelta(hours=24):
            raise AccessBlocked("policy profile expired/future; independent refresh required")

    def request_matches(self, request):
        if request.category != self.category or request.mpn != (
            RAM_MPN if self.category == "ram" else GPU_MPN
        ):
            raise AccessBlocked("fixed reviewed target request mismatch")


PROFILES = {
    "tdvat": Profile(
        "tdvat",
        "https://tdvat.ru/videokarty/tproduct/611579327082-videokarta-msi-geforce-rtx-5090-32g-supr",
        "gpu",
        "2026-10-12T10:45:00+00:00",
        GPU_POLICY,
    ),
    "evens": Profile(
        "evens",
        "https://evens-pc.ru/catalog/komplektuyushhie-dlya-pk/videokartyi/videokartyi-nvidia/videokarta-rtx-5090-32gb-msi-suprim-liquid-soc",
        "gpu",
        "2026-10-12T10:45:00+00:00",
        GPU_POLICY,
    ),
    "ram28": Profile(
        "ram28",
        "https://28bit.ru/operativnaya-pamyat-96-gb-6000-mhz-g-skill-trident-z5-neo-rgb-f5-6000j3036f48gx2-tz5nr/",
        "ram",
        "2026-10-12T00:03:50.785796+00:00",
        "075e4aed15e66133b3abce64d1b34bf860efc2e70e49f2573952ce76b9c1b6d0",
    ),
    "ramregard": Profile(
        "ramregard",
        "https://www.regard.ru/product/500515/operativnaia-pamiat-96gb-ddr5-6000mhz-gskill-trident-z5-neo-rgb-f5-6000j3036f48gx2-tz5nr-2x48gb-kit",
        "ram",
        "2026-10-12T08:50:30+00:00",
        "06f57568832e337db2d56f14c16d1316955aafe7965fe9268e293c3a7b25fa9e",
    ),
}


def release_gate(path, expected_hash):
    if path is None or expected_hash is None:
        raise AccessBlocked(
            "independent controller review receipt required before production writes/HTTP"
        )
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise AccessBlocked("bounded local operator review receipt required")
    raw = path.read_bytes()
    if digest(raw) != expected_hash:
        raise AccessBlocked("review receipt hash mismatch")
    value = json.loads(raw, object_pairs_hook=unique_members)
    current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True
    ):
        raise AccessBlocked(
            "reviewed source/controller snapshot is dirty; no production writes/HTTP"
        )
    if (
        set(value) != {"status", "independent", "reviewed_commit", "profile_hashes"}
        or value["status"] != "limited_controller_PASS"
        or value["independent"] is not True
        or value["reviewed_commit"] != current
        or value["profile_hashes"] != {k: PROFILES[k].fingerprint for k in ("tdvat", "evens")}
    ):
        raise AccessBlocked("review verdict/exact current SHA/profile binding invalid")
    return value
