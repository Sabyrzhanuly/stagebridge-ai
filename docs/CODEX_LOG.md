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
