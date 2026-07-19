# Codex task set #2 — deepen Codex usage (round 2)

> Read `AGENTS.md` first and obey every guardrail. Work in a branch **`feature/codex-round-2`**.
> Goal of this round: make Codex's footprint broad and substantial — new features, tests, and CI — so the "Technological Implementation" judging criterion (how thoroughly the project uses Codex) is strong. Do real, working, verified work; don't stub.
>
> **Do the tasks in priority order (P0 → P2).** After each task: run the checks, commit with a clear Russian message. Keep a running list of what you did in `docs/CODEX_LOG.md` (create it) — file paths + one line each — so the README can cite it.
>
> Guardrails recap (from AGENTS.md): additive/surgical only; do NOT touch `alembic/versions/**`, `crypto.py`, backup / structure-sync / `pg_connection.py` internals; every new UI string goes into **all three** locales (ru/kk/en) with key parity; AI must answer in the UI language (pass `lang`, backend already supports it); AI is advisory — never executes anything. Model stays `gpt-5.6`.

---

## P0 — AI Lock Analyzer (6th AI feature)

Mirror the existing **AI Query Advisor** exactly (that's the reference implementation to copy).

**Backend**
- `backend/app/services/ai_service.py`: add `async def lock_analysis(api_key, model, payload, lang="ru")` following the same shape as `query_advisor`. JSON contract:
  `severity ('ok'|'warning'|'critical')`, `summary` (string), `blocking_chains` (array of strings — who blocks whom), `recommendations` (array), `notes` (array). Advisory only.
- `backend/app/api/ai.py`: add `POST /ai/lock-analysis` using the existing `PayloadIn` (already has `lang`), calling `ai_service.lock_analysis`.

**Frontend** — `frontend/src/views/MonitoringView.vue`, the **Waiting locks** panel (`snapshot.locks`, type in `api/types.ts`: `{pid, relation, mode, granted, query, wait_duration?}`):
- Add an **"AI: analyze locks"** action above/near the locks table that opens an `AiInsight` card (reuse the component exactly like the Query Advisor does).
- `endpoint="/ai/lock-analysis"`, `badge-field="severity"`, sections = `blocking_chains` / `recommendations` / `notes`.
- `payload` = `{ payload: JSON.stringify({ locks: snapshot.locks, collected_at, source }) }`.
- Only show the action when `snapshot.locks.length > 0` (empty state stays as-is). Don't break the responsive-stack layout.

**i18n** — add `lockAnalysis.*` to `ru/kk/en`: `label`, `action`, `secBlocking`, `secRecommendations`, `secNotes` (kk = literary Kazakh; en = clean English). Badge labels reuse the existing `ai.*` severity keys.

**Checks:** `npx vue-tsc -b` (0 errors); locale parity equal in ru/kk/en; `docker compose up -d --build backend frontend` boots; endpoint returns JSON (POST needs auth → 401 unauth is fine as a route-exists check).

---

## P1 — Backend tests (pytest)

There are currently **no tests**. Add a real, passing test suite. This is graded as "genuine effort / non-trivial implementation".

- Create `backend/tests/` with `test_ai_service.py` and `test_ai_api.py`.
- Add `pytest`, `pytest-asyncio`, `anyio` (as needed) to `backend/requirements.txt` (httpx is already present).
- **Pure-function tests (no network):** `ai_service._lang()` maps ru/kk/en correctly and falls back to ru; `ai_service._safe_json()` parses valid JSON and wraps invalid text as `{summary, raw:true}`; `ai_service._retry_chat_kwargs()` swaps `max_tokens`↔`max_completion_tokens` and strips `temperature`/`response_format` on a simulated 400 "unsupported parameter" error, and returns `None` on unrelated errors.
- **API tests with the OpenAI call mocked** (monkeypatch `ai_service._chat` / `_create_chat_completion` so no real key is needed): `POST /api/ai/query-advisor` and `/api/ai/lock-analysis` return the expected JSON keys; `GET /api/ai/status` reports `available:false` when no key is configured. Use FastAPI's `TestClient`/`httpx.AsyncClient`; stub auth dependency if required.
- **Run:** `cd backend && python -m pytest -q` must pass. Put the exact command in `docs/CODEX_LOG.md`.

---

## P1 — GitHub Actions CI

Create `.github/workflows/ci.yml` that runs on push/PR to `main`:
- **frontend job:** `cd frontend && npm ci && npx vue-tsc -b` (type-check).
- **backend job:** `cd backend && pip install -r requirements.txt && python -m pytest -q` (or `python -m py_compile` over `app/**` if pytest deps are heavy — prefer pytest).
- Keep it lean (ubuntu-latest, Node 20, Python 3.11). Add a `![CI](…/actions/workflows/ci.yml/badge.svg)` badge line near the top of `README.md`.

---

## P2 — EXPLAIN-grounded Query Advisor (upgrade, optional but high-value)

Make the Query Advisor reason about the **real plan**, not just the SQL text.
- Backend: for the query-advisor request, if a concrete server + query is available, run **`EXPLAIN (FORMAT JSON)`** (WITHOUT `ANALYZE`, so nothing executes) via the existing read path, with a short statement_timeout, **only for `SELECT`/`WITH` queries**. Feed the plan JSON into `ai_service.query_advisor` as extra context. If EXPLAIN fails or the query isn't a SELECT, silently fall back to the current text-only behavior.
- Guardrail: read-only, no `ANALYZE`, no writes, timeout-bounded; do not touch the managed-connection internals beyond issuing the EXPLAIN. Demo server is `demopg`.
- Update the advisor prompt to use the plan when present ("prefer evidence from the plan").

## P2 — Realistic slow-query seed for the demo

- Add `scripts/seed_slow_queries.sh` (and/or an `infra/demopg-init` seed) that creates a couple of un-indexed tables in `demo_shop` with enough rows and runs a few genuinely slow queries (missing-index seq scans, unindexed JOINs) so the Monitoring "Slow queries" list and the AI Query Advisor demo look realistic (not just `generate_series`). Document it in the README/DEMO.

---

## When done
- All checks green (`vue-tsc`, `pytest`, `docker compose up --build`), locale parity intact, existing 5 AI features + the rest of the app still work.
- `docs/CODEX_LOG.md` lists every change (feature → files touched → one line).
- Append a short, **honest** note to the README's "How Codex & GPT-5.6 were used" section listing the round-2 work (Lock Analyzer, tests, CI, EXPLAIN grounding).
- Do **not** `git push` or open a PR — leave it on `feature/codex-round-2` for the owner to review.
- Provide the **`/feedback` Codex Session ID** for this round.
