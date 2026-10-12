"""One canonical dataset → SQLite/JSON/CSV/XLSX/Markdown, no extra dependency."""

import csv
import hashlib
import io
import json
import os
import sqlite3
import uuid
import zipfile
from html import escape
from xml.etree import ElementTree as ET

from pc_sourcing.durable_jobs import (
    absolute,
    encoded,
    fsync_directory,
    publish_directory,
    write_file,
)
from pc_sourcing.normalized_offers import canonical, compare

COLUMNS = [
    "offer_id",
    "source",
    "url",
    "model",
    "mpn",
    "requested_quantity",
    "available_quantity",
    "condition",
    "stock",
    "moscow_fulfillment",
    "warranty",
    "seller",
    "seller_entity",
    "identity",
    "differences",
    "item_subtotal_rub",
    "known_cost_rub",
    "full_total_rub",
    "conditional_prices",
    "payment_routes",
    "label",
    "synthetic",
    "observed_at",
    "gaps",
    "canonical_row",
]
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def literal(value):
    value = "" if value is None else str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def flat(row):
    o, d = row["offer"], row["decision"]
    values = [
        o["id"],
        o["source"],
        o["url"],
        o["title"],
        o["mpn"],
        o["request"]["quantity"],
        o["available_quantity"],
        o["condition"],
        o["stock"],
        canonical(o["fulfillment"]),
        canonical(o["warranty"]),
        o["seller_name"],
        d["confirmed_seller_key"],
        d["match"],
        canonical(d["differences"]),
        d["item_subtotal_rub"],
        d["known_cost_rub"],
        d["full_total_rub"],
        canonical(o["conditional_prices"]),
        canonical(d["payment"]["passed_routes"]),
        d["label"],
        str(o["synthetic"]).lower(),
        o["observed_at"],
        canonical(d["gaps"]),
        canonical(row),
    ]
    return [literal(v) for v in values]


def validate_xml_text(rows):
    for values in [COLUMNS] + rows:
        for column, value in zip(COLUMNS, values, strict=True):
            for char in value:
                code = ord(char)
                if not (
                    code in {9, 10, 13}
                    or 0x20 <= code <= 0xD7FF
                    or 0xE000 <= code <= 0xFFFD
                    or 0x10000 <= code <= 0x10FFFF
                ):
                    raise ValueError(
                        f"XML 1.0 cannot represent U+{code:04X} in {column}; original input retained"
                    )


def preflight_export(offers, as_of):
    dataset = compare(offers, as_of)
    validate_xml_text([flat(r) for r in dataset["rows"]])
    return dataset


def sheet_xml(rows):
    validate_xml_text(rows)
    root = ET.Element("{" + NS + "}worksheet")
    data = ET.SubElement(root, "{" + NS + "}sheetData")
    for index, values in enumerate([COLUMNS] + rows, 1):
        r = ET.SubElement(data, "{" + NS + "}row", r=str(index))
        for value in values:
            cell = ET.SubElement(r, "{" + NS + "}c", t="inlineStr")
            s = ET.SubElement(cell, "{" + NS + "}is")
            text = ET.SubElement(
                s, "{" + NS + "}t", {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}
            )
            text.text = value
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).replace(b"\r", b"&#13;")


