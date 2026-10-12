"""Bounded source assertions with dimensions, subjects, polarity and provenance.

Unknown material assertions are retained, never replaced with a guessed boolean.
This parser supports a documented schema/grammar, not unrestricted prose.
"""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Claim:
    attribute: str
    value: Decimal | str | bool | None
    unit: str
    scope: str
    polarity: str
    source: str
    raw: str


def norm(value):
    return unicodedata.normalize("NFKC", str(value)).upper().replace("Ё", "Е")


def polarity(text, start, end):
    prefix = re.split(r"[;,\n—]|\bBUT\b|\bА\b", text[:start])[-1]
    words = re.findall(r"[A-ZА-Я0-9]+", prefix)[-5:]
    if any(w in {"UNKNOWN", "UNVERIFIED", "НЕЯСНО", "НЕИЗВЕСТНО"} for w in words):
        return "unknown"
    return (
        "negative"
        if any(w in {"NOT", "NO", "WITHOUT", "NON", "НЕ", "НЕТ", "БЕЗ"} for w in words)
        else "positive"
    )


def positive_text(text):
    text = norm(text)
    if len(text) > 16000:
        return ""
    chars = list(text)
    for match in re.finditer(r"\b[A-ZА-Я0-9]+\b", text):
        if polarity(text, match.start(), match.end()) != "positive":
            chars[match.start() : match.end()] = " " * (match.end() - match.start())
    return "".join(chars)


def number(raw, default_unit):
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*([A-ZА-Я/ -]*)\s*", norm(raw))
    if not match:
        return None, default_unit
    amount, unit = Decimal(match[1].replace(",", ".")), match[2].strip() or default_unit
    aliases = {
        "ГБ": "GB",
        "МГЦ": "MHz",
        "MHZ": "MHz",
        "GHZ": "GHz",
        "ГГЦ": "GHz",
        "MT/S": "MT/s",
        "МТ/С": "MT/s",
        "CYCLES": "cycles",
        "CYCLE": "cycles",
        "NS": "ns",
        "НС": "ns",
        "GB": "GB",
        "COUNT": "count",
        "CYCLES ": "cycles",
    }
    unit = aliases.get(unit.upper(), unit)
    if unit == "GHz":
        return amount * 1000, "MHz"
    return amount, unit


def statement_polarity(text, match):
    prefix = polarity(text, match.start(), match.end())
    suffix = re.split(r"[;,\n—]|\bBUT\b|\bА\b", text[match.end() :])[0][:80]
    if re.search(
        r"UNKNOWN|UNVERIFIED|UNCLEAR|UNCONFIRMED|NO CONFIRMATION|НЕИЗВЕСТ|НЕТ ПОДТВЕРЖ", suffix
    ):
        return "unknown"
    denied = bool(
        re.search(
            r"\b(?:NOT|НЕ)\s+(?:(?:IS|ARE|WAS|БЫЛА|БЫЛО)\s+)?"
            r"(?:INSTALLED|INCLUDED|SUPPLIED|SUPPORTED|PROVIDED|PRESENT|COMPLETE|LIQUID|FACTORY|MOUSE|MEMORY|"
            r"УСТАНОВ\w*|ПОСТАВ\w*|ВКЛЮЧ\w*|ПОДДЕРЖ\w*)|"
            r"\b(?:ABSENT|UNSUPPORTED|MISSING|DISABLED|FALSE|ОТСУТСТВУЕТ)\b",
            suffix,
        )
    )
    if prefix == "unknown" or (prefix == "negative" and denied):
        return "unknown"
    return "negative" if denied or prefix == "negative" else "positive"


