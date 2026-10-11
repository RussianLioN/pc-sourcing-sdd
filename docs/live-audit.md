# Ретроспектива и ранний технический аудит

Дата: 11 октября 2026, облачная среда Linux. Baseline T008:
`5e031fcdd2daf7690585ed84f1b731c0972f4dc3`.
Остановка после переноса не завершала исходный продуктовый замысел. T008 принят
как офлайн/облачный перенос; T007 исторически непринят. Новый этап additive.

## Источники и правила их чтения

Лично проверены ключевые исходные разделы «Поиск комплектующих и Avito — решение
для dodik» (§9–18) и «SDD и мультиагентная разработка поиска комплектующих»
(§9–14). Оригинальные DOCX повторно материализованы в текущую облачную среду,
прочитаны ZIP/XML bytes; совпадение с repo копиями проверяется по SHA-256.
«Комплектующие — исследование 11.10.2026» содержит исторический перечень 12
позиций, quantities и ссылки. Его цены не используются в данных приложения.
Частные ссылки переписки и идентификаторы пользователя в публичный отчёт не
включены; точный частный реестр остаётся в пакете аудита.

Пункт 9 методологии требует contract → scoped task → implementation → unit,
contract/property → common snapshot → independent review/repair → offline,
затем ограниченный разрешённый live smoke → принятие по одному SHA/spec hash.
Первый deliverable: SKU → candidates → normalized evidence → SQLite → report.
Изменение запуска агентов в T008 не отменило live продуктовый этап.

| Исходное требование | Реализация на baseline / T009 | Тест или evidence | Оставшийся пробел |
|---|---|---|---|
| Москва, exact MPN и OC/SOC отдельно | v1 три фиксированных targets; T009 request/identity | legacy SKU tests; новые hard-exclusion/MPN tests | полный актуальный BOM и characteristics analogues |
| MSI 5090 factory liquid того же производителя | v1 evidence gate; T009 conservative SUPRIM LIQUID identity | GPU air/5090D/waterblock/ASUS exclusions | manufacturer facts verification и широкий аналоговый каталог |
| Поисковый адаптер | T009 connected response import и keyless HTTPS /search | настоящий connector запрос; настоящий Python smoke | keyless cap не производственная ёмкость |
| Snippets только candidates | T009 не извлекает цену/stock/payment из выдачи | snippet null/manual tests | первичные карточки разрешённых магазинов |
| 15–25 независимых продавцов; цель 3–5 на SKU | T009 draft registry 18 потенциальных доменов | registry gate и отчёт: confirmed sellers = 0 | проверка существования/условий/independence каждого; список не метрика выполненного охвата |
| 3–5 типов разрешённых источников | T009 conservative Product JSON-LD transport | graph/ambiguity/conflict tests | API/feed/visible text/browser adapters, права источников |
| Истинные цены из источника и количество | JSON-LD положительная unconditional RUB, остальное null | price invalid/currency/context checks | доказанная итоговая цена, quantity, лидеры и ручная перепроверка |
| Avito protected OR postpay без required advance | frozen v1 PAY-01; T009 indexed Avito manual | legacy payment tests; live manual regression | разрешённый первичный Avito путь, transaction evidence |
| Unknown != false/0 | новый live observation с nullable fields | unknown SQLite/JSON roundtrip | нет скрытого адаптирования в v1 nonnullable bool |
| URL/time/field evidence, freshness | T009 primary facts и hashes; search max 60 min | provenance/time rejection | user-facing stale leader recheck и source-specific retention |
| Domain queue, robots, stops, no bypass | T009 sequential Reader, delay/rate/card/byte/time bounds | denial/429/CAPTCHA/robots/private IP tests | постоянная shared queue/cache только после отдельного дизайна |
| Dedup и независимые продавцы | canonical URL + queries preserved | tracking/variant tests | доказанный seller identity между площадками |
| SQLite + JSON/CSV/XLSX + readable report | T009 SQLite/JSON/CSV/Markdown, один result | DB equality, artifact verify, relocation/tamper | XLSX export и полный сравнительный user report |
| Corpus >=50, zero hard-rule violations, >=95% identity | baseline synthetic corpus + focused new tests | regressions, не рыночная оценка accuracy | 50 размеченных карточек, отдельный oracle, leaders review |
| Разрешённый live primary и эксплуатационный e2e | живой search → blocked card checks → real candidate report | fresh smoke artifacts | первый разрешённый первичный источник; отсутствие обязательного check не проходит DoD |
| Independent exact-snapshot review | ранее T008; T009 требует новый review | exact SHA будет передан родителю | parent-assigned reviewer, не самопроверка writer |
| Reproducible operation и перенос evidence | T009 immutable run path + manifest/check | relocated package + tamper tests | production operation; постоянный hosting не разрешён |

