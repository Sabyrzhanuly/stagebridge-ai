# DB CONTROL CENTER — FULL TECHNICAL SPEC (V2)

## 1. Цель системы

Создать самодостаточный сервис управления PostgreSQL:
- доступы
- бэкапы
- восстановление
- мониторинг
- аудит
- прогресс задач (real-time)

---

## 2. Архитектура

Frontend (Vue 3)
↓
Backend API (FastAPI)
↓
Queue (RabbitMQ)
↓
Workers (Celery)
↓
PostgreSQL (managed) / внешний S3

Redis:
- Pub/Sub (events)
- cache (metrics)

---

## 3. Основные модули

### 3.1 Auth + RBAC
Роли:
- admin
- dba
- devops
- operator
- viewer

Права:
- manage_servers
- manage_roles
- run_backup
- run_restore
- dangerous_ops (prod)

---

### 3.2 Environments

Каждый сервер:
- dev
- test
- staging
- production

Политики:
- prod restore → approval required
- prod delete → forbidden

---

### 3.3 Servers

CRUD серверов PostgreSQL:
- host
- port
- ssl
- credentials (encrypted)

---

### 3.4 Roles / Users

Функции:
- create user
- delete user
- grant roles
- revoke roles

Templates:
- readonly
- readwrite
- admin

---

### 3.5 Databases

- list databases
- create
- drop
- connection control

---

## 4. Backup System

### 4.1 Stages

queued
preparing
dumping
compressing
uploading
verifying
completed
failed

---

### 4.2 Flow

1. lock connections (optional)
2. pg_dump
3. compress
4. upload to S3 (хранилище сервера, UI «Настройки → Хранилище S3»)
5. checksum
6. save metadata

---

### 4.3 Storage

Внешний S3-compatible storage (per-server через UI):
bucket — из настроек хранилища

path:
server/db/timestamp.dump

---

### 4.4 Retention

- daily: 7
- weekly: 4
- monthly: 3

---

## 5. Restore System

### Flow

1. approval check
2. lock db
3. terminate sessions
4. pg_restore
5. unlock db

---

### Safety

- restore to staging first (optional)
- dry-run mode

---

## 6. Progress System (ВАЖНО)

### Events

{
  "type": "backup_progress",
  "task_id": "uuid",
  "stage": "dumping",
  "progress": 45,
  "message": "Dumping users"
}

---

### Sources

- pg_dump parsing
- file upload bytes
- pg_restore logs

---

### Transport

Worker → Redis Pub/Sub → WebSocket → UI

---

### UI

Bottom Task Panel:
- progress bars
- statuses
- cancel button
- expand details

---

## 7. Monitoring

- active connections
- slow queries
- locks
- db size

cache:
Redis (TTL 120s)

---

## 8. Audit

Fields:
- user_id
- action
- entity
- payload
- result
- timestamp

---

## 9. Notifications

Channels:
- Telegram
- Email

Events:
- backup success/fail
- restore start/end
- alerts

---

## 10. Approval System

Flow:
user → request → admin approve → execute

---

## 11. Worker Requirements

- retry policy
- cancel support
- task locks (1 db = 1 task)
- structured logs
- progress events

---

## 12. DevOps

### Scripts

install.sh
upgrade.sh
backup_self.sh
restore_self.sh

---

### Docker services

- frontend
- backend
- worker
- scheduler
- redis
- rabbitmq
- appdb (meta)

---

## 13. Security

- Fernet encryption
- .env secrets
- RBAC
- audit log

---

## 14. Future

- multi cluster
- auto restore dev from prod
- grafana
- metrics API

---

## 15. Acceptance Criteria

- backup with live progress
- restore with approval
- role management
- audit log visible
- notifications working
- system health page
