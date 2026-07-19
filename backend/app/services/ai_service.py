"""ИИ-слой (OpenAI) поверх PG Control Center.

Ключ и модель приходят явными аргументами (из настроек в БД или из .env —
разрешает вызывающий код, см. api/ai.py). Все ответы советующие; система
ничего не выполняет по тексту ИИ.
"""

from __future__ import annotations

_DEFAULT_MODEL = "gpt-5.6"

# Язык ответа ИИ следует за языком интерфейса (ru/kk/en).
_LANG_MAP = {
    "ru": "русском языке",
    "kk": "казахском языке (қазақ тілінде)",
    "en": "английском языке (in English)",
}


def _lang(lang: str) -> str:
    return _LANG_MAP.get((lang or "ru").split("-")[0], _LANG_MAP["ru"])


class AIUnavailable(RuntimeError):
    pass


async def _chat(api_key: str, model: str, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 900) -> str:
    if not api_key:
        raise AIUnavailable("OpenAI-ключ не задан.")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    selected_model = model or _DEFAULT_MODEL
    kwargs = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if selected_model.startswith("gpt-5"):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = 0.2
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await _create_chat_completion(client, kwargs)
    return (resp.choices[0].message.content or "").strip()


async def _create_chat_completion(client, kwargs: dict):
    for _ in range(4):
        try:
            return await client.chat.completions.create(**kwargs)
        except Exception as exc:
            retry_kwargs = _retry_chat_kwargs(kwargs, exc)
            if retry_kwargs is None:
                raise
            kwargs = retry_kwargs
    return await client.chat.completions.create(**kwargs)


def _retry_chat_kwargs(kwargs: dict, exc: Exception) -> dict | None:
    if getattr(exc, "status_code", None) != 400:
        return None
    msg = str(exc).lower()
    if not any(token in msg for token in ("unsupported", "not supported", "does not support", "unknown parameter", "invalid parameter")):
        return None

    retry = dict(kwargs)
    changed = False
    if "max_tokens" in retry and "max_tokens" in msg and "max_completion_tokens" in msg:
        retry["max_completion_tokens"] = retry.pop("max_tokens")
        changed = True
    elif "max_completion_tokens" in retry and "max_completion_tokens" in msg and "max_tokens" in msg:
        retry["max_tokens"] = retry.pop("max_completion_tokens")
        changed = True
    elif "max_tokens" in retry and "max_tokens" in msg:
        retry.pop("max_tokens")
        changed = True
    elif "max_completion_tokens" in retry and "max_completion_tokens" in msg:
        retry.pop("max_completion_tokens")
        changed = True

    for field in ("temperature", "response_format"):
        if field in retry and field in msg:
            retry.pop(field)
            changed = True

    return retry if changed else None


# ── Фичи ──────────────────────────────────────────────────────────────

async def migration_plan(api_key: str, model: str, diff_summary: str, generated_sql: str = "", lang: str = "ru") -> dict:
    system = (
        f"Ты — старший инженер PostgreSQL. Отвечай на {_lang(lang)}. Верни СТРОГО JSON с полями: "
        "overall_risk ('low'|'medium'|'high'), summary (строка), "
        "risks (массив строк), steps (массив строк — безопасный порядок применения), "
        "rollback (массив строк). Опирайся только на дифф. Не возвращай исполняемый SQL как источник выполнения."
    )
    user = f"Структурный дифф test→prod:\n{diff_summary}\n\nСгенерированный SQL:\n{generated_sql[:6000]}"
    return _safe_json(await _chat(api_key, model, system, user, json_mode=True, max_tokens=1100))


async def assistant(api_key: str, model: str, question: str, context: str = "", lang: str = "ru") -> str:
    system = (
        f"Ты — встроенный ассистент PG Control Center (серверы, бэкапы, restore-сценарии, structure-sync, мониторинг). "
        f"Отвечай кратко и по делу на {_lang(lang)}. Давай практичные команды/SQL при необходимости, предупреждай о рисках."
    )
    user = question if not context else f"Контекст:\n{context}\n\nВопрос: {question}"
    return await _chat(api_key, model, system, user, max_tokens=800)


async def diagnostics_analysis(api_key: str, model: str, payload: str, lang: str = "ru") -> dict:
    system = (
        f"Ты — эксперт по производительности PostgreSQL. Отвечай на {_lang(lang)}. Верни СТРОГО JSON: "
        "severity ('ok'|'warning'|'critical'), findings (массив строк), "
        "recommendations (массив строк), quick_wins (массив строк). Опирайся только на данные."
    )
    return _safe_json(await _chat(api_key, model, system, f"Данные диагностики (JSON):\n{payload[:8000]}", json_mode=True, max_tokens=1000))


