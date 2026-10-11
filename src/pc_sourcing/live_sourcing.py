"""Request → real bounded search → permitted card checks → portable evidence report."""

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from pc_sourcing.live_models import (
    Candidate,
    Fact,
    Observation,
    Request,
    SourcePolicy,
)
from pc_sourcing.live_transport import AccessBlocked, Reader, keyless_search

ROOT = Path(__file__).resolve().parents[2]


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)


def digest(value):
    return hashlib.sha256(value).hexdigest()


class CardHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks, self.visible, self.script = [], [], None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.hidden += 1
            if dict(attrs).get("type", "").lower() == "application/ld+json":
                self.script = []
        elif tag == "style":
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag == "script":
            if self.script is not None:
                self.blocks.append("".join(self.script))
            self.script = None
            self.hidden = max(0, self.hidden - 1)
        elif tag == "style":
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        elif not self.hidden:
            self.visible.append(data)


def products(value):
    if isinstance(value, list):
        for row in value:
            yield from products(row)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if types == "Product" or isinstance(types, list) and "Product" in types:
            yield value
        if "@graph" in value:
            yield from products(value["@graph"])


def identity(request, title, mpn):
    """Conservative matching of primary identities, never inferred from a snippet."""
    text = (title or "").upper()
    if request.category == "gpu":
        if (
            any(x in text for x in ("5090D", "WATERBLOCK", "ВОДОБЛОК"))
            or "MSI" not in text
            or "5090" not in text
            or "SUPRIM LIQUID" not in text
        ):
            return "excluded", ("Не подтверждена полная заводская MSI RTX 5090 SUPRIM LIQUID",)
    if request.category == "gpu" and " SOC" in text and " OC" in request.name.upper():
        return "analogue", ("SOC вместо OC; отдельный вариант, не точный SKU",)
    if request.mpn:
        if mpn == request.mpn:
            return "exact", ()
        if not mpn:
            return "unresolved", ("Артикул производителя отсутствует",)
        if request.category == "gpu":
            return "analogue", (f"MPN {mpn} вместо {request.mpn}; OC/SOC проверить отдельно",)
        return "excluded", (f"MPN {mpn} вместо {request.mpn}; аналог не обоснован",)
    if title and " ".join(title.casefold().split()) == " ".join(request.name.casefold().split()):
        return "exact", ()
    return "unresolved", ("Полное имя/характеристики не подтверждены",)


def parse_card(request, candidate, html, now):
    document = CardHTML()
    document.feed(html)
    found = []
    try:
        for block in document.blocks:
            found.extend(products(json.loads(block)))
    except (ValueError, RecursionError):
        return Observation(candidate=candidate, status="unresolved", reason="Malformed JSON-LD")
    if len(found) != 1:
        return Observation(
            candidate=candidate,
            status="unresolved",
            reason="Expected exactly one primary Product; category/variants ambiguous",
        )
    product = found[0]
    title = product.get("name") if isinstance(product.get("name"), str) else None
    mpn = product.get("mpn") if isinstance(product.get("mpn"), str) else None
    match, differences = identity(request, title, mpn)
    facts = []
    page_hash = digest(html.encode())

    def add(field, value, selector):
        facts.append(
            Fact(
                field=field,
                value=value,
                url=candidate.url,
                observed_at=now,
                origin="store_card",
                selector=selector,
                content_sha256=page_hash,
            )
        )

    if title:
        add("title", title, "Product.name")
    if mpn:
        add("mpn", mpn, "Product.mpn")
    offers = product.get("offers", [])
    offers = offers if isinstance(offers, list) else [offers]
    price, stock, condition = None, "unknown", "unknown"
    reasons = []
    if len(offers) != 1 or not isinstance(offers[0], dict) or offers[0].get("@type") != "Offer":
        reasons.append("Single unconditional Offer not confirmed")
    else:
        offer = offers[0]
        value = offer.get("price")
        # No floats, ranges, first payments, zero, discount or foreign conversion.
        if (
            offer.get("priceCurrency") == "RUB"
            and not isinstance(value, bool)
            and str(value).isdigit()
            and len(str(value)) <= 10
            and 0 < int(value) < 10**10
            and not offer.get("priceSpecification")
        ):
            price = int(value)
        availability = offer.get("availability")
        stock = {
            "https://schema.org/InStock": "in_stock",
            "https://schema.org/PreOrder": "preorder",
            "https://schema.org/OutOfStock": "unavailable",
        }.get(availability, "unknown")
        condition = {
            "https://schema.org/NewCondition": "new",
            "https://schema.org/UsedCondition": "used",
        }.get(offer.get("itemCondition"), "unknown")
        visible = " ".join(document.visible).casefold()
        if stock == "in_stock" and any(
            x in visible
            for x in ("нет в наличии", "под заказ", "предзаказ", "out of stock", "preorder")
        ):
            stock, price = "unknown", None
            reasons.append("Visible text contradicts JSON-LD; price/stock unresolved")
        visible_prices = {
            int(re.sub(r"[ \u00a0\u202f]", "", m))
            for m in re.findall(
                r"(?<![\d.,])([\d][\d \u00a0\u202f]*)\s*(?:₽|руб\.?|RUB)",
                " ".join(document.visible),
                flags=re.IGNORECASE,
            )
        }
        if price is not None and any(p != price for p in visible_prices):
            price = None
            reasons.append("Visible prices differ from JSON-LD; price unresolved")
        if any(
            x in visible
            for x in (
                "первый платёж",
                "первый платеж",
                "кешбэк",
                "cashback",
                "цена по карте",
                "в месяц",
                "/мес",
            )
        ):
            price = None
            reasons.append("Conditional price context requires source-specific parser")
        if price is not None:
            add("price_rub", price, "Product.offers.price + priceCurrency=RUB")
        if stock != "unknown":
            add("stock", stock, "Product.offers.availability")
        if condition != "unknown":
            add("condition", condition, "Product.offers.itemCondition")
    reasons.append("Moscow fulfillment, seller review, quantity and full costs not confirmed")
    return Observation(
        candidate=candidate,
        status="observed",
        reason="; ".join(reasons),
        title=title,
        mpn=mpn,
        price_rub=price,
        stock=stock,
        condition=condition,
        match=match,
        differences=differences,
        facts=tuple(facts),
    )


