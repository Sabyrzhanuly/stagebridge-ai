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
