"""PRIMARY-01–09: curated capabilities, original robots and honest primary observations."""

import hashlib
from datetime import UTC, datetime

import pytest
from test_live_sourcing import GPU, candidate

from pc_sourcing.curated_primary import CuratedReader, RobotsRules, observe
from pc_sourcing.live_sourcing import run, verify
from pc_sourcing.live_transport import AccessBlocked

URL = "https://28bit.ru/palit-card/"


def registry(**changes):
    return {
        "origin": "https://28bit.ru",
        "status": "bounded_public_read",
        "reviewed_at": datetime.now(UTC).isoformat(),
        "listings": [{"url": URL, "title": "Palit 5090"}],
        **changes,
    }


def html():
    return (
        '<h1>Palit RTX 5090 GAMEROCK</h1><div itemscope itemtype="http://schema.org/Product">'
        '<meta itemprop="sku" content="30845"><meta itemprop="mpn" content="NE75090019R5-GB2020G">'
        '<div itemprop="offers" itemscope itemtype="http://schema.org/Offer">'
        '<meta itemprop="price" content="629990"><meta itemprop="priceCurrency" content="RUB">'
        '<link itemprop="availability" href="http://schema.org/InStock"></div></div>'
    )


@pytest.mark.parametrize(
    "path,allowed",
    [
        ("/api/x", False),
        ("/card", True),
        ("/test", False),
        ("/tester", True),
        ("/card?buy=1", False),
        ("/%61pi/x", False),
    ],
)
def test_wildcards_anchors_queries_encoding(path, allowed):
    rules = RobotsRules(
        "User-agent: *\nDisallow: */api/*\nDisallow: /test$\nSitemap: https://28bit.ru/map"
    )
    assert rules.allowed("https://28bit.ru" + path) is allowed


def test_longest_allow_wins_and_specific_agent_overrides_star():
    rules = RobotsRules(
        "User-agent: *\nDisallow: /\nUser-agent: PC-Sourcing-Research\n"
        "Disallow: /private\nAllow: /private/public"
    )
    assert rules.allowed("https://28bit.ru/card")
    assert not rules.allowed("https://28bit.ru/private/x")
    assert rules.allowed("https://28bit.ru/private/public")


def test_equal_pattern_allow_and_encoded_unreserved():
    rules = RobotsRules("User-agent: *\nDisallow: /blocked\nAllow: /blocked\nDisallow: /%61pi/")
    assert rules.allowed("https://28bit.ru/blocked")
    assert not rules.allowed("https://28bit.ru/api/x")


@pytest.mark.parametrize(
    "text",
    [
        "<html>captcha access denied</html>",
        "captcha",
        "User-agent: *\nDisallow: /%ZZ",
        "User-agent: *\nUnknown: yes",
    ],
)
def test_invalid_robots_closed(text):
    with pytest.raises(AccessBlocked):
        RobotsRules(text)


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/card",
        "https://28bit.ru.evil/card",
        "https://28bit.ru/cart/",
        "https://28bit.ru/card?buy=1",
        "https://28bit.ru/%63art/",
        "https://28bit.ru@evil/card",
    ],
)
def test_invalid_capabilities_rejected_before_network(tmp_path, url):
    with pytest.raises(ValueError):
        CuratedReader(registry(listings=[{"url": url, "title": "untrusted"}]), tmp_path / "state")


def test_unlisted_url_zero_requests(tmp_path):
    reader = CuratedReader(
        registry(), tmp_path / "state", transport=lambda u: pytest.fail("no request")
    )
    with pytest.raises(AccessBlocked, match="not in reviewed"):
        reader.observe(GPU, candidate("https://28bit.ru/other/"), datetime.now(UTC))


@pytest.mark.parametrize("failure", ["HTTP 403", "HTTP 429", "timeout", "CAPTCHA"])
def test_persistent_source_stop_across_readers(tmp_path, failure):
    calls = []

    def denied(url):
        calls.append(url)
        raise AccessBlocked(failure)

    state = tmp_path / "stop.json"
    reader = CuratedReader(registry(), state, transport=denied, sleep=lambda _: None)
    with pytest.raises(AccessBlocked):
        reader.observe(GPU, candidate(URL), datetime.now(UTC))
    assert state.exists() and len(calls) == 1
    reader2 = CuratedReader(registry(), state, transport=lambda u: pytest.fail("no retry"))
    with pytest.raises(AccessBlocked, match="persistent"):
        reader2.observe(GPU, candidate(URL), datetime.now(UTC))


