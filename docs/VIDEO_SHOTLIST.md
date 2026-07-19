# StageBridge AI — executable demo-video plan (for a coding agent)

Goal: produce a **≤3-minute MP4** demo of StageBridge AI with **English voiceover**, ready to upload to YouTube for the OpenAI Build Week submission.

**Approach (fully automatable from a terminal):**
1. **Record** the walkthrough with **Playwright** (it records video of the browser context natively → `.webm`).
2. **Generate voiceover** per segment with a TTS API → `.mp3` files.
3. **Assemble** with **ffmpeg**: convert webm→mp4, concatenate the narration, mux audio over video, trim to ≤3:00.
4. Output `stagebridge-demo.mp4`.

> Do NOT hardcode secrets. Read the login password from `.env` (`SUPER_ADMIN_PASSWORD`). Never print it or commit it.

---

## 0. Prerequisites (already true on this machine, verify only)

- App running: `docker compose ps` → all up. Frontend at **http://localhost**, backend at **http://localhost:8000**.
- OpenAI key with **gpt-5.6** access is set in Settings → AI (Active model must read `gpt-5.6`).
- Demo server exists at route `/servers/1/monitoring`, `pg_stat_statements` enabled (Slow queries table is populated).
- Login: username `admin`, password from `.env` → `SUPER_ADMIN_PASSWORD`.

If Slow queries is empty, run this once to generate load:
```bash
docker compose exec -T demopg psql -U postgres -d demo_shop -c "SELECT count(*) FROM generate_series(1,500000) g; SELECT g, md5(g::text) FROM generate_series(1,200000) g ORDER BY md5(g::text) LIMIT 5;"
```

---

## 1. Shot list (screen ↔ voiceover, ~2:20 total)

Each row: what the recorder does on screen, how long to hold, and the exact English narration for that segment. Narration total ≈ 340 words ≈ 2:20 at a calm pace.

| # | Screen / action | Hold | Voiceover (English) |
|---|---|---|---|
| 1 | **Dashboard** (`/`). Show the server list + stat cards. | 16s | "This is StageBridge AI — an AI-powered control center for PostgreSQL fleets. Servers, backups, migrations, diagnostics and real-time monitoring in one place. The principle: deterministic code establishes the facts, and GPT-5.6 explains the risk and the safe next step. The AI advises — it never executes anything by itself." |
| 2 | **Scenarios → structure-sync** (`/scenarios` → open a structure-sync run → show the generated SQL diff → click **AI migration plan**, wait ~8s, show the risk/steps/rollback card). *If no run exists, skip this shot.* | 26s | "The hardest job in database work is pushing a structure change from test to production. StageBridge computes the exact SQL diff, and GPT-5.6 returns an overall risk level, the concrete risks, a safe order to apply them, and a rollback plan. Facts from the code, judgment from the model." |
| 3 | **Diagnostics** (open server → Diagnostics tab → **Run**, then click **AI analysis**, wait ~8s). *If unavailable, skip.* | 14s | "Same pattern for diagnostics: run a health check, and the AI classifies severity and says exactly what's wrong and how to fix it." |
| 4 | **Backups** (`/backups`, pick the demo server → click **AI backup risk**, wait ~8s). *If unavailable, skip.* | 14s | "Before a restore, it weighs the real backup state and flags what to check — for example when some databases have no fresh backup." |
| 5 | **AI Query Advisor** (`/servers/1/monitoring` → scroll to **Slow queries** → click **AI: Optimize** on the top row → scroll to the panel → click **AI: optimize query** → wait ~8s → show the card with Problems / How to rewrite / Caveats). | 34s | "This feature I built with Codex, on GPT-5.6. It's the AI Query Advisor. From live pg_stat_statements monitoring I pick a slow query, and GPT-5.6 diagnoses it — the problems, suggested CREATE INDEX statements, and how to rewrite it. Codex wrote the whole feature end to end: the FastAPI service, the endpoint, this monitoring UI, and the translations." |
| 6 | **Settings → AI** (`/settings` → click the **AI** tab → show "Active model: **gpt-5.6**"). | 12s | "Every AI feature in the product runs on GPT-5.6 through the OpenAI API. The key is set right here in the UI and stored encrypted — no config files, no restart." |
| 7 | **Language switch** (top-right toggle: click **РУС**, pause 1s, click **ҚАЗ**, pause 1s, click **ENG**). | 12s | "And the entire interface — plus the AI's own answers — ship in three languages: Kazakh, Russian and English, switchable live." |
| 8 | **Back to Dashboard** (`/`). | 8s | "StageBridge AI: real infrastructure, a thin and trustworthy AI layer on GPT-5.6, and Codex in the loop. Thanks for watching." |

**Minimum viable cut:** shots 1, 5, 6, 7, 8 (≈1:30) — all guaranteed to work. Shots 2–4 are bonus; include them only if those screens have data, otherwise skip without breaking the flow.

---

## 2. Recording script (Playwright, Python) — skeleton to adapt

