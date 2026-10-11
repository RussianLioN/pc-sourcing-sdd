"""Pinned direct HTTPS; managed proxy restricted to one fixed search endpoint."""

import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from pc_sourcing.live_models import canonical_url

USER_AGENT = "PC-Sourcing-Research/1.0"
MAX_BYTES = 2_000_000


class AccessBlocked(ValueError):
    pass


@dataclass(frozen=True)
class Response:
    body: bytes
    headers: dict
    status: int


def public_address(host):
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    ips = [row[4][0] for row in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise AccessBlocked("non-public destination")
    return ips[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        address = public_address(self.host)
        raw = socket.create_connection((address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def read_bounded(response):
    deadline = time.monotonic() + 30
    pieces, size = [], 0
    while True:
        if time.monotonic() > deadline:
            raise AccessBlocked("response time budget exhausted")
        part = response.read1(min(65536, MAX_BYTES + 1 - size))
        size += len(part)
        if size > MAX_BYTES:
            raise AccessBlocked("response exceeds byte budget")
        if not part:
            return b"".join(pieces)
        pieces.append(part)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def managed_https(url, payload, headers):
    # The proxy resolves its own destination: local DNS is not a binding proof.
    # Block arbitrary source URLs; only this fixed service request is permitted.
    if (
        url != "https://api.tavily.com/search"
        or payload is None
        or headers.get("X-Tavily-Access-Mode") != "keyless"
    ):
        raise AccessBlocked("managed proxy destination cannot be pinned; primary access blocked")
    public_address("api.tavily.com")
    request = urllib.request.Request(url, data=payload, headers=headers)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=15) as response:
            result_headers = {k.lower(): v for k, v in response.headers.items()}
            if result_headers.get("content-encoding", "identity") != "identity":
                raise AccessBlocked("unsupported content encoding")
            if int(result_headers.get("content-length", "0")) > MAX_BYTES:
                raise AccessBlocked("response exceeds byte budget")
            body = read_bounded(response)
            if len(body) > MAX_BYTES:
                raise AccessBlocked("response exceeds byte budget")
            return Response(body, result_headers, response.status)
    except urllib.error.HTTPError as exc:
        raise AccessBlocked(
            f"HTTP {exc.code}; no retry; Retry-After=" + exc.headers.get("Retry-After", "unknown")
        ) from exc
    except (OSError, urllib.error.URLError) as exc:
        raise AccessBlocked(f"managed transport {type(exc).__name__}; no retry") from exc


def https(url, *, payload=None, headers=None):
    url = canonical_url(url)
    request_headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity", **(headers or {})}
    if urllib.request.getproxies().get("https"):
        return managed_https(url, payload, request_headers)
    p = urlsplit(url)
    connection = PinnedHTTPS(p.hostname, timeout=15, context=ssl.create_default_context())
    try:
        connection.request(
            "POST" if payload is not None else "GET",
            p.path + ("?" + p.query if p.query else ""),
            body=payload,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity", **(headers or {})},
        )
        response = connection.getresponse()
        result_headers = {k.lower(): v for k, v in response.getheaders()}
        if response.status != 200:
            retry = result_headers.get("retry-after", "unknown")
            raise AccessBlocked(f"HTTP {response.status}; no retry; Retry-After={retry}")
        if result_headers.get("content-encoding", "identity") != "identity":
            raise AccessBlocked("unsupported content encoding")
        if int(result_headers.get("content-length", "0")) > MAX_BYTES:
            raise AccessBlocked("response exceeds byte budget")
        body = read_bounded(response)
        if len(body) > MAX_BYTES:
            raise AccessBlocked("response exceeds byte budget")
        return Response(body, result_headers, response.status)
    except (OSError, http.client.HTTPException) as exc:
        raise AccessBlocked(f"transport {type(exc).__name__}; no retry") from exc
    finally:
        connection.close()


def keyless_search(query):
    response = https(
        "https://api.tavily.com/search",
        payload=json.dumps(
            {
                "query": query,
                "country": "Russia",
                "max_results": 5,
                "search_depth": "basic",
                "include_raw_content": False,
            }
        ).encode(),
        headers={"Content-Type": "application/json", "X-Tavily-Access-Mode": "keyless"},
    )
    try:
        result = json.loads(response.body)
        if not isinstance(result, dict) or not isinstance(result.get("results"), list):
            raise AccessBlocked("keyless cap or unexpected response; no auth/retry")
        return result
    except (ValueError, UnicodeError) as exc:
        raise AccessBlocked("invalid search response; no retry") from exc


DENIAL_MARKERS = (
    "captcha",
    "access denied",
    "verify you are human",
    "доступ ограничен",
    "login required",
    "authentication required",
)


def checked_robots(response):
    """Support only unambiguous stdlib rules; unsupported syntax stops the domain."""
    if response.status != 200 or not response.headers.get("content-type", "").lower().startswith(
        "text/plain"
    ):
        raise AccessBlocked("invalid robots response status/content type")
    text = response.body.decode("utf-8", errors="strict").lstrip("\ufeff")
    if any(marker in text.lower() for marker in DENIAL_MARKERS) or "<" in text or ">" in text:
        raise AccessBlocked("robots CAPTCHA/access denial/HTML; no bypass")
    agent, allow, deny = False, False, False
    known = {"user-agent", "allow", "disallow", "crawl-delay", "request-rate", "sitemap"}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, sep, value = line.partition(":")
        name, value = name.lower().strip(), value.strip()
        if not sep or name not in known:
            raise AccessBlocked("unsupported or malformed robots directive")
        if name == "user-agent":
            if not value:
                raise AccessBlocked("empty robots user-agent")
            agent = True
        elif name in {"allow", "disallow", "crawl-delay", "request-rate"}:
            if not agent:
                raise AccessBlocked("robots rule without user-agent")
            if name in {"allow", "disallow"}:
                if any(c in value for c in "*$%") or (value and not value.startswith("/")):
                    raise AccessBlocked("unsupported robots wildcard/encoded pattern")
                allow |= name == "allow" and bool(value)
                deny |= name == "disallow" and bool(value)
            elif name == "crawl-delay" and not re.fullmatch(r"[0-9]{1,2}", value):
                raise AccessBlocked("unsupported robots crawl-delay")
            elif name == "request-rate" and not re.fullmatch(
                r"[1-9][0-9]{0,2}/[1-9][0-9]{0,2}", value
            ):
                raise AccessBlocked("unsupported robots request-rate")
    if not agent or (allow and deny):
        raise AccessBlocked("robots empty/ambiguous allow-disallow precedence")
    robots = RobotFileParser()
    robots.parse(text.splitlines())
    return robots


class Reader:
    """One sequential run, max 10 cards. No background or multi-process claim."""

    def __init__(self, policies, *, transport=https, sleep=time.sleep):
        self.policies = {p.domain: p for p in policies}
        self.transport, self.sleep = transport, sleep
        self.stopped, self.robots, self.last = {}, {}, {}
        self.count = 0

    def read(self, url, now):
        url = canonical_url(url)
        host = urlsplit(url).hostname
        if host == "avito.ru" or host.endswith(".avito.ru"):
            raise AccessBlocked("Avito prior denial; direct access disabled")
        policy = self.policies.get(host)
        if not policy or policy.status != "allowed" or not policy.retain_facts:
            raise AccessBlocked("source terms/retention not confirmed")
        if (
            not policy.terms_url
            or not policy.reviewed_at
            or not 0 <= (now - policy.reviewed_at).total_seconds() <= 7 * 86400
        ):
            raise AccessBlocked("source policy missing, stale or future")
        if host in self.stopped:
            raise AccessBlocked(self.stopped[host])
        if self.count >= 10:
            raise AccessBlocked("card budget exhausted")
        try:
            if host not in self.robots:
                response = self.transport(f"https://{host}/robots.txt")
                robots = checked_robots(response)
                self.robots[host] = robots
                self.last[host] = time.monotonic()
            robots = self.robots[host]
            if not robots.can_fetch(USER_AGENT, url):
                raise AccessBlocked("robots disallows card")
            interval = max(policy.min_interval_seconds, robots.crawl_delay(USER_AGENT) or 0)
            rate = robots.request_rate(USER_AGENT)
            if rate:
                interval = max(interval, rate.seconds / rate.requests)
            if interval > 60:
                raise AccessBlocked("source delay exceeds run budget")
            self.sleep(max(0, interval - (time.monotonic() - self.last.get(host, 0))))
            self.count += 1
            response = self.transport(url)
            self.last[host] = time.monotonic()
            text = response.body.decode("utf-8", errors="strict")
            if any(marker in text.lower() for marker in DENIAL_MARKERS):
                raise AccessBlocked("CAPTCHA/access denial; no bypass")
            if "text/html" not in response.headers.get("content-type", ""):
                raise AccessBlocked("unsupported card content type")
            return text
        except (AccessBlocked, UnicodeError, ValueError, TypeError, OSError) as exc:
            self.stopped[host] = str(exc)
            raise AccessBlocked(str(exc)) from exc
