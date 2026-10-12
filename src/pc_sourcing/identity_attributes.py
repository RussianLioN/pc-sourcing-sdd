"""Normalize explicit identity attributes; contradictory declarations never vanish behind MPN.

This deterministic bounded parser is not general language understanding. It retains
sets of declarations, including conflicting values, and compares only attributes
with a justified requested value. Full product name/MPN gates stay in the caller.
"""

import re
import unicodedata
from decimal import Decimal

ALIASES = {
    "capacity": {"capacity", "memorysize", "memorycapacity", "vram", "объем", "емкость"},
    "speed": {"speed", "memoryspeed", "frequency", "частота"},
    "latency": {"caslatency", "latency", "cl", "тайминги"},
    "memory_type": {"memorytype", "ddr", "типпамяти"},
    "profile": {"profile", "memoryprofile", "профиль"},
    "full_item": {"iscomplete", "completeitem", "fullitem", "комплектность"},
    "factory_liquid": {"factoryliquid", "factorycooling", "заводскоежидкостноеохлаждение"},
}


def normalized(text):
    return unicodedata.normalize("NFKC", text or "").upper().replace("Ё", "Е")


def attributes(text, *, category, structured=None):
    text = normalized(text)
    result = {}

    def add(field, value):
        result.setdefault(field, set()).add(str(value))

    topology = list(re.finditer(r"(\d+)\s*[XХ×*]\s*(\d+)\s*(?:GB|ГБ)\b", text))
    totals = text
    for match in reversed(topology):
        add("modules", int(match[1]))
        add("module_capacity", int(match[2]))
        add("capacity", int(match[1]) * int(match[2]))
        totals = totals[: match.start()] + totals[match.end() :]
    for value in re.findall(r"\b(\d+)\s*(?:GB|ГБ)\b", totals):
        add("capacity", int(value))
    for value in re.findall(r"\b(G?DDR\s*[2-9]X?)\b", text):
        add("memory_type", re.sub(r"\s", "", value))
    if category == "ram":
        for value in re.findall(r"\bDDR[2-9][\s-]+(\d{4,5})\b", text):
            add("speed", int(value))
        for value, unit in re.findall(r"\b(\d+(?:[.,]\d+)?)\s*(MHZ|МГЦ|GHZ|ГГЦ|MT/S|МТ/С)\b", text):
            amount = Decimal(value.replace(",", ".")) * (1000 if unit in {"GHZ", "ГГЦ"} else 1)
            add("speed", int(amount) if amount == int(amount) else str(amount))
        for value in re.findall(
            r"\b(?:CL|CAS(?:\s+LATENCY)?|ЛАТЕНТНОСТЬ|ЗАДЕРЖКА)[\s:=]*(\d{1,3})\b", text
        ):
            add("latency", int(value))
        for clause in re.split(r"[;:.\n]", text):
            for profile in ("EXPO", "XMP"):
                if re.search(r"\b" + profile + r"\b", clause):
                    negative = bool(
                        re.search(r"\b(?:NOT|NO|WITHOUT|UNSUPPORTED|НЕ|НЕТ|БЕЗ)\b", clause)
                    )
                    add("profile_" + profile, not negative)
            if re.search(r"\bXMP\b", clause) and re.search(r"\b(?:ONLY|ТОЛЬКО)\b", clause):
                add("profile_EXPO", False)
        if re.search(r"SO[ -]?DIMM|REGISTERED|\bECC\b", text):
            add("desktop_unbuffered", False)
    # Role is distinct from model mentions: a part 'for <model>' isn't that item.
    brand_for = bool(re.search(r"\b(?:FOR|ДЛЯ)\s+(?:MSI|LOGITECH|G[.]?\s*SKILL)\b", text))
    packaging = bool(re.search(r"PACKAG|\bBOX\b|КОРОБ|УПАКОВ", text))
    part = bool(re.search(r"RECEIVER|ПРИЕМНИК|DONGLE|HOUSING|SHELL|КОРПУС|ЗАПЧАСТ", text))
    only = bool(re.search(r"\b(?:ONLY|ТОЛЬКО|ЛИШЬ)\b", text))
    accessory = bool(
        re.search(
            r"MOUSE\s*PAD|КОВРИК|CHARGING\s+(?:DOCK|STATION)|ЗАРЯДН\w*\s+СТАНЦ|DUMMY|ПАМЯТИ НЕТ",
            text,
        )
    )
    absent_main = bool(
        re.search(
            r"\b(?:MOUSE|GPU|MEMORY|МЫШЬ|ВИДЕОКАРТА|ПАМЯТЬ)\s+(?:(?:IS|ARE)\s+)?(?:NOT\s+INCLUDED|ABSENT)|\bNO\s+(?:MOUSE|GPU|MEMORY)\b",
            text,
        )
    )
    if brand_for or accessory or absent_main or ((packaging or part) and only):
        add("full_item", False)
    # Seller/aftermarket provenance plus a cooling modification contradicts factory origin.
    seller = bool(re.search(r"ПРОДАВЦ|SELLER|AFTERMARKET", text))
    cooling = bool(re.search(r"СЖО|ЖИДКОСТ|LIQUID|COOLING|ВОДЯН", text))
    modified = bool(
        re.search(r"УСТАНОВ|ПОСТАВ|МОНТИР|ДОБАВ|ЗАМЕН|INSTALL|FIT|SUPPL|AFTERMARKET", text)
    )
    nonfactory = bool(re.search(r"(?:НЕ|NOT|NON)[ -]+(?:ЗАВОДСК|FACTORY)", text))
    if cooling and ((seller and modified) or nonfactory):
        add("factory_liquid", False)
    if structured:
        entries = list(structured.items())
        extra = structured.get("additionalProperty", [])
        if isinstance(extra, dict):
            extra = [extra]
        if isinstance(extra, list):
            entries.extend(
                (p.get("name", ""), p.get("value")) for p in extra if isinstance(p, dict)
            )
        for key, raw in entries:
            if not isinstance(key, str):
                continue
            name = re.sub(r"[^A-ZА-Я0-9]", "", normalized(key)).casefold()
            field = next((f for f, names in ALIASES.items() if name in names), None)
            if name in {"expo", "xmp"}:
                field = "profile_" + name.upper()
            if field is None:
                continue
            values = raw if isinstance(raw, list) else [raw]
            for value in values:
                if field in {"full_item", "factory_liquid", "profile_EXPO", "profile_XMP"}:
                    if type(value) is bool:
                        add(field, value)
                    elif normalized(str(value)) in {"TRUE", "FALSE"}:
                        add(field, normalized(str(value)) == "TRUE")
                    else:
                        add(field, "unknown_declaration")
                elif field in {"speed", "capacity", "latency"}:
                    match = re.fullmatch(
                        r"\s*(\d+)\s*(?:GB|ГБ|MHZ|МГЦ|MT/S|МТ/С)?\s*", normalized(str(value))
                    )
                    if match:
                        add(field, int(match[1]))
                    else:
                        add(field, "unknown_declaration")
                elif field == "memory_type":
                    add(field, re.sub(r"\s", "", normalized(str(value))))
                elif field == "profile":
                    declared = attributes(str(value), category="ram")
                    for declared_field, declared_values in declared.items():
                        if declared_field.startswith("profile_"):
                            for declared_value in declared_values:
                                add(declared_field, declared_value)
    return result


def conflicts(request, texts, *, structured=None):
    expected = attributes(request.name, category=request.category)
    if request.category == "gpu":
        expected.update(capacity={"32"}, memory_type={"GDDR7"}, factory_liquid={"True"})
    if request.mpn == "F5-6000J3036F48GX2-TZ5NR":
        expected.update(
            capacity={"96"},
            modules={"2"},
            module_capacity={"48"},
            memory_type={"DDR5"},
            speed={"6000"},
            latency={"30"},
            profile_EXPO={"True"},
            desktop_unbuffered={"True"},
        )
    expected["full_item"] = {"True"}
    observed = attributes(
        "\n".join(t for t in texts if isinstance(t, str)),
        category=request.category,
        structured=structured,
    )
    return tuple(
        sorted(
            field
            for field, values in observed.items()
            if field in expected and not values <= expected[field]
        )
    )