def test_real_rules_and_primary_e2e_metadata_roundtrip(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        if url.endswith("robots.txt"):
            return (
                b"User-agent: *\nDisallow: /*?*%5B%5D=*\nDisallow: /cart/\n"
                b"Disallow: /shop/captcha.php?rid*\nClean-param: utm_source\nSitemap: https://28bit.ru/map",
                {"content-type": "text/plain"},
            )
        return html().encode(), {"content-type": "text/html", "cache-control": "max-age=0"}

    reader = CuratedReader(registry(), tmp_path / "state", transport=fetch, sleep=lambda _: None)
    out = tmp_path / "report"
    data = run(GPU, out, envelopes=[], reader=reader)
    row = data["observations"][0]
    assert len(calls) == 2 and row["match"] == "excluded" and not row["eligible"]
    assert row["mpn"] == "NE75090019R5-GB2020G"
    assert row["price_rub"] is None and row["region"] is None and row["delivery_rub"] is None
    assert row["primary"]["final_url"] == URL
    assert (
        hashlib.sha256(row["primary"]["retained_content"].encode()).hexdigest()
        == row["primary"]["retained_sha256"]
    )
    assert verify(out)["status"] == "passed"


def test_store_sku_never_substitutes_mpn():
    text = html().replace('<meta itemprop="mpn" content="NE75090019R5-GB2020G">', "")
    result = observe(GPU, candidate(URL), text, {}, datetime.now(UTC))
    assert result.mpn is None
    assert result.primary["retained_content"].find("30845") > 0


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/card",
        "https://28bit.ru/private/",
        "https://28bit.ru/robots.txt?action=1",
        "https://127.0.0.1/",
    ],
)
def test_network_helper_itself_rejects_noncapability(monkeypatch, url):
    from pc_sourcing import curated_primary

    monkeypatch.setattr(curated_primary, "public_address", lambda h: pytest.fail("no DNS"))
    with pytest.raises(AccessBlocked, match="fixed reviewed"):
        curated_primary.fixed_get(url)


def test_declared_stock_is_not_confirmed_stock():
    result = observe(GPU, candidate(URL), html(), {}, datetime.now(UTC))
    assert result.stock == "unknown"
    assert [f.value for f in result.facts if f.field == "declared_stock"] == ["in_stock"]