def xlsx_bytes(rows):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            """<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>""",
        )
        z.writestr(
            "_rels/.rels",
            """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>""",
        )
        z.writestr(
            "xl/workbook.xml",
            """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Offers" sheetId="1" r:id="rId1"/></sheets></workbook>""",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>""",
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml(rows))
    return out.getvalue()


def markdown(dataset):
    lines = [
        "# Проверяемые предложения",
        "",
        f"Срез: {dataset['as_of']}. Независимых продавцов подтверждено: {dataset['independent_sellers_confirmed']}.",
        "",
        "Данные synthetic явно помечены. Полный product DoD не завершён.",
        "",
        "| Модель / источник | Артикул | Количество | Состояние / наличие | Полная цена RUB | Решение |",
        "|---|---|---|---|---|---|",
    ]

    def text(v):
        return (
            escape(
                canonical(v)
                if isinstance(v, (dict, list))
                else str(v)
                if v is not None
                else "unknown"
            )
            .replace("|", "\\|")
            .replace("\n", " ")
        )

    for row in dataset["rows"]:
        o, d = row["offer"], row["decision"]
        lines.append(
            "| "
            + " | ".join(
                [
                    text(o["title"]) + " — " + text(o["url"]),
                    text(o["mpn"]),
                    text(o["available_quantity"]) + "/" + text(o["request"]["quantity"]),
                    text(o["condition"]) + " / " + text(o["stock"]),
                    text(d["full_total_rub"]),
                    text(d["label"]) + (" [SYNTHETIC]" if o["synthetic"] else ""),
                ]
            )
            + " |"
        )
        lines.extend(
            [
                "",
                f"**{text(o['id'])}**: получение {text(o['fulfillment'])}; гарантия {text(o['warranty'])}; оплата {text(d['payment']['passed_routes'])}; различия {text(d['differences'])}; пробелы {text(d['gaps'])}.",
                "",
                "<!-- canonical-row: " + canonical(row).replace("--", "\\u002d\\u002d") + " -->",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def export_bundle(offers, destination, as_of):
    dataset = preflight_export(offers, as_of)
    destination = absolute(destination)
    if destination.exists():
        raise ValueError("export output already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = destination.parent / ("." + uuid.uuid4().hex + ".normalized")
    stage.mkdir()
    rows = [flat(r) for r in dataset["rows"]]
    write_file(stage / "comparison.json", encoded(dataset))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    write_file(stage / "offers.csv", buffer.getvalue().encode())
    write_file(stage / "offers.xlsx", xlsx_bytes(rows))
    write_file(stage / "report.md", markdown(dataset).encode())
    with sqlite3.connect(stage / "normalized.sqlite") as db:
        db.executescript(
            "CREATE TABLE snapshot(data TEXT NOT NULL);CREATE TABLE rows(offer_id TEXT PRIMARY KEY,data TEXT NOT NULL);CREATE TABLE rejections(data TEXT NOT NULL);"
        )
        db.execute("INSERT INTO snapshot VALUES (?)", (canonical(dataset),))
        db.executemany(
            "INSERT INTO rows VALUES (?,?)",
            [(r["offer"]["id"], canonical(r)) for r in dataset["rows"]],
        )
        db.executemany(
            "INSERT INTO rejections VALUES (?)", [(canonical(r),) for r in dataset["rejections"]]
        )
    names = ["comparison.json", "offers.csv", "offers.xlsx", "report.md", "normalized.sqlite"]
    manifest = {
        "format": "normalized-export-1",
        "files": {name: hashlib.sha256((stage / name).read_bytes()).hexdigest() for name in names},
    }
    write_file(stage / "manifest.json", encoded(manifest))
    verify_bundle(stage)
    with (stage / "normalized.sqlite").open("rb") as handle:
        os.fsync(handle.fileno())
    fsync_directory(stage)
    publish_directory(stage, destination)
    return dataset


def verify_bundle(root):
    root = absolute(root)
    manifest = json.loads((root / "manifest.json").read_bytes())
    names = {"comparison.json", "offers.csv", "offers.xlsx", "report.md", "normalized.sqlite"}
    if manifest.get("format") != "normalized-export-1" or set(manifest.get("files", {})) != names:
        raise ValueError("invalid normalized export manifest")
    for name, h in manifest["files"].items():
        path = root / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != h:
            raise ValueError("normalized export hash mismatch")
    data = json.loads((root / "comparison.json").read_bytes())
    rows = [flat(r) for r in data["rows"]]
    with (root / "offers.csv").open(newline="") as f:
        values = list(csv.reader(f))
        if values != [COLUMNS] + rows:
            raise ValueError("CSV canonical rows mismatch")
    with zipfile.ZipFile(root / "offers.xlsx") as z:
        for name in z.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                ET.fromstring(z.read(name))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        cells = [
            [c.find(".//{" + NS + "}t").text or "" for c in r]
            for r in sheet.find("{" + NS + "}sheetData")
        ]
        if cells != [COLUMNS] + rows:
            raise ValueError("XLSX canonical rows mismatch")
    if (root / "report.md").read_text() != markdown(data):
        raise ValueError("Markdown canonical rows mismatch")
    with sqlite3.connect(f"file:{root / 'normalized.sqlite'}?mode=ro", uri=True) as db:
        if json.loads(db.execute("SELECT data FROM snapshot").fetchone()[0]) != data:
            raise ValueError("SQLite canonical snapshot mismatch")
        if [json.loads(r[0]) for r in db.execute("SELECT data FROM rows ORDER BY rowid")] != data[
            "rows"
        ]:
            raise ValueError("SQLite canonical rows mismatch")
        if [
            json.loads(r[0]) for r in db.execute("SELECT data FROM rejections ORDER BY rowid")
        ] != data["rejections"]:
            raise ValueError("SQLite canonical rejections mismatch")
    return {"status": "passed", "rows": len(rows), "formats": 5}
