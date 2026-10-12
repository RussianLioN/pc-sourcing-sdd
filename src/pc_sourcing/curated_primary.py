"""Reviewed exact-URL capabilities for public buyer research through managed gateway."""

import hashlib
import json
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from pc_sourcing.live_models import Candidate, Fact, Observation, canonical_url
from pc_sourcing.live_sourcing import dumps, identity
from pc_sourcing.live_transport import DENIAL_MARKERS, AccessBlocked, public_address, read_bounded

APPROVED_ORIGIN = "https://28bit.ru"
APPROVED_PATHS = {
    "/robots.txt",
    "/operativnaya-pamyat-96-gb-6000-mhz-g-skill-trident-z5-neo-rgb-f5-6000j3036f48gx2-tz5nr/",
    "/videokart-palit-ne75090019r5-gb2020g-geforce-rtx-5090-32gb-gamerock/",
}
VOID = {"meta", "link", "img", "input", "br", "hr", "source", "area", "wbr", "embed"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def fixed_get(url):
    url = canonical_url(url)
    parts = urlsplit(url)
    if (
        f"{parts.scheme}://{parts.netloc}" != APPROVED_ORIGIN
        or parts.path not in APPROVED_PATHS
        or parts.query
    ):
        raise AccessBlocked("network helper requires fixed reviewed source capability")
    dns_status = "public_precheck_only_not_binding"
    try:
        public_address(urlsplit(url).hostname)  # known non-public answers still reject
    except socket.gaierror:
        # Only a fixed reviewed trusted-origin capability reaches this branch.
        # Managed proxy has its own resolver; unknown local DNS is not source denial.
        dns_status = "unknown_local_resolver_unavailable"
    request = urllib.request.Request(
        url, headers={"User-Agent": "PC-Sourcing-Research/1.0", "Accept-Encoding": "identity"}
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            headers = {k.lower(): v for k, v in response.headers.items()}
            headers["x-primary-local-dns-status"] = dns_status
            if response.status != 200 or response.geturl() != url:
                raise AccessBlocked("primary response status/final URL differs")
            if headers.get("content-encoding", "identity") != "identity":
                raise AccessBlocked("unsupported source encoding")
            return read_bounded(response), headers
    except urllib.error.HTTPError as exc:
        raise AccessBlocked(f"primary HTTP {exc.code}; no retry/fallback") from exc
    except (OSError, ValueError) as exc:
        raise AccessBlocked(f"primary transport {type(exc).__name__}; no retry/fallback") from exc


def path_matches(pattern, path):
    """Greedy bounded glob matcher; no regex backtracking on external policy text."""
    i = j = 0
    star = -1
    restart = 0
    while j < len(path):
        if i < len(pattern) and pattern[i] == "*":
            star, restart = i, j
            i += 1
        elif i < len(pattern) and pattern[i] == path[j]:
            i += 1
            j += 1
        elif star >= 0:
            restart += 1
            j, i = restart, star + 1
        else:
            return False
    return all(c == "*" for c in pattern[i:])


class RobotsRules:
    """Bounded RFC9309 path patterns; unsupported policy directives fail closed."""

    def __init__(self, text):
        if any(m in text.lower() for m in DENIAL_MARKERS if m != "captcha") or "<" in text:
            raise AccessBlocked("robots denial/HTML")
        if re.search(r"(?i)captcha", text) and any(
            "captcha" in line.lower() and not line.lower().startswith("disallow:")
            for line in text.splitlines()
        ):
            raise AccessBlocked("robots CAPTCHA denial")
        groups, group, have_rule = [], None, False
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            name, sep, value = line.partition(":")
            name, value = name.strip().lower(), value.strip()
            if not sep:
                raise AccessBlocked("malformed robots line")
            if name == "user-agent":
                if group is None or have_rule:
                    group = {"agents": [], "rules": [], "delay": 10}
                    groups.append(group)
                    have_rule = False
                if not value:
                    raise AccessBlocked("empty robots agent")
                group["agents"].append(value.lower())
            elif name in {"allow", "disallow"}:
                if (
                    group is None
                    or len(value) > 500
                    or (value and not value.startswith(("/", "*")))
                ):
                    raise AccessBlocked("malformed/oversized robots pattern")
                have_rule = True
                if value:
                    if "\\" in value or "$" in value[:-1]:
                        raise AccessBlocked("unsupported robots pattern")
                    if re.search(r"%(?![0-9A-Fa-f]{2})", value):
                        raise AccessBlocked("malformed robots percent encoding")

                    def normalize(match):
                        char = chr(int(match[1], 16))
                        return char if re.fullmatch(r"[A-Za-z0-9_.~-]", char) else match[0].upper()

                    value = re.sub(r"%([0-9A-Fa-f]{2})", normalize, value)
                    anchored = value.endswith("$")
                    raw = value[:-1] if anchored else value
                    pattern = raw if anchored else raw + "*"
                    group["rules"].append((len(raw.replace("*", "")), name == "allow", pattern))
            elif name == "crawl-delay":
                if group is None or not re.fullmatch(r"[0-9]{1,2}", value):
                    raise AccessBlocked("unsupported robots delay")
                group["delay"] = max(10, int(value))
            elif name == "sitemap":
                if not value.startswith("https://"):
                    raise AccessBlocked("invalid robots sitemap")
            elif name == "clean-param":
                continue  # every curated query string is rejected independently
            else:
                raise AccessBlocked("unsupported robots directive")
        token = "pc-sourcing-research/1.0"
        scores = [
            max(
                (len(a) if a != "*" else 0 for a in g["agents"] if a == "*" or a in token),
                default=-1,
            )
            for g in groups
        ]
        best = max(scores, default=-1)
        selected = [g for g, score in zip(groups, scores, strict=True) if score == best]
        if best < 0:
            raise AccessBlocked("robots applicable agent missing")
        self.rules = [rule for g in selected for rule in g["rules"]]
        self.delay = max(g["delay"] for g in selected)
        if self.delay > 60:
            raise AccessBlocked("robots delay exceeds budget")

    def allowed(self, url):
        p = urlsplit(url)
        if p.query or "%" in p.path or "\\" in p.path:
            return False
        matched = [
            (length, allow)
            for length, allow, pattern in self.rules
            if path_matches(pattern, p.path)
        ]
        return max(matched, default=(0, True))[1]


class ProductScope(HTMLParser):
    """Retain scalar metadata/h1 and price-type selectors, never page/session HTML."""

    def __init__(self):
        super().__init__()
        self.stack, self.scope, self.properties, self.h1, self.h1_depth = [], None, {}, [], None
        self.price_types = []
        self.product_count = 0
        self.item_scopes = {}
        self.scope_relations = {}
        self.visible_product_text = []
        self.visible_length = 0
        self.text_overflow = False
        self.unsupported_material = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in VOID:
            self.stack.append(tag)
        if attrs.get("itemtype", "").rstrip("/").endswith("schema.org/Product"):
            self.product_count += 1
            self.scope = len(self.stack)
        if "itemscope" in attrs:
            self.scope_relations[len(self.stack)] = attrs.get("itemprop")
            self.item_scopes[len(self.stack)] = (
                attrs.get("itemtype", "").rstrip("/").rsplit("/", 1)[-1]
            )
        if tag == "h1":
            self.h1_depth = len(self.stack)
        if self.scope and attrs.get("itemprop"):
            prop = attrs["itemprop"]
            owner = self.item_scopes[max(self.item_scopes)] if self.item_scopes else None
            required_owner = (
                "Offer"
                if prop in {"price", "priceCurrency", "availability", "itemCondition"}
                else "Product"
            )
            if (
                owner == "Brand"
                and prop == "name"
                and self.scope_relations.get(max(self.item_scopes)) in {"brand", "manufacturer"}
            ):
                value = attrs.get("content")
                if value is not None and len(value) <= 300:
                    self.properties.setdefault("manufacturer", []).append(value)
                else:
                    self.unsupported_material = True
                return
            if owner == "PropertyValue":
                self.unsupported_material = True
            if owner != required_owner:
                return
            value = attrs.get("content", attrs.get("href"))
            if value is not None and len(value) <= 300 and len(prop) <= 100:
                if sum(len(v) for v in self.properties.values()) >= 128:
                    self.unsupported_material = True
                else:
                    self.properties.setdefault(prop, []).append(value)
            elif value is not None:
                self.unsupported_material = True
        if tag == "input" and attrs.get("name") == "pricetype_radio":
            self.price_types.append(
                {
                    "value": attrs.get("value"),
                    "name": attrs.get("data-name"),
                    "checked": "checked" in attrs,
                }
            )

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag in self.stack:
            depth = len(self.stack) - self.stack[::-1].index(tag)
            if self.h1_depth and depth <= self.h1_depth:
                self.h1_depth = None
            if self.scope and depth <= self.scope:
                self.scope = None
            self.item_scopes = {d: kind for d, kind in self.item_scopes.items() if d < depth}
            self.scope_relations = {
                d: relation for d, relation in self.scope_relations.items() if d < depth
            }
            del self.stack[depth - 1 :]

    def handle_data(self, text):
        if self.h1_depth:
            self.h1.append(text)
        if self.scope and self.stack[-1] not in {"script", "style"} and text.strip():
            if self.visible_length + len(text) <= 4000 and not self.text_overflow:
                self.visible_product_text.append(text)
                self.visible_length += len(text)
            else:
                self.text_overflow = True


def observe(request, candidate, html, provenance, now):
    parsed = ProductScope()
    parsed.feed(html)
    title = " ".join(" ".join(parsed.h1).split())
    # Store SKU is preserved separately and never substituted for manufacturer MPN.
    props = parsed.properties
    mpns = list(dict.fromkeys(props.get("mpn", [])))
    mpn = mpns[0] if len(mpns) == 1 else None
    # Reviewed 28BIT Palit title convention: NE-prefixed manufacturer identifier,
    # never numeric store sku. Preserve suffix exactly; conflicting declarations unknown.
    declared = re.search(r"(?i)\bPalit\s*\((NE[A-Z0-9]+-[A-Z0-9]+)\)", title)
    if re.search(r"(?i)\bG[.]?\s*Skill\b", title):
        ram_declared = re.search(r"\b(F5-[A-Z0-9]+(?:-[A-Z0-9]+)+)\b", title, re.IGNORECASE)
        if ram_declared:
            declared = ram_declared
    conflict = len(mpns) > 1 or bool(declared and mpn and declared[1].upper() != mpn.upper())
    names = list(dict.fromkeys(props.get("name", [])))

    def normalize(value):
        return " ".join(value.casefold().split())

    conflict = conflict or bool(
        names and (len(names) != 1 or normalize(names[0]) != normalize(title))
    )
    conflict = (
        conflict or parsed.product_count != 1 or parsed.text_overflow or parsed.unsupported_material
    )
    if conflict:
        mpn = None
    elif not mpns and declared:
        mpn = declared[1]
    mpn_selector = "Product meta[itemprop=mpn]" if mpns else "h1 declared manufacturer code (NE/F5)"
    match, differences = identity(request, title, mpn)
    if conflict:
        match, differences = "unresolved", ("Conflicting or multiple primary Product identities",)
    from pc_sourcing.identity_attributes import conflicts
    from pc_sourcing.identity_claims import assertions_data, extract

    attribute_conflicts = conflicts(
        request,
        [title, " ".join(parsed.visible_product_text), *props.get("description", [])],
        structured=props,
        allow_variant_difference=bool(request.mpn and mpn and request.mpn != mpn),
    )
    if attribute_conflicts and match != "excluded":
        match, differences = (
            "unresolved",
            ("Conflicting primary attributes: " + ", ".join(attribute_conflicts),),
        )
        conflict = True
    if request.category == "ram" and (
        not re.search(r"(?i)оперативная память|\bRAM\b|\bmemory\b", title)
        or re.search(r"(?i)ноутбук|компьютер|\blaptop\b|\bDDR[234]\b", title)
    ):
        match, differences = "unresolved", ("Категория/характеристики памяти не согласованы",)
    primary = {
        "h1": title,
        "product_count": parsed.product_count,
        "properties": props,
        "price_types": parsed.price_types,
        "visible_product_text": " ".join(parsed.visible_product_text),
        "identity_conflicts": list(attribute_conflicts),
        "identity_assertions": assertions_data(
            extract(
                [title, " ".join(parsed.visible_product_text), *props.get("description", [])],
                request.category,
                props,
            )
        ),
        "visible_text_truncated": parsed.text_overflow,
        "unsupported_material_schema": parsed.unsupported_material,
    }
    retained = dumps(primary)
    retained_hash = hashlib.sha256(retained.encode()).hexdigest()
    evidence = []
    for field, value, selector in [
        ("title", title, "h1"),
        ("mpn", mpn, mpn_selector),
    ]:
        if value:
            evidence.append(
                Fact(
                    field=field,
                    value=value,
                    url=candidate.url,
                    observed_at=now,
                    origin="store_card",
                    selector=selector,
                    content_sha256=retained_hash,
                )
            )
    price = None
    prices = list(dict.fromkeys(props.get("price", [])))
    currencies = list(dict.fromkeys(props.get("priceCurrency", [])))
    # Retail UI presence alone does not establish every applicable payment condition.
    # Preserve displayed price as evidence, keep unconditional price unknown initially.
    if (
        parsed.product_count == 1
        and len(prices) == 1
        and re.fullmatch(r"[0-9]{1,10}", prices[0])
        and currencies == ["RUB"]
        and int(prices[0]) > 0
    ):
        evidence.append(
            Fact(
                field="displayed_price_rub",
                value=int(prices[0]),
                url=candidate.url,
                observed_at=now,
                origin="store_card",
                selector='[itemscope][itemtype$="schema.org/Product"] [itemprop="offers"] meta[itemprop="price"]',
                content_sha256=retained_hash,
            )
        )
    availability = list(dict.fromkeys(props.get("availability", [])))
    stock = "unknown"
    if parsed.product_count == 1 and len(availability) == 1:
        stock = {"InStock": "in_stock", "PreOrder": "preorder", "OutOfStock": "unavailable"}.get(
            availability[0].rsplit("/", 1)[-1], "unknown"
        )
    if stock != "unknown":
        evidence.append(
            Fact(
                field="declared_stock",
                value=stock,
                url=candidate.url,
                observed_at=now,
                origin="store_card",
                selector='[itemscope][itemtype$="schema.org/Product"] [itemprop="offers"] link[itemprop="availability"]',
                content_sha256=retained_hash,
            )
        )
    return Observation(
        candidate=candidate,
        status="observed" if parsed.product_count == 1 and not conflict else "unresolved",
        reason="Primary content read; unconditional price, Moscow fulfillment, "
        "condition, seller review and quantity not confirmed",
        title=title or None,
        mpn=mpn,
        price_rub=price,
        stock="unknown",
        match=match,
        differences=differences,
        facts=tuple(evidence),
        primary={
            **provenance,
            "retained_content": retained,
            "retained_sha256": retained_hash,
            "content_kind": "selected_primary_metadata",
        },
    )


class CuratedReader:
    def __init__(self, registry, state, *, transport=fixed_get, sleep=time.sleep):
        if not Path(state).is_absolute() or Path(state).is_symlink():
            raise ValueError("source state must be an absolute regular path")
        self.registry, self.state = registry, Path(state).resolve()
        if (
            registry.get("origin") != APPROVED_ORIGIN
            or registry.get("status") != "bounded_public_read"
        ):
            raise ValueError("unknown/unapproved curated origin")
        self.urls = {canonical_url(row["url"]): row for row in registry["listings"]}
        for url in self.urls:
            p = urlsplit(url)
            if f"{p.scheme}://{p.netloc}" != APPROVED_ORIGIN or p.query or "%" in p.path:
                raise ValueError("invalid curated capability")
            if any(
                segment in p.path.split("/")
                for segment in (
                    "my",
                    "checkout",
                    "cart",
                    "signup",
                    "login",
                    "search",
                    "webasyst",
                    "api",
                    "order",
                )
            ):
                raise ValueError("action/private source capability")
        reviewed = datetime.fromisoformat(registry["reviewed_at"])
        if (
            reviewed.tzinfo is None
            or not 0 <= (datetime.now(UTC) - reviewed).total_seconds() <= 86400
        ):
            raise ValueError("curated review stale/future")
        self.transport, self.sleep, self.robots, self.count = transport, sleep, None, 0
        self.registry_hash = hashlib.sha256(dumps(registry).encode()).hexdigest()

    def seed_candidates(self, now, request=None):
        selected = self.urls.items()
        if request and request.mpn:
            matching = [
                (url, row) for url, row in selected if row.get("requested_mpn") == request.mpn
            ]
            if matching:
                selected = matching
        return [
            Candidate(
                url=url,
                title=row["title"],
                queries=(),
                observed_at=now,
                response_sha256=self.registry_hash,
                origin="curated_registry",
            )
            for url, row in selected
        ]

    def check_state(self):
        if self.state.with_name(self.state.name + ".denial.json").exists():
            raise AccessBlocked("source has persistent denial; explicit source review required")
        if self.state.exists():
            record = json.loads(self.state.read_text())
            # Legacy plain gaierror could only escape public_address before HTTP.
            # Preserve its bytes; it is an infrastructure record, not a site denial.
            if record.get("reason") == "gaierror":
                return
            raise AccessBlocked("source has persistent stop; explicit new source review required")

    def stop(self, reason):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        target = (
            self.state
            if not self.state.exists()
            else self.state.with_name(self.state.name + ".denial.json")
        )
        if target.exists():
            return
        with target.open("x") as stream:
            stream.write(
                dumps(
                    {
                        "origin": APPROVED_ORIGIN,
                        "reason": reason,
                        "at": datetime.now(UTC).isoformat(),
                    }
                )
                + "\n"
            )

    def observe(self, request, candidate, now):
        self.check_state()
        if candidate.url not in self.urls:
            raise AccessBlocked("listing not in reviewed exact-URL registry")
        if self.count >= 1:
            raise AccessBlocked("primary one-card research budget exhausted")
        try:
            if self.robots is None:
                body, headers = self.transport(APPROVED_ORIGIN + "/robots.txt")
                if not headers.get("content-type", "").startswith("text/plain"):
                    raise AccessBlocked("robots content type")
                self.robots = RobotsRules(body.decode("utf-8"))
                self.robots_hash = hashlib.sha256(body).hexdigest()
            if not self.robots.allowed(candidate.url):
                raise AccessBlocked("robots disallows curated listing")
            self.sleep(self.robots.delay)
            self.count += 1
            body, headers = self.transport(candidate.url)
            text = body.decode("utf-8")
            if any(marker in text.lower() for marker in DENIAL_MARKERS):
                raise AccessBlocked("primary CAPTCHA/access denial")
            if not headers.get("content-type", "").startswith("text/html"):
                raise AccessBlocked("primary content type")
            provenance = {
                "requested_url": candidate.url,
                "final_url": candidate.url,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "response_body_sha256": hashlib.sha256(body).hexdigest(),
                "robots_sha256": self.robots_hash,
                "registry_sha256": self.registry_hash,
                "http_date": headers.get("date"),
                "age": headers.get("age"),
                "cache_control": headers.get("cache-control"),
                "local_dns_status": headers.get("x-primary-local-dns-status", "not_recorded"),
                "target_ip_binding": "unknown behind managed gateway",
            }
            return observe(request, candidate, text, provenance, datetime.now(UTC))
        except socket.gaierror as exc:
            self.state.parent.mkdir(parents=True, exist_ok=True)
            diagnostic = self.state.with_name(self.state.name + f".dns-{time.time_ns()}.json")
            with diagnostic.open("x") as stream:
                stream.write(
                    dumps(
                        {
                            "origin": APPROVED_ORIGIN,
                            "stage": "local_dns_precheck",
                            "errno": exc.errno,
                            "reason": "gaierror",
                            "source_http_request_sent": False,
                            "at": datetime.now(UTC).isoformat(),
                        }
                    )
                    + "\n"
                )
            raise AccessBlocked(
                "runtime DNS precheck failed before source HTTP; no retry in run"
            ) from exc
        except (AccessBlocked, OSError, ValueError, TypeError, UnicodeError) as exc:
            self.stop(str(exc)[:200] if isinstance(exc, AccessBlocked) else type(exc).__name__)
            raise AccessBlocked(
                "primary source stopped: "
                + (str(exc)[:200] if isinstance(exc, AccessBlocked) else type(exc).__name__)
            ) from exc
