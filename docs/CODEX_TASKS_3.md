# Codex task set #3 — two more DBA AI tools + frontend tests

> Read `AGENTS.md` first, obey every guardrail. Work in branch **`feature/codex-round-3`**.
> Goal: broaden Codex's footprint further (judging criterion "Technological Implementation") with two genuinely useful, **read-only** DBA features and a real frontend test setup. Mirror the existing AI features exactly — `query_advisor` / `lock_analysis` in `ai_service.py`, their routes in `api/ai.py`, and the `AiInsight` component are the reference patterns to copy.
>
> Do P0 → P1 in order. After each: run checks, commit (Russian message), append to `docs/CODEX_LOG.md`. At the end, add a short honest note to the README "How Codex & GPT-5.6 were used" round-3 line and provide the `/feedback` Codex Session ID.
>
> Guardrails recap: additive/surgical; NO touching `alembic/versions/**`, `crypto.py`, backup / structure-sync / `pg_connection.py` **internals** (you may *call* its read helpers); every new UI string in **all three** locales (ru/kk/en) with parity; AI answers in the UI language (pass `lang`; backend already supports it); AI is advisory — never executes anything; model stays `gpt-5.6`. All new DB reads must be **read-only** and **tenant-authorized** (reuse `get_owned_server` + `ensure_database_access` exactly like `_with_explain_plan` in `api/ai.py`).

---

## P0 — AI Config Advisor (7th AI feature)

Advise on PostgreSQL configuration. Read-only.

**Backend**
- `ai_service.py`: `async def config_advisor(api_key, model, payload, lang="ru")` → JSON: `severity ('ok'|'warning'|'critical')`, `summary`, `findings` (array), `recommendations` (array — concrete `SET`/`postgresql.conf` suggestions, advisory only), `notes` (array). Same `_chat(..., json_mode=True)` + `_safe_json` pattern.
- `api/ai.py`: `POST /ai/config-advisor` using `PayloadIn`. The frontend sends the relevant settings in `payload`, so no new DB read is strictly required — but if you prefer, read a curated set server-side via the existing `pg_config_service` helpers (read-only) using the tenant-authorized server lookup.

**Frontend** — `frontend/src/views/PgConfigView.vue`:
- Add an **"AI: review config"** action that opens an `AiInsight` card (reuse the component; `endpoint="/ai/config-advisor"`, `badge-field="severity"`, sections = `findings` / `recommendations` / `notes`).
- `payload` = a compact JSON of the key settings already shown on this screen (e.g. `shared_buffers`, `work_mem`, `maintenance_work_mem`, `effective_cache_size`, `max_connections`, `random_page_cost`, `wal_*` if available) plus, if easy, current connections and cache-hit from monitoring. Keep it small.

**i18n**: `configAdvisor.*` in ru/kk/en (`label`, `action`, `secFindings`, `secRecommendations`, `secNotes`). Badge labels reuse `ai.*`.

---

## P0 — AI Schema Reviewer (8th AI feature)

Review a database's schema for common design problems. Read-only.

**Backend**
- New read-only helper (e.g. in a new `schema_review_service.py`, or extend an existing read service — do NOT modify `schema_diff_service`/`db_admin_service` behavior): collect compact schema metadata for one database via read-only queries against `information_schema` / `pg_catalog` (tables + row estimates, columns with types & nullability, primary keys, foreign keys, indexes). **Cap the size** — top N tables by size/rows (e.g. 40) and truncate — so the payload stays small.
- `ai_service.py`: `async def schema_review(api_key, model, payload, lang="ru")` → JSON: `severity`, `summary`, `issues` (array — e.g. "table X has no primary key", "FK Y.z has no supporting index", "column uses text where an enum/smallint fits"), `recommendations` (array — advisory DDL suggestions), `notes` (array).
- `api/ai.py`: `POST /ai/schema-review` accepting `server_id` + `database` (+ `lang`) in the body; **tenant-authorize** with `get_owned_server` + `ensure_database_access` (copy the pattern from `_with_explain_plan`). Read the schema via the new helper, pass it to `ai_service.schema_review`.

**Frontend** — `frontend/src/views/DatabasesView.vue`:
- Add a per-row **"AI: review schema"** action (or a panel below the table for the selected DB) that opens `AiInsight` with `endpoint="/ai/schema-review"`, sections `issues` / `recommendations` / `notes`, `badge-field="severity"`, and `payload = { server_id, database, lang }`.

**i18n**: `schemaReview.*` in ru/kk/en (`label`, `action`, `secIssues`, `secRecommendations`, `secNotes`).

**Safety:** only SELECTs against catalog/information_schema; no writes; bounded size; short statement_timeout; reuse the read connection helpers (`get_target_pool` + close in `finally`, like `query_plan_service`).

---

## P1 — Frontend tests (Vitest) + CI extension

There are currently **no frontend tests**. Add a real setup.
- Add dev deps: `vitest`, `@vue/test-utils`, `jsdom`, `@vitest/coverage-v8`. Add `"test": "vitest run"` (and `"test:watch": "vitest"`) to `frontend/package.json`. Configure Vitest (jsdom env) — either in `vite.config.ts` (`test:` block) or a `vitest.config.ts`.
- Write meaningful component/unit tests:
  - `AiInsight.vue`: renders the run button; on a mocked `api.post` success, renders `summary` + section items + severity badge; shows the disabled hint when `/ai/status` reports unavailable; **posts `lang` from the current locale**.
  - `LangSwitcher.vue`: renders РУС/ҚАЗ/ENG and calls `setLang` on click.
  - utils: `utils/tags.ts`, `utils/pgHealth.ts`, `utils/format.ts` — pure-function assertions.
  Mock `../api/client` and `vue-i18n` where needed.
- **Extend CI** (`.github/workflows/ci.yml`): in the frontend job add `npm test` after the type-check. Keep it green.

---

## Checks before done (run all)
- `cd frontend && npx vue-tsc -b` → 0 errors; `npm test` → all pass.
- `cd backend && python -m pytest -q` → still all pass (add backend tests for the two new pure prompt-builders / `_safe_json` shapes if convenient).
- Locale parity: equal key counts ru/kk/en; every new `t('configAdvisor.*' / 'schemaReview.*')` present in all three.
- `docker compose up -d --build backend frontend` boots; `docker compose ps` healthy.
- Manual: PG configuration → **AI: review config** returns a card; Databases → **AI: review schema** returns a card (needs an OpenAI key with gpt-5.6 access set in Settings → AI). Existing 6 AI features + the rest of the app still work; language switching intact.
- No writes ever issued to managed servers; all new reads tenant-authorized and read-only.

## Done when
- Both features work end to end, frontend tests + CI green, `docs/CODEX_LOG.md` updated, README round-3 note added.
- Do **not** push or open a PR — leave it on `feature/codex-round-3` for the owner to review.
- Provide the `/feedback` Codex Session ID.