def candidates(envelopes, queries, now):
    rows, rejects, seen = [], [], {}
    for envelope in envelopes:
        query, stamp, response = (envelope.get(k) for k in ("query", "observed_at", "response"))
        if (
            query not in queries
            or not isinstance(response, dict)
            or str(response.get("query", "")).replace('"', "") != query.replace('"', "")
        ):
            raise ValueError("search envelope query mismatch")
        observed = datetime.fromisoformat(stamp)
        if observed.tzinfo is None or not 0 <= (now - observed).total_seconds() <= 3600:
            raise ValueError("search response missing offset, stale or future")
        if not isinstance(response.get("results"), list) or len(response["results"]) > 20:
            raise ValueError("invalid search results/budget")
        sha = digest(dumps(response).encode())
        for index, row in enumerate(response["results"]):
            try:
                c = Candidate(
                    url=row["url"],
                    title=row["title"],
                    queries=(query,),
                    observed_at=observed,
                    response_sha256=sha,
                )
                if c.url in seen:
                    previous = seen[c.url]
                    # Preserve every response provenance independently in search.json.
                    c = previous.model_copy(
                        update={"queries": tuple(dict.fromkeys((*previous.queries, query)))}
                    )
                    rows[rows.index(previous)] = c
                else:
                    rows.append(c)
                seen[c.url] = c
            except (ValueError, KeyError, TypeError) as exc:
                rejects.append({"query": query, "index": index, "reason": type(exc).__name__})
    return rows, rejects