Исходные количественные gates были предложены исследованием для полного пилота,
а не выполнены baseline. Новый full DoD явно сохраняет их. T009 — ограниченный
вертикальный этап; его unit tests не подменяют coverage/accuracy acceptance.

## Реально применённые средства

| Средство | Что действительно выполнено | Граница доказательства |
|---|---|---|
| Library skill | текущий materialization helper, три DOCX, читаемые bytes/hash | восстановление оригиналов, не живые магазинные цены |
| Tavily search skill + existing connector | bounded actual search | candidate links, не первичная цена/stock |
| Official Tavily keyless API | Python HTTPS request через штатный managed gateway, два запроса | бесплатный light-use smoke; caps без auth/retries |
| pc-payment-audit skill | read SKILL + decision table, actual payment suite | frozen OR/payment behavior на fixtures |
| pc-snapshot-check skill | byte blob guard по accepted baseline, new T009 ownership | сохранность файлов; не independent verdict |
| pc-cloud-setup skill | actual pinned bootstrap --check и baseline quality | установленная Linux среда; старый nested blocker не переписан |
| Spec Kit implementation workflow | project prerequisite script с explicit feature/no-persist; pinned runner для fixed validation workflow | работает coordinator shell workflow; это не автономный repair/новый worker |
| pytest / Ruff / SQLite | focused tests, full regression/format + database roundtrip | проверки одного exact SHA должны повторяться после commit |
| Native cloud review | родитель назначает distinct reviewer task | writer не вправе сам объявить независимую приёмку |

Документация keyless проверена по официальной странице
https://docs.tavily.com/documentation/keyless. Search бесплатный, rate-limited;
новых credentials нет. Ответ может нормализовать quotation marks в query echo;
приём envelope допускает только такое наблюдаемое отличие, не смену товара/MPN.

Первый direct socket smoke был blocked (ConnectionRefusedError); отказ сохранён.
В среде уже есть managed proxy. Использование этого штатного маршрута исправило
transport; конфигурация/сеть/секреты не менялись. Второй smoke выявил дефект
query echo matching; исправление и regression затем дали 10 реальных candidates.
Никакой отказ целевого магазина/Avito не обходился.

Проверено соглашение Регард через доступный public read. Оно лицензирует обычное
использование сайта, но не подтвердило нужный автоматический сбор/retention для
этого адаптера. Robots/readable price-list через инструмент не подтверждены;
Регард остаётся pending, карточки не читаются. Другие draft domains также pending.
Avito locked denied: переоткрытие, смена IP/инструмента/identity не выполнялись.

## Обязательные внешние предпосылки

Ядру не нужны Telegram token, OpenAI API key, bot account, paid search или hosting.
Для bounded cloud поиска сейчас хватает keyless доступа или существующего
connector. При cap сохраняется blocked; создание ключа требует отдельного решения.
Для подтверждённых предложений нужен проверенный разрешённый первичный путь хотя
бы одного магазина (условия чтения и minimal facts retention, robots/лимиты),
затем остальные источники для coverage. Это задача policy/source verification,
а не запрос случайного API key. Прямой Avito требует отдельного подтверждения
допустимого пути; платежи не угадываются. Telegram/deployment/постоянный доступ —
отдельные разрешения только если выбран соответствующий этап.
