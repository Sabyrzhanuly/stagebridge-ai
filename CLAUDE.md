# CLAUDE.md — PG Admin System (PG Control Center)

Правила для Claude в этом проекте. Эквивалент `.cursor/rules/*.mdc` под Cursor.
Источник истины по правилам — `.cursor/rules/`; этот файл переносит их под Claude.

## Язык

**Отвечать на русском.**

## О проекте

Веб-приложение **PG Control Center**: управление PostgreSQL-серверами через UI и API
(доступы, бэкапы, восстановление, мониторинг, аудит, real-time прогресс задач).
Полное ТЗ — `DB_CONTROL_CENTER_FULL_TZ_V2.md`.

## Принципы разработки

1. **Plan → Code** — допущения проговаривать явно; при неоднозначности — уточнять.
2. **YAGNI** — без лишних абстракций. Слои `api / services / models` — стандарт проекта.
3. **Хирургические правки** — менять только запрошенное, не расползаться по файлам.
4. **Баг** — сначала воспроизведение, потом фикс, потом верификация.

## Границы (важно)

- Работать **только внутри** `pgadmin-system/`.
- **Не трогать** соседнюю папку `cluster-admin/` (настройка PG-кластера — отдельный проект).
- **Не подключаться** к удалённым/управляемым PG-серверам от имени агента.
- Внутренняя БД (`appdb` в Docker) — только через Alembic и код backend.

## Стек

| Слой | Технологии |
|------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy async + asyncpg, Alembic, Pydantic v2, Celery, Redis, RabbitMQ, Fernet |
| Frontend | Vue 3 (`<script setup>`), Vite, TypeScript, **PrimeVue 4**, Pinia, Axios, Font Awesome |
| Storage | Внешний S3/MinIO (per-server, через UI «Настройки → Хранилище S3») |
| CLI | Typer + Rich поверх REST (httpx) |
| Deploy | Docker Compose (7 сервисов) |

## Структура

```
pgadmin-system/
  backend/app/     — main, config, database, models/, schemas/, api/, services/, tasks/
  backend/cli/     — Typer CLI
  backend/alembic/ — миграции
  frontend/src/    — App.vue, components/ (AppLayout, TaskPanel), views/, stores/, router/, api/
  docker-compose.yml
  scripts/         — install, upgrade, backup_self (деплой Control Center)
  .cursor/         — rules и skills (источник этих правил)
```

## Запуск

```bash
cd pgadmin-system
cp .env.example .env
# FERNET_KEY: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker compose up -d
docker compose exec backend alembic upgrade head
```

Порты: appdb `5433`, redis `6380`, backend `8000`, frontend `80`.
Frontend dev (hot reload): `cd frontend && npm install && npm run dev` (прокси `/api` и `/ws` → `:8000`).

## Backend (FastAPI) — `backend/**/*.py`

- Эндпоинты — под `/api`.
- Сервисы (`services/`) — без зависимости от FastAPI (чистая бизнес-логика).
- Фоновые задачи — **только Celery**.
- Пароли серверов — шифровать через **Fernet** (`crypto.py`).
- Миграции — Alembic (`alembic upgrade head`); генерация: `alembic revision --autogenerate -m "…"`.
- SQL-конвенции пользователя (WITH, EXISTS, хранимки PG 12) — только для raw SQL/скриптов, **не** для SQLAlchemy/Alembic.

### Новый API-эндпоинт

Модель `models/<сущность>.py` → схема `schemas/<сущность>.py` → сервис `services/<сущность>_service.py`
→ роутер `api/<сущность>.py` → подключить в `main.py` → миграция Alembic.

### Новая Celery-задача

Файл `tasks/<задача>_tasks.py` → регистрация в `tasks/celery_app.py`
→ прогресс через Redis pub/sub → WebSocket `/ws` (клиент: `frontend/src/stores/tasks.ts`).

## Frontend (Vue 3) — `frontend/**/*.{vue,ts}`

- Компоненты — `<script setup lang="ts">`.
- Типы — в `api/types.ts`.
- Ошибки — через `useToast()` (PrimeVue).
- WebSocket задач — `stores/tasks.ts`.
- Новая страница: View в `views/<Name>View.vue` → маршрут в `router/index.ts` → пункт меню в
  `components/AppLayout.vue` (**не** App.vue).
