# План 1.0.0

Один writer (эта облачная задача), независимый reviewer назначается родителем.
Применяем spec-anchored этапы из раздела 9: контракт → задача → код → проверки
общего snapshot → review/repair → bounded live pilot → acceptance.

1. T009: additive request/search bridge, strict live observations, permission
registry, conservative JSON-LD reader, SQLite/report/CSV, transfer verification.
Только Python stdlib и существующий Pydantic; runtime LLM/API key не требуется.
2. Реальный Tavily connector smoke из текущей задачи. Connector не доступен
напрямую Python; orchestrator сохраняет полный structured response в envelope.
Standalone search использует официально документированный keyless /search API; cap/denial останавливает поиск без auth/retry. Ни
подключение инструмента, ни envelope не доказывают разрешение первичной карточки.
3. Разрешённые политики источников проверяются до чтения карточек. Реестр
изначально pending; Avito locked denied. API/feed/browser adapters добавляются
отдельными задачами после подтверждения разрешённого пути и полей.
4. После сверки оригинального списка добавить весь BOM, параметры аналогов,
quantity/warranty/fulfillment, seller identity и ranking полных сравнимых цен.
5. Расширить corpus до 50+ и 3–5 типов источников; отдельный реальный пользовательский
e2e и воспроизведение эксплуатации. Не заявлять полноту при blocked источниках.
6. Commit exact SHA, secret scan, push feature/cloud-portability без force;
родитель запускает независимый review. Исправления дают новый SHA и новые проверки.

Новые файлы live_* не импортируют coordinator scripts. Старые файлы byte-protected.
No credentials/deployment/accounts/cookies/proxies/CAPTCHA bypass/orders/contacts.
Transport использует штатный managed proxy только для фиксированного keyless search endpoint; primary-card URLs blocked без подтверждённого destination pin. Direct HTTPS pin сохраняется; сеть/identity не изменяются.
Сохраняем только минимальные факты/выдержки, response hash, URL/time; policy
должна явно разрешать эту минимальную retention. Cache не переиспользует цену;
повторным наблюдениям нужен новый run directory. Единственный процесс/очередь
на запуск, не обещаем межпроцессный scheduler или persistent hosting.
