# Codex round 2 log

Ветка: `feature/codex-round-2`.

## P0 — AI Lock Analyzer

- `backend/app/services/ai_service.py` — добавлен advisory-only анализ снимка блокировок с локализованным строгим JSON-контрактом.
- `backend/app/api/ai.py` — добавлен авторизованный `POST /api/ai/lock-analysis` через общий `PayloadIn`.
- `frontend/src/views/MonitoringView.vue` — в непустой панели ожидающих блокировок добавлен `AiInsight` с цепочками, рекомендациями и оговорками.
- `frontend/src/i18n/locales/{ru,kk,en}.json` — добавлен паритетный набор `lockAnalysis.*` для трёх языков.

Проверки после задачи:

- `cd frontend && npx vue-tsc -b`
- `cd backend && python -m pytest -q`
- `docker compose up -d --build`

Результат: `vue-tsc` — 0 ошибок; локали — по 1061 ключу без расхождений; Docker-стек собран и запущен; `POST /api/ai/lock-analysis` без авторизации вернул ожидаемый 401. До добавления P1-набора `pytest` ожидаемо сообщил `no tests ran`.

## P1 — Backend tests

- `backend/tests/test_ai_service.py` — добавлены pure-function тесты локализации, JSON fallback и совместимости параметров OpenAI.
- `backend/tests/test_ai_api.py` — добавлены изолированные API-тесты Query Advisor, Lock Analyzer и статуса без ключа; сеть, auth и БД подменены.
- `backend/pytest.ini` — зафиксирован function scope асинхронных fixture для воспроизводимого запуска.
- `backend/requirements.txt` — закреплены `pytest`, `pytest-asyncio` и `anyio`.

Проверки после задачи:

- `cd frontend && npx vue-tsc -b`
- `cd backend && python -m pytest -q`
- `docker compose up -d --build`

Результат: `vue-tsc` — 0 ошибок; `python -m pytest -q` в backend-контейнере Python 3.11 — `17 passed`; Docker-стек пересобран и запущен. Локальный системный `python` имеет версию 3.8, поэтому не соответствует Python 3.11 проекта и CI.

## P1 — GitHub Actions CI

- `.github/workflows/ci.yml` — добавлены frontend type-check и backend pytest jobs для push/PR в `main` на Node 20 и Python 3.11.
- `README.md` — возле заголовка добавлен badge нового CI workflow.

Проверки после задачи:

- `cd frontend && npx vue-tsc -b`
- `cd backend && python -m pytest -q`
- `docker compose up -d --build`

Результат: `vue-tsc` — 0 ошибок; backend pytest — `17 passed`; Docker-стек пересобран и запущен. Workflow использует существующие lock-файлы зависимостей и не требует внешних сервисов.

## P2 — EXPLAIN-grounded Query Advisor

- `backend/app/services/query_plan_service.py` — добавлен parser-gated `EXPLAIN (FORMAT JSON)` в read-only транзакции с `statement_timeout`, без `ANALYZE`.
- `backend/app/api/ai.py` — Query Advisor обогащает контекст планом только после проверки доступа к серверу/БД и молча откатывается к тексту при ошибке.
- `backend/app/services/monitor_service.py`, `backend/app/schemas/monitoring.py`, `frontend/src/api/types.ts` — slow query дополнен именем исходной БД с обратной совместимостью snapshots.
- `frontend/src/views/MonitoringView.vue` — advisor передаёт текущий server id и БД выбранного запроса.
- `backend/app/services/ai_service.py` — промпт требует предпочитать факты EXPLAIN доступным догадкам.
- `backend/tests/test_query_plan_service.py` — покрыты SELECT/WITH allowlist, DML/multi-statement denylist и гарантии read-only/timeout/no-ANALYZE.
- `backend/tests/test_ai_api.py` — добавлены интеграционные проверки plan-grounding и тихого text-only fallback.
- `backend/requirements.txt` — закреплён SQL-парсер `sqlparse`.

Проверки после задачи:

- `cd frontend && npx vue-tsc -b`
- `cd backend && python -m pytest -q`
- `docker compose up -d --build`

Результат: `vue-tsc` — 0 ошибок; backend pytest — `28 passed`; Docker-стек пересобран и запущен. Живой read-only EXPLAIN на `demopg/demo_shop` вернул JSON-план `Seq Scan` (`Plan Rows: 1570`), а slow-query collector вернул имя БД `demo_shop`.

## P2 — Realistic slow-query seed

- `infra/demopg-init/003-slow-query-demo.sql` — добавлены idempotent demo-таблицы и повторяемые seq scan/unindexed JOIN запросы после очистки статистики загрузки.
- `scripts/seed_slow_queries.sh` — добавлен повторный запуск того же seed для существующего Docker volume с выводом top slow queries.
- `README.md`, `docs/DEMO.md` — задокументированы запуск seed и сценарий показа EXPLAIN-grounded Query Advisor.

Проверки после задачи:

- `cd frontend && npx vue-tsc -b`
- `cd backend && python -m pytest -q`
- `docker compose up -d --build`

Результат: seed дважды выполнен на существующем volume (повторно `INSERT 0 0`), shell syntax валиден; четыре запроса получили по 3 вызова и mean 11–76 мс. Slow-query без placeholders прошёл collector → EXPLAIN с `has_plan: true`. `vue-tsc` — 0 ошибок; backend pytest — `28 passed`; Docker-стек пересобран и запущен.