async def backup_risk(api_key: str, model: str, payload: str, lang: str = "ru") -> dict:
    system = (
        f"Ты — DBA, оценивающий риск восстановления бэкапа PostgreSQL. Отвечай на {_lang(lang)}. Верни СТРОГО JSON: "
        "risk ('low'|'medium'|'high'), summary (строка), checks (массив строк), cautions (массив строк). Опирайся только на данные."
    )
    return _safe_json(await _chat(api_key, model, system, f"Данные бэкапа/цели (JSON):\n{payload[:6000]}", json_mode=True, max_tokens=900))


async def query_advisor(api_key: str, model: str, payload: str, lang: str = "ru") -> dict:
    system = (
        f"Ты — эксперт по производительности PostgreSQL. Отвечай на {_lang(lang)}. "
        "Тебе дают медленный SQL-запрос, (опционально) статистику из pg_stat_statements, "
        "контекст схемы и план EXPLAIN (FORMAT JSON). Если план есть, предпочитай его фактические "
        "оценки догадкам по тексту запроса. Верни СТРОГО JSON с полями: "
        "severity ('ok'|'warning'|'critical'), summary (строка — в чём проблема), "
        "problems (массив строк), indexes (массив строк — готовые CREATE INDEX ... предложения), "
        "rewrite (массив строк — как переписать запрос), notes (массив строк — оговорки/риски). "
        "Опирайся только на данные. Индексы — только предложения, не выполняются автоматически."
    )
    return _safe_json(await _chat(api_key, model, system, f"Данные запроса (JSON):\n{payload[:8000]}", json_mode=True, max_tokens=1100))


async def lock_analysis(api_key: str, model: str, payload: str, lang: str = "ru") -> dict:
    system = (
        f"Ты — эксперт по конкурентному доступу и блокировкам PostgreSQL. Отвечай на {_lang(lang)}. "
        "Тебе дают снимок ожидающих блокировок. Верни СТРОГО JSON с полями: "
        "severity ('ok'|'warning'|'critical'), summary (строка), "
        "blocking_chains (массив строк — кто и кого блокирует), "
        "recommendations (массив строк), notes (массив строк). "
        "Опирайся только на данные и явно отмечай недостаток контекста. "
        "Давай только рекомендации: ничего не выполняется автоматически."
    )
    return _safe_json(await _chat(api_key, model, system, f"Данные блокировок (JSON):\n{payload[:8000]}", json_mode=True, max_tokens=1000))


async def config_advisor(api_key: str, model: str, payload: str, lang: str = "ru") -> dict:
    system = (
        f"Ты — старший DBA PostgreSQL. Отвечай на {_lang(lang)}. "
        "Тебе дают компактный снимок ключевых параметров pg_settings и связанных сигналов. "
        "Верни СТРОГО JSON с полями: "
        "severity ('ok'|'warning'|'critical'), summary (строка), "
        "findings (массив строк), recommendations (массив строк — конкретные advisory-only SET/postgresql.conf предложения), "
        "notes (массив строк). Опирайся только на данные. "
        "Не утверждай, что изменения были применены, и не предлагай автоматическое выполнение."
    )
    return _safe_json(await _chat(api_key, model, system, f"Данные конфигурации PostgreSQL (JSON):\n{payload[:8000]}", json_mode=True, max_tokens=1000))


async def schema_review(api_key: str, model: str, payload: str, lang: str = "ru") -> dict:
    system = (
        f"Ты — старший PostgreSQL DBA и reviewer схем данных. Отвечай на {_lang(lang)}. "
        "Тебе дают ограниченный read-only снимок таблиц, колонок, primary keys, foreign keys и индексов. "
        "Верни СТРОГО JSON с полями: "
        "severity ('ok'|'warning'|'critical'), summary (строка), "
        "issues (массив строк), recommendations (массив строк — advisory-only DDL предложения), "
        "notes (массив строк). Ищи только типовые проблемы дизайна: таблицы без PK, nullable ключевые поля, "
        "FK без очевидного поддерживающего индекса, чрезмерно широкие text-поля, подозрительные дубли индексов. "
        "Не утверждай, что DDL выполнен, и не предлагай автоматическое применение."
    )
    return _safe_json(await _chat(api_key, model, system, f"Снимок схемы PostgreSQL (JSON):\n{payload[:10000]}", json_mode=True, max_tokens=1200))


def _safe_json(content: str) -> dict:
    import json

    try:
        return json.loads(content)
    except Exception:
        return {"summary": content, "raw": True}
