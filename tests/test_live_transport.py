"""LIVE-03/04: denied sources and bounded transport do not acquire access."""

import json
from datetime import timedelta

import pytest
from test_live_sourcing import NOW, card

from pc_sourcing import live_transport as transport
from pc_sourcing.live_models import SourcePolicy
from pc_sourcing.live_transport import AccessBlocked, Reader, Response


def policy(**updates):
    values = {
        "domain": "shop.example",
        "seller": "Synthetic test shop",
        "status": "allowed",
        "terms_url": "https://shop.example/terms",
        "reviewed_at": NOW,
        "basis": "synthetic policy; not live permission",
        "retain_facts": True,
    }
    return SourcePolicy(**(values | updates))


def test_pending_and_avito_never_request():
    calls = []
    reader = Reader([policy(status="pending")], transport=lambda url: calls.append(url))
    for url in ["https://shop.example/card", "https://www.avito.ru/card", "https://avito.ru/card"]:
        with pytest.raises(AccessBlocked):
            reader.read(url, NOW)
    assert calls == []


@pytest.mark.parametrize(
    "patch",
    [
        {"retain_facts": False},
        {"terms_url": None},
        {"reviewed_at": NOW - timedelta(days=8)},
        {"reviewed_at": NOW + timedelta(seconds=1)},
    ],
)
def test_policy_incomplete_stale_future(patch):
    reader = Reader([policy(**patch)], transport=lambda url: pytest.fail("must not request"))
    with pytest.raises(AccessBlocked):
        reader.read("https://shop.example/card", NOW)


@pytest.mark.parametrize("failure", ["HTTP 403", "HTTP 429", "timeout", "HTTP 302"])
def test_domain_stop_no_retry(failure):
    calls = []

    def fetch(url):
        calls.append(url)
        if url.endswith("robots.txt"):
            return Response(b"User-agent: *\nAllow: /", {"content-type": "text/plain"}, 200)
        raise AccessBlocked(failure)

    reader = Reader([policy()], transport=fetch, sleep=lambda _: None)
    for url in ["https://shop.example/one", "https://shop.example/two"]:
        with pytest.raises(AccessBlocked, match=failure):
            reader.read(url, NOW)
    assert len(calls) == 2


def test_robots_and_captcha_block():
    reader = Reader(
        [policy()],
        transport=lambda url: Response(
            b"User-agent: *\nDisallow: /", {"content-type": "text/plain"}, 200
        ),
        sleep=lambda _: None,
    )
    with pytest.raises(AccessBlocked, match="robots"):
        reader.read("https://shop.example/card", NOW)
    reader = Reader(
        [policy()],
        transport=lambda url: Response(
            b"User-agent: *\nAllow: /" if url.endswith("robots.txt") else b"captcha",
            {"content-type": "text/plain" if url.endswith("robots.txt") else "text/html"},
            200,
        ),
        sleep=lambda _: None,
    )
    with pytest.raises(AccessBlocked, match="CAPTCHA"):
        reader.read("https://shop.example/card", NOW)


def test_single_domain_queue_and_card_budget():
    delays = []
    reader = Reader(
        [policy()],
        transport=lambda url: Response(
            b"User-agent: *\nAllow: /\nCrawl-delay: 10"
            if url.endswith("robots.txt")
            else card().encode(),
            {"content-type": "text/plain" if url.endswith("robots.txt") else "text/html"},
            200,
        ),
        sleep=delays.append,
    )
    for i in range(10):
        reader.read(f"https://shop.example/{i}", NOW)
    assert len(delays) == 10 and all(9 <= seconds <= 10 for seconds in delays)
    with pytest.raises(AccessBlocked, match="budget"):
        reader.read("https://shop.example/11", NOW)


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "192.168.1.1"]
)
def test_private_dns_rejected(monkeypatch, address):
    monkeypatch.setattr(
        transport.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (address, 443))]
    )
    with pytest.raises(AccessBlocked, match="non-public"):
        transport.public_address("shop.example")


