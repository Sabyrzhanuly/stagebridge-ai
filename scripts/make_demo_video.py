#!/usr/bin/env python3
"""StageBridge AI demo video: full menu tour + AI highlights → MP4."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo-video"
RAW = OUT / "video_raw"
VO = OUT / "voiceover"

BASE = os.environ.get("DEMO_BASE_URL", "http://localhost")
API = os.environ.get("DEMO_API_URL", "http://localhost:8000/api")
USER = "admin"
AI_WAIT_MS = 6500

# segment_id → voiceover (English)
VOICEOVERS: dict[str, str] = {
    "intro": (
        "This is StageBridge AI — a PostgreSQL control center with an AI layer on GPT-5.6. "
        "The sidebar covers the whole product: fleet dashboard, backups, scenarios, audit, team and settings."
    ),
    "nav_backups": (
        "Backups: per-database pg_dump to S3, on-demand runs, schedules, and restore scenarios."
    ),
    "nav_scenarios": (
        "Scenarios splits into restore drills and structure migration — pushing SQL diffs from test to production."
    ),
    "nav_audit": (
        "Audit logs every admin action — who did what, when, and on which server."
    ),
    "nav_users": (
        "Users and roles: RBAC so operators only see the actions they are allowed to run."
    ),
    "server_tour": (
        "Open any server for a dedicated workspace — overview, roles, databases, live monitoring, "
        "diagnostics, and PostgreSQL configuration."
    ),
    "monitoring": (
        "Monitoring streams connections, database sizes, locks, and slow queries from pg_stat_statements."
    ),
    "databases": "The database inventory shows owners, sizes, and quick navigation.",
    "roles": "Role management lists PostgreSQL roles and privileges on this server.",
    "diagnostics": (
        "Diagnostics runs deterministic health checks; GPT-5.6 then classifies severity and suggests fixes."
    ),
    "pg_config": "PG configuration surfaces postgresql.conf settings you can review from the UI.",
    "query_advisor": (
        "Built with Codex on GPT-5.6: the AI Query Advisor. Pick a slow query, and the model returns problems, "
        "index suggestions, and a rewrite — backend service, API endpoint, UI and i18n, all Codex end to end."
    ),
    "backups_ai": (
        "Before a restore, AI backup risk analysis weighs real backup freshness and flags gaps to check."
    ),
    "structure_sync": (
        "Structure migration computes the SQL diff; GPT-5.6 adds risk level, ordered steps, and a rollback plan."
    ),
    "settings_ai": (
        "Every AI feature runs on GPT-5.6 through the OpenAI API. The key lives here, encrypted in the database — "
        "no config files, no restart."
    ),
    "i18n": (
        "The UI and AI answers ship in Kazakh, Russian and English — switchable live in the header."
    ),
    "tasks": "Background Celery jobs — backups, migrations, restores — with real-time progress over WebSocket.",
    "outro": (
        "StageBridge AI: full PostgreSQL operations, a thin trustworthy AI layer on GPT-5.6, and Codex in the loop. "
        "Thanks for watching."
    ),
}


@dataclass
class Segment:
    id: str
    hold_ms: int
    record: Callable[..., Awaitable[bool | None]]
    optional: bool = False


@dataclass
class Plan:
    segments: list[Segment] = field(default_factory=list)
    recorded_ids: list[str] = field(default_factory=list)
    login_trim_ms: int = 0


def load_env() -> str:
    load_dotenv(ROOT / ".env")
    pwd = os.environ.get("SUPER_ADMIN_PASSWORD", "").strip()
    if not pwd:
        sys.exit("SUPER_ADMIN_PASSWORD is missing in .env")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print("[tts] OPENAI_API_KEY empty — using edge-tts for voiceover")
    return pwd


def api_login(password: str) -> str | None:
    body = json.dumps({"username": USER, "password": password}).encode()
    req = urllib.request.Request(
        f"{API}/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode()).get("access_token")
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        return None


def api_get(path: str, token: str) -> object | None:
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def structure_sync_available(token: str) -> bool:
    scenarios = api_get("/structure-sync/scenarios", token)
    if not isinstance(scenarios, list):
        return False
    for sc in scenarios:
        runs = api_get(f"/structure-sync/{sc['id']}/runs", token)
        if isinstance(runs, list):
            for run in runs:
                if (run.get("generated_sql") or "").strip():
                    return True
    return False


def ensure_slow_queries() -> None:
    cmd = [
        "docker", "compose", "exec", "-T", "demopg", "psql", "-U", "postgres", "-d", "demo_shop", "-c",
        "SELECT count(*) FROM generate_series(1,500000) g; "
        "SELECT g, md5(g::text) FROM generate_series(1,200000) g ORDER BY md5(g::text) LIMIT 5;",
    ]
    print("[preflight] warming slow queries on demopg …")
    subprocess.run(cmd, cwd=ROOT, check=False, capture_output=True)


async def pause(page, ms: int) -> None:
    if ms > 0:
        await page.wait_for_timeout(ms)


async def login(page, password: str) -> None:
    await page.goto(f"{BASE}/login")
    await page.locator("#username").fill(USER)
    await page.locator("#password input").fill(password)
    await page.get_by_role("button", name="Sign in").click()
    await page.wait_for_url(f"{BASE}/**")
    await pause(page, 1200)


async def nav_sidebar(page, label: str) -> None:
    item = page.locator(".app-menu-item").filter(has_text=label).first
    await item.scroll_into_view_if_needed()
    await item.click()
    await pause(page, 1400)


async def open_first_server(page) -> None:
    link = page.locator("a.link-primary").first
    await link.scroll_into_view_if_needed()
    await link.click()
    await pause(page, 1600)


async def goto_server_overview(page, server_id: int = 1) -> None:
    await page.goto(f"{BASE}/servers/{server_id}")
    await pause(page, 1200)


async def server_btn(page, name: str, server_id: int = 1) -> None:
    await goto_server_overview(page, server_id)
    btn = page.get_by_role("button", name=name).first
    await btn.scroll_into_view_if_needed()
    await btn.click()
    await pause(page, 1400)


async def run_ai_button(page, label: str) -> None:
    btn = page.get_by_role("button", name=label).first
    if await btn.count() == 0:
        return
    await btn.scroll_into_view_if_needed()
    await btn.click()
    await pause(page, AI_WAIT_MS)
    card = page.locator(".ai-insight-card").first
    if await card.count():
        await card.scroll_into_view_if_needed()


# --- segment recorders ---

async def seg_intro(page) -> None:
    await page.goto(f"{BASE}/")
    await pause(page, 7000)


async def seg_nav_backups(page) -> None:
    await nav_sidebar(page, "Backups")
    await pause(page, 4000)


async def seg_nav_scenarios(page) -> None:
    await nav_sidebar(page, "Scenarios")
    await pause(page, 1800)
    await page.locator("[role='tab'], .p-tab").filter(has_text="Structure migration").first.click()
    await pause(page, 1800)
    await page.locator("[role='tab'], .p-tab").filter(has_text="Restore").first.click()
    await pause(page, 2400)


async def seg_nav_audit(page) -> None:
    await nav_sidebar(page, "Audit")
    await pause(page, 3500)


async def seg_nav_users(page) -> None:
    await nav_sidebar(page, "Users")
    await pause(page, 3500)


async def seg_server_tour(page) -> None:
    await nav_sidebar(page, "Dashboard")
    await pause(page, 800)
    await open_first_server(page)
    await pause(page, 5000)


async def seg_monitoring(page) -> None:
    await server_btn(page, "Monitoring")
    await page.get_by_text("Slow queries", exact=False).first.scroll_into_view_if_needed()
    await pause(page, 5000)


async def seg_databases(page) -> None:
    await server_btn(page, "Databases")
    await pause(page, 3500)


async def seg_roles(page) -> None:
    await server_btn(page, "Roles")
    await pause(page, 3000)


async def seg_diagnostics(page) -> None:
    await server_btn(page, "Diagnostics")
    run_btn = page.get_by_role("button", name="Run")
    if await run_btn.count():
        await run_btn.click()
        await pause(page, 4500)
    await run_ai_button(page, "AI diagnostics analysis")
    await pause(page, 3500)


async def seg_pg_config(page) -> None:
    await server_btn(page, "PG configuration")
    await pause(page, 3500)


async def seg_query_advisor(page) -> None:
    await page.goto(f"{BASE}/servers/1/monitoring")
    await pause(page, 1800)
    await page.get_by_text("Slow queries", exact=False).first.scroll_into_view_if_needed()
    await pause(page, 600)
    await page.get_by_role("button", name="AI: Optimize").first.click()
    await pause(page, 600)
    await run_ai_button(page, "AI: optimize query")
    await pause(page, 12000)


async def seg_backups_ai(page) -> None:
    await nav_sidebar(page, "Backups")
    combo = page.locator(".p-select").first
    if await combo.count():
        await combo.click()
        opt = page.locator(".p-select-option").first
        if await opt.count():
            await opt.click()
            await pause(page, 1800)
    await run_ai_button(page, "AI: backup and restore risk analysis")
    await pause(page, 3500)


async def seg_structure_sync(page) -> bool:
    await nav_sidebar(page, "Scenarios")
    await page.locator("[role='tab'], .p-tab").filter(has_text="Structure migration").first.click()
    await pause(page, 1500)
    hist = page.locator("button").filter(has=page.locator(".fa-clock-rotate-left")).first
    if await hist.count() == 0:
        return False
    await hist.click()
    await pause(page, 1200)
    row = page.locator(".p-datatable-tbody tr").first
    if await row.count() == 0:
        return False
    await row.click()
    await pause(page, 1000)
    sql = page.locator("textarea").first
    if await sql.count() == 0:
        return False
    val = (await sql.input_value()).strip()
    if not val or val in ("—", "-"):
        return False
    await run_ai_button(page, "AI migration plan: risks and order")
    await pause(page, 4000)
    return True


async def seg_settings_ai(page) -> None:
    await nav_sidebar(page, "Settings")
    await pause(page, 1200)
    ai_tab = page.locator("[role='tab'], .p-tab").filter(has_text="AI").first
    await ai_tab.click()
    await pause(page, 1200)
    model = page.locator("strong").filter(has_text="gpt-5.6")
    if await model.count():
        await model.first.scroll_into_view_if_needed()
    else:
        await page.locator(".ai-settings-form").scroll_into_view_if_needed()
    await pause(page, 9000)


async def seg_i18n(page) -> None:
    for lang in ("РУС", "ҚАЗ", "ENG"):
        await page.get_by_role("button", name=lang).click()
        await pause(page, 2200)


async def seg_tasks(page) -> None:
    btn = page.locator(".sidebar-tasks-btn").first
    if await btn.count():
        await btn.click()
        await pause(page, 3000)


async def seg_outro(page) -> None:
    await nav_sidebar(page, "Dashboard")
    await pause(page, 5000)


def build_segments(include_structure: bool) -> list[Segment]:
    segments = [
        Segment("intro", 0, seg_intro),
        Segment("nav_backups", 0, seg_nav_backups),
        Segment("nav_scenarios", 0, seg_nav_scenarios),
        Segment("nav_audit", 0, seg_nav_audit),
        Segment("nav_users", 0, seg_nav_users),
        Segment("server_tour", 0, seg_server_tour),
        Segment("monitoring", 0, seg_monitoring),
        Segment("databases", 0, seg_databases),
        Segment("roles", 0, seg_roles),
        Segment("diagnostics", 0, seg_diagnostics),
        Segment("pg_config", 0, seg_pg_config),
        Segment("query_advisor", 0, seg_query_advisor),
        Segment("backups_ai", 0, seg_backups_ai),
    ]
    if include_structure:
        segments.append(Segment("structure_sync", 0, seg_structure_sync, optional=True))
    segments.extend([
        Segment("settings_ai", 0, seg_settings_ai),
        Segment("i18n", 0, seg_i18n),
        Segment("tasks", 0, seg_tasks),
        Segment("outro", 0, seg_outro),
    ])
    return segments


async def record_walkthrough(plan: Plan, password: str) -> Path:
    from playwright.async_api import async_playwright

    RAW.mkdir(parents=True, exist_ok=True)
    for old in RAW.glob("*.webm"):
        old.unlink()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1600, "height": 900},
            record_video_dir=str(RAW),
            record_video_size={"width": 1600, "height": 900},
        )
        await ctx.add_init_script("localStorage.setItem('pgcc.lang','en')")
        page = await ctx.new_page()

        t0 = asyncio.get_event_loop().time()
        await login(page, password)
        plan.login_trim_ms = int((asyncio.get_event_loop().time() - t0) * 1000)

        for seg in plan.segments:
            print(f"[record] {seg.id}")
            result = await seg.record(page)
            if seg.optional and result is False:
                print(f"[record] {seg.id} skipped (no data)")
                continue
            plan.recorded_ids.append(seg.id)

        await ctx.close()
        await browser.close()

    webms = sorted(RAW.glob("*.webm"), key=lambda p: p.stat().st_mtime)
    if not webms:
        raise RuntimeError("Playwright did not produce a .webm file")
    return webms[-1]


def tts_segment(text: str, out: Path) -> None:
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        from openai import OpenAI

        client = OpenAI()
        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text,
            instructions="Clear English product demo, calm pace.",
        ) as resp:
            resp.stream_to_file(out)
    else:
        import edge_tts

        async def _run() -> None:
            comm = edge_tts.Communicate(text, voice="en-US-JennyNeural", rate="-3%")
            await comm.save(str(out))

        asyncio.run(_run())


def generate_voiceover(plan: Plan) -> Path:
    VO.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for seg_id in plan.recorded_ids:
        text = VOICEOVERS[seg_id]
        out = VO / f"vo_{seg_id}.mp3"
        print(f"[tts] {seg_id}")
        tts_segment(text, out)
        lines.append(f"file '{out.as_posix()}'")
    lst = VO / "vo.txt"
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    merged = VO / "voiceover.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(merged)],
        check=True,
        capture_output=True,
    )
    return merged


def probe_duration(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(proc.stdout.strip())


def assemble(webm: Path, voiceover: Path, plan: Plan) -> Path:
    video_mp4 = OUT / "video.mp4"
    trimmed = OUT / "video_trimmed.mp4"
    final = OUT / "stagebridge-demo.mp4"
    trim_s = max(plan.login_trim_ms / 1000.0, 0)

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(video_mp4)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{trim_s:.3f}", "-i", str(video_mp4), "-c:v", "copy", str(trimmed)],
        check=True,
        capture_output=True,
    )

    v_dur = probe_duration(trimmed)
    a_dur = probe_duration(voiceover)
    print(f"[assemble] video={v_dur:.1f}s audio={a_dur:.1f}s")

    vf = []
    if v_dur > a_dur * 1.04:
        speed = min(v_dur / a_dur, 1.35)
        vf.append(f"setpts=PTS/{speed:.4f}")
        print(f"[assemble] speeding video ×{speed:.3f}")

    cmd = ["ffmpeg", "-y", "-i", str(trimmed), "-i", str(voiceover), "-c:a", "aac", "-shortest", "-t", "180"]
    if vf:
        cmd.extend(["-vf", ",".join(vf), "-c:v", "libx264", "-pix_fmt", "yuv420p"])
    else:
        cmd.extend(["-c:v", "copy"])
    cmd.append(str(final))
    subprocess.run(cmd, check=True, capture_output=True)
    return final


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    password = load_env()
    ensure_slow_queries()

    token = api_login(password)
    ss_ok = structure_sync_available(token) if token else False
    plan = Plan(segments=build_segments(ss_ok))
    ids = [s.id for s in plan.segments]
    print(f"[plan] segments: {ids} (structure_sync={'yes' if ss_ok else 'skip'})")

    webm = asyncio.run(record_walkthrough(plan, password))
    print(f"[record] webm: {webm}")

    voice = generate_voiceover(plan)
    final = assemble(webm, voice, plan)
    dur = probe_duration(final)
    print(f"[done] {final} ({dur:.1f}s)")
    if dur > 180:
        print("WARNING: video exceeds 3 minutes")


if __name__ == "__main__":
    main()