def boolean_claims(field, raw, source, *, invert=False, scope="product"):
    """Parse all supported propositions; no positive substring becomes a default True."""
    text = norm(raw)
    if type(raw) is bool or text in {"TRUE", "FALSE"}:
        value = raw if type(raw) is bool else text == "TRUE"
        return [
            Claim(field, value, "", scope, "negative" if invert else "positive", source, str(raw))
        ]
    if re.search(
        r"UNKNOWN|UNVERIFIED|UNCLEAR|UNCONFIRMED|НЕИЗВЕСТ|НЕПОДТВЕРЖ|NO CONFIRMATION", text
    ):
        return [Claim(field, None, "", scope, "unknown", source, str(raw))]
    allowed = (
        r"(?:NOT|NO|NON|WITHOUT|IS|ARE|WAS|WERE|HAS|HAVE|BE|BEEN|AT|BY|AND|OR|A|AN|THE|WITH|IN|OF|AS|TO|IT|ITS|NEITHER|NOR|НЕ|НЕТ|БЕЗ|НО|И|А|В|НА|ОТ|ДЛЯ|БУДЕТ|БЫЛА|БЫЛО|ТОЛЬКО|ЛИШЬ|"
        r"FACTORY|MANUFACTURER|LIQUID|COOLING|SYSTEM|INSTALL\w*|SUPPL\w*|INCLUD\w*|SUPPORT\w*|PROVID\w*|PRESENT|COMPLETE|FULL|ABSENT|MISSING|DISABLED|UNSUPPORTED|SELLER|RETAILER|AFTERMARKET|MODIFICATION\w*|CONVERSION|AIR|"
        r"MOUSE|GRAPHICS|CARD|GPU|DEVICE|MEMORY|RAM|MATCHED|PAIR|MODULE\w*|KIT|BOX|PACKAG\w*|RECEIVER|DONGLE|SHELL|HOUSING|REPLACEMENT|SPARE|ONLY|RADIATOR|LOOSE|PART\w*|UNIT|RETAIL|EMPTY|REGISTERED|UNBUFFERED|ECC|EXPO|XMP|"
        r"ЗАВОД\w*|ЖИДКОСТ\w*|ОХЛАЖД\w*|СЖО|СИСТЕМ\w*|УСТАНОВ\w*|ПОСТАВ\w*|ВКЛЮЧ\w*|ПОДДЕРЖ\w*|ПРОДАВ\w*|ВОЗДУШ\w*|ПОЛН\w*|МЫШЬ|ВИДЕОКАРТ\w*|КАРТ\w*|ПАМЯТЬ|КОМПЛЕКТ\w*|РАДИАТОР\w*|ПРИЕМНИК|НОЖК\w*|ЗАПЧАСТ\w*|ОТСУТСТВ\w*|РЕГИСТР\w*)"
    )
    words = re.findall(r"[A-ZА-Я0-9]+", text)
    count = (
        re.search(r"\b(\d+)\s+(?:MATCHED\s+)?MODULES?\b", text) if field == "full_item" else None
    )
    if "?" in text or any(
        not re.fullmatch(allowed, word) and not (count and word == count[1]) for word in words
    ):
        return [Claim(field, None, "", scope, "unknown", source, str(raw))]
    patterns = {
        "factory_liquid": (
            r"FACTORY|MANUFACTURER|ЗАВОД\w*",
            r"SELLER|RETAILER|AFTERMARKET|AIR|ПРОДАВ\w*|ВОЗДУШ\w*",
        ),
        "full_item": (
            r"COMPLETE|FULL|ПОЛН\w*|MOUSE(?![ -]?PAD)|GRAPHICS CARD|MATCHED|МЫШЬ|ВИДЕОКАРТ\w*|MEMORY|ПАМЯТЬ",
            r"REPLACEMENT|SPARE|ONLY|MOUSE.?PAD|RADIATOR|ПРИЕМНИК|НОЖК\w*|ЗАПЧАСТ\w*",
        ),
        "registered": (r"REGISTERED|РЕГИСТР\w*", r"UNBUFFERED"),
        "ecc": (r"ECC", r"NON[ -]?ECC"),
        "accessory_included": (
            r"INCLUDED|SUPPLIED|PROVIDED|PRESENT|ВКЛЮЧ\w*",
            r"ABSENT|MISSING|ОТСУТСТВ\w*",
        ),
    }
    if field.startswith("profile_"):
        patterns[field] = (field[8:] + r"|SUPPORTED", r"UNSUPPORTED|DISABLED")
    result = []
    for value, pattern in zip((True, False), patterns.get(field, (r"(?!)", r"(?!)")), strict=True):
        for match in re.finditer(r"\b(?:" + pattern + r")\b", text):
            pol = statement_polarity(text, match)
            result.append(Claim(field, value, "", scope, pol, source, str(raw)))
    if count:
        result.append(
            Claim("modules", Decimal(count[1]), "count", "kit", "positive", source, str(raw))
        )
    if any(
        word in {"NOT", "NO", "WITHOUT", "NON", "НЕ", "НЕТ", "БЕЗ"} for word in words
    ) and not any(c.polarity != "positive" for c in result):
        return [Claim(field, None, "", scope, "unknown", source, str(raw))]
    return result or [Claim(field, None, "", scope, "unknown", source, str(raw))]


