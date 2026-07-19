# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

StageBridge AI is a hackathon MVP that analyzes PostgreSQL schema compatibility between a
production and a development database. It inspects both catalogs, diffs them, runs read-only
preflight data checks against production, and produces an advisory (never executed) remediation
plan via OpenAI or a deterministic mock. Backend is Django REST Framework; frontend is Vue 3 + Pinia.

## Commands

Run backend commands from `backend/`, frontend commands from `frontend/`. On Windows use the
project virtualenv: `.\.venv\Scripts\python`. A `Makefile` and `scripts-dev.ps1` wrap the common ones.

```powershell
# Backend (Python 3.12)
.\.venv\Scripts\python -m pytest                          # all backend tests
.\.venv\Scripts\python -m pytest backend/analysis/tests/test_preflight_and_actions.py   # one file
.\.venv\Scripts\python -m pytest -k dry_run               # one test by keyword
.\.venv\Scripts\python backend\manage.py check            # Django system check
.\.venv\Scripts\python backend\manage.py migrate          # apply migrations

# Frontend (Node 22)
npm run typecheck        # vue-tsc --noEmit (also runs as part of build)
npm run build            # type-check + vite build
npm run test:i18n        # enforce the i18n locale-parity contract (see below)
npm run dev              # vite dev server on 0.0.0.0:5173

# Full stack
docker compose up --build            # UI :5173, API :8000, PostgreSQL :55432
docker compose down -v && docker compose up --build   # reset seeded demo databases
```

`pytest` is configured in `backend/pytest.ini` with `DJANGO_SETTINGS_MODULE=stagebridge.settings`
(no pytest-django plugin config needed beyond that). There is no linter/formatter configured.

## Architecture

### Two analysis modes
The entire system branches on `AnalysisRun.mode`:
- **`demo`** — uses the four seeded PostgreSQL databases (`stagebridge_prod/dev/stage/dryrun`),
  filters conflicts to a fixed `DEMO_CATEGORIES` set, and is the **only** mode that can run the
  dry-run executor.
- **`live`** — user-configured `ConnectionProfile` connections. Strictly **report-only**: it
  inspects, diffs, and previews SQL but never executes DDL/DML and cannot enter the dry run.

### Backend request flow (all logic lives in `backend/analysis/`)
`views.py` (function-based DRF views) → `services/` (all business logic) → `models.py`.
Views stay thin: they validate input, resolve locale, call a service, and serialize.

Analysis pipeline (`services/analysis_service.py::run_schema_analysis`):
1. `connections.py` opens read-only connections (demo target or live profile).
2. `schema_inspector.py` builds a catalog snapshot per side (tables, columns, constraints, indexes, enums, sequences).
3. `diff_engine.py::detect_conflicts` produces `Conflict` objects; when preflight is enabled it
   invokes `preflight.py::PreflightRunner` **against the production connection only** to count/sample affected rows.
4. Metrics + report are built and persisted; failures are caught and stored on the run (status `failed`).

AI plan (`services/ai_provider.py`): `get_provider_plan` picks OpenAI vs mock based on
`OPENAI_API_KEY`. Both return a Pydantic `RemediationPlanModel` (`services/types.py`). Each recommended
action is validated against the `ALLOWED_ACTION_TYPES` allowlist (`services/actions.py`) and stored as
`ApprovedAction`. Actions requiring approval start unapproved. OpenAI uses the Responses API with
strict `json_schema` structured output — the system prompt forbids returning executable SQL.

Dry run (`services/dry_run.py`, demo-only): resets `stagebridge_dryrun`, applies the dev schema,
loads production rows through the approved-action templates, and records `DryRunLog` steps. It is the
one place that writes to a database, and only ever to `stagebridge_dryrun`.

### Safety invariants (do not break these)
- Live/demo inspection connections are opened read-only (`SET TRANSACTION READ ONLY` /
  `default_transaction_read_only`) with a statement timeout. Live analysis never writes.
- All dynamic SQL identifiers go through `psycopg.sql` composition + `validate_identifier`
  (`services/preflight.py`); never string-format an identifier into SQL.
- Non-local DB hosts are blocked unless `ALLOW_EXTERNAL_DB_HOSTS=1` (`connections.py::assert_host_allowed`).
- The API never returns connection passwords.
- New remediation actions must be added to **both** the OpenAI prompt's `allowed_action_types` list
  and `ALLOWED_ACTION_TYPES` in `services/actions.py`, plus a `render_sql_preview` branch.

### Localization (bilingual backend + trilingual UI, ru default)
Locales are `ru` (default), `en` (fallback), `kk`. Locale is resolved per-request in
`services/localization.py::request_locale` from the body `locale`, `?locale=`, or `Accept-Language`.
**All user-facing backend strings must go through `translate`/`translate_list`** — the message
catalog is the big `MESSAGES` dict in `localization.py`; there are no `.po` files. The chosen locale
is also injected into the AI system prompt so plan explanations come back in that language.

Frontend locale (`frontend/src/i18n/`) is persisted in `localStorage` and sent on every request via
an axios `Accept-Language` interceptor (`src/api.ts`). The three JSON locale files must stay in exact
key parity — `npm run test:i18n` enforces identical leaf keys, required namespaces, and language names.
When adding/removing a UI string, update `en.json`, `ru.json`, and `kk.json` together.

### Frontend structure
Vue 3 (Composition API, `<script setup>`) + Pinia. All server state and API calls funnel through the
single store `src/stores/stagebridge.ts`; components/views should call store actions, not `api` directly.
`src/api.ts` is a shared axios instance whose `baseURL` is `VITE_API_BASE_URL || '/api'` (Vite proxies
`/api` to the backend in dev). Views in `src/views/`, presentational pieces in `src/components/`.

## Configuration

Copy `.env.example` to `.env`. Key vars: `OPENAI_API_KEY` (empty → mock provider),
`OPENAI_MODEL` (required only when the key is set), `PROD_DB_*`/`DEV_DB_*`/`STAGE_DB_*`/`DRYRUN_DB_*`
(fall back to `POSTGRES_*`), `PG_STATEMENT_TIMEOUT_MS`, `ALLOW_EXTERNAL_DB_HOSTS`.
The backend metadata DB defaults to SQLite (`backend/db.sqlite3`); set `BACKEND_DB_ENGINE=postgres`
to switch. CORS is handled by a custom `analysis.middleware.SimpleCorsMiddleware`, not django-cors-headers.

## Known constraints (MVP)
- Connection-profile passwords are stored **unencrypted** at rest — use low-privilege read-only DB users.
- Dry run is intentionally limited to the seeded demo schemas; live analyses are report-only.
- Structural changes without a bounded generic data query are labeled `unsupported_preflight` for manual review.
- The backend container runs the Django dev server.
