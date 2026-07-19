# StageBridge AI — demo video script (≤ 3:00)

> Record the browser at http://localhost, ~1080p. Generate the voiceover from the **Narration** with any TTS and lay it over the screen recording.
> Target ~2:45. `[m:ss]` = approx timestamp · **[ON SCREEN]** = what to show · **Narration** = what the voice says.
> Default voiceover language: **English** (judges). Kazakh/Russian variants: translate the narration 1:1 — timings hold.
> Golden rule of the demo: **deterministic code establishes the facts, GPT-5.6 explains the risk and the safe next step. The AI advises — it never executes on its own.**

---

**[0:00] — [ON SCREEN: Dashboard with the PostgreSQL fleet]**
Narration: "This is StageBridge AI — a control center for a fleet of PostgreSQL servers. One console for access, backups, restore, migrations, monitoring and audit. And GPT-5.6 is built into every one of those screens."

**[0:12] — [ON SCREEN: open a server → metric cards. Toggle the language switcher РУС → ҚАЗ → ENG]**
Narration: "The whole interface is trilingual — Russian, Kazakh, English. And it's not just the menus: the AI answers in whatever language the interface is set to."

**[0:28] — [ON SCREEN: Monitoring → click a slow query → the AI panel auto-runs, animated loader, then a card with a risk badge]**
Narration: "Here's the first AI touchpoint. I pick a slow query — the Query Advisor builds a real EXPLAIN plan on the server, hands it to GPT-5.6, and the model explains the bottleneck and proposes an index. The advice is grounded in the actual plan, not a guess."

**[0:50] — [ON SCREEN: same page — Lock Analyzer panel explaining a blocking chain; then PG Config → Config Advisor card]**
Narration: "Next to it — a lock analyzer: who is blocking whom and what to do about it. And a configuration advisor that reads the server's postgresql settings and suggests safe changes."

**[1:08] — [ON SCREEN: Databases → SQL Explorer. Type in plain Russian, click Run → the generated SQL appears nicely formatted, then a results table]**
Narration: "Natural language to SQL. I type a question in plain words — GPT-5.6 generates the query and shows it formatted. But the safety is strict: only a single SELECT runs, in a read-only transaction, with a timeout and a row limit. It never modifies data."

**[1:30] — [ON SCREEN: in a database row click "AI: review schema" → panel auto-runs → issues / recommendations / notes]**
Narration: "The schema reviewer takes a read-only snapshot of the structure and finds design problems — missing indexes, risky types, anti-patterns."

**[1:46] — [ON SCREEN: open the floating AI Assistant, ask a question → the answer streams in token by token]**
Narration: "Running through the whole product is an assistant. The answer streams in, word by word — a genuinely live conversation about your database. The same layer builds migration plans, diagnostics, and pre-backup risk assessments."

**[2:06] — [ON SCREEN: Scenarios → structure-sync run showing "awaiting swap approval" → click Approve; then Audit → AI summary]**
Narration: "Dangerous operations require an explicit confirmation: an atomic database swap only happens on a button press. And the audit log is folded by the AI into a short summary — what happened and what to watch."

**[2:24] — [ON SCREEN: GitHub — commits, green CI badge, AGENTS.md file, tests folder]**
Narration: "How it's built. Six of these AI features were written with Codex — the Query Advisor, lock analyzer, config advisor, schema reviewer, natural-language-to-SQL, and audit summary. Codex worked under the guardrails in AGENTS.md: read-only, additive-only. Plus sixty-three automated tests and CI on GitHub Actions. Every model call is GPT-5.6."

**[2:50] — [ON SCREEN: back to Dashboard, logo, repo URL]**
Narration: "StageBridge AI — PostgreSQL under control, with GPT-5.6 behind every decision. Thanks for watching."

---

## Coverage checklist (nothing skipped)
All 10 AI touchpoints: **migration plan · assistant (streaming) · diagnostics · backup risk · Query Advisor (EXPLAIN-grounded) · Lock Analyzer · Config Advisor · Schema Reviewer · NL→SQL Explorer · Audit summary** · trilingual UI **and** AI answers (kk/ru/en) · safety model (advisory · read-only NL→SQL · atomic swap on confirmation) · honest Codex/GPT-5.6 story (6 features via Codex, AGENTS.md, 63 tests, CI).

## Recording tips
- **Recorder:** OBS Studio or Win+G. Browser at http://localhost, ~1080p.
- **Cut the waiting:** AI calls take a few seconds — speed those segments 1.5–2× in the editor so the demo stays under 3:00.
- **Voiceover:** paste Narration into a TTS, export audio, lay it on the timeline (Clipchamp / CapCut), trim to ≤ 3:00.
- **Upload:** YouTube (Public or working Unlisted) → paste the link into Devpost → Project details → Video demo link.
