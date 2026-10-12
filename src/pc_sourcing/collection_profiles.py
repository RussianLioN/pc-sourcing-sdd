"""Reviewed exact REGARD F5 HTML capability; no catalogue/search/feed expansion."""

import hashlib
import json
import socket
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pc_sourcing.collection_acquisition import RAM_MPN, Acquisition
from pc_sourcing.curated_primary import NoRedirect, RobotsRules
from pc_sourcing.durable_jobs import encoded
from pc_sourcing.live_models import Candidate
from pc_sourcing.live_sourcing import parse_card
from pc_sourcing.live_transport import DENIAL_MARKERS, AccessBlocked, public_address, read_bounded

REGARD_URL = "https://www.regard.ru/product/500515/operativnaia-pamiat-96gb-ddr5-6000mhz-gskill-trident-z5-neo-rgb-f5-6000j3036f48gx2-tz5nr-2x48gb-kit"
REGARD_ORIGIN = "https://www.regard.ru"
REVIEWED_AT = "2026-10-12T08:50:30+00:00"  # earliest known review time, not invented completion
REVIEW_HASH = "06f57568832e337db2d56f14c16d1316955aafe7965fe9268e293c3a7b25fa9e"


def regard_get(url):
    if url not in {REGARD_URL, REGARD_ORIGIN + "/robots.txt"} or urlsplit(url).query:
        raise AccessBlocked("REGARD exact reviewed URL capability only")
    try:
        public_address(urlsplit(url).hostname)
    except socket.gaierror:
        pass  # fixed reviewed trusted origin; managed resolver binding remains unknown
    request = urllib.request.Request(
        url, headers={"User-Agent": "PC-Sourcing-Research/1.0", "Accept-Encoding": "identity"}
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            if response.status != 200 or response.geturl() != url:
                raise AccessBlocked("REGARD status/final URL mismatch")
            headers = {k.lower(): v for k, v in response.headers.items()}
            if headers.get("content-encoding", "identity") != "identity":
                raise AccessBlocked("unsupported source encoding")
            return read_bounded(response), headers
    except urllib.error.HTTPError as exc:
        raise AccessBlocked(f"REGARD HTTP {exc.code}; no retry/fallback") from exc
    except (OSError, ValueError) as exc:
        raise AccessBlocked(f"REGARD transport {type(exc).__name__}; no retry/fallback") from exc


def regard_rules(raw):
    text = raw.decode("utf-8")
    # Host is a non-access extension, accepted only if consistent with this exact origin.
    lines = []
    for line in text.splitlines():
        if line.lower().startswith("host:"):
            if line.partition(":")[2].strip() not in {REGARD_ORIGIN, "www.regard.ru"}:
                raise AccessBlocked("robots Host conflicts with reviewed origin")
        else:
            lines.append(line)
    rules = RobotsRules("\n".join(lines))
    if not rules.allowed(REGARD_URL):
        raise AccessBlocked("robots disallows exact REGARD card")
    return rules


class RegardReader:
    def __init__(self, registry, state, *, transport=regard_get, sleep=time.sleep):
        if registry != RegardAcquisition.profile():
            raise AccessBlocked("REGARD profile changed/unsupported")
        reviewed = datetime.fromisoformat(registry["reviewed_at"])
        if not 0 <= (datetime.now(UTC) - reviewed).total_seconds() <= 86400:
            raise AccessBlocked("source review expired/future")
        self.registry, self.state, self.transport, self.sleep = registry, state, transport, sleep
        self.urls = {REGARD_URL: registry["listings"][0]}
        self.count = 0

    def check_state(self):
        if self.state.exists() or self.state.with_name(self.state.name + ".denial.json").exists():
            raise AccessBlocked("REGARD persistent source denial; no alternate access")

    def seed_candidates(self, now, request):
        return [
            Candidate(
                url=REGARD_URL,
                title=request.name,
                queries=(),
                observed_at=now,
                response_sha256=hashlib.sha256(encoded(self.registry)).hexdigest(),
                origin="curated_registry",
            )
        ]

    def observe(self, request, candidate, now):
        self.check_state()
        if candidate.url != REGARD_URL or request.mpn != RAM_MPN or self.count >= 1:
            raise AccessBlocked("exact source budget/context")
        try:
            robots, headers = self.transport(REGARD_ORIGIN + "/robots.txt")
            if not headers.get("content-type", "").startswith("text/plain"):
                raise AccessBlocked("robots MIME invalid")
            rules = regard_rules(robots)
            self.sleep(max(5, rules.delay))
            self.check_state()
            self.count += 1
            body, headers = self.transport(REGARD_URL)
            if not headers.get("content-type", "").startswith("text/html"):
                raise AccessBlocked("card MIME invalid")
            html = body.decode("utf-8")
            if any(m in html.lower() for m in DENIAL_MARKERS):
                raise AccessBlocked("source CAPTCHA/access denial")
            o = parse_card(request, candidate, html, datetime.now(UTC))
            previous = o.primary or {}
            assertions = json.loads(previous.get("retained_content", "{}")).get(
                "identity_assertions", []
            )
            names = {
                "title": "name",
                "mpn": "mpn",
                "price_rub": "price",
                "stock": "availability",
                "condition": "itemCondition",
            }
            selected = {
                "h1": o.title,
                "product_count": 1 if o.title else 0,
                "properties": {names[f.field]: [str(f.value)] for f in o.facts if f.field in names},
                "identity_assertions": assertions,
                "identity_conflicts": list(o.differences),
                "price_types": [],
            }
            if o.price_rub is not None:
                selected["price_rub"] = o.price_rub
            retained = encoded(selected).decode()
            h = hashlib.sha256(retained.encode()).hexdigest()
            primary = {
                "retained_content": retained,
                "retained_sha256": h,
                "content_kind": "selected_primary_metadata",
                "response_body_sha256": hashlib.sha256(body).hexdigest(),
                "robots_sha256": hashlib.sha256(robots).hexdigest(),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "requested_url": REGARD_URL,
                "final_url": REGARD_URL,
                "registry_sha256": hashlib.sha256(encoded(self.registry)).hexdigest(),
                "http_date": headers.get("date"),
                "age": headers.get("age"),
                "cache_control": headers.get("cache-control"),
                "target_ip_binding": "unknown behind managed gateway",
            }
            return o.model_copy(
                update={
                    "primary": primary,
                    "facts": tuple(f.model_copy(update={"content_sha256": h}) for f in o.facts),
                }
            )
        except (AccessBlocked, OSError, ValueError, TypeError) as exc:
            if not self.state.exists():
                self.state.write_bytes(
                    encoded(
                        {
                            "origin": REGARD_ORIGIN,
                            "reason": str(exc)[:200],
                            "at": datetime.now(UTC).isoformat(),
                        }
                    )
                )
            raise


class RegardAcquisition(Acquisition):
    source_key = "regard"
    target_url = REGARD_URL

    @staticmethod
    def profile():
        return {
            "origin": REGARD_ORIGIN,
            "status": "bounded_public_read",
            "reviewed_at": REVIEWED_AT,
            "review_time_basis": "earliest review start timestamp",
            "review_evidence_sha256": REVIEW_HASH,
            "scope": "one known canonical F5 HTML card; minimal nonpersonal facts; no query/search/feed/API/image/review; >=5s serial",
            "listings": [{"url": REGARD_URL, "requested_mpn": RAM_MPN}],
        }

    def canonical_registry(self):
        return self.profile()

    def default_transport(self):
        return regard_get

    def reader(self, registry, state, **kwargs):
        return RegardReader(registry, state, **kwargs)
