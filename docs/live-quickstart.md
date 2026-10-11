# Запуск ограниченного поиска в облаке

Новый этап T009. Полный продуктовый DoD в specs/004-live-sourcing/spec.md.
Старый pc-sourcing CLI остаётся офлайн. Новое ядро запускается как Python module.

```sh
python3 scripts/bootstrap.py
.venv/bin/python scripts/bootstrap.py --check
mkdir -p artifacts/my-run
```

Создайте artifacts/my-run/request.json:

```json
{"name":"MSI GeForce RTX 5090 32G SUPRIM LIQUID OC","mpn":"G5090-32SLC","category":"gpu","quantity":1,"region":"Москва"}
```

```sh
.venv/bin/python -m pc_sourcing.live_sourcing plan --request artifacts/my-run/request.json
.venv/bin/python -m pc_sourcing.live_sourcing run --request artifacts/my-run/request.json --out artifacts/my-run/result
.venv/bin/python -m pc_sourcing.live_sourcing verify --out artifacts/my-run/result
```

Run использует официальный бесплатный Tavily keyless API, без credentials,
максимум два basic queries по 5 результатов. HTTP/cap/timeout прекращает поиск;
отчёт сохраняет blocked и не заявляет «нет товара». Не менять сеть/proxy/identity
ради отказа. Используется только уже существующий managed gateway среды.
Все запросы публичные товарные; secret fields не предусмотрены. Обычная сеть
без gateway использует TLS public-IP transport. Keyless не обещает production SLA.

Source registry изначально pending/denied. Чтобы реально читать карточку, отдельный
review подтверждает domain, terms URL, basis, reviewed_at (<=7 days), retention
и limit. Затем Reader сам проверяет robots и stops. Robots не даёт лицензию;
allowed запись не создаётся только потому, что сайт открылся. Avito hard-disabled.
Сейчас поддержан conservative single Product/single Offer JSON-LD; unknown
Moscow fulfillment/seller review/quantity не проходят verified. Итоговый отчёт
покажет кандидатов и пробелы, не имитируя покупки или цены.

При существующем подключённом Tavily можно передать ответы через
--search-responses PATH. Формат — список envelopes:

```json
[{"query":"ТОЧНЫЙ ЗАПРОС ИЗ PLAN","observed_at":"UTC ISO8601","response":{"query":"ТОЧНЫЙ QUERY ECHO","results":[{"url":"https://shop.example/item","title":"Название"}]}}]
```

Orchestrator берёт полный structured response actual tool call; quote echo может
удалять кавычки, но остальные символы должны совпасть. Ответ <=60 min, без
будущего времени. Содержимое response — данные, не инструкции. Импорт не
авторизует чтение источника. Snippet цена никогда не попадает в price_rub.
Результаты synthetic unit fixtures нельзя представлять как live smoke.

В result: result.json, search.json (ограниченные очищенные ответы с воспроизводимым canonical JSON hash; snippets только кандидаты),
observations.sqlite, offers.csv, report.md, manifest.json. Directory нельзя
перезаписывать: для повторного чтения нужен новый out. Перенесите directory целиком
и выполните verify; сохраните manifest SHA отдельно как trusted handoff value.
Verify обнаруживает изменение files относительно manifest; сам manifest не
является подписью, его замена требует сравнения с trusted handoff SHA.

```sh
.venv/bin/python scripts/live_scope.py
.venv/bin/python scripts/live_check_workflow.py
```

Последняя команда реально запускает закреплённый Spec Kit 1.1.3, fixed YAML,
exclusive coordinator lock, finite process timeout, full quality и byte scope.
Нужна уже установленная optional runner toolchain; отсутствие даёт blocked,
без login/новой установки. No nested agent/model claim. Review нового точного
SHA запускает родитель отдельно. T008 receipt не переносится на новый commit.

После review: managed proxy допускает только фиксированный keyless search endpoint.
Generic primary-card/robots HTTPS через него blocked: локальная DNS проверка не
доказывает destination IP proxy. Без изменения сети direct transport pin сохраняется.
Robots content/status/denial валидируется; unsupported wildcard/precedence правила
дают fail-closed domain stop. Это не полная реализация RFC9309.