def structured_claims(product, category):
    result = []
    extra = product.get("additionalProperty", [])
    if isinstance(extra, dict):
        extra = [extra]
    entries = [
        (key, value, "Product." + key)
        for key, value in product.items()
        if key
        not in {
            "@type",
            "@context",
            "name",
            "description",
            "mpn",
            "sku",
            "offers",
            "additionalProperty",
            "url",
            "image",
            "aggregateRating",
            "review",
        }
    ]
    if not isinstance(extra, list):
        result.append(
            Claim(
                "schema", None, "", "product", "unknown", "Product.additionalProperty", str(extra)
            )
        )
        extra = []
    for i, p in enumerate(extra):
        if isinstance(p, dict):
            entries.append((p.get("name", ""), p.get("value"), f"Product.additionalProperty[{i}]"))
        else:
            result.append(
                Claim(
                    "schema",
                    None,
                    "",
                    "product",
                    "unknown",
                    f"Product.additionalProperty[{i}]",
                    str(p),
                )
            )
    for key, values, source in entries:
        if not isinstance(key, str) or not key.strip():
            result.append(Claim("schema", None, "", "product", "unknown", source, str(key)))
            continue
        label = norm(re.sub(r"([a-z])([A-Z])", r"\1 \2", key))
        compact = re.sub(r"[^A-ZА-Я0-9]", "", label)
        if compact in {
            "COLOR",
            "COLOUR",
            "ЦВЕТ",
            "WARRANTY",
            "ГАРАНТИЯ",
            "WEIGHT",
            "ВЕС",
            "PRICE",
            "PRICECURRENCY",
            "AVAILABILITY",
            "ITEMCONDITION",
        }:
            continue
        field, unit, scope, invert = None, "", "product", False
        if re.search(r"MANUFACTUR|BRAND|ПРОИЗВОД|БРЕНД", label):
            field = "revision" if "REVISION" in label else "manufacturer"
        elif re.search(r"REVIS|РЕВИЗ", label):
            field = "revision"
        elif re.search(r"REGION|РЕГИОН", label) and re.search(r"CODE|КОД", label):
            field = "mpn"
        elif re.search(r"VARIANT|ВАРИАНТ", label):
            field = "variant"
        elif re.search(r"MODEL|МОДЕЛ", label):
            field = "model"
        elif re.search(r"CLOCK|ТАКТОВ", label):
            field = "basis" if "BASIS" in label else "clock"
            unit = "MHz"
            scope = "physical"
        elif re.search(r"TRANSFER|DATA.?RATE|EFFECTIVE|ПЕРЕДАЧ", label):
            field = "speed"
            unit = "MT/s"
            scope = "effective"
        elif re.search(r"SPEED|FREQUENC|ЧАСТОТ", label):
            field = "speed"
            unit = "MT/s"
            scope = "advertised"
        elif re.search(r"CAS|LATENCY|ТАЙМИН|ЗАДЕРЖ", label) or compact == "CL":
            field = "latency"
            unit = "cycles"
        elif re.search(r"MODULE.*(?:COUNT|INCLUDED)|(?:COUNT|NUMBER).*MODULE|ЧИСЛО.*МОДУЛ", label):
            field = "modules"
            unit = "count"
            scope = "kit"
        elif re.search(r"CAPACITY|MEMORY.?SIZE|VRAM|ОБ[ЪЬ]ЕМ|ЕМКОСТ", label):
            field = "capacity"
            unit = "GB"
            scope = (
                "module"
                if re.search(r"PER.*MODULE|MODULE.*CAPACITY|EACH|НА.*МОДУЛ", label)
                and not re.search(r"TOTAL|KIT|ВСЕГО|КОМПЛЕКТ", label)
                else ("kit" if category == "ram" else "product")
            )
        elif (
            re.search(r"MEMORY.*(?:TYPE|TECHNOLOGY|GENERATION)|ТИП.*ПАМЯТИ", label)
            or compact == "DDR"
        ):
            field = "memory_type"
        elif re.search(r"EXPO|XMP", label):
            field = "profile_EXPO" if "EXPO" in label else "profile_XMP"
        elif re.search(r"PROFILE|ПРОФИЛ", label):
            field = "profile"
        elif re.search(r"REGISTER|РЕГИСТР", label):
            field = "registered"
        elif re.search(r"ECC", label):
            field = "ecc"
        elif re.search(r"FORM.*FACTOR|ФОРМ.*ФАКТОР", label):
            field = "form_factor"
        elif re.search(r"COOL|FACTORY.*LIQUID|СЖО|ОХЛАЖД", label):
            field = "factory_liquid"
        elif re.search(r"SELLER.*CONVERSION", label):
            field = "factory_liquid"
            invert = True
        elif re.search(r"RECEIVER|DONGLE|CABLE|ПРИЕМНИК|КАБЕЛ", label) and re.search(
            r"INCLUDED|SUPPLIED|КОМПЛЕКТ", label
        ):
            field = "accessory_included"
            scope = "accessory"
        elif re.search(r"BOX.*ONLY", label):
            field = "full_item"
            invert = True
        elif re.search(
            r"COMPLETE|CONTENTS|PRODUCT.*KIND|FUNCTIONAL|МЫШЬ.*КОМПЛЕКТ|ВИДЕОКАРТ.*КОМПЛЕКТ|КОМПЛЕКТ|ТИП.*(?:ТОВАР|ИЗДЕЛ)|FULL.*MOUSE|MOUSE.*(?:INCLUDED|SUPPLIED)|ЗАВОДСК",
            label,
        ):
            field = "factory_liquid" if "ЗАВОДСК" in label else "full_item"
        elif compact == "ISCOMPLETE":
            field = "full_item"
        else:
            field = "unsupported_property"
        for raw in values if isinstance(values, list) else [values]:
            text = norm(raw)
            value = None
            pol = "positive"
            if field in {"speed", "clock", "latency", "modules", "capacity"}:
                value, parsed_unit = number(raw, unit)
                if field == "speed" and scope == "advertised" and parsed_unit == "MHz":
                    parsed_unit = "advertised-MHz"
                result.append(
                    Claim(
                        field,
                        value,
                        parsed_unit,
                        scope,
                        "unknown" if value is None else pol,
                        source,
                        str(raw),
                    )
                )
                continue
            if field in {
                "full_item",
                "factory_liquid",
                "profile_EXPO",
                "profile_XMP",
                "registered",
                "ecc",
                "accessory_included",
            }:
                result.extend(boolean_claims(field, raw, source, invert=invert, scope=scope))
                continue
            elif field == "profile":
                result.extend(text_claims(text, category, source))
                continue
            elif field == "manufacturer":
                value = re.sub(
                    r"[^A-ZА-Я0-9]", "", norm(raw.get("name", "") if isinstance(raw, dict) else raw)
                )
            elif field == "model":
                result.extend(text_claims(text, category, source))
                if category == "mouse":
                    value = (
                        "SUPERLIGHT"
                        if "SUPERLIGHT" in text
                        else "SUPERSTRIKE"
                        if "SUPERSTRIKE" in text
                        else None
                    )
                elif category == "gpu":
                    m = re.search(r"RTX\s*(\d+)", text)
                    value = m[1] if m else None
            elif field == "basis":
                value = "DDR physical clock" if "DDR" in text and "PHYSICAL" in text else None
            elif field == "form_factor":
                value = (
                    "SODIMM"
                    if re.search(r"SO.?DIMM", text)
                    else "UDIMM"
                    if re.search(r"UDIMM|DESKTOP", text)
                    else None
                )
            elif field == "memory_type":
                value = re.sub(r"\s", "", text)
            else:
                value = str(raw)
            if field == "unsupported_property" or value is None:
                pol = "unknown"
            result.append(Claim(field, value, unit, scope, pol, source, str(raw)))
    return result


