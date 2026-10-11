# Разрешённый поиск в облаке — 1.0.0

Основание: явное поручение пользователя продолжить продукт после T008.
Baseline: 5e031fcdd2daf7690585ed84f1b731c0972f4dc3. T007 остаётся непринятым.
Источники: Library libfile_89e134d178e08191b23a0d461814b7a3, разделы 9–18;
libfile_6032ad2fa60081918e1211d8ae62ad59, особенно раздел 9, шаги 1–9.
Исторический перечень: libfile_32d589879610819196e34b20b97c1a27;
цены полностью исключены. Полный актуальный перечень ожидает сверки родителя.

## Граница и истории

US1: пользователь задаёт товар/MPN и количество, получает план запросов по Москве,
передаёт настоящий ответ существующего поискового подключения и получает SQLite,
JSON/CSV и читаемый отчёт с кандидатами, наблюдениями и пробелами.
US2: разрешённая первичная карточка проверяется ограниченным HTTPS чтением;
отказ одного источника не блокирует остальные. Avito напрямую не читается.
US3: пакет результатов переносится в другое место и проверяется по SHA-256;
повтор не изменяет факты и не выдаёт старую цену за текущую.

Это отдельный live-контракт. Offer/Evidence/Evaluation 1.0.0, constitution,
старые specs/tests/goldens и история принятия не изменяются. Поля нового
наблюдения не заполняются неподтверждёнными bool из старого контракта.

| ID | Требование | Acceptance case |
|---|---|---|
| LIVE-01 | Москва, непустое имя и MPN при наличии, количество > 0; GPU только MSI RTX 5090 factory liquid; OC/SOC отдельно | request validation; GPU variants |
| LIVE-02 | поиск существующим подключением или заранее существующим tvly; ответ связан с точным запросом и временем; snippets только candidates | real connector smoke; mismatched query; no snippet prices |
| LIVE-03 | реестр 15–25 потенциальных источников, проверка условий отдельно от robots; pending/denied не читаются | registry gates; Avito zero requests |
| LIVE-04 | HTTPS, public IP only, no credentials, no redirects, bounded timeout/bytes/count, последовательная очередь домена; 403/CAPTCHA/429/timeout останавливают домен без retries | transport negatives; shared domain stop |
| LIVE-05 | primary Product JSON-LD только для одной модели/варианта; MPN, цена RUB, stock, condition по evidence; конфликт/неполнота остаются unknown | graph/list; ambiguous products/offers; wrong currency; visible conflict |
| LIVE-06 | URL, UTC, origin, value, selector, content hash; null неизвестных цены/доставки/продавца/оплаты; никаких source-spec prices | evidence retention; unknown roundtrip |
| LIVE-07 | точное/аналог/unresolved/excluded отдельно; GPU hard exclusions; у аналога явные отличия, без повышения eligibility | OC/SOC; air; waterblock; suffix |
| LIVE-08 | Avito без полного подтверждённого PAY-01 — «требует ручной проверки»; indexed Avito не подтверждает stock/payment | manual Avito candidate |
| LIVE-09 | дедуп canonical URL с сохранением provenance; seller independence unknown не считается подтверждённым числом продавцов | URL fragments/tracking; different variants/queries preserved |
| LIVE-10 | JSON/CSV/SQLite/report используют один сохранённый результат, поле цены не полная цена при неизвестной доставке; freshness 60 min предупреждение, не изменение v1 24h | report/DB equality; stale/future |
| LIVE-11 | immutable run directory, hashes каждого файла, проверяемая переносимость и обнаружение tamper; не хранить secrets/raw full pages | relocation; changed artifact; rerun refusal |
| LIVE-12 | unit/integration/negative/e2e + live smoke с passed/blocked/not_run; exact SHA перед review, независимый reviewer отдельно; не принимать продукт по snippets | full suite; fresh live receipt; parent review |

## Исполняемый DoD полного продукта

1. Окончательный список моделей/количеств сверён с исходниками и пользователем.
2. В свежем облачном checkout пользовательский ввод запускает живой разрешённый
поиск и проверку карточек до SQLite/JSON/CSV/отчёта. Доступный способ запуска
документирован и воспроизведён; connector-assisted режим назван явно.
3. Реестр содержит 15–25 проверенных независимых источников/продавцов или явные
blocked категории; несколько aliases и групп запросов; бюджет/причина остановки.
Для каждой модели цель 3–5 независимых подходящих продавцов, когда существуют;
слабое покрытие не скрывается. Нет утверждения полноты рынка.
4. Не менее 50 размеченных разнородных карточек; ноль hard-rule нарушений;
>=95% correct exact/analogue/excluded, все лидеры отдельно перепроверены.
5. Подтверждённые предложения требуют первичной идентичности, полной безусловной
цены товара, Moscow fulfillment, new condition, seller review, stock, для Avito
PAY-01; unknown не проходит. Наличие не означает резерв/безопасность.
6. Freshness, dedup seller identity, quantity, warranty, доставка и стоимость
показываются; неизвестные расходы не равны нулю. Evidence переживает перенос.
7. Один интеграционный SHA прошёл все required checks и реальный независимый
review; blocked обязательный live сценарий оставляет full DoD незавершённым.
8. Операционная инструкция проверена повторным реальным запуском; ошибки и
доступы не маскируются. Telegram, scheduler, hosting/deployment — отдельные
последующие решения с разрешением, не предпосылка ядра.

T009 реализует безопасный ограниченный вертикальный путь и инфраструктуру
проверки, а не автоматически весь DoD. Неразрешённый источник остаётся видимым.