## Финальный аудит и документация

- `backend/tests/test_ai_api.py` — добавлены smoke-тесты контрактов четырёх существующих AI endpoint.
- `README.md` — отражены все шесть AI-функций и честный перечень round-2 работы Codex/GPT-5.6 со ссылкой на этот журнал.

Финальные проверки:

- `cd frontend && npx vue-tsc -b` — 0 ошибок.
- `cd backend && python -m pytest -q` — `32 passed` в backend-контейнере Python 3.11.
- Паритет локалей — по 1013 конечных ключей в `ru`, `kk` и `en`, расхождений нет.
- `docker compose up -d --build` — полная сборка успешна; backend, frontend, worker и scheduler запущены, appdb/demopg/Redis/RabbitMQ/MinIO работают без падений.
- Все шесть AI POST endpoint без авторизации вернули ожидаемый 401, что подтверждает регистрацию маршрутов.
- Ручная проверка `http://localhost/servers/1/monitoring`: реальные seeded slow queries отображаются; Lock Analyzer на реальной advisory-блокировке вернул severity, цепочку, рекомендации и оговорки; после снятия блокировки действие скрылось. На viewport 390x844 горизонтального overflow нет, ошибок и предупреждений в browser console нет.
- Read-only collector → `EXPLAIN (FORMAT JSON)` для seeded slow query подтверждён отдельно (`has_plan: true`, корневой узел `Sort`). Последний сквозной вызов Query Advisor дошёл до OpenAI, но сохранённый пользовательский ключ получил внешний `401 insufficient permissions`; это ограничение прав ключа, а не ошибка локального маршрута или EXPLAIN-пути.

## Codex round 3

Ветка: `feature/codex-round-3`.

## P0 — AI Config Advisor

- `backend/app/services/ai_service.py` — добавлен advisory-only `config_advisor` со строгим JSON-контрактом `severity/summary/findings/recommendations/notes` и ответом на языке интерфейса.
- `backend/app/api/ai.py` — добавлен `POST /api/ai/config-advisor` через существующий `PayloadIn` и общий `_require_key`.
- `frontend/src/views/PgConfigView.vue` — добавлен `AiInsight` для проверки конфигурации, payload ограничен ключевыми `pg_settings`, pending restart и ошибками conf/hba.
- `frontend/src/i18n/locales/{ru,kk,en}.json` — добавлен паритетный набор `configAdvisor.*`.
- `backend/tests/test_ai_api.py` — добавлен контрактный тест `/api/ai/config-advisor`.

Проверки после задачи:

- `cd frontend && npx vue-tsc -b` — 0 ошибок.
- `cd frontend && npm test` — ожидаемо не выполнен: script `test` ещё отсутствует до P1.
- `cd backend && python -m pytest -q` — локальный Python 3.8 без зависимостей проекта (`pytest_asyncio`, `sqlalchemy`), поэтому дополнительно проверено в контейнере.
- `docker compose exec -T backend python -m pytest -q` — `33 passed`.
- Паритет локалей — `ru`, `kk`, `en` по 1018 конечных ключей, расхождений нет.
- `docker compose up -d --build` — сборка успешна, контейнеры поднялись.
- `docker compose ps` — backend, frontend, worker, scheduler и инфраструктура запущены; appdb/demopg/Redis/RabbitMQ/MinIO healthy.

## P0 — AI Schema Reviewer

- `backend/app/services/schema_review_service.py` — добавлен новый read-only collector схемы: топ таблиц по размеру, колонки, PK, FK и индексы через `pg_catalog`/`information_schema`, с cap по объёму, `statement_timeout`, read-only транзакцией и закрытием pool в `finally`.
- `backend/app/services/ai_service.py` — добавлен advisory-only `schema_review` со строгим JSON-контрактом `severity/summary/issues/recommendations/notes`.
- `backend/app/api/ai.py` — добавлен `POST /api/ai/schema-review`; маршрут проверяет сервер через `get_owned_server` и доступ к БД через `ensure_database_access`, затем передаёт снимок схемы в AI.
- `frontend/src/views/DatabasesView.vue` — добавлена per-row кнопка `schemaReview.action` и панель `AiInsight` для выбранной БД.
- `frontend/src/i18n/locales/{ru,kk,en}.json` — добавлен паритетный набор `schemaReview.*`.
- `backend/tests/test_ai_api.py`, `backend/tests/test_schema_review_service.py` — добавлены тесты контракта endpoint, tenant-authorization и read-only collector.

Проверки после задачи:

- `cd frontend && npx vue-tsc -b` — 0 ошибок.
- `cd frontend && npm test` — ожидаемо не выполнен: script `test` ещё отсутствует до P1.
- `cd backend && python -m pytest -q` — локальный Python 3.8 без зависимостей проекта (`pytest_asyncio`, `sqlalchemy`), поэтому дополнительно проверено в контейнере.
- `docker compose exec -T backend python -m pytest -q` — `36 passed`.
- Паритет локалей — `ru`, `kk`, `en` по 1023 конечных ключа, расхождений нет.
- `docker compose up -d --build` — сборка успешна, контейнеры поднялись.
- `docker compose ps` — backend, frontend, worker, scheduler и инфраструктура запущены; appdb/demopg/Redis/RabbitMQ/MinIO healthy.
