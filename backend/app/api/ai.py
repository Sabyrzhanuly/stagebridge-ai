"""ИИ-эндпоинты PG Control Center.

Ключ и модель берутся из настроек в БД (заданы через UI), с откатом на .env.
Настройку ключа можно менять через PUT /ai/config (только админ платформы).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_context, AuthContext
from app.config import settings
from app.database import get_db
from app.services import ai_service, app_settings_service, query_plan_service, schema_review_service
from app.services.tenancy_service import ensure_database_access, get_owned_server, is_global_admin

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(get_auth_context)])

_KEY = "openai_api_key"
_MODEL = "openai_model"
_DEFAULT_MODEL = "gpt-5.6"


async def _config(db: AsyncSession) -> tuple[str, str, str]:
    """Вернуть (api_key, model, source). Приоритет: БД → .env."""
    key = await app_settings_service.get_setting(db, _KEY)
    model = await app_settings_service.get_setting(db, _MODEL)
    source = "db"
    if not key:
        key = settings.openai_api_key
        source = "env" if key else "none"
    if not model:
        model = settings.openai_model or _DEFAULT_MODEL
    return key or "", model or _DEFAULT_MODEL, source


async def _require_key(db: AsyncSession) -> tuple[str, str]:
    key, model, _ = await _config(db)
    if not key:
        raise HTTPException(503, "ИИ-функции отключены: задайте OpenAI-ключ в Настройках.")
    return key, model


class MigrationPlanIn(BaseModel):
    diff_summary: str
    generated_sql: str = ""
    lang: str = "ru"


class AssistantIn(BaseModel):
    question: str
    context: str = ""
    lang: str = "ru"


class PayloadIn(BaseModel):
    payload: str
    lang: str = "ru"


class SchemaReviewIn(BaseModel):
    server_id: int
    database: str
    lang: str = "ru"


class NlToSqlIn(BaseModel):
    server_id: int
    database: str
    question: str
    lang: str = "ru"


class AiConfigIn(BaseModel):
    api_key: str | None = None
    model: str | None = None


@router.get("/status")
async def ai_status(db: AsyncSession = Depends(get_db)):
    key, model, source = await _config(db)
    return {"available": bool(key), "model": model if key else None, "source": source}


@router.get("/config")
async def ai_config(db: AsyncSession = Depends(get_db)):
    """Статус для страницы настроек — ключ НЕ возвращается, только факт наличия."""
    key, model, source = await _config(db)
    return {"configured": bool(key), "model": model, "source": source}


@router.put("/config")
async def ai_config_set(
    body: AiConfigIn,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if not is_global_admin(auth.user):
        raise HTTPException(403, "Изменение ИИ-настроек доступно только администратору платформы")
    if body.api_key is not None:
        if body.api_key.strip():
            await app_settings_service.set_setting(db, _KEY, body.api_key.strip())
        else:
            await app_settings_service.delete_setting(db, _KEY)
    if body.model is not None and body.model.strip():
        await app_settings_service.set_setting(db, _MODEL, body.model.strip())
    key, model, source = await _config(db)
    return {"configured": bool(key), "model": model, "source": source}


@router.post("/migration-plan")
async def ai_migration_plan(body: MigrationPlanIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return await ai_service.migration_plan(key, model, body.diff_summary, body.generated_sql, lang=body.lang)


@router.post("/assistant")
async def ai_assistant(body: AssistantIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return {"answer": await ai_service.assistant(key, model, body.question, body.context, lang=body.lang)}


@router.post("/diagnostics")
async def ai_diagnostics(body: PayloadIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return await ai_service.diagnostics_analysis(key, model, body.payload, lang=body.lang)


@router.post("/backup-analysis")
async def ai_backup_analysis(body: PayloadIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return await ai_service.backup_risk(key, model, body.payload, lang=body.lang)


@router.post("/query-advisor")
async def ai_query_advisor(
    body: PayloadIn,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    key, model = await _require_key(db)
    payload = await _with_explain_plan(body.payload, db, auth)
    return await ai_service.query_advisor(key, model, payload, lang=body.lang)


@router.post("/lock-analysis")
async def ai_lock_analysis(body: PayloadIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return await ai_service.lock_analysis(key, model, body.payload, lang=body.lang)


@router.post("/config-advisor")
async def ai_config_advisor(body: PayloadIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return await ai_service.config_advisor(key, model, body.payload, lang=body.lang)


@router.post("/schema-review")
async def ai_schema_review(
    body: SchemaReviewIn,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    key, model = await _require_key(db)
    server = await get_owned_server(body.server_id, auth.user, auth.org, db)
    if auth.org is not None:
        await ensure_database_access(auth.org, body.server_id, body.database, db)
    payload = await schema_review_service.collect_schema_metadata(server, body.database)
    return await ai_service.schema_review(
        key,
        model,
        json.dumps(payload, ensure_ascii=False, default=str),
        lang=body.lang,
    )


@router.post("/nl-to-sql")
async def ai_nl_to_sql(
    body: NlToSqlIn,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    key, model = await _require_key(db)
    server = await get_owned_server(body.server_id, auth.user, auth.org, db)
    if auth.org is not None:
        await ensure_database_access(auth.org, body.server_id, body.database, db)

    schema_context = await schema_review_service.collect_schema_metadata(server, body.database)
    ai_result = await ai_service.nl_to_sql(
        key,
        model,
        body.question,
        schema_context,
        lang=body.lang,
    )
    sql = str(ai_result.get("sql") or "").strip()
    explanation = str(ai_result.get("explanation") or ai_result.get("summary") or "")
    notes = ai_result.get("notes") if isinstance(ai_result.get("notes"), list) else []

    if not query_plan_service.is_explainable_query(sql):
        return {
            "sql": sql,
            "explanation": explanation,
            "notes": notes,
            "executed": False,
            "reason": "not a safe read-only SELECT",
        }

    result = await query_plan_service.run_readonly_select(server, sql, body.database)
    return {
        "sql": sql,
        "explanation": explanation,
        "notes": notes,
        "executed": True,
        **result,
    }


async def _with_explain_plan(payload: str, db: AsyncSession, auth: AuthContext) -> str:
    try:
        context = json.loads(payload)
        if not isinstance(context, dict):
            return payload
        server_id = context.get("server_id")
        query = context.get("query")
        database = context.get("database") or "postgres"
        if not isinstance(server_id, int) or not isinstance(query, str) or not isinstance(database, str):
            return payload

        server = await get_owned_server(server_id, auth.user, auth.org, db)
        if auth.org is not None:
            await ensure_database_access(auth.org, server_id, database, db)
        plan = await query_plan_service.explain_query(server, query, database)
        if plan is None:
            return payload
        context["explain_plan"] = plan
        return json.dumps(context, ensure_ascii=False, default=str)
    except Exception:
        return payload