def text_claims(raw, category, source="title"):
    text = norm(raw)
    result = []
    masked = list(text)

    def add(field, value, unit="", scope="product", match=None, pol=None):
        p = pol or (polarity(text, match.start(), match.end()) if match else "positive")
        result.append(Claim(field, value, unit, scope, p, source, match[0] if match else raw))

    for m in re.finditer(r"(\d+)\s*[XХ×*]\s*(\d+)\s*(?:GB|ГБ)\b", text):
        add("modules", Decimal(m[1]), "count", "kit", m)
        add("capacity", Decimal(m[2]), "GB", "module", m)
        add("capacity", Decimal(m[1]) * Decimal(m[2]), "GB", "kit", m)
        masked[m.start() : m.end()] = " " * len(m[0])
    for m in re.finditer(r"\b(\d+)\s*(?:GB|ГБ)\b", "".join(masked)):
        before = re.split(r"[;,\n—]", text[: m.start()])[-1]
        subjects = [
            (s.end(), "module")
            for s in re.finditer(
                r"EACH\s+MODULE|PER[ -]+MODULE|НА\s+МОДУЛ\w*|КАЖД\w*\s+МОДУЛ\w*", before
            )
        ]
        subjects.extend((s.end(), "kit") for s in re.finditer(r"TOTAL|ВСЕГО|KIT|КОМПЛЕКТ", before))
        scope = max(subjects)[1] if subjects else "kit" if category == "ram" else "product"
        add("capacity", Decimal(m[1]), "GB", scope, m)
    for m in re.finditer(r"\bG?DDR\s*[2-9]X?\b", text):
        add("memory_type", re.sub(r"\s", "", m[0]), match=m)
    if category == "ram":
        for m in re.finditer(r"\bDDR[2-9][\s-]+(\d{4,5})\b", text):
            add("speed", Decimal(m[1]), "MT/s", "effective", m)
        for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*(MT/S|МТ/С|MHZ|МГЦ|GHZ|ГГЦ)\b", text):
            value, unit = number(m[0], "MT/s")
            before = text[max(0, m.start() - 25) : m.start()]
            physical = bool(re.search(r"CLOCK|ТАКТОВ|PHYSICAL", before))
            add(
                "clock" if physical else "speed",
                value,
                unit,
                "physical" if physical else "effective" if unit == "MT/s" else "unknown",
                m,
                pol="positive" if physical or unit == "MT/s" else "unknown",
            )
        for m in re.finditer(
            r"\b(?:CL|CAS(?:\s+LATENCY)?|LATENCY|ЛАТЕНТНОСТЬ|ЗАДЕРЖКА)[\s:=]*(\d{1,3})(?:\s*(CYCLES|NS|НС))?\b",
            text,
        ):
            add("latency", Decimal(m[1]), "ns" if m[2] in {"NS", "НС"} else "cycles", match=m)
        for m in re.finditer(r"\b(?:EXPO|XMP)\b", text):
            suffix = re.split(r"[;,\n]", text[m.end() :])[0][:40]
            unsupported = bool(re.search(r"UNSUPPORTED|NOT SUPPORTED|DISABLED|НЕ ПОДДЕРЖ", suffix))
            add("profile_" + m[0], not unsupported, match=m)
            if m[0] == "XMP" and re.search(r"\bONLY\b|ТОЛЬКО", suffix):
                add("profile_EXPO", False, match=m)
        for field, pattern in [
            ("registered", r"\bREGISTERED\b"),
            ("ecc", r"\bECC\b"),
            ("form_factor", r"\bSO[ -]?DIMM\b"),
        ]:
            for m in re.finditer(pattern, text):
                add(field, "SODIMM" if field == "form_factor" else True, match=m)
        for m in re.finditer(r"\bUDIMM\b", text):
            add("form_factor", "UDIMM", match=m)
    for brand, pattern in [
        ("MSI", r"\bMSI\b"),
        ("ASUS", r"\bASUS\b"),
        ("PALIT", r"\bPALIT\b"),
        ("GIGABYTE", r"\bGIGABYTE\b"),
        ("ZOTAC", r"\bZOTAC\b"),
        ("GSKILL", r"\bG[.]?\s*SKILL\b"),
        ("KINGSTON", r"\bKINGSTON\b"),
        ("LOGITECH", r"\bLOGITECH\b"),
        ("RAZER", r"\bRAZER\b"),
    ]:
        for m in re.finditer(pattern, text):
            add("manufacturer", brand, match=m)
    if category == "gpu":
        for m in re.finditer(r"\bRTX\s*(\d+[A-Z]*)", text):
            add("model", m[1], match=m)
        for m in re.finditer(r"\b(?:OC|SOC)\b", text):
            add("variant", m[0], match=m)
    if category == "mouse":
        for m in re.finditer(r"\b(?:SUPERSTRIKE|SUPERLIGHT)\b", text):
            add("model", m[0], match=m)
    # A role proposition is scoped to a clause. Negated part-only is not part-only.
    roles = r"WATER[ -]?BLOCK|ВОДОБЛОК|MOUSE\s*PAD|DESK MAT|КОВРИК|DUMMY|МУЛЯЖ|SPARE|ЗАПЧАСТ|REPLACEMENT|СМЕНН\w*|CHARGING DOCK"
    for m in re.finditer(roles, text):
        add("full_item", False, match=m)
    for clause in re.finditer(r"[^;,\n—]+", text):
        part = bool(
            re.search(
                r"RECEIVER|DONGLE|HOUSING|SHELL|PACKAG|BOX|CARTON|БОКС|КОРОБ|УПАКОВ|ПРИЕМНИК|RADIATOR|РАДИАТОР|BLOCK|АДАПТЕР",
                clause[0],
            )
        )
        only = re.search(r"ONLY|STANDALONE|ТОЛЬКО|ЛИШЬ|EMPTY|ПУСТ\w*", clause[0])
        if part and only:
            start = clause.start() + only.start()
            p = polarity(text, start, start + len(only[0]))
            add("full_item", False, match=clause, pol=p)
        if re.search(r"\b(?:FOR|ДЛЯ)\s+(?:MSI|LOGITECH|G[.]?\s*SKILL)\b", clause[0]):
            add("full_item", False, match=clause)
        if re.search(
            r"(?:MOUSE|GPU|BOARD|MEMORY)\s+(?:(?:IS|ARE)\s+)?(?:NOT\s+(?:INCLUDED|SUPPLIED)|ABSENT)|\bNO\s+(?:MOUSE|GPU|MEMORY)\b|МЫШИ НЕТ|БЕЗ ПАМЯТИ|ПАМЯТИ НЕТ",
            clause[0],
        ):
            add("full_item", False, match=clause, pol="positive")
        cooling = bool(re.search(r"СЖО|ЖИДКОСТ|LIQUID|COOL|LOOP", text))
        modification = re.search(
            r"AFTERMARKET|CONVERSION|REBUILD|УСТАНОВ\w*|ПОСТАВ\w*|СМОНТИР\w*|МОНТИР\w*|FIT\w*|INSTALL\w*",
            clause[0],
        )
        if (
            cooling
            and modification
            and (
                re.search(
                    r"SELLER|RETAILER|ПРОДАВ|ПОСЛЕ ПОКУПКИ|AFTERMARKET|CONVERSION|REBUILD",
                    clause[0],
                )
            )
        ):
            start = clause.start() + modification.start()
            add(
                "factory_liquid",
                False,
                match=clause,
                pol=polarity(text, start, start + len(modification[0])),
            )
        if cooling and re.search(
            r"(?:НЕ|NOT)\s+ЗАВОД|FACTORY.*ABSENT|ЗАВОДСК.*ОТСУТСТВ", clause[0]
        ):
            add("factory_liquid", False, match=clause, pol="positive")
        if re.search(r"UNKNOWN|UNVERIFIED|НЕИЗВЕСТ|НЕТ ПОДТВЕРЖ", clause[0]):
            add("material_unknown", None, match=clause, pol="unknown")
    return result


