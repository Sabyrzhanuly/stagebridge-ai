# StageBridge AI — Devpost submission (ready to paste)

> Copy each block into the matching Devpost field. Written for OpenAI Build Week judges.
> Everything below describes a **working, live product** — not a mockup.

---

## Project name
**StageBridge AI**

## Tagline (elevator pitch, ~200 chars)
An AI-powered control center for PostgreSQL fleets. Deterministic code computes the facts — schema diffs, backup state, diagnostics — and OpenAI explains the risks and builds a safe, step-by-step plan. Advisory by design.

---

## Inspiration

Every team that runs PostgreSQL hits the same scary moment: pushing a structure change from `test` to `prod`, restoring a backup, or refreshing staging from production. One wrong `ALTER` and you lose data or break the app. Existing admin tools show you *what* changed — but not *whether it's safe* or *in what order to apply it*. That judgment lives in a senior DBA's head.

We wanted to put that judgment into the tool itself — using an LLM the right way: on top of **hard facts**, not vibes.

## What it does

StageBridge AI is a full PostgreSQL fleet control center — servers, backups, restore scenarios, **structure migrations (test → prod)**, diagnostics, and real-time monitoring — with an **AI layer wired into four places**:

1. **AI migration plan** — for a structure-sync dry-run, the AI reads the generated SQL diff and returns an overall risk level, concrete risks (e.g. a new `UNIQUE` constraint failing on existing duplicate rows), a **safe apply order**, and a **rollback plan**.
2. **AI assistant** — a floating panel on every screen; ask "how do I safely move structure from test to prod?" and get a practical, PostgreSQL-aware answer.
3. **AI diagnostics analysis** — after a server health check, the AI classifies severity, says what's wrong (missing roles, ACL issues), and recommends fixes.
4. **AI backup risk analysis** — before a restore, the AI weighs the real backup state ("`demo_shop` has a fresh backup, `demo_prod`/`demo_test` don't → high risk") and lists what to check.

Crucially: **the AI never executes anything.** It's advisory. Real operations run through controlled Celery jobs with approval gates, verification, and an atomic database-name swap for rollback.

The whole thing runs a real stack end-to-end: real PostgreSQL servers, real `pg_dump` to S3/MinIO, real structure migrations with a verify step. It even installs the correct `pg_dump` client version to match each server automatically.

## How we built it

- **Frontend:** Vue 3 + PrimeVue (Pinia, Vite, WebSocket for live task progress).
- **Backend:** FastAPI (async SQLAlchemy), with a metadata DB (`appdb`, Alembic).
- **Task engine:** Celery workers over RabbitMQ run the heavy, irreversible work — `pg_dump`/`pg_restore`, cloning, DDL — while Redis pub/sub streams progress to the UI over WebSocket.
- **Storage:** S3-compatible (MinIO) for backups, configured per-server from the UI.
- **AI layer:** a single `ai_service` calling **OpenAI Chat Completions with JSON-mode structured output**, exposed as `/api/ai/*`. Each feature returns a strict JSON shape (risk / steps / rollback) so the UI renders clean cards, not a wall of text.
- **Key management:** the OpenAI key is entered **in the UI (Settings → AI)** and stored **Fernet-encrypted in the database** — no `.env` edits, no restart, and secrets never sit in plaintext config.

## Challenges we ran into

- **Making the AI trustworthy, not chatty.** We kept the LLM strictly on facts the deterministic engine produces (the SQL diff, the diagnostics report, the backup history) and forced structured JSON output, so the plan is reproducible and the UI is predictable.
- **Real infrastructure is unforgiving.** Getting `pg_dump` to match the server's major version meant building an in-app PostgreSQL client installer (pulls the right `postgresql-client-16` from PGDG on demand).
- **Safety model.** Structure sync clones prod into a temp DB, applies the plan, verifies row counts, waits for approval, then does an **atomic rename swap** — nothing is destroyed until the very last step.

## Accomplishments that we're proud of

- **Four distinct AI touchpoints**, all live against real OpenAI, all returning structured output that renders as clean UI.
- A genuinely **working end-to-end cycle**: analyze → AI plan → approve → migrate/backup → verify — on real databases and real S3 storage.
- **Secure key UX** — set the OpenAI key from the UI, encrypted at rest, hot-applied with no restart.
- The AI actually **reasons about real state** (e.g. flags that two of three databases have no backup) rather than giving generic advice.

## What we learned

The best LLM product is often the thinnest LLM layer: let deterministic systems establish ground truth, then use the model for the part humans are slow at — explaining risk and sequencing safe steps. Structured output turns "a chatbot" into "a feature."

## What's next

- Apply the AI plan back as a guided, approval-gated execution (not just advisory).
- Broaden AI diagnostics to slow-query and lock analysis with concrete remediation.
- Anomaly detection over the live monitoring stream.
- Multi-tenant policies so each org gets its own AI budget and audit trail.

## Built With

`openai` · `python` · `fastapi` · `sqlalchemy` · `celery` · `rabbitmq` · `redis` · `postgresql` · `vue` · `typescript` · `primevue` · `vite` · `docker` · `minio` · `websockets`

---

## Submission checklist (do these on Devpost)

- [ ] Paste the sections above into the matching Devpost fields.
- [ ] **Try it out** links: your live URL (or GitHub repo).
- [ ] **Image gallery** — upload the screenshots we captured this session (dashboard, AI migration plan, AI assistant, AI diagnostics, AI backup risk, Settings → AI). Put the **AI migration plan** shot first — it's the strongest.
- [ ] **Demo video (≤3 min)** — follow `docs/DEMO.md` scenario. Show the AI plan first, narrate "facts from code, risk from AI, nothing auto-executed."
- [ ] **Built With** tags — add the list above.
- [ ] Click **Submit** yourself once it looks right.

## 60-second video script (record with the app open)

1. (0:00) Dashboard — "A control center for PostgreSQL fleets. Real servers, backups, migrations."
2. (0:10) Scenarios → structure-sync history → show generated SQL diff → click **AI migration plan** → read risk / order / rollback. "Diff from code, risk from OpenAI, and it never runs anything itself."
3. (0:35) Diagnostics → **AI analysis**. Backups → **AI backup risk** ("two DBs have no backup → high risk").
4. (0:50) Settings → AI — "key set in the UI, encrypted, no restart." Close on the AI assistant answering a question.
