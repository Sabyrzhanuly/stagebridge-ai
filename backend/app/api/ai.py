"""ИИ-эндпоинты PG Control Center.

Ключ и модель берутся из настроек в БД (заданы через UI), с откатом на .env.
Настройку ключа можно менять через PUT /ai/config (только админ платформы).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_context, AuthContext
from app.config import settings
from app.database import get_db
from app.services import ai_service, app_settings_service
from app.services.tenancy_service import is_global_admin

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(get_auth_context)])

_KEY = "openai_api_key"
_MODEL = "openai_model"


async def _config(db: AsyncSession) -> tuple[str, str, str]:
    """Вернуть (api_key, model, source). Приоритет: БД → .env."""
    key = await app_settings_service.get_setting(db, _KEY)
    model = await app_settings_service.get_setting(db, _MODEL)
    source = "db"
    if not key:
        key = settings.openai_api_key
        source = "env" if key else "none"
    if not model:
        model = settings.openai_model or "gpt-4o-mini"
    return key or "", model or "gpt-4o-mini", source


async def _require_key(db: AsyncSession) -> tuple[str, str]:
    key, model, _ = await _config(db)
    if not key:
        raise HTTPException(503, "ИИ-функции отключены: задайте OpenAI-ключ в Настройках.")
    return key, model


class MigrationPlanIn(BaseModel):
    diff_summary: str
    generated_sql: str = ""


class AssistantIn(BaseModel):
    question: str
    context: str = ""


class PayloadIn(BaseModel):
    payload: str


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
    return await ai_service.migration_plan(key, model, body.diff_summary, body.generated_sql)


@router.post("/assistant")
async def ai_assistant(body: AssistantIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return {"answer": await ai_service.assistant(key, model, body.question, body.context)}


@router.post("/diagnostics")
async def ai_diagnostics(body: PayloadIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return await ai_service.diagnostics_analysis(key, model, body.payload)


@router.post("/backup-analysis")
async def ai_backup_analysis(body: PayloadIn, db: AsyncSession = Depends(get_db)):
    key, model = await _require_key(db)
    return await ai_service.backup_risk(key, model, body.payload)