def run(
    request, output, *, envelopes=None, policies=(), now=None, search=keyless_search, reader=None
):
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("run timestamp requires UTC offset")
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("run directory exists; use a new immutable run path")
    output.mkdir(parents=True)
    events = []
    queries = request.queries()
    if envelopes is None:
        envelopes = []
        for query in queries:
            try:
                response = search(query)
                envelopes.append(
                    {
                        "query": query,
                        "observed_at": datetime.now(UTC).isoformat(),
                        "response": response,
                    }
                )
            except AccessBlocked as exc:
                events.append({"stage": "search", "status": "blocked", "reason": str(exc)})
                break
        # Clock is read after the response, not before it.
        now = datetime.now(UTC)
    reader = reader or Reader(policies)
    rows, rejects = candidates(envelopes, queries, now)
    observations = []
    for row in rows:
        try:
            html = reader.read(row.url, now)
            result = parse_card(request, row, html, datetime.now(UTC))
        except AccessBlocked as exc:
            host = urlsplit_host(row.url)
            avito = host == "avito.ru" or host.endswith(".avito.ru")
            result = Observation(
                candidate=row,
                status="blocked",
                reason=str(exc),
                label="требует ручной проверки"
                if avito
                else "кандидат: первичный источник не проверен",
            )
        observations.append(result.model_dump(mode="json"))
    data = {
        "schema_version": "live/1.0.0",
        "request": request.model_dump(),
        "as_of": now.isoformat(),
        "observations": observations,
        "rejections": rejects,
        "events": events,
        "queries_planned": queries,
        "queries_completed": [e["query"] for e in envelopes],
        "independent_sellers_confirmed": 0,
        "full_product_dod": "not_completed",
        "stop_reason": "bounded query/card budget; unconfirmed sources remain blocked",
    }
    (output / "result.json").write_text(dumps(data) + "\n")
    # Strip snippets and raw content: they never establish facts and are not retained.
    search_receipt = [
        {
            "query": e["query"],
            "observed_at": e["observed_at"],
            "response_sha256": digest(dumps(e["response"]).encode()),
            "results": [
                {"url": r.get("url"), "title": r.get("title")} for r in e["response"]["results"]
            ],
        }
        for e in envelopes
    ]
    (output / "search.json").write_text(dumps(search_receipt) + "\n")
    with sqlite3.connect(output / "observations.sqlite") as con:
        con.execute("CREATE TABLE runs (result TEXT NOT NULL)")
        con.execute("INSERT INTO runs VALUES (?)", (dumps(data),))
        con.execute("CREATE TABLE observations (url TEXT PRIMARY KEY, data TEXT NOT NULL)")
        con.executemany(
            "INSERT INTO observations VALUES (?, ?)",
            [(o["candidate"]["url"], dumps(o)) for o in observations],
        )
    with (output / "offers.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["url", "title", "mpn", "price_rub", "stock", "match", "label", "reason"])
        for o in observations:
            fields = [
                o["candidate"]["url"],
                o["title"] or o["candidate"]["title"],
                o["mpn"],
                o["price_rub"],
                o["stock"],
                o["match"],
                o["label"],
                o["reason"],
            ]
            writer.writerow(
                [
                    "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v
                    for v in fields
                ]
            )
    lines = [
        "# Поиск комплектующих: Москва",
        "",
        escape(request.name),
        f"Время UTC: {now.isoformat()}",
        "",
        "Независимых подтверждённых продавцов: 0. Покрытие слабое.",
        "Полный DoD не завершён. Проверенных предложений для покупки нет.",
        "Цена товара при наличии не является полной стоимостью получения.",
    ]
    for o in observations:
        lines.extend(["", "## Кандидат", "<pre>" + escape(dumps(o)) + "</pre>"])
    lines.extend(["", "## Пробелы поиска", "<pre>" + escape(dumps(events)) + "</pre>"])
    (output / "report.md").write_text("\n\n".join(lines) + "\n")
    files = {p.name: digest(p.read_bytes()) for p in output.iterdir() if p.is_file()}
    spec = ROOT / "specs/004-live-sourcing/spec.md"
    (output / "manifest.json").write_text(
        dumps(
            {
                "files": files,
                "status": "completed_with_gaps",
                "spec_sha256": digest(spec.read_bytes()),
                "code_sha256": {
                    p.name: digest(p.read_bytes())
                    for p in (ROOT / "src/pc_sourcing").glob("live_*.py")
                },
                "runtime": sys.version,
                "limitations": [
                    "No production/deployment/Avito access claim",
                    "No confirmed Moscow fulfillment or seller review in generic JSON-LD adapter",
                ],
            }
        )
        + "\n"
    )
    return data


def urlsplit_host(url):
    from urllib.parse import urlsplit

    return urlsplit(url).hostname


def verify(output):
    output = Path(output).resolve()
    manifest = json.loads((output / "manifest.json").read_text())
    expected = {"result.json", "search.json", "observations.sqlite", "offers.csv", "report.md"}
    if set(manifest["files"]) != expected:
        raise ValueError("unexpected manifest files")
    for name, sha in manifest["files"].items():
        path = output / name
        if path.is_symlink() or digest(path.read_bytes()) != sha:
            raise ValueError("artifact changed: " + name)
    data = json.loads((output / "result.json").read_text())
    with sqlite3.connect(f"file:{output / 'observations.sqlite'}?mode=ro", uri=True) as con:
        if json.loads(con.execute("SELECT result FROM runs").fetchone()[0]) != data:
            raise ValueError("SQLite/result mismatch")
    return {"status": "passed", "files": len(expected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "run", "verify"])
    parser.add_argument("--request", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--search-responses", type=Path)
    parser.add_argument("--registry", type=Path, default=ROOT / "sources/live-registry.json")
    args = parser.parse_args()
    try:
        if args.action == "verify":
            result = verify(args.out)
        else:
            request = Request.model_validate_json(args.request.read_bytes())
            if args.action == "plan":
                result = {"queries": request.queries(), "region": request.region}
            else:
                policies = [
                    SourcePolicy.model_validate(p) for p in json.loads(args.registry.read_text())
                ]
                envelopes = (
                    json.loads(args.search_responses.read_text()) if args.search_responses else None
                )
                data = run(request, args.out, envelopes=envelopes, policies=policies)
                result = {
                    "status": "completed_with_gaps",
                    "candidates": len(data["observations"]),
                    "search_events": data["events"],
                    "out": str(args.out.resolve()),
                }
        print(dumps(result))
    except (ValueError, OSError, TypeError) as exc:
        print(dumps({"status": "failed", "reason": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