- RBAC: опасные действия — через `authStore.hasPermission()`.
- **Только PrimeVue 4** — любой React/Tailwind (напр. из Magic MCP) переписывать в Vue SFC.
- Тема: `.app-dark` + переменные в `frontend/src/styles/global.css`.
- Design system: `design-system/pg-control-center/MASTER.md` (+ `pages/admin-app.md`, `pages/scenarios.md`).

## Docker Compose — `docker-compose*.yml`

7 сервисов: **appdb, redis, rabbitmq, backend, worker, scheduler, frontend**.

| Сервис | Порт (host) |
|--------|-------------|
| appdb | 5433 |
| redis | 6380 |
| rabbitmq | 5672, 15672 |
| backend | 8000 |
| worker / scheduler | — (Celery, без host-порта) |
| frontend | 80 |

- Healthcheck: appdb, redis, rabbitmq.
- Конфиг — `.env` из `.env.example`.
- Backend hot-reload — volume `./backend:/app`.
- S3/MinIO — внешний, per-server через UI (не в compose).
- Celery-очереди: `org_{id}` per-organization + `platform` для PG-клиентов; worker: `python -m app.tasks.worker_main`.
- PG-клиенты — ставятся через UI (только platform admin), том `pg_client_lib`.

## Celery Beat

| Задача | Интервал |
|--------|----------|
| collect_all_metrics | 60 с |
| run_scheduled_backups | 60 с |
| run_scheduled_scenarios | 60 с |
| check_alert_rules | 120 с |
| cleanup_old_backups | ежедневно 03:00 UTC |

## Деплой для пользователя (обязательно)

После **любой** доработки, которую пользователь увидит в браузере, — пересобрать и поднять
контейнеры **до конца ответа**, не дожидаясь напоминания:

| Что менялось | Команда |
|--------------|---------|
| `frontend/**` | `docker compose up -d --build frontend` |
| `backend/**` (API, services) | `docker compose up -d --build backend` (+ `worker scheduler`, если Celery/tasks) |
| Оба слоя | `docker compose up -d --build frontend backend worker scheduler` |

Проверить `docker compose ps`. В ответе указать URL: **http://localhost** (frontend :80).
Исключение: пользователь явно работает через `npm run dev` — тогда Docker frontend пересобирать не нужно.

## Workflow: skills, MCP, память

Проект несёт свой набор Cursor-skills в `.cursor/skills/`. Claude не обязан их запускать, но
**читает** релевантный `SKILL.md`, прежде чем импровизировать:

| Задача | Материал для чтения |
|--------|---------------------|
| Разработка (API, Celery, Docker, структура) | `.cursor/skills/pgadmin-system-dev/SKILL.md` + `api-reference.md` |
| UI / layout / редизайн | `.cursor/skills/frontend-ui/SKILL.md`, `ui-ux-pro-max`, `design-system/pg-control-center/` |
| План до кода, неясные требования | `.cursor/skills/grill-me/` — сначала согласовать, без кода |
| Дока библиотек (FastAPI, Vue, PrimeVue) | MCP **context7** — не полагаться на память модели |
| Память проекта | MCP **mempalace**, wing `pgadmin-system` |

- Перед задачей в 2+ шага: `mempalace_search` (wing `pgadmin-system`) → нужный SKILL.md → правила выше.
- После нетривиальной задачи фиксировать результат в mempalace (rooms: `backend-structure`,
  `frontend-structure`, `configuration`, `problems-solved`, `general`/`decisions`).
- Vault для заметок: `D:\Notes\cursor-agent-kb\pgadmin-system\`.

Кратко в конце ответа указывать, что применено (skills / MCP / design-system) — одной строкой.

## Ключевые сервисы backend

| Файл | Назначение |
|------|------------|
| `pg_connection.py` | asyncpg к управляемым серверам |
| `crypto.py` | Fernet-шифрование паролей |
| `backup_service.py` | pg_dump → S3 (per-server) |
| `db_admin_service.py` | DDL на серверах (через Celery) |
| `audit_service.py` | журнал действий |