def test_keyless_exact_endpoint_no_key(monkeypatch):
    calls = []

    def fetch(url, **kwargs):
        calls.append((url, kwargs))
        query = json.loads(kwargs["payload"])["query"]
        return Response(json.dumps({"query": query, "results": []}).encode(), {}, 200)

    monkeypatch.setattr(transport, "https", fetch)
    transport.keyless_search("public product")
    url, kwargs = calls[0]
    assert url == "https://api.tavily.com/search"
    assert kwargs["headers"]["X-Tavily-Access-Mode"] == "keyless"
    assert "Authorization" not in kwargs["headers"]


def test_bounded_bytes_and_deadline(monkeypatch):
    class Oversized:
        def read1(self, size):
            return b"a" * size

    monkeypatch.setattr(transport, "MAX_BYTES", 64)
    with pytest.raises(AccessBlocked, match="byte budget"):
        transport.read_bounded(Oversized())
    times = iter([0, 31])
    monkeypatch.setattr(transport.time, "monotonic", lambda: next(times))
    with pytest.raises(AccessBlocked, match="time budget"):
        transport.read_bounded(Oversized())


def test_managed_proxy_respects_redirect_and_denial(monkeypatch):
    import urllib.error

    monkeypatch.setattr(transport, "public_address", lambda host: "8.8.8.8")
    calls = []

    class Denied:
        def open(self, request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 403, "denied", {}, None)

    monkeypatch.setattr(transport.urllib.request, "build_opener", lambda *a: Denied())
    with pytest.raises(AccessBlocked, match="HTTP 403"):
        transport.managed_https(
            "https://api.tavily.com/search", b"{}", {"X-Tavily-Access-Mode": "keyless"}
        )
    assert calls == ["https://api.tavily.com/search"]
    assert (
        transport.NoRedirect().redirect_request(None, None, 302, None, {}, "https://else.example")
        is None
    )


@pytest.mark.parametrize(
    "body,mime",
    [
        (b"<html>captcha access denied</html>", "text/html"),
        (b"captcha access denied", "text/plain"),
        (b"<html>ordinary error</html>", "text/plain"),
        (b"unknown text", "text/plain"),
        (b"", "text/plain"),
        (b"User-agent: *\nAllow: /", "application/json"),
        (b"User-agent: *\nDisallow: */api/*", "text/plain"),
        (b"User-agent: *\nAllow: /\nDisallow: /private", "text/plain"),
    ],
)
def test_invalid_or_unsupported_robots_stops_before_card(body, mime):
    calls = []

    def fetch(url):
        calls.append(url)
        return Response(body, {"content-type": mime}, 200)

    reader = Reader([policy()], transport=fetch, sleep=lambda _: None)
    for url in ["https://shop.example/card", "https://shop.example/neighbor"]:
        with pytest.raises(AccessBlocked):
            reader.read(url, NOW)
    assert calls == ["https://shop.example/robots.txt"]


def test_managed_proxy_arbitrary_target_rejected_before_dns_or_request(monkeypatch):
    monkeypatch.setattr(transport, "public_address", lambda host: pytest.fail("must not resolve"))
    monkeypatch.setattr(
        transport.urllib.request, "build_opener", lambda *a: pytest.fail("must not connect")
    )
    for url in [
        "https://shop.example/card",
        "https://api.tavily.com/extract",
        "https://api.tavily.com/search?url=private",
        "https://api.tavily.com.evil/search",
    ]:
        with pytest.raises(AccessBlocked, match="cannot be pinned"):
            transport.managed_https(url, b"{}", {"X-Tavily-Access-Mode": "keyless"})


def test_proxy_branch_never_uses_local_dns_as_destination_proof(monkeypatch):
    monkeypatch.setattr(transport.urllib.request, "getproxies", lambda: {"https": "managed"})
    monkeypatch.setattr(transport, "public_address", lambda host: pytest.fail("must not resolve"))
    with pytest.raises(AccessBlocked, match="primary access blocked"):
        transport.https("https://shop.example/card")
