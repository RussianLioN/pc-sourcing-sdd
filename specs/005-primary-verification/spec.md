# T010 — bounded curated primary verification 1.0.0

Authority: coordinator instruction to continue the product after independent
engineering PASS of candidate milestone 130d67acd07b68a942dd62daf9127723556916e3.
This is prospective primary transport/verification, not production acceptance.
Original product DoD, v1 contracts/goldens, T008/T009 specs and receipts are immutable.

## Scope and trust boundary

One reviewed store origin initially: https://28bit.ru; exact approved listing URLs,
robots URL and policy URLs in coordinator-owned registry. Ordinary bounded public
buyer research/minimal factual evidence, no site-wide crawl, accounts or actions.
Published privacy/payment policy and original robots reviewed; no prior denial for
selected path. No explicit broad redistribution/automation license is claimed.
Avito/NIX/prior source denials are not retried via this route.

The existing managed gateway works for fixed public source reads. Our T009 arbitrary
proxy URL prohibition is an architectural constraint, not a missing user permission
or blanket runtime denial. T010 adds a separate trusted-origin capability: fixed
allowlisted origin, exact reviewed paths, DNS public precheck, verified TLS through
existing gateway, no redirect, no credentials/cookies, GET only. User/search content
cannot add origins/paths or action parameters. Proxy's actual destination IP is
unknown: local DNS is not a binding proof; no public-IP-only claim for this route.
Pinned-IP direct transport remains unchanged. This prospective extension preserves
SSRF checks while narrowing managed requests to explicit trusted source capabilities.

Tavily keyless /extract was actually tested on source robots and returned 200, but
changed machine syntax (wildcards/escaping). It is unsuitable for robots byte truth.
Its documented response does not establish HTTP redirect chain/final URL or source
cache age. It is not the primary verified transport in this iteration.

| ID | Requirement | Acceptance |
|---|---|---|
| PRIMARY-01 | only exact reviewed public HTTPS origin/URLs; no user additions, IP/userinfo/query/actions/redirects | capability negatives; origin spoof; unlisted URL zero requests |
| PRIMARY-02 | original robots bytes, MIME/status/body denial checks; source-wide persistent stop for 403/429/CAPTCHA/timeout; no channel fallback | robots negative corpus; ledger across readers |
| PRIMARY-03 | RFC9309 wildcard/anchor/longest precedence for bounded patterns; unsupported syntax fails closed; selected agents explicit | real 28BIT rules and wildcard/precedence/encoding negatives |
| PRIMARY-04 | retain bounded primary product JSON-LD/selected visible facts with original URL, final URL, UTC, exact retained hash and selectors; no full page/session secrets | reproducible fragment hash, transfer; evidence field ownership |
| PRIMARY-05 | distinguish source body hash from retained fragment hash; gateway IP/freshness gaps explicitly unknown; metadata Date/Age/Cache-Control | provenance tests and actual smoke |
| PRIMARY-06 | source-specific product scope; MPN vs store SKU; single model/offer; price/stock conflicts unresolved; RUB is item price, unknown delivery not 0 | conditional/conflict/category/recommendation regressions |
| PRIMARY-07 | manufacturer/5090/factory liquid hard rule; actual Palit 5090 primary must excluded, never analogue/verified; Moscow heading isn't confirmed fulfillment | actual negative live e2e + exact identity tests |
| PRIMARY-08 | existing reports use same observation, real primary excerpt/hash persisted; persistent denial state not silently reset; fresh dirs | SQLite/report equality and rerun/ledger tests |
| PRIMARY-09 | exact SHA full suite, new scope, secret scan, actual bounded primary smoke, independent review | fresh receipts; no candidate milestone/product readiness confusion |

Read-only preflight is evidence discovery, not acceptance of implementation.
No verified purchase offer may be emitted until all current product gates are
confirmed. This iteration deliberately retains eligible=False when fulfillment,
condition, seller review, quantity or total costs are unknown.
