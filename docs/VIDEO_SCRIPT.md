# StageBridge AI — demo video script (≤3 min, English, for AI voiceover)

> Record your screen at http://localhost following the storyboard GIF (`stagebridge-demo-storyboard.gif`).
> Generate the voiceover with any TTS (allowed by the rules) from the narration below, then lay it over the screen recording.
> Target length ~2:30. Numbers in [brackets] are approximate timestamps. [ON SCREEN] = what to show.

---

**[0:00] — [ON SCREEN: Dashboard]**
"This is StageBridge AI — an AI-powered control center for PostgreSQL fleets. Servers, backups, migrations, diagnostics and real-time monitoring, all in one place. The idea is simple: deterministic code establishes the facts, and GPT-5.6 explains the risk and the safe next step. The AI advises — it never executes anything on its own."

**[0:20] — [ON SCREEN: Scenarios → structure-sync, open a dry-run, show the generated SQL diff, click "AI migration plan"]**
"Here's the hardest problem in database work — pushing a structure change from test to production. StageBridge computes the exact SQL diff, then GPT-5.6 reads it and returns an overall risk level, the concrete risks, a safe order to apply them, and a rollback plan. Facts from code, judgment from the model."

**[0:50] — [ON SCREEN: server → Diagnostics → click AI analysis]**
"Same pattern for diagnostics: run a health check, and the AI classifies severity and tells you exactly what's wrong and how to fix it."

**[1:05] — [ON SCREEN: Backups → AI backup risk]**
"And before a restore, it weighs the real backup state and flags what to check — for example, when some databases have no fresh backup."

**[1:20] — [ON SCREEN: Monitoring → Slow queries → click "AI: Optimize" → the advisor card]**
"This feature I built with Codex, on GPT-5.6. It's the AI Query Advisor. From live pg_stat_statements monitoring, I pick a slow query, and GPT-5.6 diagnoses it — the problems, suggested CREATE INDEX statements, and how to rewrite it. Codex wrote the whole feature end to end: the FastAPI service, the endpoint, this monitoring UI, and the translations."

**[1:50] — [ON SCREEN: Settings → AI, show "Active model: gpt-5.6"]**
"Every AI feature in the product runs on GPT-5.6 through the OpenAI API. The key is set right here in the UI and stored encrypted — no config files, no restart."

**[2:05] — [ON SCREEN: click the language switcher РУС / ҚАЗ / ENG, toggle once]**
"One more thing — the entire interface ships in three languages: Kazakh, Russian and English, switchable live."

**[2:15] — [ON SCREEN: back to Dashboard]**
"StageBridge AI: real infrastructure, a thin and trustworthy AI layer on GPT-5.6, and Codex in the loop. Thanks for watching."

---

## Recording tips
- **Screen recorder:** Win+G (Xbox Game Bar) or OBS Studio. Record the browser at http://localhost, ~1080p.
- **Voiceover:** paste the narration into a TTS (ChatGPT voice / any TTS), export audio, drop it onto the video timeline (CapCut / Windows "Clipchamp"). Trim to ≤3:00.
- **Upload:** YouTube, visibility **Public** (or Unlisted is also accepted if the link works). Paste the link into Devpost → Project details → Video demo link.
- Keep it tight: cut loading spinners; the AI calls take a few seconds — speed those parts up 1.5–2× in the editor.