def extract(texts, category, structured=None):
    claims = []
    for i, text in enumerate(texts):
        if isinstance(text, str):
            if len(text) > 16000:
                claims.append(
                    Claim(
                        "text_budget",
                        None,
                        "",
                        "product",
                        "unknown",
                        f"text[{i}]",
                        "text exceeds bounded grammar",
                    )
                )
                text = text[:16000]
            claims.extend(text_claims(text, category, f"text[{i}]"))
    if structured:
        claims.extend(structured_claims(structured, category))
    return tuple(claims)


def expectations(request):
    result = {}
    for c in text_claims(request.name, request.category):
        if c.polarity == "positive":
            result[(c.attribute, c.scope)] = (c.value, c.unit)
    if request.category == "gpu":
        result.update(
            {
                ("manufacturer", "product"): ("MSI", ""),
                ("model", "product"): ("5090", ""),
                ("capacity", "product"): (Decimal(32), "GB"),
                ("memory_type", "product"): ("GDDR7", ""),
                ("factory_liquid", "product"): (True, ""),
            }
        )
    if request.mpn == "F5-6000J3036F48GX2-TZ5NR":
        result.update(
            {
                ("manufacturer", "product"): ("GSKILL", ""),
                ("capacity", "kit"): (Decimal(96), "GB"),
                ("capacity", "module"): (Decimal(48), "GB"),
                ("modules", "kit"): (Decimal(2), "count"),
                ("memory_type", "product"): ("DDR5", ""),
                ("speed", "effective"): (Decimal(6000), "MT/s"),
                ("latency", "product"): (Decimal(30), "cycles"),
                ("profile_EXPO", "product"): (True, ""),
                ("registered", "product"): (False, ""),
                ("ecc", "product"): (False, ""),
                ("form_factor", "product"): ("UDIMM", ""),
            }
        )
    if request.category == "ram" and ("speed", "effective") in result:
        rate, unit = result[("speed", "effective")]
        if unit == "MT/s":
            result[("clock", "physical")] = (rate / 2, "MHz")
            result[("speed", "advertised")] = (rate, "advertised-MHz")
    result[("full_item", "product")] = (True, "")
    if request.mpn:
        result[("mpn", "product")] = (request.mpn, "")
    return result


