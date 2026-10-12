"""Compatibility diagnostics over typed source claims; decisions use unit/scope-aware validation."""

from pc_sourcing.identity_claims import expectations, extract, validate


def attributes(text, *, category, structured=None):
    """Legacy diagnostic view only: never use these flattened sets for decisions."""
    result = {}
    for c in extract([text], category, structured):
        name = (
            "module_capacity" if c.attribute == "capacity" and c.scope == "module" else c.attribute
        )
        value = str(c.value) if c.value is not None else "unknown_declaration"
        result.setdefault(name, set()).add(value)
    return result


def conflicts(request, texts, *, structured=None, allow_variant_difference=False):
    return validate(
        request,
        extract(texts, request.category, structured),
        allow_variant_difference=allow_variant_difference,
    )


def hard_ram_difference(request, title):
    expected = expectations(request)
    for c in extract([title], "ram"):
        key = (c.attribute, c.scope)
        if key not in {
            ("capacity", "kit"),
            ("memory_type", "product"),
            ("manufacturer", "product"),
        }:
            continue
        wanted = expected.get(key)
        if c.polarity == "positive" and wanted and (c.value, c.unit) != wanted:
            return True
    return False