def test_original_robots_denial_stops_before_card(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return b"<html>captcha access denied</html>", {"content-type": "text/html"}

    reader = CuratedReader(registry(), tmp_path / "stop", transport=fetch, sleep=lambda _: None)
    with pytest.raises(AccessBlocked):
        reader.observe(GPU, candidate(URL), datetime.now(UTC))
    assert len(calls) == 1 and calls[0].endswith("robots.txt")


def test_no_moscow_inference_from_page_header():
    result = observe(
        GPU, candidate(URL), "<div>Ваш город Москва?</div>" + html(), {}, datetime.now(UTC)
    )
    assert result.region is None and result.condition == "unknown" and result.seller_checked is None


def test_primary_retained_tamper_detected_without_rewriting_report(tmp_path):
    import json

    def fetch(url):
        return (
            b"User-agent: *\nDisallow: /cart/" if url.endswith("robots.txt") else html().encode(),
            {"content-type": "text/plain" if url.endswith("robots.txt") else "text/html"},
        )

    out = tmp_path / "tamper"
    reader = CuratedReader(registry(), tmp_path / "state", transport=fetch, sleep=lambda _: None)
    run(GPU, out, envelopes=[], reader=reader)
    original = (out / "result.json").read_bytes()
    record = json.loads(original)
    record["observations"][0]["primary"]["retained_content"] = "forged"
    (out / "result.json").write_text(json.dumps(record))
    with pytest.raises(ValueError, match="artifact changed"):
        verify(out)


def test_card_redirect_denied_by_network_helper(monkeypatch):
    import urllib.error

    from pc_sourcing import curated_primary

    monkeypatch.setattr(curated_primary, "public_address", lambda h: "8.8.8.8")
    calls = []

    class Redirect:
        def open(self, request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 302, "redirect", {}, None)

    monkeypatch.setattr(curated_primary.urllib.request, "build_opener", lambda *a: Redirect())
    with pytest.raises(AccessBlocked, match="HTTP 302"):
        curated_primary.fixed_get("https://28bit.ru/robots.txt")
    assert calls == ["https://28bit.ru/robots.txt"]


def test_path_glob_long_external_pattern_no_regex_backtracking():
    from pc_sourcing.curated_primary import path_matches

    assert not path_matches("/" + "*a" * 200 + "z", "/" + "a" * 250)
    assert path_matches("/api/*", "/api/test")


def test_multiple_product_metadata_not_promoted_to_displayed_price():
    result = observe(GPU, candidate(URL), html() + html(), {}, datetime.now(UTC))
    assert result.status == "unresolved"
    assert not [f for f in result.facts if f.field == "displayed_price_rub"]


def test_dns_precheck_is_runtime_failure_not_site_denial(tmp_path):
    import socket

    def unresolved(url):
        raise socket.gaierror(-3, "temporary resolver failure")

    state = tmp_path / "stop.json"
    reader = CuratedReader(registry(), state, transport=unresolved, sleep=lambda _: None)
    with pytest.raises(AccessBlocked, match="before source HTTP"):
        reader.observe(GPU, candidate(URL), datetime.now(UTC))
    assert not state.exists()
    assert len(list(tmp_path.glob("stop.json.dns-*.json"))) == 1


def test_legacy_dns_record_preserved_without_treating_it_as_site_ban(tmp_path):
    import json

    state = tmp_path / "stop.json"
    raw = json.dumps({"origin": "https://28bit.ru", "reason": "gaierror"})
    state.write_text(raw)
    reader = CuratedReader(
        registry(), state, transport=lambda u: pytest.fail("no implicit request")
    )
    reader.check_state()
    assert state.read_text() == raw


def test_primary_report_time_is_not_before_source_facts(tmp_path):
    def fetch(url):
        return (
            b"User-agent: *\nDisallow: /cart/" if url.endswith("robots.txt") else html().encode(),
            {"content-type": "text/plain" if url.endswith("robots.txt") else "text/html"},
        )

    reader = CuratedReader(registry(), tmp_path / "state", transport=fetch, sleep=lambda _: None)
    data = run(GPU, tmp_path / "timing", envelopes=[], reader=reader)
    as_of = datetime.fromisoformat(data["as_of"])
    assert all(
        datetime.fromisoformat(f["observed_at"]) <= as_of
        for o in data["observations"]
        for f in o["facts"]
    )


def test_reviewed_palit_title_mpn_preserves_suffix_and_ignores_numeric_store_id():
    text = html().replace('<meta itemprop="mpn" content="NE75090019R5-GB2020G">', "")
    text = text.replace("Palit RTX 5090 GAMEROCK", "Palit (NE75090019R5-GB2020G) RTX 5090 GAMEROCK")
    result = observe(GPU, candidate(URL), text, {}, datetime.now(UTC))
    assert result.mpn == "NE75090019R5-GB2020G" and result.match == "excluded"
    numeric = text.replace("NE75090019R5-GB2020G", "30845")
    assert observe(GPU, candidate(URL), numeric, {}, datetime.now(UTC)).mpn is None


def test_primary_mpn_declarations_conflict_unknown():
    text = html().replace(
        "Palit RTX 5090 GAMEROCK", "Palit (NE75090S19R5-GB2020G) RTX 5090 GAMEROCK"
    )
    result = observe(GPU, candidate(URL), text, {}, datetime.now(UTC))
    assert result.mpn is None and result.status == "unresolved"


def test_frozen_t009_scope_rejects_t010_snapshot(tmp_path):
    import importlib
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    historical = importlib.import_module("live_scope")
    checkout = tmp_path / "successor scope"
    subprocess.run(["git", "clone", "--shared", "--quiet", str(root), str(checkout)], check=True)
    with pytest.raises(ValueError, match="unowned changes"):
        historical.check(checkout)


def test_exact_ram_title_mpn_confirmed_without_merging_timing_variant():
    from pc_sourcing.live_models import Request

    target = "F5-6000J3036F48GX2-TZ5NR"
    request = Request(name="G.Skill 96 GB", mpn=target, category="ram")
    body = html().replace(
        "Palit RTX 5090 GAMEROCK", "Оперативная память 96 Gb G.Skill (" + target + ")"
    )
    body = body.replace('<meta itemprop="mpn" content="NE75090019R5-GB2020G">', "")
    exact = observe(request, candidate(URL), body, {}, datetime.now(UTC))
    assert exact.mpn == target and exact.match == "exact" and not exact.eligible
    analogue = observe(
        request, candidate(URL), body.replace("J3036", "J2836"), {}, datetime.now(UTC)
    )
    assert analogue.mpn != target and analogue.match != "exact"


def test_target_mpn_selects_reviewed_ram_seed(tmp_path):
    from pc_sourcing.live_models import Request

    target = "F5-6000J3036F48GX2-TZ5NR"
    ram_url = "https://28bit.ru/ram/"
    reader = CuratedReader(
        registry(
            listings=[
                {"url": URL, "title": "Palit"},
                {"url": ram_url, "title": "G.Skill", "requested_mpn": target},
            ]
        ),
        tmp_path / "state",
    )
    seeds = reader.seed_candidates(
        datetime.now(UTC), Request(name="G.Skill 96 GB", mpn=target, category="ram")
    )
    assert len(seeds) == 1 and seeds[0].url == ram_url


def test_managed_fixed_capability_records_unavailable_local_dns_without_claiming_public(
    monkeypatch,
):
    import socket

    from pc_sourcing import curated_primary

    def unavailable(host):
        raise socket.gaierror(-2, "local resolver unavailable")

    class Response:
        status = 200
        headers = {"Content-Type": "text/plain"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def geturl(self):
            return "https://28bit.ru/robots.txt"

    class Gateway:
        def open(self, request, timeout):
            assert request.full_url == "https://28bit.ru/robots.txt"
            return Response()

    monkeypatch.setattr(curated_primary, "public_address", unavailable)
    monkeypatch.setattr(curated_primary.urllib.request, "build_opener", lambda *a: Gateway())
    monkeypatch.setattr(curated_primary, "read_bounded", lambda r: b"User-agent: *")
    _, headers = curated_primary.fixed_get("https://28bit.ru/robots.txt")
    assert headers["x-primary-local-dns-status"] == "unknown_local_resolver_unavailable"


def test_known_nonpublic_dns_still_rejects_fixed_origin_before_gateway(monkeypatch):
    from pc_sourcing import curated_primary

    def private(host):
        raise AccessBlocked("non-public destination")

    monkeypatch.setattr(curated_primary, "public_address", private)
    monkeypatch.setattr(
        curated_primary.urllib.request, "build_opener", lambda *a: pytest.fail("no gateway call")
    )
    with pytest.raises(AccessBlocked, match="non-public"):
        curated_primary.fixed_get("https://28bit.ru/robots.txt")


def test_actual_denial_persists_even_with_preserved_legacy_dns_record(tmp_path):
    import json

    state = tmp_path / "stop.json"
    old = json.dumps({"origin": "https://28bit.ru", "reason": "gaierror"})
    state.write_text(old)
    calls = []

    def denied(url):
        calls.append(url)
        raise AccessBlocked("HTTP 403")

    reader = CuratedReader(registry(), state, transport=denied, sleep=lambda _: None)
    with pytest.raises(AccessBlocked):
        reader.observe(GPU, candidate(URL), datetime.now(UTC))
    assert state.read_text() == old
    assert state.with_name(state.name + ".denial.json").exists()
    second = CuratedReader(registry(), state, transport=lambda u: pytest.fail("no retry"))
    with pytest.raises(AccessBlocked, match="persistent denial"):
        second.observe(GPU, candidate(URL), datetime.now(UTC))
    assert len(calls) == 1
