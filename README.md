# PG Admin System (PG Control Center)

Веб-приложение для управления PostgreSQL-серверами.

> Отдельный проект от [cluster-admin/](../cluster-admin/).  
> В Cursor: **Open Folder → `pgadmin-system`**.

## Стек

| Слой | Технологии |
|------|------------|
| Backend | FastAPI, SQLAlchemy async, Celery, Alembic, Redis, RabbitMQ |
| Frontend | Vue 3, PrimeVue 4, Pinia, Vite, TypeScript |
| Storage | Внешний S3/MinIO (per-server, через UI) |
| Deploy | Docker Compose (7 сервисов) |

## Быстрый старт

```bash
cd pgadmin-system
cp .env.example .env
# Задать FERNET_KEY:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up -d
docker compose exec backend alembic upgrade head
```

| Сервис | URL / порт |
|--------|------------|
| Frontend | http://localhost:80 |
| Backend API | http://localhost:8000/api |
| Health | http://localhost:8000/api/health |
| appdb | localhost:5433 |
| Redis | localhost:6380 |

Бэкапы: подключите внешний S3/MinIO в **Настройки → Хранилище S3** для каждого сервера.

## Разработка frontend (hot reload)

```bash
cd frontend
npm install
npm run dev
```

Прокси `/api` и `/ws` → `localhost:8000` (см. `vite.config.ts`).

## Структура

```
pgadmin-system/
  backend/app/
    api/          — REST + WebSocket
    models/       — SQLAlchemy
    services/     — бизнес-логика
    tasks/        — Celery
  frontend/src/
    views/        — страницы
    components/   — AppLayout, TaskPanel
    stores/       — Pinia
  scripts/        — install, upgrade, backup_self (деплой Control Center)
  docker-compose.yml
```

## Документация для агента

- Skill: `.cursor/skills/pgadmin-system-dev/SKILL.md`
- Rules: `.cursor/rules/`
