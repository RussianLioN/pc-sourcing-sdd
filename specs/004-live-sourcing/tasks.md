# Задачи нового продуктового этапа

- [ ] T009 [US1] Request, search envelope, sources, observation и report в src/pc_sourcing/live_*.py; tests/test_live_sourcing.py, tests/test_live_transport.py.
- [ ] T010 [US2] Проверить реальные условия источников и добавить разрешённые API/feed/card adapters в новой назначенной задаче; sources/live-registry.json.
- [ ] T011 [US1] После сверки оригиналов полный BOM, характеристики аналогов, quantity/fulfillment/warranty и seller dedup в новой спецификации.
- [ ] T012 [US3] Corpus 50+, реальные лидеры/coverage, эксплуатационный e2e, transfer и independent review точного SHA.

Dependencies: T009 → T010; сверка оригиналов → T011; T010 + T011 → T012.
Нет параллельных writers. Routine failures: narrow repair + regression.
Source policy/access failure: keep blocked and continue other sources.
