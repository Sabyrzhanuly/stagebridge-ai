# Codex task set #5 — streaming assistant + a "magic" AI loader

> Read `AGENTS.md` first, obey every guardrail. Work in branch **`feature/codex-round-5`**.
> This round is about UX polish for the AI layer: a rich animated "thinking" loader for the structured AI cards, and **real token streaming for the AI assistant chat**. Do P0 → P1 in order; after each, run checks, commit (Russian message), append to `docs/CODEX_LOG.md`, add a README round-5 note, and provide the `/feedback` Codex Session ID at the end. Do NOT push / open a PR.
>
> Context: the model is `gpt-5.6-terra` (a reasoning model — reasoning tokens are hidden; only the final answer streams). `_chat` already gives gpt-5* a token headroom of `max(max_tokens*3, 4000)`; keep that behavior for streaming too. `StreamingResponse` is already used in `backend/app/api/backups.py` — copy that pattern.
> Guardrails recap: additive/surgical; no touching migrations/crypto/backup-structure-sync internals; i18n in **all three** locales with parity; AI advisory; model `gpt-5.6-terra`; respect `prefers-reduced-motion`.

---

## P0 — "Magic" thinking loader (all structured AI cards + assistant)

Today the wait state is a plain "ИИ анализирует…" label. Make it feel alive.

**`frontend/src/components/AiInsight.vue`** (used by 8 features — Query Advisor, Lock Analyzer, Config Advisor, Schema Reviewer, Audit Summary, diagnostics, backup risk, migration plan):
- While `loading`, render an animated loader in place of the button label: e.g. a sparkle/shimmer bar plus **rotating status phrases** that cycle every ~1.5s ("Читаю данные…" → "Анализирую…" → "Формирую рекомендации…"). Keep it tasteful, not noisy.
- Add the phrases as i18n arrays/keys under `ai.thinking*` in ru/kk/en (parity). Cycle via a small timer that clears on unmount / when loading ends.
- Respect `@media (prefers-reduced-motion: reduce)` — fall back to a static label, no animation.

**`frontend/src/components/AiAssistant.vue`**: upgrade the current `ai-typing "…"` bubble to a nicer animated typing indicator (three pulsing dots) with the same reduced-motion fallback.

**Tests (Vitest):** loader/animation nodes render while `loading` is true and disappear when a result arrives; reduced-motion path renders the static fallback.

---

## P0 — Real streaming for the AI assistant

The assistant returns plain text (not JSON), so it can stream token-by-token like a real chat.

**Backend**
- `ai_service.py`: add `async def assistant_stream(api_key, model, question, context="", lang="ru")` that yields text chunks. Add a small `_chat_stream` helper mirroring `_chat` (same gpt-5* headroom, same system/user messages) but calling `client.chat.completions.create(..., stream=True)` and `yield`-ing `delta.content` pieces as they arrive. Keep the non-streaming `assistant()` intact as a fallback.
- `api/ai.py`: add `POST /ai/assistant/stream` returning a `StreamingResponse(media_type="text/event-stream")` (copy the pattern from `backups.py`). Emit each text chunk as an SSE `data:` line; end with a terminal event (e.g. `data: [DONE]`). Reuse `_require_key`, and pass `lang`. On any error mid-stream, emit a final SSE error line so the client can show it gracefully.

**Frontend** — `frontend/src/components/AiAssistant.vue`:
- In `send()`, call the stream endpoint with `fetch` (POST) and read `response.body.getReader()` (EventSource can't POST). Append an empty assistant message, then progressively append streamed chunks to it (typewriter effect), scrolling as it grows. Show the typing loader until the first chunk arrives.
- **Graceful fallback:** if the stream request fails or streaming isn't available, fall back to the existing `POST /ai/assistant` non-streaming call. Never leave the chat stuck.
- Keep it working with the language toggle (pass `lang`).

**Tests:** backend — the stream endpoint yields multiple chunks then `[DONE]` with a mocked streaming OpenAI client; a mid-stream error yields an error event. Frontend — a mocked streamed response appends text progressively (or the fallback path fires on error).

---

## P1 — Polish
- Make sure the structured cards (AiInsight) still use the non-streaming endpoints — streaming is only for the free-text assistant. Don't try to stream partial JSON.
- Small a11y pass: the streaming assistant message should be announced politely (aria-live="polite") without spamming.

## Checks before done (run all)
- `cd frontend && npx vue-tsc -b` → 0 errors; `npm test` → pass. `cd backend && python -m pytest -q` → pass.
- Locale parity equal in ru/kk/en; new `ai.thinking*` keys present in all three.
- `docker compose up -d --build backend frontend` boots; assistant streams token-by-token; every structured AI card shows the animated loader then its result; reduced-motion shows static fallbacks.
- All 10 AI features still work; nothing else regressed.

## Done when
- Streaming assistant + animated loaders work end to end, tests + CI green, `docs/CODEX_LOG.md` + README round-5 note updated, left on `feature/codex-round-5`, and the `/feedback` Codex Session ID is provided.
