"""Reviewed robots fixtures: no product request made to test policy admission."""

import pytest

from pc_sourcing.collection_profiles import REGARD_URL, regard_get, regard_rules
from pc_sourcing.live_transport import AccessBlocked


def test_saved_reviewed_robots_allows_known_canonical_ram_and_blocks_query():
    raw = b"User-agent: *\nDisallow: *?*\nDisallow: /profile*\nHost: https://www.regard.ru\nSitemap: https://www.regard.ru/sitemap.xml\n"
    rules = regard_rules(raw)
    assert rules.allowed(REGARD_URL)
    assert not rules.allowed(REGARD_URL + "?search=F5")
    assert not rules.allowed("https://www.regard.ru/profile")


@pytest.mark.parametrize(
    "url",
    [
        REGARD_URL + "?utm_source=x",
        "https://www.regard.ru/api/",
        "https://andpro.ru/upload/price/price.xlsx",
        "https://www.avito.ru/item",
        "https://api.tavily.com/search",
    ],
)
def test_unknown_url_or_forbidden_query_rejects_before_network(url):
    with pytest.raises(AccessBlocked, match="exact"):
        regard_get(url)