```python
# pip install playwright && playwright install chromium
import os, asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://localhost"
USER = "admin"
PWD  = os.environ["SUPER_ADMIN_PASSWORD"]  # never hardcode; loaded from .env
OUT  = Path("video_raw"); OUT.mkdir(exist_ok=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            viewport={"width": 1600, "height": 900},
            record_video_dir=str(OUT),
            record_video_size={"width": 1600, "height": 900},
        )
        # Force English UI before the app boots (storage key: pgcc.lang)
        await ctx.add_init_script("localStorage.setItem('pgcc.lang','en')")
        page = await ctx.new_page()

        # --- login (not narrated; keep it quick) ---
        await page.goto(f"{BASE}/login")
        await page.get_by_label("Username").fill(USER)      # or first textbox
        await page.get_by_label("Password").fill(PWD)
        await page.get_by_role("button", name="Sign in").click()
        await page.wait_for_url(f"{BASE}/")
        await page.wait_for_timeout(1500)

        # SHOT 1 — Dashboard (16s)
        await page.wait_for_timeout(16000)

        # SHOT 5 — AI Query Advisor (34s)
        await page.goto(f"{BASE}/servers/1/monitoring")
        await page.wait_for_timeout(2500)
        await page.get_by_text("Slow queries").scroll_into_view_if_needed()
        # click the first "AI: Optimize" button in the table
        await page.get_by_role("button", name="AI: Optimize").first.click()
        await page.wait_for_timeout(800)
        # click the panel's run button
        await page.get_by_role("button", name="AI: optimize query").click()
        await page.wait_for_timeout(9000)  # GPT-5.6 latency
        # scroll the result card into view and hold
        await page.wait_for_timeout(21000)

        # SHOT 6 — Settings → AI (12s)
        await page.goto(f"{BASE}/settings")
        await page.wait_for_timeout(1500)
        await page.get_by_role("tab", name="AI").click()
        await page.wait_for_timeout(10000)

        # SHOT 7 — language switch (12s)
        for lang in ["РУС", "ҚАЗ", "ENG"]:
            await page.get_by_role("button", name=lang).click()
            await page.wait_for_timeout(3500)

        # SHOT 8 — back to Dashboard (8s)
        await page.goto(f"{BASE}/")
        await page.wait_for_timeout(8000)

        await ctx.close()   # finalizes the .webm in ./video_raw
        await browser.close()

asyncio.run(main())
```
Notes for the agent:
- Selectors are by visible text/role — adjust names to what's on screen (e.g. the run button label is `t('queryAdvisor.label')` → "AI: optimize query"; the row button is "AI: Optimize"). If `get_by_label` misses, use `page.locator("input").nth(0/1)`.
- Insert shots 2–4 before shot 5 only if those screens work; mirror the pattern (goto → click AI button → `wait_for_timeout(9000)` for the call → hold).
- Keep the total on-screen time aligned with the narration durations in the table so audio and video line up.

## 3. Voiceover (TTS)

Generate one MP3 per shot (so timing stays aligned), English, calm pace. Example with the OpenAI TTS API:
```python
# one call per segment; text = the row's Voiceover cell
from openai import OpenAI
client = OpenAI()  # uses OPENAI_API_KEY
resp = client.audio.speech.create(model="gpt-4o-mini-tts", voice="alloy", input=SEGMENT_TEXT)
resp.stream_to_file(f"vo_{i}.mp3")
```
(Any TTS works — ElevenLabs, Azure, etc. Using AI voice is explicitly allowed by the hackathon rules.)

## 4. Assemble with ffmpeg

```bash
# a) concat narration in shot order into one track
printf "file 'vo_1.mp3'\nfile 'vo_2.mp3'\n...\n" > vo.txt
ffmpeg -f concat -safe 0 -i vo.txt -c copy voiceover.mp3

# b) convert the Playwright webm to mp4
ffmpeg -i video_raw/*.webm -c:v libx264 -pix_fmt yuv420p -r 30 video.mp4

# c) mux: video + narration, cut to the shorter stream, cap at 3:00
ffmpeg -i video.mp4 -i voiceover.mp3 -c:v copy -c:a aac -shortest -t 180 stagebridge-demo.mp4
```
If video is longer than audio, either add small `wait_for_timeout` gaps, or speed the video slightly: `-filter:v "setpts=0.9*PTS"`. Keep final length **≤ 3:00**.

## 5. Deliver

- Watch `stagebridge-demo.mp4` once end to end. Confirm: audio is in sync, the AI Query Advisor card is readable, "gpt-5.6" is visible in Settings, length ≤ 3:00.
- Upload to **YouTube** (Public or Unlisted). 
- Return the YouTube URL — it goes into Devpost → Project details → Video demo link.

## Hard requirements checklist (from the rules)
- [ ] ≤ 3 minutes, clear demo **with audio**.
- [ ] Narration explicitly covers **what you built** and **how you used Codex and GPT-5.6** (shots 1, 5, 6 do this).
- [ ] Public on YouTube; link on the submission form.
- [ ] No third-party trademarks / copyrighted music.