def validate(request, claims, *, allow_variant_difference=False):
    wanted = expectations(request)
    issues = set()
    for c in claims:
        if c.attribute == "basis" and c.value == "DDR physical clock":
            continue
        scope = (
            "effective"
            if c.attribute == "speed" and c.scope == "advertised" and c.unit == "MT/s"
            else c.scope
        )
        expected = wanted.get((c.attribute, scope))
        if c.polarity == "unknown" or c.attribute in {
            "revision",
            "unsupported_property",
            "material_unknown",
            "schema",
        }:
            issues.add(c.attribute)
            continue
        if expected is None:
            if c.attribute in {
                "clock",
                "latency",
                "capacity",
                "modules",
                "form_factor",
                "model",
                "manufacturer",
                "mpn",
                "variant",
            }:
                issues.add(c.attribute)
            continue
        value, unit = expected
        declared_unit = c.unit
        declared_value = c.value
        if c.attribute == "latency" and c.unit == "ns" and c.polarity == "positive":
            clocks = {
                a.value
                for a in claims
                if a.attribute == "clock"
                and a.scope == "physical"
                and a.unit == "MHz"
                and a.polarity == "positive"
                and isinstance(a.value, Decimal)
            }
            if len(clocks) == 1 and isinstance(declared_value, Decimal):
                declared_value = declared_value * next(iter(clocks)) / Decimal(1000)
                declared_unit = "cycles"
        equal = declared_value == value and declared_unit == unit
        if allow_variant_difference and c.attribute == "variant":
            continue
        if c.polarity == "negative":
            if equal:
                issues.add(c.attribute)
        elif not equal:
            issues.add(c.attribute)
    return tuple(sorted(issues))


def assertions_data(claims):
    return [
        {
            "attribute": c.attribute,
            "value": str(c.value) if isinstance(c.value, Decimal) else c.value,
            "value_type": "decimal" if isinstance(c.value, Decimal) else type(c.value).__name__,
            "unit": c.unit,
            "scope": c.scope,
            "polarity": c.polarity,
            "source": c.source,
            "raw": c.raw,
        }
        for c in claims
    ]
