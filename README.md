# StageBridge AI

**An AI-powered control center for PostgreSQL fleets.** Deterministic code computes the facts — schema diffs, backup state, diagnostics — and OpenAI explains the risks and builds a safe, step-by-step plan. **Advisory by design: the AI never executes anything.**

> Built for the OpenAI hackathon. A working, live product — not a mockup.

**Stack:** FastAPI · Celery · RabbitMQ · Redis · PostgreSQL · MinIO/S3 · Vue 3 + PrimeVue · OpenAI · Docker Compose
**Languages:** the entire UI ships in **Kazakh 🇰🇿 / Russian 🇷🇺 / English 🇬🇧** (vue-i18n, switch live in the top bar).

---

## Why

Every team running PostgreSQL hits the same scary moment: pushing a structure change from `test` to `prod`, restoring a backup, or refreshing staging from production. One wrong `ALTER` and you lose data or break the app. Existing admin tools show you *what* changed — not *whether it's safe* or *in what order to apply it*. That judgment lives in a senior DBA's head.

StageBridge AI puts that judgment into the tool — using an LLM the right way: **on top of hard facts, not vibes.**

## The AI layer (five touchpoints)

1. **AI migration plan** — for a structure-sync dry-run, the AI reads the generated SQL diff and returns an overall risk level, concrete risks (e.g. a new `UNIQUE` constraint failing on existing duplicate rows), a **safe apply order**, and a **rollback plan**.
2. **AI assistant** — a floating panel on every screen; ask *"how do I safely move structure from test to prod?"* and get a practical, PostgreSQL-aware answer.
3. **AI diagnostics analysis** — after a server health check, the AI classifies severity, says what's wrong (missing roles, ACL issues), and recommends fixes.
4. **AI backup risk analysis** — before a restore, the AI weighs the real backup state (*"`demo_shop` has a fresh backup, `demo_prod`/`demo_test` don't → high risk"*) and lists what to check.
5. **AI Query Advisor** — from Monitoring → Slow queries, the AI reads a selected `pg_stat_statements` query and returns advisory-only optimization notes, suggested `CREATE INDEX ...` statements, and rewrite ideas.

Every feature calls **OpenAI Chat Completions with JSON-mode structured output**, so the UI renders clean risk/steps/rollback cards instead of a wall of text. The OpenAI key is entered **in the UI (Settings → AI)** and stored **Fernet-encrypted in the database** — no `.env` edits, no restart, secrets never in plaintext.

## How Codex & GPT-5.6 were used

In this session, Codex added the AI Query Advisor feature end to end: the FastAPI service method and `/api/ai/query-advisor` route, the Monitoring slow-query action and `AiInsight` card, matching kk/ru/en translations, and this README update. The application now defaults AI calls to `gpt-5.6`; at runtime, GPT-5.6 is used only for advisory responses when a user-provided OpenAI key is configured in Settings → AI.

## The safety model

The AI is advisory; real work runs through controlled Celery jobs. Structure sync clones prod into a temp DB, applies the plan, **verifies row counts, waits for approval, then does an atomic rename swap** — nothing is destroyed until the very last step. Real `pg_dump` → S3/MinIO, and the app even installs the matching `postgresql-client` major version for each server on demand (from PGDG).

## Architecture

| Layer | Tech |
|------|------|
| Frontend | Vue 3 (`<script setup>`), PrimeVue, Pinia, Vite, TypeScript, vue-i18n (kk/ru/en), WebSocket for live task progress |
| Backend | FastAPI (async SQLAlchemy + asyncpg), Alembic, Pydantic v2, Fernet |
| Task engine | Celery workers over RabbitMQ; Redis pub/sub streams progress → WebSocket |
| AI | single `ai_service` → OpenAI Chat Completions (JSON mode), exposed at `/api/ai/*` |
| Storage | S3-compatible (MinIO), configured per-server from the UI |
| Deploy | Docker Compose — 9 services |

`appdb 5433 · redis 6380 · rabbitmq 5672/15672 · backend 8000 · worker · scheduler · frontend 80 · minio 9000/9001 · demopg` (demo server with sample databases).

## Quick start

```bash
cp .env.example .env
# Generate a Fernet key for encrypting server passwords:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Put it in FERNET_KEY, then:

docker compose up -d --build
```

Open **http://localhost** — a demo PostgreSQL server with sample databases is provisioned automatically.

To enable the AI features: **Settings → AI**, paste your OpenAI API key, Save. (Stored encrypted; applied instantly, no restart.)

### Frontend dev (hot reload)

```bash
cd frontend && npm install && npm run dev
```

Vite proxies `/api` and `/ws` → `localhost:8000`.

## Project layout

```
backend/app/
  api/          — REST + WebSocket (incl. ai.py)
  services/     — business logic (ai_service, backup_service, schema_diff_service, …)
  tasks/        — Celery (backup, structure_sync, diagnostics, …)
  models/ schemas/ alembic/
frontend/src/
  views/        — pages
  components/   — AppLayout, TaskPanel, AiAssistant, AiInsight, LangSwitcher
  i18n/locales/ — kk.json / ru.json / en.json (full UI coverage)
  stores/       — Pinia (tasks over WebSocket)
docker-compose.yml
docs/           — DEMO.md, DEVPOST_SUBMISSION.md, pitch.html
```

## Demo & pitch

- `docs/DEMO.md` — end-to-end demo scenario.
- `docs/DEVPOST_SUBMISSION.md` — full write-up.
- `docs/pitch.html` — one-page pitch with screenshots.

## What's next

Apply the AI plan back as a guided, approval-gated execution · broaden diagnostics to slow-query/lock analysis · anomaly detection over the live monitoring stream · per-org AI budgets and audit trail.

## Built with

`openai` · `python` · `fastapi` · `sqlalchemy` · `celery` · `rabbitmq` · `redis` · `postgresql` · `vue` · `typescript` · `primevue` · `vite` · `docker` · `minio` · `websockets`
