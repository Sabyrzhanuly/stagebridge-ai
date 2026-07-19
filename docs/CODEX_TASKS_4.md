# Codex task set #4 — NL→SQL explorer + AI audit summary + polish

> Read `AGENTS.md` first, obey every guardrail. Work in branch **`feature/codex-round-4`**.
> Reference patterns to copy: `query_advisor` / `schema_review` in `ai_service.py`, their routes in `api/ai.py` (incl. the `_with_explain_plan` tenant-auth pattern and `schema_review_service.collect_schema_metadata`), and the `AiInsight` component. Do P0 → P1 in order; after each, run checks, commit (Russian message), append to `docs/CODEX_LOG.md`. Add a round-4 note to the README "How Codex & GPT-5.6 were used". Provide the `/feedback` Codex Session ID at the end. Do NOT push / open a PR.
>
> Guardrails recap: additive/surgical; NO touching `alembic/versions/**`, `crypto.py`, backup / structure-sync / `pg_connection.py` internals (you may *call* its read helpers); i18n in **all three** locales with parity; AI answers in the UI language (`lang`); AI is advisory; model `gpt-5.6`; all managed-server DB access **read-only** and **tenant-authorized**.

---

## P0 — Natural-language → SQL explorer (9th AI feature) — SECURITY-CRITICAL

Let a user ask a question in plain language; the AI writes a **read-only SELECT**, the app validates it, runs it safely, and shows the rows. This is the flashiest feature — and the riskiest, so the safety rules below are mandatory and non-negotiable.

**Backend**
- `ai_service.py`: `async def nl_to_sql(api_key, model, question, schema_context, lang="ru")` → JSON: `sql` (string — a single read-only SELECT only), `explanation` (string), `notes` (array). The system prompt MUST instruct: generate exactly one read-only `SELECT` (or `WITH … SELECT`), no DML/DDL, no writes, no multiple statements, and to add a sensible `LIMIT` if none.
- `api/ai.py`: `POST /ai/nl-to-sql` with body `{ server_id, database, question, lang }`. Steps, in order:
  1. **Tenant-authorize**: `get_owned_server` + `ensure_database_access` (copy `_with_explain_plan`).
  2. Build `schema_context` by calling `schema_review_service.collect_schema_metadata` (already bounded/read-only) so the model knows the tables.
  3. Get `sql` from `ai_service.nl_to_sql`.
  4. **Validate the generated SQL with `query_plan_service.is_explainable_query(sql)`** (single SELECT only). If it fails → return `{ sql, explanation, notes, executed: false, reason: "not a safe read-only SELECT" }` and DO NOT execute.
  5. If valid → execute through a **new dedicated safe-runner** (put it in `query_plan_service.py` or a small new module, mirroring `explain_query`): `readonly=True` transaction, `set_config('statement_timeout', ...)` (≤3s), wrap as `SELECT * FROM ( <sql> ) _q LIMIT 100` (hard row cap), `get_target_pool` + `close()` in `finally`. Return `{ sql, explanation, columns, rows (≤100, values truncated), row_count, executed: true, notes }`.
  6. Never execute anything that isn't a validated single SELECT. Never build the outer query by string-concatenating anything except the already-validated `sql`.

**Frontend** — a new **"SQL Explorer"** panel. Simplest placement: a new section on `DatabasesView.vue` (or a new route `/servers/:id/explorer` with a nav item; your call — keep it small). A text input for the question, a **Run** button that posts to `/ai/nl-to-sql`, then shows: the generated SQL (read-only, in a `<code>` block), the `explanation`, and a result table of `rows` (or the "not executed / reason" note). Show the disabled hint when AI is unavailable (reuse the `/ai/status` check pattern). Never auto-run anything destructive — the backend only ever returns SELECT results.

**i18n**: `nlToSql.*` in ru/kk/en (label, action, placeholder for the question, generatedSql, explanation, notExecuted, etc.).

**Backend tests** (mock the OpenAI call): a generated non-SELECT (e.g. `DELETE …`) is rejected with `executed:false`; a valid `SELECT` path returns rows shape; the safe-runner wraps with `LIMIT`. Reuse the mocking approach from `tests/test_ai_api.py`.

---

## P0 — AI Audit Summary (10th AI feature)

Summarize the internal audit log (this is our own `appdb` — read-only, safe).

**Backend**
- `ai_service.py`: `async def audit_summary(api_key, model, payload, lang="ru")` → JSON: `summary`, `highlights` (array — notable actions), `anomalies` (array — suspicious/risky patterns), `notes` (array).
- `api/ai.py`: `POST /ai/audit-summary` (`PayloadIn` or a small model with an optional `limit`). Read the recent audit records via the existing audit read path / `audit_service` (respect tenant/org scoping like the Audit page does — do not leak other orgs' records), cap to the last ~200 entries, compact them, pass to `ai_service.audit_summary`.

**Frontend** — `AuditView.vue`: an **"AI: summarize audit"** action opening `AiInsight` (`endpoint="/ai/audit-summary"`, sections `highlights` / `anomalies` / `notes`, `badge-field="severity"` if you add one, else omit badge).

**i18n**: `auditSummary.*` in ru/kk/en.

---

## P1 — Polish

- **Export from `AiInsight`**: add small "Copy" / "Download .md" buttons on the result card so users can save AI recommendations (and, when a section looks like SQL/indexes, a "Copy SQL" affordance). Keep it unobtrusive; add `common.*` or `ai.*` i18n keys in all three locales.
- **A few more tests**: cover `nl_to_sql` rejection path and `audit_summary` shape (backend); a small `AiInsight` export-button test (frontend). Keep CI green.

---

## Checks before done (run all)
- `cd frontend && npx vue-tsc -b` → 0 errors; `npm test` → pass. `cd backend && python -m pytest -q` → pass.
- Locale parity equal in ru/kk/en; every new `t('nlToSql.*'/'auditSummary.*'/export keys)` present in all three.
- `docker compose up -d --build backend frontend` boots healthy.
- **Security review of NL→SQL:** confirm non-SELECT is never executed, execution is read-only + timeout + LIMIT-capped + tenant-authorized, and no string concatenation beyond the validated SQL.
- Existing 8 AI features + the rest of the app still work; language switching intact.

## Done when
- Both features work end to end, tests + CI green, `docs/CODEX_LOG.md` + README round-4 note updated, left on `feature/codex-round-4`, and the `/feedback` Codex Session ID is provided.
