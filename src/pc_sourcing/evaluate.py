"""Детерминированная оценка локальных предложений по спецификации 1.0.0."""

from datetime import UTC, datetime, timedelta

from pc_sourcing.models import TARGETS, Evaluation, Offer


def utc_time(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Время оценки должно содержать часовой пояс")
    return value.astimezone(UTC)


def evaluate(offer: Offer, as_of: datetime) -> Evaluation:
    as_of = utc_time(as_of)
    reasons = []
    origins = {"store_card", "seller_statement", "platform_transaction"}
    current = [
        e
        for e in offer.evidence
        if e.offer_id == offer.id
        and e.synthetic == offer.synthetic
        and e.origin in origins
        and timedelta(0) <= as_of - e.observed_at <= timedelta(hours=24)
    ]

    def confirmed(field, value, allowed=origins, ids=None):
        expected = str(value).lower() if isinstance(value, bool) else str(value)
        records = [e for e in current if e.field == field and e.origin in allowed]
        # Два актуальных противоречащих свидетельства не дают подтверждения.
        return bool(
            any(e.value == expected and (ids is None or e.id in ids) for e in records)
            and all(e.value == expected for e in records)
            and offer.source != "snippet"
        )

    passed = []
    for name in ("protected", "postpay"):
        route = getattr(offer, name)
        problems = []
        if route.status != "confirmed_applicable":
            problems.append(f"статус {route.status}")
        for field in ("covers_item", "covers_amount", "covers_region", "covers_order"):
            if not getattr(route, field):
                problems.append(f"не подтверждено {field}")
        if route.external_advance_required is not False:
            problems.append("внешний аванс требуется или неизвестен")
        allowed = (
            {"platform_transaction"}
            if name == "protected"
            else {"seller_statement", "platform_transaction", "store_card"}
        )
        if not confirmed(f"{name}_route", "confirmed_applicable", allowed, route.evidence_ids):
            problems.append("нет актуального соответствующего свидетельства способа оплаты")
        if problems:
            reasons.append(f"{name}: {'; '.join(problems)}; причина источника: {route.reason}")
        else:
            passed.append(name)
            reasons.append(f"{name}: полная применимость подтверждена; {route.reason}")

    global_ok = True
    if offer.global_payment_conflict:
        reasons.append("Глобальный конфликт условий оплаты")
        global_ok = False
    if offer.global_advance_required is not False or not confirmed(
        "global_advance_required", False
    ):
        reasons.append("Отсутствие обязательного внешнего аванса по всей покупке не подтверждено")
        global_ok = False
    if offer.optional_risky_alternative:
        reasons.append("Предложен необязательный рискованный альтернативный способ оплаты")
    if not global_ok or offer.source == "snippet":
        passed = []
    payment = bool(passed)

    exact = offer.sku == TARGETS[offer.product] and confirmed("sku", offer.sku)
    checks = {
        "Точный артикул не подтверждён (аналог рассматривается отдельно)": exact,
        "Нет подтверждённой положительной цены в RUB": (
            offer.price_rub is not None
            and offer.price_rub > 0
            and offer.currency == "RUB"
            and confirmed("price_rub", offer.price_rub)
        ),
        "Регион Москва не подтверждён": offer.region == "Москва" and confirmed("region", "Москва"),
        "Новое состояние не подтверждено": offer.condition == "new"
        and confirmed("condition", "new"),
        "Проверка продавца не подтверждена": offer.seller_checked
        and confirmed("seller_checked", True),
        "Заводское жидкостное охлаждение не подтверждено": (
            offer.product != "gpu"
            or (offer.factory_liquid is True and confirmed("factory_liquid", True))
        ),
        "Сведения предложения устарели или датированы будущим": (
            timedelta(0) <= as_of - offer.observed_at <= timedelta(hours=24)
        ),
    }
    reasons.extend(reason for reason, ok in checks.items() if not ok)
    stock_ok = confirmed("stock", offer.stock)
    if not stock_ok:
        reasons.append("Наличие не подтверждено актуальным свидетельством")
    if offer.stock != "in_stock":
        reasons.append(f"Наличие: {offer.stock}; товар не подтверждён в наличии")

    if offer.source == "snippet":
        eligibility, label = "candidate", "кандидат из поискового фрагмента"
        reasons.append("Поисковый фрагмент не подтверждает условия предложения")
    elif offer.source == "avito" and not payment:
        eligibility, label = "manual", "требует ручной проверки"
    elif not all(checks.values()) or not stock_ok or offer.stock not in {"in_stock", "preorder"}:
        eligibility, label = "excluded", "исключено из подтверждённых"
    elif offer.stock == "preorder":
        eligibility, label = "conditional", "предзаказ — условия требуют уточнения"
    else:
        eligibility, label = "verified", "подтверждено по данным"
        reasons.append("Все обязательные условия отбора подтверждены")
    return Evaluation(
        offer_id=offer.id,
        evaluated_at=as_of,
        exact_sku=exact,
        payment_gate_passed=payment,
        passed_routes=tuple(passed),
        eligibility=eligibility,
        eligible=eligibility == "verified",
        label=label,
        reasons=tuple(reasons),
        evidence_ids=tuple(e.id for e in offer.evidence),
        synthetic=offer.synthetic,
    )
