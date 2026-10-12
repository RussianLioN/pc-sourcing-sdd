"""Request → real bounded search → permitted card checks → portable evidence report."""

import argparse
import csv
import fcntl
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


def safe_search_response(value):
    """Retain a reproducible bounded response while removing credentials/full pages."""
    sensitive = {
        "api_key",
        "authorization",
        "cookie",
        "cookies",
        "password",
        "secret",
        "access_token",
        "refresh_token",
        "download_url",
        "raw_content",
    }
    if isinstance(value, dict):
        return {
            k: "[omitted]" if k.lower() in sensitive else safe_search_response(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [safe_search_response(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"(?:sk-proj-|ghp_|tvly-)[A-Za-z0-9_-]{12,}", "[redacted]", value)
        value = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._-]+", "Bearer [redacted]", value)
        value = re.sub(
            r"(?i)([?&](?:token|api_key|access_token|signature|sig|key)=)[^&\s]*",
            r"\1[redacted]",
            value,
        )
        return value
    return value


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
    from pc_sourcing.identity_attributes import conflicts

    tokens = set(re.findall(r"[A-Z0-9]+", text))
    if not text.strip():
        return "unresolved", ("Primary model/title отсутствует",)
    if request.category == "gpu":
        if (
            "AIR" in tokens
            or "WATERBLOCK" in tokens
            or "ВОДОБЛОК" in text
            or re.search(r"\bWATER[\s_-]*BLOCK\b", text)
            or any(t.startswith("5090") and t != "5090" for t in tokens)
            or tokens.intersection({"ASUS", "PALIT", "GIGABYTE", "ZOTAC"})
        ):
            return "excluded", ("Не полная заводская MSI RTX 5090 SUPRIM LIQUID",)
        if re.search(r"\bRTX\s+(?!5090\b)[0-9]+", text):
            return "excluded", ("Другая модель GPU",)
    attribute_conflicts = conflicts(request, [title])
    if attribute_conflicts:
        # Explicit wrong RAM total/DDR with a different code is a hard exclusion;
        # copied matching code or unapproved substitutions remain unresolved.
        hard_wrong = (
            request.category == "ram"
            and mpn != request.mpn
            and set(attribute_conflicts) & {"capacity", "memory_type"}
        )
        return ("excluded" if hard_wrong else "unresolved"), (
            "Conflicting primary attributes: " + ", ".join(attribute_conflicts),
        )

    if request.category == "gpu":
        if not {"MSI", "RTX", "5090", "SUPRIM", "LIQUID"} <= tokens:
            return "unresolved", ("Заводской liquid вариант/полная идентичность не подтверждены",)
        requested = set(re.findall(r"[A-Z0-9]+", request.name.upper()))
        if {"OC", "SOC"} <= tokens:
            return "unresolved", ("Конфликт вариантов OC/SOC",)
        if "SOC" in tokens and mpn == "G5090-32SLC":
            return "unresolved", ("SOC title конфликтует с OC MPN",)
        if ("SOC" in tokens and "OC" in requested) or ("OC" in tokens and "SOC" in requested):
            if request.mpn and mpn == request.mpn:
                return "unresolved", ("Title variant конфликтует с заданным MPN",)
            return "analogue", ("Другой вариант OC/SOC; не точный SKU",)
        if ("OC" in requested or "SOC" in requested) and not {"OC", "SOC"} & tokens:
            return "unresolved", ("Вариант OC/SOC не подтверждён",)
    if request.category == "ram" and re.search(r"KINGSTON|ОДИН МОДУЛЬ", text):
        return ("unresolved" if mpn == request.mpn else "excluded"), ("RAM model/kit not agreed",)
    if request.category == "mouse":
        wanted = request.name.upper()
        if "SUPERSTRIKE" in wanted and ("SUPERLIGHT" in tokens or "WIRED" in tokens):
            return ("unresolved" if mpn == request.mpn else "excluded"), (
                "Mouse model/variant conflicts with request",
            )
        if "LOGITECH" in wanted and "LOGITECH" not in tokens:
            return ("unresolved" if mpn == request.mpn else "excluded"), (
                "Mouse manufacturer not agreed",
            )
        required = set(re.findall(r"[A-Z0-9]+", wanted))
        if not required <= tokens:
            return "unresolved", ("Full requested mouse model not confirmed",)
    if request.mpn:
        if mpn == request.mpn:
            return "exact", ()
        if not mpn:
            return "unresolved", ("Артикул производителя отсутствует",)
        return "unresolved", (
            f"MPN {mpn} вместо {request.mpn}; compatibility/analogue not confirmed",
        )
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
    from pc_sourcing.identity_attributes import conflicts

    attribute_conflicts = conflicts(
        request, [title, product.get("description"), " ".join(document.visible)], structured=product
    )
    if attribute_conflicts and match != "excluded":
        match, differences = (
            "unresolved",
            ("Conflicting primary attributes: " + ", ".join(attribute_conflicts),),
        )
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
    invalid_field = False
    if len(offers) != 1 or not isinstance(offers[0], dict) or offers[0].get("@type") != "Offer":
        reasons.append("Single unconditional Offer not confirmed")
    else:
        offer = offers[0]
        value = offer.get("price")
        # No floats, ranges, first payments, zero, discount or foreign conversion.
        if (
            offer.get("priceCurrency") == "RUB"
            and type(value) in (int, str)
            and re.fullmatch(r"[0-9]{1,10}", str(value)) is not None
            and 0 < int(value) < 10**10
            and not offer.get("priceSpecification")
        ):
            price = int(value)
        if value is not None and (
            type(value) not in (int, str) or re.fullmatch(r"[0-9]{1,10}", str(value)) is None
        ):
            invalid_field = True
            reasons.append("Malformed or unsupported price field")
        availability = offer.get("availability")
        if any(
            offer.get(k) is not None and not isinstance(offer.get(k), str)
            for k in ("availability", "itemCondition", "priceCurrency")
        ):
            invalid_field = True
            reasons.append("Malformed stock/condition/currency field")
        stock = (
            {
                "https://schema.org/InStock": "in_stock",
                "https://schema.org/PreOrder": "preorder",
                "https://schema.org/OutOfStock": "unavailable",
            }.get(availability, "unknown")
            if isinstance(availability, str)
            else "unknown"
        )
        condition = (
            {
                "https://schema.org/NewCondition": "new",
                "https://schema.org/UsedCondition": "used",
            }.get(offer.get("itemCondition"), "unknown")
            if isinstance(offer.get("itemCondition"), str)
            else "unknown"
        )
        visible = " ".join(document.visible).casefold()
        if condition == "new" and re.search(
            r"open[ -]?box|упаковк[а-я]* вскрыт|распакован|"
            r"refurb|восстановлен|б/у|\bused\b|витрин",
            visible,
        ):
            condition = "unknown"
            reasons.append("Visible condition contradicts NewCondition; condition unresolved")
        if stock == "in_stock" and any(
            x in visible
            for x in ("нет в наличии", "под заказ", "предзаказ", "out of stock", "preorder")
        ):
            stock, price = "unknown", None
            reasons.append("Visible text contradicts JSON-LD; price/stock unresolved")
        visible_prices = set()
        invalid_visible_price = False
        for raw_price in re.findall(
            r"(?<![0-9.,])([0-9][0-9 \u00a0\u202f]*)\s*(?:₽|руб\.?|RUB)",
            " ".join(document.visible),
            flags=re.IGNORECASE,
        ):
            digits = re.sub(r"[ \u00a0\u202f]", "", raw_price)
            if not re.fullmatch(r"[0-9]{1,10}", digits):
                invalid_visible_price = True
            else:
                visible_prices.add(int(digits))
        if invalid_visible_price:
            invalid_field = True
            price = None
            reasons.append("Visible price exceeds supported bounds; price unresolved")
        if price is not None and any(p != price for p in visible_prices):
            price = None
            reasons.append("Visible prices differ from JSON-LD; price unresolved")
        if any(
            x in visible
            for x in (
                "залог",
                "задаток",
                "deposit",
                "плата за брон",
                "аванс",
                "предоплат",
                "скидк",
                "наличными",
                "при оплате",
                "промокод",
                "подписк",
                "бонус",
                "по карте",
                "discount",
                "cash only",
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
        status="unresolved" if invalid_field else "observed",
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
    actual_search = envelopes is None
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
    bounded_envelopes = []
    for envelope in envelopes:
        cleaned = {**envelope, "response": safe_search_response(envelope["response"])}
        if len(dumps(cleaned).encode()) > 1_000_000:
            raise ValueError("search receipt exceeds retention byte budget")
        bounded_envelopes.append(cleaned)
    envelopes = bounded_envelopes
    reader = reader or Reader(policies)
    rows, rejects = candidates(envelopes, queries, now)
    registry_receipt = None
    if hasattr(reader, "seed_candidates"):
        seeded = reader.seed_candidates(now, request)
        known = {r.url for r in rows}
        rows.extend(r for r in seeded if r.url not in known)
        registry_receipt = {
            "origin": "curated_source_registry",
            "response": reader.registry,
            "response_sha256": reader.registry_hash,
        }
    observations = []
    for row in rows:
        try:
            if hasattr(reader, "observe"):
                result = reader.observe(request, row, now)
            else:
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
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            result = Observation(
                candidate=row,
                status="unresolved",
                reason=f"Malformed primary card: {type(exc).__name__}",
            )
        observations.append(result.model_dump(mode="json"))
    if hasattr(reader, "observe"):
        now = datetime.now(UTC)  # collection end includes actual primary observation times
    data = {
        "schema_version": "live/1.0.0",
        "request": request.model_dump(),
        "as_of": now.isoformat(),
        "observations": observations,
        "rejections": rejects,
        "events": events,
        "search_provenance": "live_keyless_https"
        if actual_search
        else "imported_response_unverified",
        "queries_planned": queries,
        "queries_completed": [e["query"] for e in envelopes],
        "independent_sellers_confirmed": 0,
        "full_product_dod": "not_completed",
        "stop_reason": "bounded query/card budget; unconfirmed sources remain blocked",
    }
    (output / "result.json").write_text(dumps(data) + "\n")
    # Hash the exact retained sanitized response; this is integrity, not a server signature.
    search_receipt = [
        {
            "query": e["query"],
            "observed_at": e["observed_at"],
            "response_sha256": digest(dumps(e["response"]).encode()),
            "hash_scheme": "sha256/canonical-json-sanitized-v1",
            "response": e["response"],
            "origin": "live_keyless_https" if actual_search else "imported_response_unverified",
            "endpoint": "https://api.tavily.com/search" if actual_search else None,
            "access_mode": "keyless" if actual_search else None,
            "redaction": "credentials/full page content omitted; snippets are candidates only",
        }
        for e in envelopes
    ]
    if registry_receipt:
        search_receipt.append(registry_receipt)
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
    spec = ROOT / (
        "specs/005-primary-verification/spec.md"
        if registry_receipt
        else "specs/004-live-sourcing/spec.md"
    )
    (output / "manifest.json").write_text(
        dumps(
            {
                "files": files,
                "status": "completed_with_gaps",
                "spec_sha256": digest(spec.read_bytes()),
                "code_sha256": {
                    p.name: digest(p.read_bytes()) for p in (ROOT / "src/pc_sourcing").glob("*.py")
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
    receipts = json.loads((output / "search.json").read_text())
    for receipt in receipts:
        if digest(dumps(receipt["response"]).encode()) != receipt["response_sha256"]:
            raise ValueError("search response digest mismatch")
    for o in data["observations"]:
        primary = o.get("primary")
        if primary and digest(primary["retained_content"].encode()) != primary["retained_sha256"]:
            raise ValueError("primary retained content digest mismatch")
    retained_hashes = {r["response_sha256"] for r in receipts}
    if any(o["candidate"]["response_sha256"] not in retained_hashes for o in data["observations"]):
        raise ValueError("candidate response evidence missing")
    with sqlite3.connect(f"file:{output / 'observations.sqlite'}?mode=ro", uri=True) as con:
        if json.loads(con.execute("SELECT result FROM runs").fetchone()[0]) != data:
            raise ValueError("SQLite/result mismatch")
    return {"status": "passed", "files": len(expected)}


class PersistentSearch:
    """Fixed keyless endpoint stop shared across CLI runs; never auto-reset a denial."""

    def __init__(self, state, search=keyless_search):
        self.state = Path(state)
        if (
            not self.state.is_absolute()
            or self.state.is_symlink()
            or self.state.parent.is_symlink()
        ):
            raise ValueError("search stop state requires absolute non-symlink path")
        self.search = search

    def __call__(self, query):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        lockpath = self.state.with_name(self.state.name + ".lock")
        if lockpath.is_symlink():
            raise AccessBlocked("search stop lock symlink")
        with lockpath.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.state.exists() or self.state.is_symlink():
                raise AccessBlocked("persisted keyless search stop; no retry or automatic reset")
            try:
                return self.search(query)
            except AccessBlocked as exc:
                with self.state.open("x") as stream:
                    stream.write(
                        dumps(
                            {
                                "endpoint": "https://api.tavily.com/search",
                                "reason": str(exc),
                                "at": datetime.now(UTC).isoformat(),
                            }
                        )
                        + "\n"
                    )
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "run", "verify"])
    parser.add_argument("--request", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--search-responses", type=Path)
    parser.add_argument("--primary-registry", type=Path)
    parser.add_argument("--source-state", type=Path)
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
                primary_reader = None
                if args.primary_registry:
                    from pc_sourcing.curated_primary import CuratedReader

                    if not args.source_state:
                        raise ValueError("curated primary requires explicit absolute source state")
                    primary_reader = CuratedReader(
                        json.loads(args.primary_registry.read_text()), args.source_state
                    )
                data = run(
                    request,
                    args.out,
                    envelopes=envelopes,
                    policies=policies,
                    reader=primary_reader,
                    search=PersistentSearch(ROOT / "artifacts/source-state/tavily-stop.json"),
                )
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
