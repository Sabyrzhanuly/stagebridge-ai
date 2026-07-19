"""Чтение/запись платформенных настроек key→value (значение шифруется Fernet)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting
from app.services.crypto import decrypt, encrypt


async def get_setting(db: AsyncSession, key: str) -> str | None:
    row = await db.get(AppSetting, key)
    if not row or not row.value_encrypted:
        return None
    try:
        return decrypt(row.value_encrypted)
    except Exception:
        return None


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(AppSetting, key)
    enc = encrypt(value)
    if row:
        row.value_encrypted = enc
    else:
        db.add(AppSetting(key=key, value_encrypted=enc))
    await db.commit()


async def delete_setting(db: AsyncSession, key: str) -> None:
    row = await db.get(AppSetting, key)
    if row:
        await db.delete(row)
        await db.commit()
