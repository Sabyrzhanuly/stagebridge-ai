"""ИИ-слой (OpenAI) поверх PG Control Center.

Ключ и модель приходят явными аргументами (из настроек в БД или из .env —
разрешает вызывающий код, см. api/ai.py). Все ответы советующие; система
ничего не выполняет по тексту ИИ.
"""

from __future__ import annotations

_LANG = "русском языке"


class AIUnavailable(RuntimeError):
    pass


async def _chat(api_key: str, model: str, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 900) -> str:
    if not api_key:
        raise AIUnavailable("OpenAI-ключ не задан.")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    kwargs = {
        "model": model or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await client.chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()


# ── Фичи ──────────────────────────────────────────────────────────────

async def migration_plan(api_key: str, model: str, diff_summary: str, generated_sql: str = "") -> dict:
    system = (
        f"Ты — старший инженер PostgreSQL. Отвечай на {_LANG}. Верни СТРОГО JSON с полями: "
        "overall_risk ('low'|'medium'|'high'), summary (строка), "
        "risks (массив строк), steps (массив строк — безопасный порядок применения), "
        "rollback (массив строк). Опирайся только на дифф. Не возвращай исполняемый SQL как источник выполнения."
    )
    user = f"Структурный дифф test→prod:\n{diff_summary}\n\nСгенерированный SQL:\n{generated_sql[:6000]}"
    return _safe_json(await _chat(api_key, model, system, user, json_mode=True, max_tokens=1100))


async def assistant(api_key: str, model: str, question: str, context: str = "") -> str:
    system = (
        f"Ты — встроенный ассистент PG Control Center (серверы, бэкапы, restore-сценарии, structure-sync, мониторинг). "
        f"Отвечай кратко и по делу на {_LANG}. Давай практичные команды/SQL при необходимости, предупреждай о рисках."
    )
    user = question if not context else f"Контекст:\n{context}\n\nВопрос: {question}"
    return await _chat(api_key, model, system, user, max_tokens=800)


async def diagnostics_analysis(api_key: str, model: str, payload: str) -> dict:
    system = (
        f"Ты — эксперт по производительности PostgreSQL. Отвечай на {_LANG}. Верни СТРОГО JSON: "
        "severity ('ok'|'warning'|'critical'), findings (массив строк), "
        "recommendations (массив строк), quick_wins (массив строк). Опирайся только на данные."
    )
    return _safe_json(await _chat(api_key, model, system, f"Данные диагностики (JSON):\n{payload[:8000]}", json_mode=True, max_tokens=1000))


async def backup_risk(api_key: str, model: str, payload: str) -> dict:
    system = (
        f"Ты — DBA, оценивающий риск восстановления бэкапа PostgreSQL. Отвечай на {_LANG}. Верни СТРОГО JSON: "
        "risk ('low'|'medium'|'high'), summary (строка), checks (массив строк), cautions (массив строк). Опирайся только на данные."
    )
    return _safe_json(await _chat(api_key, model, system, f"Данные бэкапа/цели (JSON):\n{payload[:6000]}", json_mode=True, max_tokens=900))


def _safe_json(content: str) -> dict:
    import json

    try:
        return json.loads(content)
    except Exception:
        return {"summary": content, "raw": True}
